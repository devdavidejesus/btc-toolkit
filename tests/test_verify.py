"""Merkle-proof verification, with the genesis block as a fully real case."""

import hashlib
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from btc_toolkit import cli, verify
from btc_toolkit.api import MempoolAPIError, NotFoundError
from btc_toolkit.encoding import sha256d
from btc_toolkit.opreturn import TransactionNotFoundError
from btc_toolkit.rawtx import _serialize, decode_tx, parse_hex
from btc_toolkit.verify import (
    NotConfirmedError, VerificationError, bits_to_target, merkle_root_from_proof, parse_header, verify_tx,
)
from tests.test_rawtx import GENESIS_TX, GENESIS_TXID

GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
GENESIS_HEADER = (
    "0100000000000000000000000000000000000000000000000000000000000000000000003ba3edfd7a7b12b27ac72c3e67768f617fc81bc3"
    "888a51323a9fb8aa4b1e5e4a29ab5f49ffff001d1dac2b7c"
)


def _api(status=None, tx_hex=GENESIS_TX, proof=None, header=GENESIS_HEADER):
    """Patch the four endpoints verify reads, answering with the genesis block unless told otherwise."""
    status = status or {"confirmed": True, "block_height": 0, "block_hash": GENESIS_HASH}
    proof = proof or {"block_height": 0, "merkle": [], "pos": 0}

    def get_json(path, network="mainnet"):
        return status if path.endswith("/status") else proof

    def get_text(path, network="mainnet"):
        return tx_hex if path.endswith("/hex") else header

    return patch.multiple(verify, get_json=get_json, get_text=get_text)


