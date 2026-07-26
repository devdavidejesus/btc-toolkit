"""Tests for the UTXO set inspector."""

import unittest
from unittest.mock import patch

from btc_toolkit.utxo import get_utxos, Utxo, UtxoSet

ADDR = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"

SAMPLE_UTXOS = [
    {
        "txid": "a" * 64,
        "vout": 0,
        "value": 50_000,
        "status": {"confirmed": True, "block_height": 900000,
                   "block_hash": "b" * 64, "block_time": 1700000000},
    },
    {
        "txid": "c" * 64,
        "vout": 1,
        "value": 150_000_000,
        "status": {"confirmed": True, "block_height": 899999,
                   "block_hash": "d" * 64, "block_time": 1699999000},
    },
    {
        "txid": "e" * 64,
        "vout": 0,
        "value": 25_000,
        "status": {"confirmed": False},
    },
]


class TestGetUtxos(unittest.TestCase):
    @patch("btc_toolkit.utxo.get_json")
    def test_full_set(self, mock_get):
        mock_get.return_value = SAMPLE_UTXOS
        us = get_utxos(ADDR)
        self.assertEqual(len(us.utxos), 3)
        self.assertEqual(us.confirmed_count, 2)
        self.assertEqual(us.unconfirmed_count, 1)
        self.assertEqual(us.total_sats, 150_075_000)

    @patch("btc_toolkit.utxo.get_json")
    def test_sorted_largest_first(self, mock_get):
        mock_get.return_value = SAMPLE_UTXOS
        us = get_utxos(ADDR)
        values = [u.value for u in us.utxos]
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertEqual(us.utxos[0].value, 150_000_000)

    @patch("btc_toolkit.utxo.get_json")
    def test_confirmed_only_filter(self, mock_get):
        mock_get.return_value = SAMPLE_UTXOS
        us = get_utxos(ADDR, confirmed_only=True)
        self.assertEqual(len(us.utxos), 2)
        self.assertEqual(us.unconfirmed_count, 0)
        self.assertEqual(us.total_sats, 150_050_000)

    @patch("btc_toolkit.utxo.get_json")
    def test_empty_set(self, mock_get):
        mock_get.return_value = []
        us = get_utxos(ADDR)
        self.assertEqual(len(us.utxos), 0)
        self.assertEqual(us.total_sats, 0)

    @patch("btc_toolkit.utxo.get_json")
    def test_unconfirmed_has_no_height(self, mock_get):
        mock_get.return_value = SAMPLE_UTXOS
        us = get_utxos(ADDR)
        unconfirmed = [u for u in us.utxos if not u.confirmed][0]
        self.assertIsNone(unconfirmed.block_height)

    @patch("btc_toolkit.utxo.get_json")
    def test_to_dict_structure(self, mock_get):
        mock_get.return_value = SAMPLE_UTXOS
        d = get_utxos(ADDR).to_dict()
        self.assertEqual(d["utxo_count"], 3)
        self.assertEqual(d["total"]["sats"], 150_075_000)
        self.assertEqual(d["total"]["btc"], "1.50075000")
        self.assertEqual(len(d["utxos"]), 3)
        self.assertNotIn("block_hash", d["utxos"][0])

    def test_invalid_address_raises(self):
        with self.assertRaises(ValueError):
            get_utxos("")

    def test_sats_to_btc(self):
        self.assertEqual(UtxoSet.sats_to_btc(150_075_000), "1.50075000")
        self.assertEqual(UtxoSet.sats_to_btc(0), "0.00000000")


if __name__ == "__main__":
    unittest.main()
