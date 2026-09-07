"""Tests for the CLI layer: dispatch, JSON output, exit codes, flags."""

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from btc_toolkit import cli
from btc_toolkit.api import set_api_base

TXID = "f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab"
ADDR = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

TX_DATA = {
    "txid": TXID, "version": 2, "locktime": 0, "size": 236, "weight": 617,
    "fee": 500,
    "vin": [{"is_coinbase": False, "sequence": 0xFFFFFFFD,
             "prevout": {"value": 2500},
             "scriptsig": "", "witness": []}],
    "vout": [{"value": 1000, "scriptpubkey": "6a22" + "00" * 34,
              "scriptpubkey_type": "op_return",
              "scriptpubkey_asm": "OP_RETURN OP_PUSHBYTES_34 " + "00" * 34},
             {"value": 1000, "scriptpubkey_type": "p2pkh"}],
    "status": {"confirmed": True, "block_height": 777954,
               "block_hash": "b" * 64, "block_time": 1677156410},
}
ADDR_DATA = {
    "address": ADDR,
    "chain_stats": {"funded_txo_sum": 100, "spent_txo_sum": 0, "tx_count": 1},
    "mempool_stats": {"funded_txo_sum": 0, "spent_txo_sum": 0, "tx_count": 0},
}
FEES_DATA = {"fastestFee": 2, "halfHourFee": 2, "hourFee": 1,
             "economyFee": 1, "minimumFee": 1}
MEMPOOL_DATA = {"count": 10, "vsize": 4000, "total_fee": 5000}
BLOCK_DATA = {
    "id": "0" * 64, "height": 0, "timestamp": 1231006505, "tx_count": 1,
    "size": 285, "weight": 1140, "difficulty": 1, "nonce": 2083236893,
    "previousblockhash": None,
}
UTXO_DATA = [{"txid": "a" * 64, "vout": 0, "value": 5000,
              "status": {"confirmed": True, "block_height": 1}}]


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.run(argv)
    return code, buf.getvalue()


class TestCliJsonPaths(unittest.TestCase):
    """Every command's --json path returns exit 0 and valid JSON."""

    def tearDown(self):
        set_api_base(None)

    @patch("btc_toolkit.fees.get_json")
    def test_fees_json(self, m):
        m.side_effect = [FEES_DATA, MEMPOOL_DATA]
        code, out = _run(["fees", "--json"])
        self.assertEqual(code, 0)
        self.assertIn("fees_sat_vb", json.loads(out))

    @patch("btc_toolkit.balance.get_json")
    def test_balance_json(self, m):
        m.return_value = ADDR_DATA
        code, out = _run(["balance", ADDR, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["address"], ADDR)

    @patch("btc_toolkit.balance.get_json")
    def test_address_json(self, m):
        m.return_value = ADDR_DATA
        code, out = _run(["address", ADDR, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["address_type"], "P2PKH")

    @patch("btc_toolkit.tx.fetch_transaction")
    def test_tx_json(self, m):
        m.return_value = TX_DATA
        code, out = _run(["tx", TXID, "--json"])
        self.assertEqual(code, 0)
        d = json.loads(out)
        self.assertTrue(d["is_rbf"])
        self.assertEqual(d["fee_sats"], 500)

    @patch("btc_toolkit.block.get_json")
    @patch("btc_toolkit.block.get_text")
    def test_block_json(self, mtext, mjson):
        mtext.return_value = "0" * 64
        mjson.return_value = BLOCK_DATA
        code, out = _run(["block", "0", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["height"], 0)

    @patch("btc_toolkit.utxo.get_json")
    def test_utxo_json(self, m):
        m.return_value = UTXO_DATA
        code, out = _run(["utxo", ADDR, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["utxo_count"], 1)

    @patch("btc_toolkit.opreturn.fetch_transaction")
    def test_opreturn_json(self, m):
        m.return_value = TX_DATA
        code, out = _run(["opreturn", TXID, "--json"])
        self.assertEqual(code, 0)
        json.loads(out)


class TestCliVisualPaths(unittest.TestCase):
    """Human output renders and exits 0 (no crash in formatting)."""

    @patch("btc_toolkit.balance.get_json")
    def test_balance_visual(self, m):
        m.return_value = ADDR_DATA
        code, out = _run(["balance", ADDR])
        self.assertEqual(code, 0)
        self.assertIn("BTC", out)

    @patch("btc_toolkit.tx.fetch_transaction")
    def test_tx_visual_shows_rbf_flag(self, m):
        m.return_value = TX_DATA
        code, out = _run(["tx", TXID])
        self.assertEqual(code, 0)
        self.assertIn("RBF", out)

    @patch("btc_toolkit.balance.get_json")
    def test_address_visual_shows_type(self, m):
        m.return_value = ADDR_DATA
        code, out = _run(["address", ADDR])
        self.assertEqual(code, 0)
        self.assertIn("P2PKH", out)


class TestCliExitCodes(unittest.TestCase):
    def test_invalid_address_exits_2(self):
        code, _ = _run(["balance", "!!!"])
        self.assertEqual(code, 2)

    def test_invalid_txid_exits_2(self):
        code, _ = _run(["tx", "nope"])
        self.assertEqual(code, 2)

    @patch("btc_toolkit.tx.fetch_transaction")
    def test_not_found_exits_1(self, m):
        from btc_toolkit.opreturn import TransactionNotFoundError
        m.side_effect = TransactionNotFoundError("gone")
        code, _ = _run(["tx", "0" * 64])
        self.assertEqual(code, 1)

    @patch("btc_toolkit.balance.get_json")
    def test_api_error_exits_1(self, m):
        from btc_toolkit.api import MempoolAPIError
        m.side_effect = MempoolAPIError("boom")
        code, _ = _run(["balance", ADDR, "--json"])
        self.assertEqual(code, 1)


class TestCliFlags(unittest.TestCase):
    def tearDown(self):
        set_api_base(None)

    @patch("btc_toolkit.balance.get_json")
    def test_api_url_sets_custom_network(self, m):
        m.return_value = ADDR_DATA
        code, out = _run(["balance", ADDR, "--json",
                          "--api-url", "http://node.local:3006/api"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["network"], "custom")

    def test_version_flag(self):
        with self.assertRaises(SystemExit) as ctx:
            _run(["--version"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
