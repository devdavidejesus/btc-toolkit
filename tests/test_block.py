"""Tests for the block info explorer."""

import unittest
from unittest.mock import patch

from btc_toolkit.block import (
    get_block,
    get_tip_height,
    BlockInfo,
    _is_block_hash,
    _is_height,
)

# Real genesis block data (block 0) — verifiable at
# https://mempool.space/api/block/000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f
GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
GENESIS_RESPONSE = {
    "id": GENESIS_HASH,
    "height": 0,
    "version": 1,
    "timestamp": 1231006505,
    "tx_count": 1,
    "size": 285,
    "weight": 1140,
    "merkle_root": "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b",
    "previousblockhash": None,
    "mediantime": 1231006505,
    "nonce": 2083236893,
    "bits": 486604799,
    "difficulty": 1,
}


class TestRefDetection(unittest.TestCase):
    def test_valid_hash(self):
        self.assertTrue(_is_block_hash(GENESIS_HASH))

    def test_height_is_not_hash(self):
        self.assertFalse(_is_block_hash("840000"))

    def test_valid_height(self):
        self.assertTrue(_is_height("0"))
        self.assertTrue(_is_height("840000"))

    def test_hash_is_not_height(self):
        self.assertFalse(_is_height(GENESIS_HASH))

    def test_garbage_is_neither(self):
        self.assertFalse(_is_block_hash("not-a-block"))
        self.assertFalse(_is_height("not-a-block"))


class TestGetBlock(unittest.TestCase):
    @patch("btc_toolkit.block.get_json")
    def test_by_hash(self, mock_json):
        mock_json.return_value = GENESIS_RESPONSE
        block = get_block(GENESIS_HASH)
        self.assertEqual(block.height, 0)
        self.assertEqual(block.tx_count, 1)
        self.assertEqual(block.nonce, 2083236893)
        self.assertEqual(block.difficulty, 1)
        mock_json.assert_called_once_with(f"/block/{GENESIS_HASH}", "mainnet")

    @patch("btc_toolkit.block.get_json")
    @patch("btc_toolkit.block.get_text")
    def test_by_height(self, mock_text, mock_json):
        mock_text.return_value = GENESIS_HASH
        mock_json.return_value = GENESIS_RESPONSE
        block = get_block("0")
        self.assertEqual(block.hash, GENESIS_HASH)
        mock_text.assert_called_once_with("/block-height/0", "mainnet")

    @patch("btc_toolkit.block.get_json")
    @patch("btc_toolkit.block.get_text")
    def test_latest(self, mock_text, mock_json):
        # 'latest' resolves tip height, then that height's hash
        mock_text.side_effect = ["840000", GENESIS_HASH]
        mock_json.return_value = {**GENESIS_RESPONSE, "height": 840000}
        block = get_block("latest")
        self.assertEqual(block.height, 840000)
        self.assertEqual(mock_text.call_count, 2)

    def test_invalid_ref_raises(self):
        with self.assertRaises(ValueError):
            get_block("not-a-block")

    @patch("btc_toolkit.block.get_json")
    def test_genesis_timestamp_utc(self, mock_json):
        mock_json.return_value = GENESIS_RESPONSE
        block = get_block(GENESIS_HASH)
        # 1231006505 = 2009-01-03 18:15:05 UTC (genesis block, verifiable)
        self.assertEqual(block.timestamp_utc, "2009-01-03 18:15:05 UTC")

    @patch("btc_toolkit.block.get_json")
    def test_to_dict_structure(self, mock_json):
        mock_json.return_value = GENESIS_RESPONSE
        d = get_block(GENESIS_HASH).to_dict()
        self.assertEqual(d["height"], 0)
        self.assertEqual(d["size_bytes"], 285)
        self.assertEqual(d["timestamp_utc"], "2009-01-03 18:15:05 UTC")
        self.assertIn("merkle_root", d)


class TestGetTipHeight(unittest.TestCase):
    @patch("btc_toolkit.block.get_text")
    def test_tip_height(self, mock_text):
        mock_text.return_value = "905432"
        self.assertEqual(get_tip_height(), 905432)
        mock_text.assert_called_once_with("/blocks/tip/height", "mainnet")


if __name__ == "__main__":
    unittest.main()
