"""Untrusted data: malformed API responses and hostile on-chain text.

The API is input btc-toolkit does not control. A wrong type anywhere in a
response must be a clean MempoolAPIError (exit code 1), never a traceback,
and on-chain text must never reach the terminal with control characters.
"""

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from btc_toolkit import cli
from btc_toolkit.api import MempoolAPIError
from btc_toolkit.balance import get_balance
from btc_toolkit.block import get_block, get_tip_height
from btc_toolkit.fees import get_fees
from btc_toolkit.opreturn import decode_op_return
from btc_toolkit.tx import get_tx
from btc_toolkit.utxo import get_utxos

TXID = "a" * 64
ADDR = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
TX = {"txid": TXID, "version": 2, "locktime": 0, "size": 200, "weight": 800, "fee": 500,
      "vin": [{"sequence": 0xFFFFFFFF, "prevout": {"value": 2500}}], "vout": [{"value": 2000}],
      "status": {"confirmed": True, "block_height": 1, "block_time": 1690000000}}
ADDRESS = {"chain_stats": {"funded_txo_sum": 10, "spent_txo_sum": 0, "tx_count": 1},
           "mempool_stats": {"funded_txo_sum": 0, "spent_txo_sum": 0, "tx_count": 0}}
BLOCK = {"id": "0" * 64, "height": 0, "timestamp": 1231006505, "tx_count": 1, "size": 285, "weight": 1140,
         "version": 1, "merkle_root": "", "previousblockhash": None, "nonce": 2083236893, "bits": 486604799,
         "difficulty": 1, "mediantime": 1231006505}


def _with(base, path, value):
    """Copy of `base` with the key at `path` (a tuple) replaced by `value`."""
    data = json.loads(json.dumps(base))
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return data


class TestMalformedResponses(unittest.TestCase):
    def assert_api_error(self, call):
        with self.assertRaises(MempoolAPIError):
            call()

    def test_tx(self):
        cases = [(("vin",), None), (("vin",), ["x"]), (("vout",), [None]), (("status",), None), (("status",), []),
                 (("vin", 0, "prevout"), "x"), (("vin", 0, "prevout", "value"), "1"), (("vin", 0, "sequence"), None),
                 (("vout", 0, "value"), None), (("fee",), "500"), (("weight",), True), (("txid",), 5),
                 (("status", "confirmed"), "yes"), (("status", "block_height"), "1"),
                 (("status", "block_height"), None), (("status", "block_time"), -1), (("status", "block_time"), 2**40)]
        for path, value in cases:
            with self.subTest(path=path, value=value), \
                    patch("btc_toolkit.tx.fetch_transaction", return_value=_with(TX, path, value)):
                self.assert_api_error(lambda: get_tx(TXID))

    def test_coinbase_input_with_null_prevout_is_valid(self):
        data = _with(TX, ("vin", 0), {"is_coinbase": True, "prevout": None, "sequence": 0xFFFFFFFF})
        with patch("btc_toolkit.tx.fetch_transaction", return_value=data):
            tx = get_tx(TXID)
        self.assertEqual((tx.is_coinbase, tx.total_input), (True, 0))

    def test_unconfirmed_tx_without_height_is_valid(self):
        with patch("btc_toolkit.tx.fetch_transaction", return_value=_with(TX, ("status",), {"confirmed": False})):
            self.assertIsNone(get_tx(TXID).block_height)

    def test_opreturn(self):
        for vout in (None, "x", [None], ["x"], [{"scriptpubkey_type": 1}],
                     [{"scriptpubkey_type": "op_return", "scriptpubkey_asm": None}]):
            with self.subTest(vout=vout), \
                    patch("btc_toolkit.opreturn.get_json", return_value={"vout": vout}):
                self.assert_api_error(lambda: decode_op_return(TXID))

    def test_balance(self):
        for path, value in [(("chain_stats",), None), (("chain_stats",), []), (("mempool_stats",), "x"),
                            (("chain_stats", "funded_txo_sum"), None), (("chain_stats", "spent_txo_sum"), "1"),
                            (("mempool_stats", "tx_count"), 1.5)]:
            with self.subTest(path=path, value=value), \
                    patch("btc_toolkit.balance.get_json", return_value=_with(ADDRESS, path, value)):
                self.assert_api_error(lambda: get_balance(ADDR))

    def test_utxo(self):
        good = {"txid": TXID, "vout": 0, "value": 1, "status": {"confirmed": True, "block_height": 1}}
        for item in (None, "x", _with(good, ("value",), None), _with(good, ("status",), None),
                     _with(good, ("vout",), "0"), _with(good, ("status", "block_height"), "1")):
            with self.subTest(item=item), patch("btc_toolkit.utxo.get_json", return_value=[good, item]):
                self.assert_api_error(lambda: get_utxos(ADDR))

    def test_fees(self):
        fees = {"fastestFee": 2, "halfHourFee": 2, "hourFee": 1, "economyFee": 1, "minimumFee": 1}
        mempool = {"count": 10, "vsize": 4000, "total_fee": 5000}
        for fees_data, mempool_data in [(_with(fees, ("fastestFee",), None), mempool),
                                        (_with(fees, ("hourFee",), float("nan")), mempool),
                                        (fees, _with(mempool, ("vsize",), None)),
                                        (fees, _with(mempool, ("total_fee",), "5000"))]:
            with self.subTest(fees=fees_data, mempool=mempool_data), \
                    patch("btc_toolkit.fees.get_json", side_effect=[fees_data, mempool_data]):
                self.assert_api_error(get_fees)

    def test_block(self):
        for path, value in [(("timestamp",), None), (("timestamp",), 2**40), (("size",), "x"), (("height",), None),
                            (("difficulty",), "1"), (("previousblockhash",), 5), (("id",), None)]:
            with self.subTest(path=path, value=value), \
                    patch("btc_toolkit.block.get_json", return_value=_with(BLOCK, path, value)):
                self.assert_api_error(lambda: get_block("0" * 64))

    def test_non_ascii_digits_are_not_a_height(self):
        with self.assertRaises(ValueError):  # "²".isdigit() is True, int("²") fails
            get_block("²")

    def test_64_digit_ref_is_a_hash_not_a_height(self):
        with patch("btc_toolkit.block.get_json", return_value=BLOCK) as m, \
                patch("btc_toolkit.block.get_text", side_effect=AssertionError("must not query /block-height")):
            get_block("0" * 64)
        self.assertEqual(m.call_args.args[0], "/block/" + "0" * 64)

    def test_block_text_endpoints(self):
        with patch("btc_toolkit.block.get_text", return_value="<html>oops</html>"):
            self.assert_api_error(lambda: get_tip_height())
        with patch("btc_toolkit.block.get_text", return_value="not-a-hash"):
            self.assert_api_error(lambda: get_block("5"))

    def test_cli_exit_code_is_1_not_a_traceback(self):
        # The same malformed data through the CLI, text and JSON mode, and in a batch.
        with patch("btc_toolkit.tx.fetch_transaction", return_value=_with(TX, ("vin",), ["x"])):
            for argv in (["tx", TXID], ["tx", TXID, "--json"]):
                with self.subTest(argv=argv), redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.run(argv), 1)
        with patch("btc_toolkit.block.get_text", return_value="<html>"), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.run(["block", "latest", "--json"]), 1)  # an API problem, not invalid input
        self.assertIn("Unexpected response", json.loads(out.getvalue())["error"])


