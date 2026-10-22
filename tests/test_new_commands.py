"""1.8.0 commands and flags: validate, decode, tx --inputs/--outputs, OP_RETURN protocol tags."""

import io
import json
import time
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from btc_toolkit import cli
from btc_toolkit.api import MempoolAPIError, NotFoundError
from btc_toolkit.opreturn import decode_op_return
from btc_toolkit.tx import get_tx
from tests.test_rawtx import BIP143_TX, GENESIS_TX, GENESIS_TXID

TXID = "f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab"
P2WPKH = "0014751e76e8199196d454941c45d1b3a323f1433bd6"  # bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4


def _run(argv, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), patch("sys.stderr", err), patch("btc_toolkit.colors._USE_COLOR", False):
        if stdin is not None:
            with patch("sys.stdin", io.StringIO(stdin)):
                code = cli.run(argv)
        else:
            code = cli.run(argv)
    return code, out.getvalue(), err.getvalue()


def _tx():
    return {
        "txid": TXID, "version": 2, "locktime": 0, "size": 200, "weight": 600, "fee": 500,
        "vin": [{"txid": "cd" * 32, "vout": 1, "sequence": 0xFFFFFFFD, "is_coinbase": False,
                 "prevout": {"value": 3000, "scriptpubkey": P2WPKH, "scriptpubkey_address": "ignored"}}],
        "vout": [{"value": 2000, "scriptpubkey": P2WPKH},
                 {"value": 500, "scriptpubkey": "6a0568656c6c6f"}],
        "status": {"confirmed": True, "block_height": 1, "block_time": 1690000000},
    }


