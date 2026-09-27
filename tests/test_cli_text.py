"""Text-mode (human output) paths of the CLI: every command's error triad
(not found / API error / invalid input) plus each command's output variants."""

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from btc_toolkit import cli
from btc_toolkit.api import MempoolAPIError
from btc_toolkit.balance import AddressNotFoundError
from btc_toolkit.block import BlockNotFoundError
from btc_toolkit.opreturn import TransactionNotFoundError

TXID = "f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab"
ADDR = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.run(argv)
    return code, buf.getvalue()


def _tx(vout=None, coinbase=False, confirmed=True, sequence=0xFFFFFFFF):
    vin = [{"is_coinbase": coinbase, "sequence": sequence,
            "prevout": None if coinbase else {"value": 2500},
            "scriptsig": "", "witness": []}]
    return {
        "txid": TXID, "version": 2, "locktime": 0, "size": 200, "weight": 800,
        "fee": 0 if coinbase else 500,
        "vin": vin,
        "vout": vout if vout is not None else [{"value": 2000, "scriptpubkey_type": "p2pkh"}],
        "status": ({"confirmed": True, "block_height": 800000, "block_hash": "b" * 64,
                    "block_time": 1690000000} if confirmed else {"confirmed": False}),
    }


def _addr(unconf_funded=0, unconf_spent=0):
    return {
        "address": ADDR,
        "chain_stats": {"funded_txo_sum": 5000, "spent_txo_sum": 1000, "tx_count": 3},
        "mempool_stats": {"funded_txo_sum": unconf_funded, "spent_txo_sum": unconf_spent, "tx_count": 1},
    }


def _utxo(n, confirmed=True):
    return {"txid": f"{n:064x}", "vout": n, "value": 1000 * (n + 1),
            "status": {"confirmed": True, "block_height": 1} if confirmed else {"confirmed": False}}


# (command argv, name of the core function as imported in cli, its NotFound exception)
ERROR_TRIAD = [
    (["opreturn", TXID], "decode_op_return", TransactionNotFoundError),
    (["tx", TXID], "get_tx", TransactionNotFoundError),
    (["balance", ADDR], "get_balance", AddressNotFoundError),
    (["address", ADDR], "get_address_overview", AddressNotFoundError),
    (["utxo", ADDR], "get_utxos", AddressNotFoundError),
    (["block", "0"], "get_block", BlockNotFoundError),
]


class TestTextErrorTriad(unittest.TestCase):
    """Every text-mode command maps failures to the documented exit codes."""

    def test_not_found_exits_1(self):
        for argv, fn, notfound in ERROR_TRIAD:
            with self.subTest(cmd=argv[0]), patch(f"btc_toolkit.cli.{fn}", side_effect=notfound("gone")):
                code, out = _run(argv)
                self.assertEqual(code, 1)
                self.assertIn("✗", out)

    def test_api_error_exits_1(self):
        for argv, fn, _ in ERROR_TRIAD + [(["fees"], "get_fees", None)]:
            with self.subTest(cmd=argv[0]), patch(f"btc_toolkit.cli.{fn}", side_effect=MempoolAPIError("down")):
                code, out = _run(argv)
                self.assertEqual(code, 1)
                self.assertIn("down", out)

    def test_invalid_input_exits_2(self):
        for argv, fn, _ in ERROR_TRIAD:
            with self.subTest(cmd=argv[0]), patch(f"btc_toolkit.cli.{fn}", side_effect=ValueError("bad input")):
                code, out = _run(argv)
                self.assertEqual(code, 2)
                self.assertIn("bad input", out)


class TestOpreturnText(unittest.TestCase):
    @patch("btc_toolkit.opreturn.fetch_transaction")
    def test_message_decoded(self, m):
        m.return_value = _tx(vout=[{"value": 0, "scriptpubkey": "6a05" + b"hello".hex(),
                                    "scriptpubkey_type": "op_return"}])
        code, out = _run(["opreturn", TXID])
        self.assertEqual(code, 0)
        self.assertIn("hello", out)
        self.assertIn("Found 1 OP_RETURN", out)

    @patch("btc_toolkit.opreturn.fetch_transaction")
    def test_raw_prints_hex_only(self, m):
        m.return_value = _tx(vout=[{"value": 0, "scriptpubkey": "6a05" + b"hello".hex(),
                                    "scriptpubkey_type": "op_return"}])
        code, out = _run(["opreturn", TXID, "--raw"])
        self.assertEqual(code, 0)
        self.assertIn(b"hello".hex(), out)
        self.assertNotIn("Message:", out)

    @patch("btc_toolkit.opreturn.fetch_transaction")
    def test_binary_payload(self, m):
        m.return_value = _tx(vout=[{"value": 0, "scriptpubkey": "6a04ff00ff00",
                                    "scriptpubkey_type": "op_return"}])
        code, out = _run(["opreturn", TXID])
        self.assertEqual(code, 0)
        self.assertIn("binary data", out)

    @patch("btc_toolkit.opreturn.fetch_transaction")
    def test_no_opreturn(self, m):
        m.return_value = _tx()
        code, out = _run(["opreturn", TXID])
        self.assertEqual(code, 0)
        self.assertIn("No OP_RETURN outputs", out)


