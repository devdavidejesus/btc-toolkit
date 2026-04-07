"""Tests for OP_RETURN decoder."""

import json
import unittest
from unittest.mock import patch, MagicMock

from op_return_reader.decoder import (
    decode_op_return,
    _decode_hex_to_text,
    _parse_scriptpubkey_asm,
    _extract_pushdata,
    TransactionNotFoundError,
    OPReturnData,
)


class TestHexDecode(unittest.TestCase):
    """Test hex-to-text decoding."""

    def test_valid_ascii(self):
        # "hello" in hex
        self.assertEqual(_decode_hex_to_text("68656c6c6f"), "hello")

    def test_valid_utf8(self):
        # "café" in hex
        text = "caf\u00e9"
        hex_data = text.encode("utf-8").hex()
        self.assertEqual(_decode_hex_to_text(hex_data), text)

    def test_binary_data_returns_none(self):
        # Random bytes unlikely to be valid UTF-8 printable text
        self.assertIsNone(_decode_hex_to_text("ff00fe01"))

    def test_empty_returns_none(self):
        self.assertIsNone(_decode_hex_to_text(""))


class TestParseASM(unittest.TestCase):
    """Test scriptPubKey ASM parsing."""

    def test_simple_opreturn(self):
        asm = "OP_RETURN OP_PUSHBYTES_5 68656c6c6f"
        self.assertEqual(_parse_scriptpubkey_asm(asm), "68656c6c6f")

    def test_opreturn_without_pushbytes(self):
        asm = "OP_RETURN 68656c6c6f"
        self.assertEqual(_parse_scriptpubkey_asm(asm), "68656c6c6f")

    def test_not_opreturn(self):
        asm = "OP_DUP OP_HASH160 abcdef"
        self.assertIsNone(_parse_scriptpubkey_asm(asm))

    def test_multiple_pushes(self):
        asm = "OP_RETURN OP_PUSHBYTES_3 aabbcc OP_PUSHBYTES_2 ddee"
        self.assertEqual(_parse_scriptpubkey_asm(asm), "aabbccddee")


class TestExtractPushdata(unittest.TestCase):
    """Test raw scriptpubkey pushdata extraction."""

    def test_simple_push(self):
        # 05 = push 5 bytes, followed by "hello"
        script = "05" + "68656c6c6f"
        self.assertEqual(_extract_pushdata(script), "68656c6c6f")

    def test_pushdata1(self):
        # 4c = OP_PUSHDATA1, 03 = 3 bytes, aabbcc
        script = "4c" + "03" + "aabbcc"
        self.assertEqual(_extract_pushdata(script), "aabbcc")

    def test_empty(self):
        self.assertIsNone(_extract_pushdata(""))


class TestDecodeOPReturn(unittest.TestCase):
    """Test full decode pipeline with mocked API."""

    @patch("op_return_reader.decoder.fetch_transaction")
    def test_decode_text_message(self, mock_fetch):
        """Test decoding a transaction with a text OP_RETURN."""
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

        txid = "a" * 64
        results = decode_op_return(txid)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].decoded_text, "hello")
        self.assertEqual(results[0].vout_index, 1)
        self.assertEqual(results[0].size, 5)

    @patch("op_return_reader.decoder.fetch_transaction")
    def test_no_opreturn(self, mock_fetch):
        """Test transaction with no OP_RETURN outputs."""
        mock_fetch.return_value = {
            "vout": [
                {
                    "scriptpubkey_type": "v0_p2wpkh",
                    "scriptpubkey": "0014abcdef",
                    "scriptpubkey_asm": "OP_0 OP_PUSHBYTES_20 abcdef",
                },
            ]
        }

        txid = "b" * 64
        results = decode_op_return(txid)
        self.assertEqual(len(results), 0)

    def test_invalid_txid(self):
        with self.assertRaises(ValueError):
            decode_op_return("not-a-valid-txid")

    def test_short_txid(self):
        with self.assertRaises(ValueError):
            decode_op_return("abcdef")


class TestOPReturnData(unittest.TestCase):
    """Test data class serialization."""

    def test_to_dict(self):
        data = OPReturnData(
            txid="a" * 64,
            vout_index=0,
            raw_hex="68656c6c6f",
            decoded_text="hello",
            raw_bytes=b"hello",
            size=5,
        )
        d = data.to_dict()
        self.assertEqual(d["decoded_text"], "hello")
        self.assertEqual(d["size_bytes"], 5)
        # Ensure raw_bytes is not in JSON output
        self.assertNotIn("raw_bytes", d)


if __name__ == "__main__":
    unittest.main()
