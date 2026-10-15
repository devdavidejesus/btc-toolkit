"""Offline raw transaction decoding."""

import unittest

from btc_toolkit.rawtx import _serialize, decode_tx, parse_hex

# The genesis block's coinbase: its txid is known independently of this code.
GENESIS_TX = (
    "01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff4d04ffff001d0104455468652054"
    "696d65732030332f4a616e2f32303039204368616e63656c6c6f72206f6e206272696e6b206f66207365636f6e64206261696c6f7574"
    "20666f722062616e6b73ffffffff0100f2052a01000000434104678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f"
    "61deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5fac00000000"
)
GENESIS_TXID = "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"

# BIP 143, "Native P2WPKH": the serialized signed transaction (one legacy input, one SegWit input).
BIP143_TX = (
    "01000000000102fff7f7881a8099afa6940d42d1e7f6362bec38171ea3edf433541db4e4ad969f00000000494830450221008b9d1dc26ba6a"
    "9cb62127b02742fa9d754cd3bebf337f7a55d114c8e5cdd30be022040529b194ba3f9281a99f2b1c0a19c0489bc22ede944ccf4ecbab4cc61"
    "8ef3ed01eeffffffef51e1b804cc89d182d279655c3aa89e815b1b309fe287d9b2b55d57b90ec68a0100000000ffffffff02202cb2060000"
    "00001976a9148280b37df378db99f66f85c95a783a76ac7a6d5988ac9093510d000000001976a9143bde42dbee7e4dbe6a21b2d50ce2f0167f"
    "aa815988ac000247304402203609e17b84f6a7d30c80bfa610b5b4542f32a8a0d5447a12fb1366d7f01cc44a0220573a954c4518331561406"
    "f90300e8f3358f51928d43c212a8caed02de67eebee0121025476c2e83188368da1ff3e292e7acafcdb3566bb0ad253f62fc70f07aeee6357"
    "11000000"
)


class TestDecode(unittest.TestCase):
    def test_genesis_coinbase(self):
        tx = decode_tx(parse_hex(GENESIS_TX))
        self.assertEqual(tx.txid, GENESIS_TXID)
        self.assertEqual(tx.wtxid, GENESIS_TXID)  # no witness: both hashes are the same
        self.assertFalse(tx.segwit)
        self.assertTrue(tx.inputs[0].is_coinbase)
        self.assertIn(b"Chancellor on brink of second bailout for banks", tx.inputs[0].script_sig)
        self.assertEqual((tx.outputs[0].value, tx.outputs[0].script_type), (50 * 10**8, "P2PK"))
        self.assertEqual((tx.size, tx.weight, tx.vsize), (204, 816, 204))
        self.assertFalse(tx.is_rbf)

    def test_segwit_bip143(self):
        raw = parse_hex(BIP143_TX)
        tx = decode_tx(raw)
        self.assertTrue(tx.segwit)
        self.assertEqual([len(i.witness) for i in tx.inputs], [0, 2])
        self.assertEqual(tx.locktime, 17)
        self.assertEqual([o.value for o in tx.outputs], [112_340_000, 223_450_000])
        self.assertEqual([o.script_type for o in tx.outputs], ["P2PKH", "P2PKH"])
        self.assertEqual((tx.size, tx.base_size, tx.weight, tx.vsize), (343, 233, 1042, 261))
        self.assertNotEqual(tx.txid, tx.wtxid)
        # Both serializations are rebuilt exactly from the decoded fields.
        self.assertEqual(_serialize(tx.version, tx.inputs, tx.outputs, tx.locktime, witness=True), raw)
        self.assertEqual(len(_serialize(tx.version, tx.inputs, tx.outputs, tx.locktime, witness=False)), 233)
        self.assertEqual(tx.txid, "e8151a2af31c368a35053ddd4bdb285a8595c769a3ad83e0fa02314a602d4609")
        self.assertTrue(tx.is_rbf)  # input 0 has sequence 0xffffffee

    def test_addresses_follow_the_network(self):
        tx = decode_tx(parse_hex(BIP143_TX), "testnet")
        self.assertTrue(all(o.address and o.address[0] in "mn" for o in tx.outputs))
        self.assertIsNone(decode_tx(parse_hex(BIP143_TX), "custom").outputs[0].address)

    def test_whitespace_is_ignored(self):
        spaced = " ".join(GENESIS_TX[i:i + 64] for i in range(0, len(GENESIS_TX), 64)) + "\n"
        self.assertEqual(decode_tx(parse_hex(spaced)).txid, GENESIS_TXID)

    def test_malformed(self):
        cases = {
            "": "no raw",
            "zz": "not hex",
            "abc": "not hex",
            GENESIS_TX[:-2]: "ends early",
            GENESIS_TX + "00": "unexpected bytes",
            "01000000" + "00" + "02": "SegWit flag",
            "01000000" + "00" + "01" + GENESIS_TX[8:]: "witness",  # marker, then no real witness section
            "01000000" + "fd0100": "non-canonical",
            "01000000" + "ff" + "ffffffffffffffff": "more items",
            "01000000" + "0001" + "00" + "00000000": "no inputs",  # with the marker, a zero input count is explicit
        }
        for raw_hex, reason in cases.items():
            with self.subTest(raw=raw_hex[:20], reason=reason), self.assertRaisesRegex(ValueError, reason):
                decode_tx(parse_hex(raw_hex))

    def test_segwit_marker_with_empty_witnesses_is_rejected(self):
        tx = decode_tx(parse_hex(GENESIS_TX))
        tx.inputs[0].witness = []
        raw = _serialize(tx.version, tx.inputs, tx.outputs, tx.locktime, witness=True)
        with self.assertRaisesRegex(ValueError, "every witness is empty"):
            decode_tx(raw)

    def test_value_above_supply_is_rejected(self):
        bad = GENESIS_TX.replace("00f2052a01000000", "ffffffffffffff7f")
        with self.assertRaisesRegex(ValueError, "21 million"):
            decode_tx(parse_hex(bad))

    def test_no_outputs_is_rejected(self):
        tx = decode_tx(parse_hex(GENESIS_TX))
        raw = _serialize(tx.version, tx.inputs, [], tx.locktime, witness=False)
        with self.assertRaisesRegex(ValueError, "no outputs"):
            decode_tx(raw)

    def test_too_large(self):
        with self.assertRaisesRegex(ValueError, "larger than any valid"):
            parse_hex("00" * 4_000_001)
        with self.assertRaisesRegex(ValueError, "larger than any valid"):
            decode_tx(b"\x00" * 4_000_001)


if __name__ == "__main__":
    unittest.main()