class TestHeaderAndMerkle(unittest.TestCase):
    def test_genesis_header(self):
        h = parse_header(parse_hex(GENESIS_HEADER))
        self.assertEqual(h.hash, GENESIS_HASH)
        self.assertEqual(h.merkle_root, GENESIS_TXID)
        self.assertEqual((h.time, h.bits, h.nonce), (1231006505, 0x1D00FFFF, 2083236893))
        self.assertEqual(h.difficulty, 1.0)
        self.assertAlmostEqual(h.work_log2, 32.0, places=4)

    def test_bits(self):
        self.assertEqual(bits_to_target(0x1D00FFFF), 0xFFFF << 208)
        self.assertEqual(bits_to_target(0x03123456), 0x123456)
        self.assertEqual(bits_to_target(0x02123400), 0x1234)
        for bad in (0x1D800000, 0x01000000, 0x23000001):
            with self.subTest(bits=hex(bad)), self.assertRaises(ValueError):
                bits_to_target(bad)

    def test_merkle_root_of_a_real_sized_tree(self):
        # Build a tree the way Bitcoin does (odd levels duplicate their last node) and prove every leaf.
        leaves = [hashlib.sha256(bytes([i])).digest() for i in range(11)]
        level, levels = leaves, [leaves]
        while len(level) > 1:
            if len(level) % 2:
                level = level + [level[-1]]
            level = [sha256d(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
            levels.append(level)
        root = levels[-1][0][::-1].hex()
        for pos in range(len(leaves)):
            branch, idx = [], pos
            for lvl in levels[:-1]:
                padded = lvl + [lvl[-1]] if len(lvl) % 2 else lvl
                branch.append(padded[idx ^ 1][::-1].hex())
                idx //= 2
            with self.subTest(pos=pos):
                self.assertEqual(merkle_root_from_proof(leaves[pos][::-1].hex(), branch, pos), root)
                if branch[0] != leaves[pos][::-1].hex():  # a lone last leaf is paired with itself: either side fits
                    self.assertNotEqual(merkle_root_from_proof(leaves[pos][::-1].hex(), branch, pos ^ 1), root)
        with self.assertRaises(ValueError):
            merkle_root_from_proof(GENESIS_TXID, [], 1)


class TestVerify(unittest.TestCase):
    def test_genesis_coinbase_verifies(self):
        with _api():
            v = verify_tx(GENESIS_TXID)
        self.assertEqual((v.block_hash, v.block_height, v.position, v.branch_length), (GENESIS_HASH, 0, 0, 0))
        self.assertEqual(v.block_time_utc, "2009-01-03 18:15:05 UTC")
        self.assertEqual(len(v.checks), 4)
        self.assertTrue(v.to_dict()["verified"])

    def test_every_lie_is_caught(self):
        other_tx = decode_tx(parse_hex(GENESIS_TX))
        other_tx.locktime = 1
        other_hex = _serialize(other_tx.version, other_tx.inputs, other_tx.outputs, 1, witness=False).hex()
        cases = {
            "hashes to": {"tx_hex": other_hex},
            "does not decode": {"tx_hex": "zz"},
            "different block height": {"proof": {"block_height": 5, "merkle": [], "pos": 0}},
            "leads to": {"proof": {"block_height": 0, "merkle": ["11" * 32], "pos": 0}},
            "bad Merkle proof": {"proof": {"block_height": 0, "merkle": [], "pos": 3}},
            "header hashes to": {"header": GENESIS_HEADER[:-2] + "7d"},
            "header from the API is invalid": {"header": GENESIS_HEADER[:20]},
            "longer than any block": {"proof": {"block_height": 0, "merkle": ["11" * 32] * 33, "pos": 0}},
        }
        for reason, kwargs in cases.items():
            with self.subTest(reason=reason), _api(**kwargs), self.assertRaisesRegex(VerificationError, reason):
                verify_tx(GENESIS_TXID)

    def test_proof_of_work_checks(self):
        # Same header, but claiming a much harder target: the hash no longer meets it.
        hard = GENESIS_HEADER[:144] + "ffff0018" + GENESIS_HEADER[152:]
        h = parse_header(parse_hex(hard))
        with _api(status={"confirmed": True, "block_height": 0, "block_hash": h.hash}, header=hard), \
                self.assertRaisesRegex(VerificationError, "above its target|leads to"):
            verify_tx(GENESIS_TXID)

    def test_work_verdict_depends_only_on_proven_work(self):
        # Genesis has difficulty 1: every hash checks out, but that much work is cheap to forge.
        with _api():
            self.assertEqual(verify_tx(GENESIS_TXID).work, "weak")
        with _api(), patch.object(verify, "STRONG_DIFFICULTY", 0.5):
            self.assertEqual(verify_tx(GENESIS_TXID).work, "strong")
            self.assertEqual(verify_tx(GENESIS_TXID, "signet").work, "weak")  # never strong off mainnet
            self.assertEqual(verify_tx(GENESIS_TXID, "custom").work, "weak")

    def test_a_64_byte_transaction_posing_as_a_merkle_node_is_refused(self):
        # CVE-2017-12842: a real 64-byte transaction T in a block can pose as an inner node whose two halves
        # are "hashes" — one of them the txid of a fake transaction. Every level of the proof is checked.
        tx = decode_tx(parse_hex(GENESIS_TX))
        tx.inputs[0].script_sig = b""
        tx.outputs[0].script = b"\x51\x51\x51\x51"
        t = _serialize(tx.version, tx.inputs, tx.outputs, tx.locktime, witness=False)
        self.assertEqual(len(t), 64)
        left, right = t[:32][::-1].hex(), t[32:][::-1].hex()
        with self.assertRaisesRegex(ValueError, "CVE-2017-12842"):
            merkle_root_from_proof(right, [left], 1)
        with self.assertRaisesRegex(ValueError, "CVE-2017-12842"):
            merkle_root_from_proof(left, [right], 0)

    def test_branch_hashes_must_be_hex(self):
        for branch in (["11" * 28 + " " * 8], ["zz" * 32], [5]):
            with self.subTest(branch=branch), self.assertRaises(ValueError):
                merkle_root_from_proof(GENESIS_TXID, branch, 0)
            with self.subTest(branch=branch), _api(proof={"block_height": 0, "merkle": branch, "pos": 0}), \
                    self.assertRaises(MempoolAPIError):
                verify_tx(GENESIS_TXID)

    def test_64_byte_transaction_is_refused(self):
        tx = decode_tx(parse_hex(GENESIS_TX))
        tx.inputs[0].script_sig = b""
        tx.outputs[0].script = b"\x51\x51\x51\x51"
        raw = _serialize(tx.version, tx.inputs, tx.outputs, tx.locktime, witness=False)
        self.assertEqual(len(raw), 64)
        txid = sha256d(raw)[::-1].hex()
        with _api(tx_hex=raw.hex()), self.assertRaisesRegex(VerificationError, "64-byte"):
            verify_tx(txid)

    def test_unconfirmed_and_unknown(self):
        with _api(status={"confirmed": False}), self.assertRaises(NotConfirmedError):
            verify_tx(GENESIS_TXID)
        with patch.object(verify, "get_json", side_effect=NotFoundError("x")), \
                self.assertRaises(TransactionNotFoundError):
            verify_tx(GENESIS_TXID)
        with self.assertRaises(ValueError):
            verify_tx("nothex")


class TestVerifyCli(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with redirect_stdout(out), patch("btc_toolkit.colors._USE_COLOR", False):
            code = cli.run(argv)
        return code, out.getvalue()

    def test_text_and_json(self):
        with _api():
            code, out = self._run(["verify", GENESIS_TXID])
        self.assertEqual(code, 0)
        self.assertIn("CONSISTENT, WEAK WORK", out)
        self.assertNotIn("VERIFIED", out)
        self.assertIn("cheap enough to fake", out)
        with _api(), patch.object(verify, "STRONG_DIFFICULTY", 0.5):
            code, out = self._run(["verify", GENESIS_TXID])
        self.assertIn("✓ VERIFIED", out)
        with _api():
            code, out = self._run(["verify", GENESIS_TXID, "--json"])
        d = json.loads(out)
        self.assertEqual((code, d["verified"], d["work"], d["block_hash"], d["bits"]),
                         (0, True, "weak", GENESIS_HASH, 0x1D00FFFF))
        self.assertTrue(all(c["passed"] for c in d["checks"]))
        for network, hint in (("signet", "block signatures are not checked"), ("testnet", "difficulty can be minimal")):
            with _api():
                self.assertIn(hint, self._run(["verify", GENESIS_TXID, "-n", network])[1])

    def test_api_url_with_and_without_network(self):
        from btc_toolkit.api import set_api_base
        try:
            with _api():
                out = self._run(["verify", GENESIS_TXID, "--api-url", "http://node.local/api"])[1]
                self.assertIn("pass both --api-url <url> and", out)
                self.assertNotIn("mempool.space/block", out)  # no public links with your own API
                d = json.loads(self._run(["verify", GENESIS_TXID, "--api-url", "http://node.local/api",
                                          "-n", "mainnet", "--json"])[1])
                self.assertEqual(d["network"], "mainnet")
        finally:
            set_api_base(None)

    def test_failures_exit_1_and_bad_input_exits_2(self):
        with _api(header=GENESIS_HEADER[:-2] + "7d"):
            code, out = self._run(["verify", GENESIS_TXID, "--json"])
        self.assertEqual((code, json.loads(out)["verified"]), (1, False))
        with _api(status={"confirmed": False}):
            code, out = self._run(["verify", GENESIS_TXID])
        self.assertEqual(code, 1)
        self.assertIn("not confirmed yet", out)
        code, _ = self._run(["verify", "nothex"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
