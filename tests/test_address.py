"""Tests for the address overview and type detection."""

import unittest
from unittest.mock import patch

from btc_toolkit.address import (
    detect_address_type,
    get_address_overview,
)


class TestDetectAddressType(unittest.TestCase):
    """Type detection against real, well-known addresses (verifiable on-chain)."""

    def test_p2pkh_genesis(self):
        # Satoshi's genesis reward address
        self.assertEqual(
            detect_address_type("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"), "P2PKH"
        )

    def test_p2sh(self):
        # learnmeabitcoin donation address (used in our Phase 5 verification)
        self.assertEqual(
            detect_address_type("3Beer3irc1vgs76ENA4coqsEQpGZeM5CTd"), "P2SH"
        )

    def test_p2wpkh(self):
        # BIP 173 test vector length: bc1 + 39 = 42 chars
        addr = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"
        self.assertEqual(len(addr), 42)
        self.assertEqual(detect_address_type(addr), "P2WPKH")

    def test_p2wsh(self):
        # 62-char bech32 (script hash)
        addr = "bc1q" + "a" * 58
        self.assertEqual(len(addr), 62)
        self.assertEqual(detect_address_type(addr), "P2WSH")

    def test_p2tr(self):
        addr = "bc1p" + "a" * 58
        self.assertEqual(detect_address_type(addr), "P2TR")

    def test_testnet_prefixes(self):
        self.assertEqual(detect_address_type("mzBc4XEFSdzCDcTxAgf6EZXgsZWpztRhef", "testnet"), "P2PKH")
        self.assertEqual(detect_address_type("2N3oefVeg6stiTb5Kh3ozCSkaqmx91FDbsm", "testnet"), "P2SH")
        self.assertEqual(detect_address_type("tb1q" + "a" * 38, "testnet"), "P2WPKH")
        self.assertEqual(detect_address_type("tb1p" + "a" * 58, "testnet"), "P2TR")

    def test_unknown(self):
        self.assertEqual(detect_address_type("xyznotanaddress123456"), "unknown")


class TestGetAddressOverview(unittest.TestCase):
    @patch("btc_toolkit.balance.get_json")
    def test_overview_aggregates(self, mock_get):
        mock_get.return_value = {
            "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "chain_stats": {
                "funded_txo_sum": 5_732_133_862,
                "spent_txo_sum": 0,
                "tx_count": 64099,
            },
            "mempool_stats": {
                "funded_txo_sum": 0,
                "spent_txo_sum": 0,
                "tx_count": 0,
            },
        }
        ov = get_address_overview("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        self.assertEqual(ov.address_type, "P2PKH")
        self.assertEqual(ov.balance.confirmed_sats, 5_732_133_862)
        self.assertEqual(ov.balance.confirmed_tx_count, 64099)

    @patch("btc_toolkit.balance.get_json")
    def test_to_dict_includes_type(self, mock_get):
        mock_get.return_value = {
            "address": "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
            "chain_stats": {"funded_txo_sum": 100, "spent_txo_sum": 0, "tx_count": 1},
            "mempool_stats": {"funded_txo_sum": 0, "spent_txo_sum": 0, "tx_count": 0},
        }
        d = get_address_overview("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq").to_dict()
        self.assertEqual(d["address_type"], "P2WPKH")
        self.assertIn("confirmed", d)

    def test_invalid_address_raises(self):
        with self.assertRaises(ValueError):
            get_address_overview("")


if __name__ == "__main__":
    unittest.main()
