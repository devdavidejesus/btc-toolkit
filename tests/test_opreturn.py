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
