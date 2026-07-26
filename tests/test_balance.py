"""Tests for the address balance checker."""

import unittest
from unittest.mock import patch

from btc_toolkit.balance import (
    get_balance,
    AddressBalance,
    _validate_address,
)


class TestSatsToBtc(unittest.TestCase):
    def test_whole_btc(self):
        self.assertEqual(AddressBalance.sats_to_btc(100_000_000), "1.00000000")

    def test_zero(self):
        self.assertEqual(AddressBalance.sats_to_btc(0), "0.00000000")

    def test_fractional(self):
        self.assertEqual(AddressBalance.sats_to_btc(150_000_000), "1.50000000")

    def test_single_sat(self):
        self.assertEqual(AddressBalance.sats_to_btc(1), "0.00000001")

    def test_large_amount(self):
        # 150.07599040 BTC (from the mempool.space docs example)
        self.assertEqual(AddressBalance.sats_to_btc(15007599040), "150.07599040")

    def test_negative(self):
        self.assertEqual(AddressBalance.sats_to_btc(-50_000_000), "-0.50000000")


class TestValidateAddress(unittest.TestCase):
    def test_valid_legacy(self):
        addr = "1wiz18xYmhRX6xStj2b9t1rwWX4GKUgpv"
        self.assertEqual(_validate_address(addr), addr)

    def test_valid_bech32(self):
        addr = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"
        self.assertEqual(_validate_address(addr), addr)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            _validate_address("")

    def test_whitespace_only_raises(self):
        with self.assertRaises(ValueError):
            _validate_address("   ")

    def test_too_short_raises(self):
        with self.assertRaises(ValueError):
            _validate_address("abc")

    def test_invalid_chars_raises(self):
        with self.assertRaises(ValueError):
            _validate_address("1wiz!@#$%^&*()xStj2b9t1rwWX4GK")

    def test_strips_whitespace(self):
        addr = "1wiz18xYmhRX6xStj2b9t1rwWX4GKUgpv"
        self.assertEqual(_validate_address(f"  {addr}  "), addr)


class TestGetBalance(unittest.TestCase):
    @patch("btc_toolkit.balance.get_json")
    def test_confirmed_balance(self, mock_get):
        # Address fully spent (net zero) — mempool.space docs example
        mock_get.return_value = {
            "address": "1wiz18xYmhRX6xStj2b9t1rwWX4GKUgpv",
            "chain_stats": {
                "funded_txo_count": 5,
                "funded_txo_sum": 15007599040,
                "spent_txo_count": 5,
                "spent_txo_sum": 15007599040,
                "tx_count": 7,
            },
            "mempool_stats": {
                "funded_txo_count": 0,
                "funded_txo_sum": 0,
                "spent_txo_count": 0,
                "spent_txo_sum": 0,
                "tx_count": 0,
            },
        }
        bal = get_balance("1wiz18xYmhRX6xStj2b9t1rwWX4GKUgpv")
        self.assertEqual(bal.confirmed_sats, 0)
        self.assertEqual(bal.unconfirmed_sats, 0)
        self.assertEqual(bal.confirmed_tx_count, 7)
        self.assertEqual(bal.funded_sats, 15007599040)
        self.assertEqual(bal.spent_sats, 15007599040)

    @patch("btc_toolkit.balance.get_json")
    def test_positive_balance(self, mock_get):
        # Funded 2 BTC, spent 0.5 BTC → 1.5 BTC confirmed
        mock_get.return_value = {
            "address": "bc1qexample",
            "chain_stats": {
                "funded_txo_sum": 200_000_000,
                "spent_txo_sum": 50_000_000,
                "tx_count": 3,
            },
            "mempool_stats": {
                "funded_txo_sum": 0,
                "spent_txo_sum": 0,
                "tx_count": 0,
            },
        }
        bal = get_balance("bc1qexample0000")
        self.assertEqual(bal.confirmed_sats, 150_000_000)
        self.assertEqual(bal.sats_to_btc(bal.confirmed_sats), "1.50000000")

    @patch("btc_toolkit.balance.get_json")
    def test_unconfirmed_incoming(self, mock_get):
        # 1 BTC confirmed, 0.25 BTC incoming in mempool
        mock_get.return_value = {
            "address": "bc1qexample",
            "chain_stats": {
                "funded_txo_sum": 100_000_000,
                "spent_txo_sum": 0,
                "tx_count": 1,
            },
            "mempool_stats": {
                "funded_txo_sum": 25_000_000,
                "spent_txo_sum": 0,
                "tx_count": 1,
            },
        }
        bal = get_balance("bc1qexample0000")
        self.assertEqual(bal.confirmed_sats, 100_000_000)
        self.assertEqual(bal.unconfirmed_sats, 25_000_000)
        self.assertEqual(bal.total_sats, 125_000_000)
        self.assertEqual(bal.mempool_tx_count, 1)

    @patch("btc_toolkit.balance.get_json")
    def test_to_dict_structure(self, mock_get):
        mock_get.return_value = {
            "address": "bc1qexample",
            "chain_stats": {
                "funded_txo_sum": 100_000_000,
                "spent_txo_sum": 0,
                "tx_count": 1,
            },
            "mempool_stats": {
                "funded_txo_sum": 0,
                "spent_txo_sum": 0,
                "tx_count": 0,
            },
        }
        d = get_balance("bc1qexample0000").to_dict()
        self.assertEqual(d["confirmed"]["sats"], 100_000_000)
        self.assertEqual(d["confirmed"]["btc"], "1.00000000")
        self.assertEqual(d["total"]["btc"], "1.00000000")
        self.assertIn("funded_sats", d)

    def test_invalid_address_raises(self):
        with self.assertRaises(ValueError):
            get_balance("")


if __name__ == "__main__":
    unittest.main()
