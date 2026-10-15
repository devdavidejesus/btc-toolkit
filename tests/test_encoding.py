"""Address encodings against the official test vectors of BIP 173 and BIP 350, copied verbatim."""
# ruff: noqa: E501 — the vectors are kept exactly as the BIPs print them

import unittest

from btc_toolkit.encoding import (
    _bech32_decode, b58check_decode, b58check_encode, decode_segwit, encode_segwit, parse_address,
    script_address, script_type,
)

# BIP 350, "Test vectors for v0-v16 native segregated witness addresses": address -> scriptPubKey
SEGWIT_VALID = [
    ('BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4', '0014751e76e8199196d454941c45d1b3a323f1433bd6'),
    ('tb1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3q0sl5k7', '00201863143c14c5166804bd19203356da136c985678cd4d27a1b8c6329604903262'),
    ('bc1pw508d6qejxtdg4y5r3zarvary0c5xw7kw508d6qejxtdg4y5r3zarvary0c5xw7kt5nd6y', '5128751e76e8199196d454941c45d1b3a323f1433bd6751e76e8199196d454941c45d1b3a323f1433bd6'),
    ('BC1SW50QGDZ25J', '6002751e'),
    ('bc1zw508d6qejxtdg4y5r3zarvaryvaxxpcs', '5210751e76e8199196d454941c45d1b3a323'),
    ('tb1qqqqqp399et2xygdj5xreqhjjvcmzhxw4aywxecjdzew6hylgvsesrxh6hy', '0020000000c4a5cad46221b2a187905e5266362b99d5e91c6ce24d165dab93e86433'),
    ('tb1pqqqqp399et2xygdj5xreqhjjvcmzhxw4aywxecjdzew6hylgvsesf3hn0c', '5120000000c4a5cad46221b2a187905e5266362b99d5e91c6ce24d165dab93e86433'),
    ('bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0', '512079be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798'),
]
# BIP 350: invalid segwit addresses
SEGWIT_INVALID = [
    'tc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vq5zuyut',
    'bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqh2y7hd',
    'tb1z0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqglt7rf',
    'BC1S0XLXVLHEMJA6C4DQV22UAPCTQUPFHLXM9H8Z3K2E72Q4K9HCZ7VQ54WELL',
    'bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kemeawh',
    'tb1q0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vq24jc47',
    'bc1p38j9r5y49hruaue7wxjce0updqjuyyx0kh56v8s25huc6995vvpql3jow4',
    'BC130XLXVLHEMJA6C4DQV22UAPCTQUPFHLXM9H8Z3K2E72Q4K9HCZ7VQ7ZWS8R',
    'bc1pw5dgrnzv',
    'bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7v8n0nx0muaewav253zgeav',
    'BC1QR508D6QEJXTDG4Y5R3ZARVARYV98GJ9P',
    'tb1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vq47Zagq',
    'bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7v07qwwzcrf',
    'tb1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vpggkg4j',
    'bc1gmk9yu',
]
# BIP 350: valid / invalid Bech32m strings
BECH32M_VALID = [
    'A1LQFN3A',
    'a1lqfn3a',
    'an83characterlonghumanreadablepartthatcontainsthetheexcludedcharactersbioandnumber11sg7hg6',
    'abcdef1l7aum6echk45nj3s0wdvt2fg8x9yrzpqzd3ryx',
    '11llllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllludsr8',
    'split1checkupstagehandshakeupstreamerranterredcaperredlc445v',
    '?1v759aa',
]
BECH32M_INVALID = [
    ' 1xj0phk',
    '\x7f1g6xzxy',
    '\x801vctc34',
    'an84characterslonghumanreadablepartthatcontainsthetheexcludedcharactersbioandnumber11d6pts4',
    'qyrz8wqd2c9m',
    '1qyrz8wqd2c9m',
    'y1b0jsk6g',
    'lt1igcx5c0',
    'in1muywd',
    'mm1crxm3i',
    'au1s5cgom',
    'M1VUXWEZ',
    '16plkw9',
    '1p2gdwpf',
]
# BIP 173: valid / invalid Bech32 strings
BECH32_VALID = [
    'A12UEL5L',
    'a12uel5l',
    'an83characterlonghumanreadablepartthatcontainsthenumber1andtheexcludedcharactersbio1tt5tgs',
    'abcdef1qpzry9x8gf2tvdw0s3jn54khce6mua7lmqqqxw',
    '11qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqc8247j',
    'split1checkupstagehandshakeupstreamerranterredcaperred2y9e3w',
    '?1ezyfcl',
]
BECH32_INVALID = [
    ' 1nwldj5',
    '\x7f1axkwrx',
    '\x801eym55h',
    'an84characterslonghumanreadablepartthatcontainsthenumber1andtheexcludedcharactersbio1569pvx',
    'pzry9x0s0muk',
    '1pzry9x0s0muk',
    'x1b4n0q5v',
    'li1dgmt3',
    'de1lg7wtÿ',
    'A1G7SGD8',
    '10a06t8',
    '1qzzfhee',
]


def _program(script_hex: str) -> tuple[int, bytes]:
    script = bytes.fromhex(script_hex)
    return (0 if script[0] == 0 else script[0] - 0x50), script[2:]