class TestReviewFindings(unittest.TestCase):
    """Cases found by an independent review of the hardening itself."""

    def test_total_fee_is_rounded_not_truncated(self):
        # mempool.space sends total_fee as BTC * 1e8: 0.29 BTC arrives as 28999999.999999996.
        fees = {"fastestFee": 2, "halfHourFee": 2, "hourFee": 1, "economyFee": 1, "minimumFee": 1}
        with patch("btc_toolkit.fees.get_json", side_effect=[fees, {"count": 1, "vsize": 1, "total_fee": 0.29 * 1e8}]):
            self.assertEqual(get_fees().mempool_total_fee, 29_000_000)

    def test_huge_numbers_are_an_api_error(self):
        fees = {"fastestFee": 10**400, "halfHourFee": 2, "hourFee": 1, "economyFee": 1, "minimumFee": 1}
        with patch("btc_toolkit.fees.get_json", side_effect=[fees, {"count": 1, "vsize": 1, "total_fee": 1}]):
            self.assertRaises(MempoolAPIError, get_fees)
        with patch("btc_toolkit.tx.fetch_transaction", return_value=_with(TX, ("fee",), 2**70)):
            self.assertRaises(MempoolAPIError, get_tx, TXID)
        for path, value in [(("size",), 2**70), (("difficulty",), 10**400)]:
            with self.subTest(path=path), patch("btc_toolkit.block.get_json", return_value=_with(BLOCK, path, value)):
                self.assertRaises(MempoolAPIError, get_block, "0" * 64)

    def test_raw_script_fallback_details(self):
        cases = [({"scriptpubkey": "6A0548656C6C6F", "scriptpubkey_asm": ""}, "48656c6c6f"),   # uppercase: lowercased
                 ({"scriptpubkey_asm": "OP_RETURN"}, "")]                                     # bare, no raw script
        for vout, expected in cases:
            vout = {"scriptpubkey_type": "op_return", **vout}
            with self.subTest(vout=vout), \
                    patch("btc_toolkit.opreturn.fetch_transaction", return_value={"vout": [vout]}):
                self.assertEqual(decode_op_return(TXID)[0].raw_hex, expected)

    def test_truncated_push_keeps_its_bytes(self):
        tx = {"vout": [{"scriptpubkey_type": "op_return", "scriptpubkey": "6a05414243",
                        "scriptpubkey_asm": "OP_RETURN OP_PUSHBYTES_5 <push past end>"}]}
        with patch("btc_toolkit.opreturn.fetch_transaction", return_value=tx):
            out = decode_op_return(TXID)
        self.assertEqual((out[0].raw_hex, out[0].decoded_text), ("414243", "ABC"))


