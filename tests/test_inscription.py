"""Inscription envelope detection in Taproot script-path witnesses."""

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from btc_toolkit import cli
from btc_toolkit.api import MempoolAPIError
from btc_toolkit.inscription import TruncatedScript, get_inscriptions, script_pushes, tapscript

TXID = "ab" * 32


def push(data: bytes) -> bytes:
    if len(data) <= 75:
        return bytes([len(data)]) + data
    if len(data) <= 255:
        return b"\x4c" + bytes([len(data)]) + data
    return b"\x4d" + len(data).to_bytes(2, "little") + data


def envelope(*fields: tuple[bytes, bytes], body: list[bytes] | None = None, close: bool = True) -> bytes:
    script = b"\x00\x63" + push(b"ord")
    for tag, value in fields:
        script += push(tag) + push(value)
    if body is not None:
        script += b"\x00" + b"".join(push(chunk) for chunk in body)
    return script + (b"\x68" if close else b"")


def tx_with(*scripts: bytes, annex: bool = False) -> dict:
    vin = []
    for script in scripts:
        witness = ["11" * 64, (b"\x20" + b"\x02" * 32 + b"\xac" + script).hex(), "c1" + "22" * 32]
        if annex:
            witness.append("50" + "00")
        vin.append({"is_coinbase": False, "witness": witness})
    return {"txid": TXID, "vin": vin, "vout": []}


class TestEnvelopes(unittest.TestCase):
    def find(self, data):
        with patch("btc_toolkit.inscription.fetch_transaction", return_value=data):
            return get_inscriptions(TXID)

    def test_text_inscription(self):
        found = self.find(tx_with(envelope((b"\x01", b"text/plain;charset=utf-8"), body=[b"Hello, ", b"Bitcoin"])))
        self.assertEqual(len(found), 1)
        e = found[0]
        self.assertEqual(e.inscription_id, f"{TXID}i0")
        self.assertEqual(e.content_type, "text/plain;charset=utf-8")
        self.assertEqual(e.body, b"Hello, Bitcoin")
        self.assertEqual(e.body_text, "Hello, Bitcoin")
        self.assertEqual(e.to_dict()["body_bytes"], 14)

    def test_binary_body_is_not_text(self):
        png = b"\x89PNG\r\n\x1a\n" + bytes(300)
        e = self.find(tx_with(envelope((b"\x01", b"image/png"), body=[png[:200], png[200:]])))[0]
        self.assertEqual(len(e.body), len(png))
        self.assertIsNone(e.body_text)

    def test_fields(self):
        parent = bytes.fromhex("cd" * 32)[::-1] + b"\x02"
        e = self.find(tx_with(envelope(
            (b"\x01", b"application/json"), (b"\x02", (1000).to_bytes(2, "little")), (b"\x03", parent),
            (b"\x05", b"\xa1\x01\x02"), (b"\x07", b"brc-20"), (b"\x09", b"br"), (b"\x0b", bytes(32)),
            body=[b"{}"],
        )))[0]
        self.assertEqual((e.pointer, e.metaprotocol, e.content_encoding), (1000, "brc-20", "br"))
        self.assertEqual(e.parents, [f"{'cd' * 32}i2"])
        self.assertEqual(e.delegate, f"{'00' * 32}i0")
        self.assertEqual(e.metadata_size, 3)
        self.assertIsNone(e.body_text)  # compressed: not shown as text

    def test_numbering_across_inputs_and_annex(self):
        one = envelope((b"\x01", b"text/plain"), body=[b"a"])
        found = self.find(tx_with(one + one, one, annex=True))
        self.assertEqual([e.inscription_id for e in found], [f"{TXID}i0", f"{TXID}i1", f"{TXID}i2"])
        self.assertEqual([e.input_index for e in found], [0, 0, 1])

    def test_not_inscriptions(self):
        cases = [
            b"\x51",  # no envelope
            b"\x00\x63" + push(b"xyz") + b"\x68",  # wrong protocol id
            b"\x00\x63" + push(b"ord") + b"\xac\x68",  # an opcode inside the envelope
        ]
        for script in cases:
            with self.subTest(script=script.hex()):
                self.assertEqual(self.find(tx_with(script)), [])
        self.assertEqual(self.find({"vin": [{"is_coinbase": True}]}), [])
        self.assertEqual(self.find({"vin": [{"witness": ["00" * 64]}]}), [])  # key-path spend: no script

    def test_unclosed_envelope_is_not_an_inscription(self):
        # As in ord: no OP_ENDIF, no inscription — and it takes no number.
        unclosed = envelope((b"\x01", b"text/plain"), body=[b"x"], close=False)
        found = self.find(tx_with(unclosed, envelope(body=[b"y"])))
        self.assertEqual([(e.inscription_id, e.input_index) for e in found], [(f"{TXID}i0", 1)])

    def test_follows_ords_field_rules(self):
        txid_bytes = bytes.fromhex("cd" * 32)[::-1]
        e = self.find(tx_with(envelope(
            (b"\x01\x00", b"text/plain"),  # not the content-type tag: tags are raw bytes
            (b"\x0b", txid_bytes + b"\x01\x00"),  # delegate index with a trailing zero: invalid in ord
            (b"\x03", txid_bytes + b"\x05\x00\x00\x00"),  # 4-byte index: trailing zeros allowed
            (b"\x02", (7).to_bytes(10, "little")),  # pointer longer than 8 bytes, zeros past the 8th
            (b"\x07", b"\xff\xfe"),  # metaprotocol that is not UTF-8
            (b"\x01", b"image/png"), (b"\x01", b"text/plain"),  # repeated field: the first value wins
            body=[b"x"],
        )))[0]
        self.assertEqual(e.content_type, "image/png")
        self.assertIsNone(e.delegate)
        self.assertEqual(e.parents, [f"{'cd' * 32}i5"])
        self.assertEqual(e.pointer, 7)
        self.assertIsNone(e.metaprotocol)
        bad_pointer = self.find(tx_with(envelope((b"\x02", bytes(8) + b"\x01"), body=[])))[0]
        self.assertIsNone(bad_pointer.pointer)

    def test_a_truncated_push_hides_the_whole_input(self):
        broken = envelope(body=[b"x"]) + b"\x4c"  # a valid envelope, then a truncated PUSHDATA1
        found = self.find(tx_with(broken, envelope(body=[b"y"])))
        self.assertEqual([(e.inscription_id, e.input_index) for e in found], [(f"{TXID}i0", 1)])

    def test_pushnum_tags_and_pushdata(self):
        script = b"\x00\x63" + push(b"ord") + b"\x51" + push(b"text/plain") + b"\x00" + push(b"z" * 300) + b"\x68"
        e = self.find(tx_with(script))[0]
        self.assertEqual((e.content_type, len(e.body)), ("text/plain", 300))

    def test_bad_witness_is_an_api_error(self):
        for vin in ({"witness": "nope"}, {"witness": ["zz"]}):
            with self.subTest(vin=vin), self.assertRaises(MempoolAPIError):
                self.find({"vin": [vin]})

    def test_helpers(self):
        for truncated in (b"\x4c", b"\x4d\x01", b"\x05ab", b"\x4c\x05ab"):
            with self.subTest(script=truncated.hex()), self.assertRaises(TruncatedScript):
                script_pushes(truncated)
        self.assertEqual(script_pushes(b"\x4f\x60\xac"), [b"\x81", b"\x10", 0xAC])
        self.assertIsNone(tapscript([b"sig"]))
        self.assertEqual(tapscript([b"s", b"script", b"cb", b"\x50"]), b"script")  # annex dropped
        self.assertEqual(tapscript([b"script", b"\x50"]), b"script")  # two items: no annex (rust-bitcoin rule)


