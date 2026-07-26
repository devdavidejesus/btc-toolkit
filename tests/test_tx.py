"""Tests for the transaction inspector."""

import unittest
from unittest.mock import patch

from btc_toolkit.tx import get_tx, TxInfo

TXID = "f" * 64

CONFIRMED_TX = {
    "txid": TXID,
    "version": 2,
    "locktime": 0,
    "size": 222,
    "weight": 561,
    "fee": 1500,
    "vin": [
        {
            "is_coinbase": False,
            "sequence": 0xFFFFFFFF,
            "prevout": {"value": 100_000},
        },
    ],
    "vout": [
        {"value": 60_000},
        {"value": 38_500},
    ],
    "status": {
        "confirmed": True,
        "block_height": 900_000,
        "block_hash": "b" * 64,
        "block_time": 1231006505,
    },
}


class TestGetTx(unittest.TestCase):
    @patch("btc_toolkit.tx.fetch_transaction")
    def test_confirmed_tx(self, mock_fetch):
        mock_fetch.return_value = CONFIRMED_TX
        tx = get_tx(TXID)
        self.assertTrue(tx.confirmed)
        self.assertEqual(tx.block_height, 900_000)
        self.assertEqual(tx.fee, 1500)
        self.assertEqual(tx.total_input, 100_000)
        self.assertEqual(tx.total_output, 98_500)
        # fee must equal input - output (consistency)
        self.assertEqual(tx.total_input - tx.total_output, tx.fee)

    @patch("btc_toolkit.tx.fetch_transaction")
    def test_vsize_and_fee_rate(self, mock_fetch):
        mock_fetch.return_value = CONFIRMED_TX
        tx = get_tx(TXID)
        # vsize = ceil(561 / 4) = 141
        self.assertEqual(tx.vsize, 141)
        self.assertAlmostEqual(tx.fee_rate, 1500 / 141, places=4)

    @patch("btc_toolkit.tx.fetch_transaction")
    def test_rbf_detection(self, mock_fetch):
        rbf_tx = dict(CONFIRMED_TX)
        rbf_tx["vin"] = [
            {"is_coinbase": False, "sequence": 0xFFFFFFFD,
             "prevout": {"value": 100_000}},
        ]
        mock_fetch.return_value = rbf_tx
        self.assertTrue(get_tx(TXID).is_rbf)

    @patch("btc_toolkit.tx.fetch_transaction")
    def test_non_rbf_max_sequence(self, mock_fetch):
        mock_fetch.return_value = CONFIRMED_TX
        self.assertFalse(get_tx(TXID).is_rbf)

    @patch("btc_toolkit.tx.fetch_transaction")
    def test_coinbase_tx(self, mock_fetch):
        coinbase = {
            "txid": TXID,
            "version": 1,
            "locktime": 0,
            "size": 285,
            "weight": 1140,
            "fee": 0,
            "vin": [{"is_coinbase": True, "sequence": 0xFFFFFFFF}],
            "vout": [{"value": 5_000_000_000}],
            "status": {"confirmed": True, "block_height": 0,
                       "block_time": 1231006505},
        }
        mock_fetch.return_value = coinbase
        tx = get_tx(TXID)
        self.assertTrue(tx.is_coinbase)
        self.assertEqual(tx.fee, 0)
        self.assertEqual(tx.total_input, 0)
        self.assertEqual(tx.total_output, 5_000_000_000)

    @patch("btc_toolkit.tx.fetch_transaction")
    def test_unconfirmed_tx(self, mock_fetch):
        mempool_tx = dict(CONFIRMED_TX)
        mempool_tx["status"] = {"confirmed": False}
        mock_fetch.return_value = mempool_tx
        tx = get_tx(TXID)
        self.assertFalse(tx.confirmed)
        self.assertIsNone(tx.block_height)
        self.assertIsNone(tx.block_time_utc)

    @patch("btc_toolkit.tx.fetch_transaction")
    def test_block_time_utc(self, mock_fetch):
        mock_fetch.return_value = CONFIRMED_TX
        # 1231006505 = genesis timestamp, verifiable
        self.assertEqual(get_tx(TXID).block_time_utc, "2009-01-03 18:15:05 UTC")

    @patch("btc_toolkit.tx.fetch_transaction")
    def test_to_dict_structure(self, mock_fetch):
        mock_fetch.return_value = CONFIRMED_TX
        d = get_tx(TXID).to_dict()
        self.assertEqual(d["status"], "confirmed")
        self.assertEqual(d["vsize"], 141)
        self.assertEqual(d["fee_rate_sat_vb"], round(1500 / 141, 2))
        self.assertFalse(d["is_coinbase"])
        self.assertFalse(d["is_rbf"])

    def test_invalid_txid_raises(self):
        with self.assertRaises(ValueError):
            get_tx("nope")


if __name__ == "__main__":
    unittest.main()