class TestOnChainTextInTheTerminal(unittest.TestCase):
    def setUp(self) -> None:
        # Colors are ANSI sequences too: turn them off so the test sees only what the message adds,
        # whether or not the suite runs in a terminal.
        patcher = patch("btc_toolkit.colors._USE_COLOR", False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _opreturn_text(self, payload: bytes) -> str:
        script = "6a" + format(len(payload), "02x") + payload.hex()
        tx = {"vout": [{"scriptpubkey_type": "op_return", "scriptpubkey": script,
                        "scriptpubkey_asm": f"OP_RETURN OP_PUSHBYTES_{len(payload)} {payload.hex()}"}]}
        buf = io.StringIO()
        with patch("btc_toolkit.opreturn.fetch_transaction", return_value=tx), redirect_stdout(buf):
            self.assertEqual(cli.run(["opreturn", TXID]), 0)
        return buf.getvalue()

    def test_escape_sequences_are_shown_escaped(self):
        out = self._opreturn_text(b"Hello world, read me \x1b]0;PWNED\x07\x1b[2J")
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\x07", out)
        self.assertIn("Hello world, read me \\x1b]0;PWNED\\x07\\x1b[2J", out)

    def test_bidi_controls_are_shown_escaped(self):
        out = self._opreturn_text("pay ‮evil".encode())
        self.assertNotIn("‮", out)
        self.assertIn("pay \\u202eevil", out)

    def test_ordinary_unicode_is_kept(self):
        out = self._opreturn_text("café ₿ 日本".encode())
        self.assertIn("café ₿ 日本", out)

    def test_json_output_escapes_control_characters(self):
        tx = {"vout": [{"scriptpubkey_type": "op_return", "scriptpubkey": "6a03" + b"a\x1bb".hex(),
                        "scriptpubkey_asm": "OP_RETURN OP_PUSHBYTES_3 " + b"a\x1bb".hex()}]}
        buf = io.StringIO()
        with patch("btc_toolkit.opreturn.fetch_transaction", return_value=tx), redirect_stdout(buf):
            cli.run(["opreturn", TXID, "--json"])
        self.assertNotIn("\x1b", buf.getvalue())
        self.assertEqual(json.loads(buf.getvalue())["outputs"][0]["decoded_text"], "a\x1bb")


class TestRawAndLinks(unittest.TestCase):
    TX = {"vout": [{"scriptpubkey_type": "op_return", "scriptpubkey": "6a0568656c6c6f",
                    "scriptpubkey_asm": "OP_RETURN OP_PUSHBYTES_5 68656c6c6f"},
                   {"scriptpubkey_type": "op_return", "scriptpubkey": "6a", "scriptpubkey_asm": "OP_RETURN"}]}

    def test_raw_is_only_hex(self):
        buf = io.StringIO()
        with patch("btc_toolkit.opreturn.fetch_transaction", return_value=self.TX), redirect_stdout(buf):
            self.assertEqual(cli.run(["opreturn", TXID, "--raw"]), 0)
        self.assertEqual(buf.getvalue(), "68656c6c6f\n\n")  # one line per OP_RETURN output, the second empty

    def test_raw_errors_go_to_stderr(self):
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.stderr", err), redirect_stdout(out):
            self.assertEqual(cli.run(["opreturn", "nope", "--raw"]), 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("Invalid txid", err.getvalue())

    def test_links_follow_the_network(self):
        cases = {"mainnet": f"https://mempool.space/tx/{TXID}",
                 "testnet": f"https://mempool.space/testnet/tx/{TXID}",
                 "signet": f"https://mempool.space/signet/tx/{TXID}"}
        for network, link in cases.items():
            buf = io.StringIO()
            with self.subTest(network=network), redirect_stdout(buf), \
                    patch("btc_toolkit.opreturn.fetch_transaction", return_value=self.TX):
                cli.run(["opreturn", TXID, "-n", network])
            self.assertIn(link, buf.getvalue())
            for other in set(cases.values()) - {link}:
                self.assertNotIn(other, buf.getvalue())

    def test_no_mempool_space_link_for_a_custom_api(self):
        from btc_toolkit.api import set_api_base
        buf = io.StringIO()
        try:
            with patch("btc_toolkit.opreturn.fetch_transaction", return_value=self.TX), redirect_stdout(buf):
                cli.run(["opreturn", TXID, "--api-url", "http://node.local/api"])
        finally:
            set_api_base(None)
        self.assertNotIn("mempool.space/tx", buf.getvalue())

    def test_empty_payload_in_text_mode(self):
        buf = io.StringIO()
        with patch("btc_toolkit.opreturn.fetch_transaction", return_value=self.TX), redirect_stdout(buf):
            cli.run(["opreturn", TXID])
        self.assertIn("Found 2 OP_RETURN output(s)", buf.getvalue())
        self.assertIn("(no data)", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