class TestTxDetails(unittest.TestCase):
    def test_inputs_and_outputs(self):
        spends = [{"spent": True, "txid": "ef" * 32, "vin": 3}, {"spent": False}]
        with patch("btc_toolkit.tx.fetch_transaction", return_value=_tx()), \
                patch("btc_toolkit.tx.get_json", return_value=spends) as gj:
            tx = get_tx(TXID, inputs=True, outputs=True)
        self.assertEqual(gj.call_args.args[0], f"/tx/{TXID}/outspends")
        i = tx.inputs[0]
        # The address is computed from the script, not taken from the API's "scriptpubkey_address".
        self.assertEqual((i.address, i.script_type, i.value),
                         ("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", "P2WPKH", 3000))
        o0, o1 = tx.outputs
        self.assertEqual((o0.spent, o0.spending_txid, o0.spending_vin), (True, "ef" * 32, 3))
        self.assertEqual((o1.script_type, o1.address, o1.spent), ("OP_RETURN", None, False))
        d = tx.to_dict()
        self.assertEqual((d["inputs"][0]["prev_vout"], d["outputs"][0]["spending_vin"]), (1, 3))

    def test_no_details_by_default(self):
        with patch("btc_toolkit.tx.fetch_transaction", return_value=_tx()), \
                patch("btc_toolkit.tx.get_json", side_effect=AssertionError("no extra request")):
            d = get_tx(TXID).to_dict()
        self.assertNotIn("inputs", d)
        self.assertNotIn("outputs", d)

    def test_custom_api_uses_a_valid_claimed_address_only(self):
        tx = _tx()
        tx["vout"][0]["scriptpubkey_address"] = "bcrt1qs758ursh4q9z627kt3pp5yysm78ddny6txaqgw"
        tx["vout"][1]["scriptpubkey_address"] = "\x1b]0;evil"
        with patch("btc_toolkit.tx.fetch_transaction", return_value=tx), \
                patch("btc_toolkit.tx.get_json", return_value=[{"spent": True}, {"spent": False}]):
            outs = get_tx(TXID, "custom", outputs=True).outputs
        self.assertEqual(outs[0].address, "bcrt1qs758ursh4q9z627kt3pp5yysm78ddny6txaqgw")
        self.assertIsNone(outs[1].address)
        self.assertEqual((outs[0].spent, outs[0].spending_txid), (True, None))  # no spender index

    def test_malformed_details_are_api_errors(self):
        bad_tx = _tx()
        bad_tx["vout"][0]["scriptpubkey"] = "zz"
        cases = [
            (bad_tx, [{"spent": False}] * 2),
            (_tx(), [{"spent": False}]),  # one entry for two outputs
            (_tx(), [{"spent": "no"}, {"spent": False}]),
            (_tx(), [{"spent": True, "txid": "\x1b"}, {"spent": False}]),
            (_tx(), ["x", {"spent": False}]),
        ]
        for data, spends in cases:
            with self.subTest(spends=spends), self.assertRaises(MempoolAPIError), \
                    patch("btc_toolkit.tx.fetch_transaction", return_value=data), \
                    patch("btc_toolkit.tx.get_json", return_value=spends):
                get_tx(TXID, inputs=True, outputs=True)

    def test_cli(self):
        with patch("btc_toolkit.tx.fetch_transaction", return_value=_tx()), \
                patch("btc_toolkit.tx.get_json", return_value=[{"spent": True, "txid": "ef" * 32, "vin": 0},
                                                             {"spent": False}]):
            code, out, _ = _run(["tx", TXID, "--inputs", "--outputs"])
            self.assertEqual(code, 0)
            for text in ("Inputs:", "Outputs:", f"spends {'cd' * 32}:1", "RBF", f"spent by {'ef' * 32}:0",
                         "unspendable (OP_RETURN)", "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"):
                self.assertIn(text, out)
            code, out, _ = _run(["tx", TXID, "--outputs", "--json"])
            self.assertEqual(len(json.loads(out)["outputs"]), 2)
            self.assertNotIn("inputs", json.loads(out))

    def test_coinbase_input_detail(self):
        tx = _tx()
        tx["vin"] = [{"txid": "00" * 32, "vout": 0xFFFFFFFF, "is_coinbase": True, "prevout": None, "sequence": 0}]
        with patch("btc_toolkit.tx.fetch_transaction", return_value=tx):
            i = get_tx(TXID, inputs=True).inputs[0]
            code, out, _ = _run(["tx", TXID, "--inputs"])
        self.assertEqual((i.script_type, i.address, i.is_coinbase), ("coinbase", None, True))
        self.assertIn("coinbase", out)


class TestOpReturnProtocols(unittest.TestCase):
    def tag(self, script_hex, asm, coinbase=False):
        tx = {"vin": [{"is_coinbase": coinbase}],
              "vout": [{"scriptpubkey_type": "op_return", "scriptpubkey": script_hex, "scriptpubkey_asm": asm}]}
        with patch("btc_toolkit.opreturn.fetch_transaction", return_value=tx):
            return decode_op_return(TXID)[0].protocol

    def test_tags(self):
        self.assertEqual(self.tag("6a5d0414011400", "OP_RETURN OP_PUSHNUM_13 OP_PUSHBYTES_4 14011400"), "runes")
        commitment = "6a24aa21a9ed" + "11" * 32
        asm = "OP_RETURN OP_PUSHBYTES_36 aa21a9ed" + "11" * 32
        self.assertEqual(self.tag(commitment, asm, coinbase=True), "witness_commitment")
        self.assertIsNone(self.tag(commitment, asm))  # the same bytes outside a coinbase are not a commitment
        omni = "6a14" + (b"omni" + bytes(16)).hex()
        self.assertEqual(self.tag(omni, "OP_RETURN OP_PUSHBYTES_20 " + (b"omni" + bytes(16)).hex()), "omni")
        self.assertIsNone(self.tag("6a0568656c6c6f", "OP_RETURN OP_PUSHBYTES_5 68656c6c6f"))

    def test_text_mode_names_the_protocol(self):
        tx = {"vout": [{"scriptpubkey_type": "op_return", "scriptpubkey": "6a5d0414011400",
                        "scriptpubkey_asm": "OP_RETURN OP_PUSHNUM_13 OP_PUSHBYTES_4 14011400"}]}
        with patch("btc_toolkit.opreturn.fetch_transaction", return_value=tx):
            code, out, _ = _run(["opreturn", TXID])
            self.assertIn("Runes (Runestone)", out)
            code, out, _ = _run(["opreturn", TXID, "--json"])
        self.assertEqual(json.loads(out)["outputs"][0]["protocol"], "runes")


