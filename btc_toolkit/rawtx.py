"""
Raw transaction decoder, offline.

Parses the consensus serialization of a transaction (legacy or SegWit,
BIP 144) and computes what can be known without the chain: txid, wtxid,
size, weight, vsize, every input and output. The fee needs the values of the
outputs being spent, which a raw transaction does not contain.

Standard library only. The input is untrusted: every length is bounded by
the bytes actually present, and the whole input must be consumed.
"""

from dataclasses import dataclass
from typing import Any

from .encoding import sha256d, script_address, script_type

MAX_TX_BYTES = 4_000_000  # a block's weight limit bounds any transaction


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def take(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError(f"raw transaction ends early (needed {n} bytes at offset {self.pos})")
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def u32(self) -> int:
        return int.from_bytes(self.take(4), "little")

    def varint(self) -> int:
        first = self.take(1)[0]
        if first < 0xFD:
            return first
        size = {0xFD: 2, 0xFE: 4, 0xFF: 8}[first]
        value = int.from_bytes(self.take(size), "little")
        if value < {2: 0xFD, 4: 0x10000, 8: 0x100000000}[size]:
            raise ValueError("non-canonical compact size")
        return value

    def count(self, min_item_bytes: int) -> int:
        """A count of items that must each take at least min_item_bytes of what is left."""
        n = self.varint()
        if n * min_item_bytes > len(self.data) - self.pos:
            raise ValueError("raw transaction declares more items than it has bytes for")
        return n

    def var_bytes(self) -> bytes:
        return self.take(self.count(1))


@dataclass
class RawInput:
    prev_txid: str
    prev_vout: int
    script_sig: bytes
    sequence: int
    witness: list[bytes]

    @property
    def is_coinbase(self) -> bool:
        return self.prev_txid == "0" * 64 and self.prev_vout == 0xFFFFFFFF

    def to_dict(self) -> dict[str, Any]:
        return {
            "prev_txid": self.prev_txid,
            "prev_vout": self.prev_vout,
            "script_sig_hex": self.script_sig.hex(),
            "sequence": self.sequence,
            "witness": [w.hex() for w in self.witness],
            "is_coinbase": self.is_coinbase,
        }


@dataclass
class RawOutput:
    value: int
    script: bytes
    address: str | None
    script_type: str

    def to_dict(self) -> dict[str, Any]:
        # Same keys, in the same order, as an output of `tx --outputs`, plus the script itself.
        return {
            "value_sats": self.value,
            "address": self.address,
            "script_type": self.script_type,
            "script_pubkey_hex": self.script.hex(),
        }


@dataclass
class DecodedTx:
    txid: str
    wtxid: str
    version: int
    locktime: int
    size: int  # bytes, witness included
    base_size: int  # bytes, without witness (what the txid commits to)
    segwit: bool
    inputs: list[RawInput]
    outputs: list[RawOutput]

    @property
    def weight(self) -> int:
        return self.base_size * 3 + self.size

    @property
    def vsize(self) -> int:
        return (self.weight + 3) // 4

    @property
    def total_output(self) -> int:
        return sum(o.value for o in self.outputs)

    @property
    def is_rbf(self) -> bool:
        return any(not i.is_coinbase and i.sequence < 0xFFFFFFFE for i in self.inputs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "txid": self.txid,
            "wtxid": self.wtxid,
            "version": self.version,
            "locktime": self.locktime,
            "segwit": self.segwit,
            "size_bytes": self.size,
            "base_size_bytes": self.base_size,
            "weight": self.weight,
            "vsize": self.vsize,
            "input_count": len(self.inputs),
            "output_count": len(self.outputs),
            "total_output_sats": self.total_output,
            "is_rbf": self.is_rbf,
            "inputs": [{"index": n, **i.to_dict()} for n, i in enumerate(self.inputs)],
            "outputs": [{"index": n, **o.to_dict()} for n, o in enumerate(self.outputs)],
        }


def parse_hex(text: str) -> bytes:
    """Hex text to bytes; whitespace is ignored. Raises ValueError."""
    clean = "".join(text.split())
    if not clean:
        raise ValueError("no raw transaction given")
    if len(clean) > 2 * MAX_TX_BYTES:
        raise ValueError("raw transaction is larger than any valid transaction")
    if len(clean) % 2 or any(ch not in "0123456789abcdefABCDEF" for ch in clean):
        raise ValueError("raw transaction is not hex")
    return bytes.fromhex(clean)


def decode_tx(raw: bytes, network: str = "mainnet") -> DecodedTx:
    """
    Decode a serialized transaction. Raises ValueError when it is malformed.

    `network` only chooses how output addresses are written (bc1 / tb1);
    with an unknown chain ('custom') no address is given.
    """
    if len(raw) > MAX_TX_BYTES:
        raise ValueError("raw transaction is larger than any valid transaction")
    r = _Reader(raw)
    version = int.from_bytes(r.take(4), "little", signed=True)

    segwit = False
    if r.data[r.pos:r.pos + 1] == b"\x00":  # BIP 144 marker
        r.take(1)
        if r.take(1) != b"\x01":
            raise ValueError("unknown SegWit flag (expected 0x01)")
        segwit = True

    inputs = []
    for _ in range(r.count(41)):  # outpoint 36 + script length 1 + sequence 4
        prev = r.take(32)[::-1].hex()
        vout = r.u32()
        script_sig = r.var_bytes()
        inputs.append(RawInput(prev, vout, script_sig, r.u32(), []))
    if not inputs:
        raise ValueError("transaction has no inputs")

    outputs = []
    for _ in range(r.count(9)):  # value 8 + script length 1
        value = int.from_bytes(r.take(8), "little")
        if value > 21_000_000 * 100_000_000:
            raise ValueError("output value above the 21 million BTC supply")
        script = r.var_bytes()
        outputs.append(RawOutput(value, script, script_address(script, network), script_type(script)))
    if not outputs:
        raise ValueError("transaction has no outputs")

    if segwit:
        for i in inputs:
            i.witness = [r.var_bytes() for _ in range(r.count(1))]
        if not any(i.witness for i in inputs):
            raise ValueError("SegWit marker present but every witness is empty")
    locktime = r.u32()
    if r.pos != len(raw):
        raise ValueError(f"{len(raw) - r.pos} unexpected bytes after the transaction")

    base = _serialize(version, inputs, outputs, locktime, witness=False)
    return DecodedTx(
        txid=sha256d(base)[::-1].hex(),
        wtxid=sha256d(raw)[::-1].hex(),
        version=version,
        locktime=locktime,
        size=len(raw),
        base_size=len(base),
        segwit=segwit,
        inputs=inputs,
        outputs=outputs,
    )


def _varint(n: int) -> bytes:
    if n < 0xFD:
        return bytes([n])
    if n <= 0xFFFF:
        return b"\xfd" + n.to_bytes(2, "little")
    if n <= 0xFFFFFFFF:
        return b"\xfe" + n.to_bytes(4, "little")
    return b"\xff" + n.to_bytes(8, "little")


def _serialize(version: int, inputs: list[RawInput], outputs: list[RawOutput], locktime: int, witness: bool) -> bytes:
    """Re-serialize; without witness this is exactly what the txid hashes."""
    parts = [version.to_bytes(4, "little", signed=True)]
    if witness:
        parts.append(b"\x00\x01")
    parts.append(_varint(len(inputs)))
    for i in inputs:
        parts += [bytes.fromhex(i.prev_txid)[::-1], i.prev_vout.to_bytes(4, "little"),
                  _varint(len(i.script_sig)), i.script_sig, i.sequence.to_bytes(4, "little")]
    parts.append(_varint(len(outputs)))
    for o in outputs:
        parts += [o.value.to_bytes(8, "little"), _varint(len(o.script)), o.script]
    if witness:
        for i in inputs:
            parts.append(_varint(len(i.witness)))
            for item in i.witness:
                parts += [_varint(len(item)), item]
    parts.append(locktime.to_bytes(4, "little"))
    return b"".join(parts)
