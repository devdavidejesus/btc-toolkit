"""Tests for the CLI layer: dispatch, JSON output, exit codes, flags."""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from btc_toolkit import cli
from btc_toolkit.api import set_api_base, set_timeout

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


class TestCliAutomation(unittest.TestCase):
    """v1.4: env vars, --timeout, stdin / --file batch, JSON Lines."""

    def setUp(self):
        self._stdin = sys.stdin
        for var in ("BTC_TOOLKIT_API_URL", "BTC_TOOLKIT_NETWORK", "BTC_TOOLKIT_TIMEOUT"):
            os.environ.pop(var, None)

    def tearDown(self):
        sys.stdin = self._stdin
        set_api_base(None)
        set_timeout(None)
        for var in ("BTC_TOOLKIT_API_URL", "BTC_TOOLKIT_NETWORK", "BTC_TOOLKIT_TIMEOUT"):
            os.environ.pop(var, None)

    # --- env vars ---
    def test_env_network_sets_default(self):
        os.environ["BTC_TOOLKIT_NETWORK"] = "signet"
        args = cli.build_parser().parse_args(["fees"])
        self.assertEqual(args.network, "signet")

    def test_env_network_invalid_falls_back_to_mainnet(self):
        os.environ["BTC_TOOLKIT_NETWORK"] = "regtest"
        args = cli.build_parser().parse_args(["fees"])
        self.assertEqual(args.network, "mainnet")

    @patch("btc_toolkit.balance.get_json")
    def test_env_api_url_applies(self, m):
        os.environ["BTC_TOOLKIT_API_URL"] = "http://node.local:3006/api"
        m.return_value = ADDR_DATA
        code, out = _run(["balance", ADDR, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["network"], "custom")

    @patch("btc_toolkit.balance.get_json")
    def test_flag_api_url_beats_env(self, m):
        os.environ["BTC_TOOLKIT_API_URL"] = "http://env.local/api"
        m.return_value = ADDR_DATA
        from btc_toolkit.api import get_api_base
        _run(["balance", ADDR, "--json", "--api-url", "http://flag.local/api"])
        self.assertEqual(get_api_base("mainnet"), "http://flag.local/api")

    # --- timeout ---
    def test_timeout_flag_applies(self):
        from btc_toolkit.api import get_timeout
        _run(["tx", "nope", "--timeout", "3"])
        self.assertEqual(get_timeout(), 3.0)

    def test_timeout_env_applies(self):
        from btc_toolkit.api import get_timeout
        os.environ["BTC_TOOLKIT_TIMEOUT"] = "7"
        _run(["tx", "nope"])
        self.assertEqual(get_timeout(), 7.0)

    def test_timeout_invalid_exits_2(self):
        code, _ = _run(["tx", "0" * 64, "--timeout", "0"])
        self.assertEqual(code, 2)
        os.environ["BTC_TOOLKIT_TIMEOUT"] = "abc"
        code, _ = _run(["tx", "0" * 64])
        self.assertEqual(code, 2)

    # --- batch ---
    @patch("btc_toolkit.balance.get_json")
    def test_stdin_batch_json_lines(self, m):
        m.side_effect = lambda path, net: dict(ADDR_DATA, address=path.split("/")[2])
        sys.stdin = io.StringIO(f"{ADDR}\n# comment\n\n{ADDR}\n")
        code, out = _run(["balance", "-", "--json"])
        self.assertEqual(code, 0)
        lines = [l for l in out.splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertEqual(json.loads(line)["address"], ADDR)

    @patch("btc_toolkit.balance.get_json")
    def test_file_batch(self, m):
        import tempfile
        m.return_value = ADDR_DATA
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write(f"{ADDR}\n{ADDR}\n{ADDR}\n")
            path = fh.name
        code, out = _run(["balance", "--json", "--file", path])
        os.unlink(path)
        self.assertEqual(code, 0)
        self.assertEqual(len([l for l in out.splitlines() if l.strip()]), 3)

    def test_batch_worst_exit_code_wins(self):
        sys.stdin = io.StringIO("!!!\n")
        code, _ = _run(["balance", "-", "--json"])
        self.assertEqual(code, 2)

    def test_tty_without_input_exits_2(self):
        class Tty:
            def isatty(self): return True
        sys.stdin = Tty()
        code, _ = _run(["tx"])
        self.assertEqual(code, 2)

    def test_empty_batch_exits_2(self):
        sys.stdin = io.StringIO("\n# only comments\n")
        code, _ = _run(["tx", "-"])
        self.assertEqual(code, 2)

    def test_missing_file_exits_2(self):
        code, _ = _run(["tx", "--file", "/nonexistent/txids.txt"])
        self.assertEqual(code, 2)