class TestInscriptionCli(unittest.TestCase):
    def _run(self, argv, data):
        out = io.StringIO()
        with redirect_stdout(out), patch("btc_toolkit.colors._USE_COLOR", False), \
                patch("btc_toolkit.inscription.fetch_transaction", return_value=data):
            code = cli.run(argv)
        return code, out.getvalue()

    def test_text_output_escapes_the_body(self):
        data = tx_with(envelope((b"\x01", b"text/plain"), body=[b"hi \x1b]0;PWNED\x07"]))
        code, out = self._run(["inscription", TXID], data)
        self.assertEqual(code, 0)
        self.assertIn(f"{TXID}i0", out)
        self.assertNotIn("\x1b", out)
        self.assertIn("not the ord index", out)

    def test_json_and_none_found(self):
        code, out = self._run(["inscription", TXID, "--json"], tx_with(envelope(body=[b"x"])))
        self.assertEqual((code, json.loads(out)["inscription_count"]), (0, 1))
        code, out = self._run(["inscription", TXID], tx_with(b"\x51"))
        self.assertEqual(code, 0)
        self.assertIn("No inscription envelope", out)

    def test_errors(self):
        code, out = self._run(["inscription", "nothex", "--json"], {})
        self.assertEqual(code, 2)
        with patch("btc_toolkit.inscription.fetch_transaction", side_effect=MempoolAPIError("down")):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(cli.run(["inscription", TXID]), 1)


if __name__ == "__main__":
    unittest.main()