class TestValidateCli(unittest.TestCase):
    def test_valid_invalid_and_network(self):
        code, out, _ = _run(["validate", "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"])
        self.assertEqual(code, 0)
        self.assertIn("checksum verified", out)
        code, out, _ = _run(["validate", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb"])
        self.assertEqual(code, 2)
        self.assertIn("checksum does not match", out)
        code, out, _ = _run(["validate", "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx", "-n", "signet", "--json"])
        self.assertEqual((code, json.loads(out)["address_type"]), (0, "P2WPKH"))
        code, out, _ = _run(["validate", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "-n", "testnet", "--json"])
        self.assertEqual(code, 2)
        self.assertIn("not a testnet one", json.loads(out)["error"])
        code, out, _ = _run(["validate", "3Beer3irc1vgs76ENA4coqsEQpGZeM5CTd"])
        self.assertIn("Hash160:", out)

    def test_batch_and_empty(self):
        code, out, _ = _run(["validate", "-", "--json"], stdin="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\nbad-address\n")
        lines = [json.loads(line) for line in out.splitlines()]
        self.assertEqual((code, lines[0]["valid"], "error" in lines[1]), (2, True, True))
        self.assertEqual(_run(["validate", "   "])[0], 2)

    def test_a_typo_never_reaches_the_api(self):
        with patch("btc_toolkit.balance.get_json", side_effect=AssertionError("must not be called")):
            code, out, _ = _run(["balance", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb", "--json"])
        self.assertEqual(code, 2)
        self.assertIn("checksum", json.loads(out)["error"])


class TestDecodeCli(unittest.TestCase):
    def test_offline(self):
        code, out, _ = _run(["decode", GENESIS_TX])
        self.assertEqual(code, 0)
        self.assertIn(GENESIS_TXID, out)
        self.assertIn("does not carry the values it spends", out)
        code, out, _ = _run(["decode", BIP143_TX, "--json"])
        self.assertEqual((code, json.loads(out)["segwit"]), (0, True))
        code, out, _ = _run(["decode", "BIP143"])
        self.assertEqual(code, 2)  # not hex

    def test_stdin(self):
        code, out, _ = _run(["decode", "-", "--json"], stdin=GENESIS_TX + "\n")
        self.assertEqual((code, json.loads(out)["txid"]), (0, GENESIS_TXID))
        code, out, err = _run(["decode"], stdin="")
        self.assertEqual(code, 2)

    def test_txid_mode_checks_the_hash(self):
        with patch("btc_toolkit.cli.get_text", return_value=GENESIS_TX):
            code, out, _ = _run(["decode", "--txid", GENESIS_TXID])
            self.assertEqual(code, 0)
            self.assertIn("hashes to the txid asked for", out)
            code, out, _ = _run(["decode", "--txid", "11" * 32, "--json"])  # the API returns another tx's bytes
            self.assertEqual(code, 1)
            self.assertIn("hashes to", json.loads(out)["error"])
        with patch("btc_toolkit.cli.get_text", return_value="zz"):
            self.assertEqual(_run(["decode", "--txid", GENESIS_TXID])[0], 1)
        with patch("btc_toolkit.cli.get_text", side_effect=NotFoundError("x")):
            code, out, _ = _run(["decode", "--txid", GENESIS_TXID])
            self.assertEqual(code, 1)
            self.assertIn("not found", out)
        self.assertEqual(_run(["decode", "--txid", "nothex"])[0], 2)
        self.assertEqual(_run(["decode", GENESIS_TX, "--txid", GENESIS_TXID])[0], 2)


class TestAuditFixes(unittest.TestCase):
    """Findings of the independent audit of 1.8.0, each reproduced before the fix."""

    def tearDown(self):
        from btc_toolkit.api import set_api_base
        set_api_base(None)

    def test_response_size_and_time_are_bounded(self):
        from unittest.mock import MagicMock

        from btc_toolkit import api

        def response(chunks):
            resp = MagicMock()
            stream = iter(chunks + [b""])
            resp.read.side_effect = lambda size=-1: next(stream)
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        big = [b"x" * 65536] * (api.MAX_RESPONSE_BYTES // 65536 + 2)
        with patch("btc_toolkit.api._urlopen", return_value=response(big)), \
                self.assertRaisesRegex(MempoolAPIError, "larger than"):
            api.get_json("/x")
        # The second chunk arrives after the deadline. Only api's own `time` is replaced: patching the global
        # time.monotonic would also feed this fake clock to any other thread still running.
        clock = iter([0.0, 1000.0, 1000.0, 1000.0])
        fake_time = types.SimpleNamespace(monotonic=lambda: next(clock), sleep=time.sleep)
        with patch("btc_toolkit.api._urlopen", return_value=response([b"[", b"1]"])), \
                patch("btc_toolkit.api.time", fake_time), \
                self.assertRaisesRegex(MempoolAPIError, "not received within"):
            api.get_json("/x")

    def test_api_url_without_userinfo_query_or_fragment(self):
        from btc_toolkit.api import set_api_base
        for url in ("http://user:pw@node/api", "http://evil\\@good/api", "http://node/api?x=1", "http://node/api#f",
                    "http://node/api?"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                set_api_base(url)

    def test_api_url_with_network_keeps_the_network(self):
        with patch("btc_toolkit.balance.get_json", return_value={"chain_stats": {}, "mempool_stats": {}}):
            code, out, _ = _run(["balance", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "--api-url", "http://n/api",
                                 "-n", "mainnet", "--json"])
            self.assertEqual((code, json.loads(out)["network"]), (0, "mainnet"))
            code, out, _ = _run(["balance", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "--api-url", "http://n/api",
                                 "--json"])
            self.assertEqual((code, json.loads(out)["network"]), (0, "custom"))

    def test_offline_commands_ignore_the_api_url_environment_variable(self):
        with patch.dict("os.environ", {"BTC_TOOLKIT_API_URL": "http://n/api"}):
            code, out, _ = _run(["validate", "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx", "--json"])
            self.assertEqual(code, 2)  # mainnet by default: a testnet address is not accepted silently
            code, out, _ = _run(["decode", BIP143_TX, "--json"])
            self.assertTrue(all(o["address"] for o in json.loads(out)["outputs"]))

    def test_lone_surrogates_are_escaped(self):
        code, out, _ = _run(["validate", "\udcff\udc9b"])
        self.assertEqual(code, 2)
        self.assertNotIn("\udc9b", out)
        out.encode("utf-8")  # printable on a strict UTF-8 terminal

    def test_a_huge_tip_height_is_an_api_error(self):
        with patch("btc_toolkit.block.get_text", return_value="9" * 5000):
            code, out, _ = _run(["block", "latest", "--json"])
        self.assertEqual(code, 1)
        self.assertEqual(_run(["block", "9" * 5000])[0], 2)

    def test_the_api_must_answer_for_the_txid_asked(self):
        with patch("btc_toolkit.opreturn.get_json", return_value={**_tx(), "txid": "ee" * 32}):
            code, out, _ = _run(["tx", TXID, "--json"])
        self.assertEqual(code, 1)
        self.assertIn("different transaction", json.loads(out)["error"])

    def test_decode_hints_and_prefixes(self):
        code, out, _ = _run(["decode", GENESIS_TXID])
        self.assertEqual(code, 2)
        self.assertIn("decode --txid", out)
        code, out, _ = _run(["decode", "0x" + GENESIS_TX, "--json"])
        self.assertEqual((code, json.loads(out)["txid"]), (0, GENESIS_TXID))
        code, out, _ = _run(["decode", "-", "--json"], stdin="\ufeff" + GENESIS_TX)
        self.assertEqual(code, 0)
        code, out, _ = _run(["decode", "--txid", "", "--json"])
        self.assertEqual(code, 2)
        with patch("sys.stdin", None):
            self.assertEqual(_run(["decode"])[0], 2)
            self.assertEqual(_run(["tx"])[0], 2)
        decoded = json.loads(_run(["decode", BIP143_TX, "--json"])[1])
        self.assertEqual(list(decoded["outputs"][0])[:4], ["index", "value_sats", "address", "script_type"])

    def test_json_error_shapes(self):
        out = _run(["validate", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb", "--json"])[1]
        self.assertIs(json.loads(out)["valid"], False)
        with patch("btc_toolkit.inscription.fetch_transaction", side_effect=MempoolAPIError("down")):
            out = _run(["inscription", TXID, "--json"])[1]
        self.assertEqual(json.loads(out)["error"], "down")


class TestLiveRunFindings(unittest.TestCase):
    """Found by running every command against mainnet, testnet and signet on a Mac (1.8.1)."""

    def test_utxo_explains_the_400_of_a_huge_address(self):
        from btc_toolkit.api import BadRequestError
        with patch("btc_toolkit.utxo.get_json", side_effect=BadRequestError("API error 400: Bad Request")):
            code, out, _ = _run(["utxo", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
            self.assertEqual(code, 1)
            self.assertIn("tens of thousands", out)
            self.assertIn("`balance` still works", out)
            code, out, _ = _run(["utxo", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "--json"])
            self.assertEqual(code, 1)
            self.assertIn("tens of thousands", json.loads(out)["error"])

    def test_a_400_is_still_a_plain_api_error_elsewhere(self):
        from btc_toolkit.api import BadRequestError, MempoolAPIError
        self.assertTrue(issubclass(BadRequestError, MempoolAPIError))

    def test_block_shows_a_difficulty_below_one(self):
        block = {"id": "0" * 64, "height": 0, "timestamp": 1598918400, "tx_count": 1, "size": 285, "weight": 1140,
                 "difficulty": 0.001126515290698186, "nonce": 52613770, "previousblockhash": None}
        with patch("btc_toolkit.block.get_json", return_value=block), \
                patch("btc_toolkit.block.get_text", return_value="0" * 64):
            code, out, _ = _run(["block", "0", "-n", "signet"])
        self.assertEqual(code, 0)
        self.assertIn("Difficulty:  0.001127", out)

    def test_the_header_names_a_custom_api(self):
        from btc_toolkit.api import set_api_base
        try:
            with patch("btc_toolkit.fees.get_json", side_effect=[{"fastestFee": 1, "halfHourFee": 1, "hourFee": 1,
                                                                  "economyFee": 1, "minimumFee": 1},
                                                                 {"count": 1, "vsize": 1, "total_fee": 1}]):
                code, out, _ = _run(["fees", "--api-url", "http://node.local/api"])
            self.assertEqual(code, 0)
            self.assertIn("fees · custom API", out)
            self.assertNotIn("Mempool.space API", out)
        finally:
            set_api_base(None)
        with patch("btc_toolkit.fees.get_json", side_effect=[{"fastestFee": 1, "halfHourFee": 1, "hourFee": 1,
                                                              "economyFee": 1, "minimumFee": 1},
                                                             {"count": 1, "vsize": 1, "total_fee": 1}]):
            self.assertIn("fees · Mempool.space API", _run(["fees"])[1])


if __name__ == "__main__":
    unittest.main()
