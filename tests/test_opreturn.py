"""Tests for the OP_RETURN decoder."""

import unittest
from unittest.mock import patch

from btc_toolkit.opreturn import (
    decode_op_return,
    _decode_hex_to_text,
    _parse_scriptpubkey_asm,
    _extract_pushdata,
    OPReturnData,
)


class TestHexDecode(unittest.TestCase):
    def test_valid_ascii(self):
        self.assertEqual(_decode_hex_to_text("68656c6c6f"), "hello")

    def test_valid_utf8(self):
        text = "caf\u00e9"
        self.assertEqual(_decode_hex_to_text(text.encode("utf-8").hex()), text)

    def test_binary_data_returns_none(self):
        self.assertIsNone(_decode_hex_to_text("ff00fe01"))

    def test_empty_returns_none(self):
        self.assertIsNone(_decode_hex_to_text(""))

    def test_null_bytes_stripped(self):
        hex_data = "00" * 60 + "6c6561726e6d6561626974636f696e"
        self.assertEqual(_decode_hex_to_text(hex_data), "learnmeabitcoin")

    def test_only_null_bytes_returns_none(self):
        self.assertIsNone(_decode_hex_to_text("0000000000"))


class TestParseASM(unittest.TestCase):
    def test_simple_opreturn(self):
        asm = "OP_RETURN OP_PUSHBYTES_5 68656c6c6f"
        self.assertEqual(_parse_scriptpubkey_asm(asm), "68656c6c6f")

    def test_opreturn_without_pushbytes(self):
        self.assertEqual(_parse_scriptpubkey_asm("OP_RETURN 68656c6c6f"), "68656c6c6f")

    def test_not_opreturn(self):
        self.assertIsNone(_parse_scriptpubkey_asm("OP_DUP OP_HASH160 abcdef"))

    def test_multiple_pushes(self):
        asm = "OP_RETURN OP_PUSHBYTES_3 aabbcc OP_PUSHBYTES_2 ddee"
        self.assertEqual(_parse_scriptpubkey_asm(asm), "aabbccddee")


class TestExtractPushdata(unittest.TestCase):
    def test_simple_push(self):
        self.assertEqual(_extract_pushdata("05" + "68656c6c6f"), "68656c6c6f")

    def test_pushdata1(self):
        self.assertEqual(_extract_pushdata("4c" + "03" + "aabbcc"), "aabbcc")

    def test_empty(self):
        self.assertIsNone(_extract_pushdata(""))


class TestDecodeOPReturn(unittest.TestCase):
    @patch("btc_toolkit.opreturn.fetch_transaction")
    def test_decode_text_message(self, mock_fetch):
        mock_fetch.return_value = {
            "vout": [
                {
                    "scriptpubkey_type": "v0_p2wpkh",
                    "scriptpubkey": "0014abcdef",
                    "scriptpubkey_asm": "OP_0 OP_PUSHBYTES_20 abcdef",
                },
                {
                    "scriptpubkey_type": "op_return",
                    "scriptpubkey": "6a0568656c6c6f",
                    "scriptpubkey_asm": "OP_RETURN OP_PUSHBYTES_5 68656c6c6f",
                },
            ]
        }
        results = decode_op_return("a" * 64)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].decoded_text, "hello")
        self.assertEqual(results[0].vout_index, 1)
        self.assertEqual(results[0].size, 5)

    @patch("btc_toolkit.opreturn.fetch_transaction")
    def test_no_opreturn(self, mock_fetch):
        mock_fetch.return_value = {
            "vout": [
                {
                    "scriptpubkey_type": "v0_p2wpkh",
                    "scriptpubkey": "0014abcdef",
                    "scriptpubkey_asm": "OP_0 OP_PUSHBYTES_20 abcdef",
                },
            ]
        }
        self.assertEqual(len(decode_op_return("b" * 64)), 0)

    def test_invalid_txid(self):
        with self.assertRaises(ValueError):
            decode_op_return("not-a-valid-txid")

    def test_short_txid(self):
        with self.assertRaises(ValueError):
            decode_op_return("abcdef")