class TestBip350Vectors(unittest.TestCase):
    def test_valid_segwit_addresses(self):
        for address, script_hex in SEGWIT_VALID:
            with self.subTest(address=address):
                hrp = address[:2].lower()
                self.assertEqual(decode_segwit(hrp, address), _program(script_hex))
                # Round trip: encoding gives back the address (lowercase).
                self.assertEqual(encode_segwit(hrp, *_program(script_hex)), address.lower())

    def test_invalid_segwit_addresses(self):
        for address in SEGWIT_INVALID:
            for hrp in ("bc", "tb"):
                with self.subTest(address=address, hrp=hrp), self.assertRaises(ValueError):
                    decode_segwit(hrp, address)

    def test_bech32m_strings(self):
        for text in BECH32M_VALID:
            with self.subTest(text=text):
                self.assertEqual(_bech32_decode(text)[2], 0x2BC830A3)
        for text in BECH32M_INVALID + BECH32_VALID:  # no string is valid as both
            with self.subTest(text=text):
                try:
                    const = _bech32_decode(text)[2]
                except ValueError:
                    continue
                self.assertNotEqual(const, 0x2BC830A3)


class TestBip173Vectors(unittest.TestCase):
    def test_bech32_strings(self):
        for text in BECH32_VALID:
            with self.subTest(text=text):
                self.assertEqual(_bech32_decode(text)[2], 1)
        for text in BECH32_INVALID:
            with self.subTest(text=text), self.assertRaises(ValueError):
                _bech32_decode(text)


class TestParseAddress(unittest.TestCase):
    # Real addresses, each with its expected type and chain.
    REAL = [
        ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "mainnet", "P2PKH", "mainnet"),  # genesis coinbase address
        ("3Beer3irc1vgs76ENA4coqsEQpGZeM5CTd", "mainnet", "P2SH", "mainnet"),
        ("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq", "mainnet", "P2WPKH", "mainnet"),
        ("bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297", "mainnet", "P2TR", "mainnet"),
        ("bc1pfeessrawgf", "mainnet", "P2A", "mainnet"),  # pay-to-anchor
        ("mzBc4XEFSdzCDcTxAgf6EZXgsZWpztRhef", "testnet", "P2PKH", "testnet"),
        ("2N3oefVeg6stiTb5Kh3ozCSkaqmx91FDbsm", "signet", "P2SH", "testnet"),
        ("tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx", "signet", "P2WPKH", "testnet"),
        ("bcrt1qs758ursh4q9z627kt3pp5yysm78ddny6txaqgw", "custom", "P2WPKH", "regtest"),
    ]

    def test_real_addresses(self):
        for address, network, kind, chain in self.REAL:
            with self.subTest(address=address):
                parsed = parse_address(address, network)
                self.assertEqual((parsed.address_type, parsed.chain), (kind, chain))

    def test_a_one_character_typo_is_caught(self):
        for typo in ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb", "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdp"):
            with self.subTest(typo=typo), self.assertRaisesRegex(ValueError, "checksum"):
                parse_address(typo, "mainnet")

    def test_wrong_network_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "mainnet address, not a signet"):
            parse_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "signet")
        with self.assertRaisesRegex(ValueError, "testnet/signet address, not a mainnet"):
            parse_address("tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx", "mainnet")
        with self.assertRaisesRegex(ValueError, "regtest"):
            parse_address("bcrt1qs758ursh4q9z627kt3pp5yysm78ddny6txaqgw", "mainnet")

    def test_uppercase_bech32_is_normalized(self):
        self.assertEqual(parse_address("BC1QAR0SRRR7XFKVY5L643LYDNW9RE59GTZZWF5MDQ").address,
                         "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")

    def test_base58_edge_cases(self):
        for bad in ("", "0OIl", "1" * 120, "1111"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                b58check_decode(bad)
        payload = bytes(21)
        self.assertEqual(b58check_decode(b58check_encode(payload)), payload)
        with self.assertRaisesRegex(ValueError, "version byte"):
            parse_address(b58check_encode(b"\x80" + bytes(20)))  # a WIF-style prefix, not an address
        with self.assertRaisesRegex(ValueError, "21 bytes"):
            parse_address(b58check_encode(bytes(25)))

    def test_unknown_network(self):
        with self.assertRaises(ValueError):
            parse_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "regtest")


class TestScripts(unittest.TestCase):
    def test_types_and_addresses(self):
        cases = [
            ("76a914" + "62e907b15cbf27d5425399ebf6f0fb50ebb88f18" + "88ac", "P2PKH", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"),
            ("a914" + "11" * 20 + "87", "P2SH", None),
            ("0014751e76e8199196d454941c45d1b3a323f1433bd6", "P2WPKH", "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"),
            ("512079be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798", "P2TR",
             "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"),
            ("51024e73", "P2A", "bc1pfeessrawgf"),
            ("6002751e", "witness_v16", "bc1sw50qgdz25j"),
            ("6a0568656c6c6f", "OP_RETURN", None),
            ("21" + "02" * 33 + "ac", "P2PK", None),
            ("5121" + "02" * 33 + "51ae", "multisig", None),
            ("0013" + "00" * 19, "nonstandard", None),
            ("", "nonstandard", None),
        ]
        for script_hex, kind, address in cases:
            script = bytes.fromhex(script_hex)
            with self.subTest(script=script_hex):
                self.assertEqual(script_type(script), kind)
                if address is not None:
                    self.assertEqual(script_address(script, "mainnet"), address)
        p2sh = script_address(bytes.fromhex("a914" + "11" * 20 + "87"), "mainnet")
        self.assertEqual(parse_address(p2sh, "mainnet").address_type, "P2SH")
        self.assertTrue(script_address(bytes.fromhex("0014" + "00" * 20), "signet").startswith("tb1q"))
        self.assertIsNone(script_address(bytes.fromhex("0014" + "00" * 20), "custom"))


if __name__ == "__main__":
    unittest.main()