class TestBalanceText(unittest.TestCase):
    @patch("btc_toolkit.balance.get_json")
    def test_pending_incoming(self, m):
        m.return_value = _addr(unconf_funded=700)
        code, out = _run(["balance", ADDR])
        self.assertEqual(code, 0)
        self.assertIn("Unconfirmed", out)
        self.assertIn("700 sats (mempool)", out)

    @patch("btc_toolkit.balance.get_json")
    def test_pending_outgoing(self, m):
        m.return_value = _addr(unconf_spent=300)
        code, out = _run(["balance", ADDR])
        self.assertEqual(code, 0)
        self.assertIn("-300 sats (mempool)", out)


class TestUtxoText(unittest.TestCase):
    @patch("btc_toolkit.utxo.get_json")
    def test_empty(self, m):
        m.return_value = []
        code, out = _run(["utxo", ADDR])
        self.assertEqual(code, 0)

    @patch("btc_toolkit.utxo.get_json")
    def test_limit_and_remaining(self, m):
        m.return_value = [_utxo(i) for i in range(5)]
        code, out = _run(["utxo", ADDR, "--limit", "2"])
        self.assertEqual(code, 0)
        self.assertIn("and 3 more", out)

    @patch("btc_toolkit.utxo.get_json")
    def test_mixed_confirmation(self, m):
        m.return_value = [_utxo(0), _utxo(1, confirmed=False)]
        code, out = _run(["utxo", ADDR])
        self.assertEqual(code, 0)
        self.assertIn("mempool", out)
        self.assertIn("Mempool: 1", out)

    @patch("btc_toolkit.utxo.get_json")
    def test_confirmed_only(self, m):
        m.return_value = [_utxo(0), _utxo(1, confirmed=False)]
        code, out = _run(["utxo", ADDR, "--confirmed-only"])
        self.assertEqual(code, 0)
        self.assertIn("confirmed", out)


class TestTxText(unittest.TestCase):
    @patch("btc_toolkit.tx.fetch_transaction")
    def test_unconfirmed(self, m):
        m.return_value = _tx(confirmed=False)
        code, out = _run(["tx", TXID])
        self.assertEqual(code, 0)
        self.assertIn("unconfirmed", out)

    @patch("btc_toolkit.tx.fetch_transaction")
    def test_coinbase(self, m):
        m.return_value = _tx(coinbase=True)
        code, out = _run(["tx", TXID])
        self.assertEqual(code, 0)
        self.assertIn("oinbase", out)


class TestOtherText(unittest.TestCase):
    @patch("btc_toolkit.fees.get_json")
    def test_fees(self, m):
        m.side_effect = [{"fastestFee": 3, "halfHourFee": 2, "hourFee": 1, "economyFee": 1, "minimumFee": 1},
                         {"count": 10, "vsize": 4000, "total_fee": 5000}]
        code, out = _run(["fees"])
        self.assertEqual(code, 0)
        self.assertIn("Fastest", out)

    @patch("btc_toolkit.block.get_json")
    @patch("btc_toolkit.block.get_text")
    def test_block(self, mt, mj):
        mt.return_value = "0" * 64
        mj.return_value = {"id": "0" * 64, "height": 0, "timestamp": 1231006505, "tx_count": 1,
                           "size": 285, "weight": 1140, "difficulty": 1, "nonce": 2083236893,
                           "previousblockhash": None}
        code, out = _run(["block", "0"])
        self.assertEqual(code, 0)
        self.assertIn("genesis", out)


if __name__ == "__main__":
    unittest.main()


class TestUnexpectedShape(unittest.TestCase):
    """If the API ever returns the wrong JSON shape, the user sees an error, not a traceback."""

    @patch("btc_toolkit.balance.get_json", return_value=["not", "an", "object"])
    def test_balance_wrong_shape_exits_1_cleanly(self, _):
        code, out = _run(["balance", ADDR])
        self.assertEqual(code, 1)
        self.assertIn("Unexpected response", out)

    @patch("btc_toolkit.utxo.get_json", return_value={"not": "an array"})
    def test_utxo_wrong_shape_exits_1_cleanly(self, _):
        code, out = _run(["utxo", ADDR])
        self.assertEqual(code, 1)
        self.assertIn("Unexpected response", out)