class TestOPReturnData(unittest.TestCase):
    def test_to_dict(self):
        data = OPReturnData(
            txid="a" * 64, vout_index=0, raw_hex="68656c6c6f",
            decoded_text="hello", raw_bytes=b"hello", size=5,
        )
        d = data.to_dict()
        self.assertEqual(d["decoded_text"], "hello")
        self.assertEqual(d["size_bytes"], 5)
        self.assertNotIn("raw_bytes", d)


if __name__ == "__main__":
    unittest.main()


class TestMalformedApiScripts(unittest.TestCase):
    """Regression tests for an issue found by fuzzing (fuzz/fuzz_parsers.py):
    a non-hex scriptpubkey from the API used to surface as ValueError, which the
    CLI reports as *invalid user input* (exit 2)."""

    def test_extract_pushdata_never_raises_on_non_hex(self):
        from btc_toolkit.opreturn import _extract_pushdata
        for bad in ("\x7f5", "+f04abcd", "zz", "6a 04", "٠١"):
            with self.subTest(bad=bad):
                self.assertIsNone(_extract_pushdata(bad))

    def test_malformed_scriptpubkey_is_an_api_error(self):
        from btc_toolkit.api import MempoolAPIError
        from btc_toolkit.opreturn import decode_op_return
        vout = {"scriptpubkey_type": "op_return", "scriptpubkey_asm": "", "scriptpubkey": "6a\x7f5"}
        with patch("btc_toolkit.opreturn.fetch_transaction", return_value={"vout": [vout]}), \
                self.assertRaises(MempoolAPIError) as ctx:
            decode_op_return("0" * 64)
        self.assertIn("malformed scriptpubkey", str(ctx.exception))

    def test_cli_reports_it_as_api_error_exit_1(self):
        import io
        from contextlib import redirect_stdout
        from btc_toolkit import cli
        vout = {"scriptpubkey_type": "op_return", "scriptpubkey_asm": "", "scriptpubkey": "6azz"}
        with patch("btc_toolkit.opreturn.fetch_transaction", return_value={"vout": [vout]}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.run(["opreturn", "0" * 64])
        self.assertEqual(code, 1)
        self.assertIn("malformed scriptpubkey", buf.getvalue())


class TestScriptParsingEdges(unittest.TestCase):
    """Edge cases of the script parsers, found uncovered by branch coverage."""

    def test_pushdata2_large_message(self):
        # OP_PUSHDATA2 (0x4d) + little-endian length: the path that decoded the
        # 6,458-byte message on mainnet, previously without a test.
        from btc_toolkit.opreturn import _extract_pushdata
        msg = b"x" * 600
        script = "4d" + (600).to_bytes(2, "little").hex() + msg.hex()
        self.assertEqual(_extract_pushdata(script), msg.hex())

    # A non-standard script must never be reported as an empty OP_RETURN:
    # whatever bytes it carries are returned.
    def test_pushdata2_truncated_length(self):
        from btc_toolkit.opreturn import _extract_pushdata
        self.assertEqual(_extract_pushdata("4d58"), "4d58")      # unreadable: the raw bytes

    def test_pushdata1_truncated_length(self):
        from btc_toolkit.opreturn import _extract_pushdata
        self.assertEqual(_extract_pushdata("4c"), "4c")

    def test_unknown_opcode_stops_parsing(self):
        from btc_toolkit.opreturn import _extract_pushdata
        self.assertEqual(_extract_pushdata("50"), "50")                 # OP_RESERVED: raw bytes
        self.assertEqual(_extract_pushdata("02aabb00cc"), "aabb")       # parsed data is kept

    def test_declared_length_longer_than_data(self):
        from btc_toolkit.opreturn import _extract_pushdata
        self.assertEqual(_extract_pushdata("05aabb"), "aabb")           # the bytes that are there

    def test_odd_trailing_nibble_is_ignored(self):
        from btc_toolkit.opreturn import _extract_pushdata
        self.assertIsNone(_extract_pushdata("02aab"))  # odd length: not strict hex

    def test_asm_skips_non_hex_tokens(self):
        from btc_toolkit.opreturn import _parse_scriptpubkey_asm
        self.assertEqual(_parse_scriptpubkey_asm("OP_RETURN zz 6869"), "6869")
        self.assertIsNone(_parse_scriptpubkey_asm("OP_RETURN zz"))

    def test_mostly_binary_payload_is_not_text(self):
        from btc_toolkit.opreturn import _decode_hex_to_text
        self.assertIsNone(_decode_hex_to_text("01" * 9 + "41"))  # 9 control chars, 1 "A"


class TestDecodeEdges(unittest.TestCase):
    def test_not_found_maps_to_transaction_not_found(self):
        from btc_toolkit.api import NotFoundError
        from btc_toolkit.opreturn import TransactionNotFoundError, fetch_transaction
        with patch("btc_toolkit.opreturn.get_json", side_effect=NotFoundError("404")), \
                self.assertRaises(TransactionNotFoundError):
            fetch_transaction("0" * 64)

    def test_op_return_without_payload_is_reported(self):
        # A bare OP_RETURN, OP_RETURN OP_0 and a Runestone marker with no data are
        # still OP_RETURN outputs: reported with an empty payload, not skipped.
        from btc_toolkit.opreturn import decode_op_return
        tx = {"vout": [
            {"scriptpubkey_type": "op_return", "scriptpubkey_asm": "OP_RETURN", "scriptpubkey": "6a"},
            {"scriptpubkey_type": "op_return", "scriptpubkey_asm": "OP_RETURN OP_0", "scriptpubkey": "6a00"},
            {"scriptpubkey_type": "op_return", "scriptpubkey_asm": "OP_RETURN OP_PUSHNUM_13", "scriptpubkey": "6a5d"},
            {"scriptpubkey_type": "op_return", "scriptpubkey_asm": "OP_RETURN OP_PUSHBYTES_2 6869",
             "scriptpubkey": "6a026869"},
        ]}
        with patch("btc_toolkit.opreturn.fetch_transaction", return_value=tx):
            out = decode_op_return("0" * 64)
        self.assertEqual([(o.vout_index, o.raw_hex, o.size, o.decoded_text) for o in out],
                         [(0, "", 0, None), (1, "", 0, None), (2, "", 0, None), (3, "6869", 2, "hi")])

    def test_op_return_type_without_op_return_script_is_an_api_error(self):
        from btc_toolkit.api import MempoolAPIError
        from btc_toolkit.opreturn import decode_op_return
        tx = {"vout": [{"scriptpubkey_type": "op_return", "scriptpubkey_asm": "", "scriptpubkey": "51"}]}
        with patch("btc_toolkit.opreturn.fetch_transaction", return_value=tx), self.assertRaises(MempoolAPIError):
            decode_op_return("0" * 64)

    def test_raw_script_pushdata4_and_small_number_opcodes(self):
        from btc_toolkit.opreturn import _extract_pushdata
        self.assertEqual(_extract_pushdata("4e05000000" + "68656c6c6f"), "68656c6c6f")      # OP_PUSHDATA4
        self.assertEqual(_extract_pushdata("00" + "0568656c6c6f"), "68656c6c6f")           # OP_0, then data
        self.assertEqual(_extract_pushdata("5d" + "0400c0a233"), "00c0a233")               # OP_13 (Runestone)
        self.assertEqual(_extract_pushdata("4e050000"), "4e050000")                        # truncated length: raw
        self.assertEqual(_extract_pushdata("51"), None)                                    # OP_1 only: no data
