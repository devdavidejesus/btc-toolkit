"""
Ordinals inscription envelopes: detect and read them in a transaction's witness.

An inscription is data in a Taproot script-path spend, wrapped in an
"envelope" that never executes:

    OP_FALSE OP_IF "ord" <tag> <value> ... OP_0 <body chunks> ... OP_ENDIF

Tags (from the ord documentation): 1 content type, 2 pointer, 3 parent,
5 metadata, 7 metaprotocol, 9 content encoding, 11 delegate, 13 rune.

Parsing follows ord's own rules (envelope.rs, inscription.rs, tag.rs): an
envelope must close with OP_ENDIF and hold only pushes; an input whose script
has a truncated push yields no envelope; tags are compared as raw bytes; the
first value of a repeated field wins (metadata chunks are joined).
Inscription IDs follow ord's form <txid>i<n>, numbering envelopes in input order.

This is envelope detection, not the ord index. It reads the bytes that are on
chain; it does not assign inscription numbers, track which sat an inscription
sits on or who owns it, or apply ord's rules for "cursed" inscriptions.

Endpoint:
    GET /api/tx/:txid   (each input's witness)
"""

from dataclasses import dataclass
import hashlib
from typing import Any

from .api import MempoolAPIError, field_bool, field_objects
from .opreturn import fetch_transaction, _validate_txid

# Tags are compared as raw bytes, as ord does: b"\x01\x00" is not the content-type tag.
TAG_CONTENT_TYPE = b"\x01"
TAG_POINTER = b"\x02"
TAG_PARENT = b"\x03"
TAG_METADATA = b"\x05"
TAG_METAPROTOCOL = b"\x07"
TAG_CONTENT_ENCODING = b"\x09"
TAG_DELEGATE = b"\x0b"

OP_FALSE, OP_IF, OP_ENDIF = 0x00, 0x63, 0x68
_ORD = b"ord"


class TruncatedScript(ValueError):
    """A push runs past the end of the script."""


def script_pushes(script: bytes) -> list[bytes | int]:
    """
    Split a script into data pushes (bytes) and other opcodes (int).
    OP_1..OP_16 and OP_1NEGATE are returned as the one-byte pushes they produce,
    as ord reads them inside an envelope. Raises TruncatedScript when a push
    runs past the end: ord then ignores every envelope of that input.
    """
    out: list[bytes | int] = []
    i, n = 0, len(script)
    while i < n:
        op = script[i]
        i += 1
        if op <= 0x4E:
            if op <= 0x4B:
                size = op
            else:
                width = {0x4C: 1, 0x4D: 2, 0x4E: 4}[op]
                if i + width > n:
                    raise TruncatedScript("push length runs past the end of the script")
                size = int.from_bytes(script[i:i + width], "little")
                i += width
            if i + size > n:
                raise TruncatedScript("push runs past the end of the script")
            out.append(script[i:i + size])
            i += size
        elif 0x51 <= op <= 0x60:
            out.append(bytes([op - 0x50]))
        elif op == 0x4F:
            out.append(b"\x81")
        else:
            out.append(op)
    return out


def tapscript(witness: list[bytes]) -> bytes | None:
    """
    The script of a Taproot script-path spend, as rust-bitcoin's Witness::tapscript (used by ord) finds it:
    third to last item when there are 3+ items and the last starts with 0x50 (an annex, BIP 341),
    otherwise second to last.
    """
    if len(witness) >= 3 and witness[-1][:1] == b"\x50":
        return witness[-3]
    return witness[-2] if len(witness) >= 2 else None


def _inscription_id(value: bytes) -> str | None:
    """
    Decode an inscription ID from a parent/delegate field, as ord's InscriptionId::from_value:
    a 32-byte txid (reversed) and a little-endian index of 0-4 bytes, with no trailing zero unless 4 bytes long.
    """
    if not 32 <= len(value) <= 36:
        return None
    index = value[32:]
    if index and len(index) != 4 and index[-1] == 0:
        return None
    return f"{value[:32][::-1].hex()}i{int.from_bytes(index, 'little')}"


def _pointer(value: bytes | None) -> int | None:
    """ord's pointer: little-endian, any length as long as bytes past the 8th are zero."""
    if value is None or any(value[8:]):
        return None
    return int.from_bytes(value[:8], "little")


@dataclass
class Envelope:
    inscription_id: str
    input_index: int
    content_type: str | None
    content_encoding: str | None
    metaprotocol: str | None
    pointer: int | None
    parents: list[str]
    delegate: str | None
    metadata_size: int
    body: bytes

    @property
    def body_sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()

    @property
    def body_text(self) -> str | None:
        """The body as text, for an uncompressed text/* or JSON content type that is valid UTF-8."""
        ctype = (self.content_type or "").lower()
        if self.content_encoding or not (ctype.startswith("text/") or ctype.startswith("application/json")):
            return None
        try:
            return self.body.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "inscription_id": self.inscription_id,
            "input_index": self.input_index,
            "content_type": self.content_type,
            "content_encoding": self.content_encoding,
            "metaprotocol": self.metaprotocol,
            "pointer": self.pointer,
            "parents": self.parents,
            "delegate": self.delegate,
            "metadata_bytes": self.metadata_size,
            "body_bytes": len(self.body),
            "body_sha256": self.body_sha256,
            "body_text": self.body_text,
        }


def _text(value: bytes | None) -> str | None:
    """A text field, or None when it is not valid UTF-8 (as ord treats it)."""
    if value is None:
        return None
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _envelopes_in(script: bytes) -> list[list[bytes]]:
    """
    The payload (pushes after "ord") of every complete envelope in a script, as ord's RawEnvelope::from_tapscript:
    OP_FALSE OP_IF "ord" <pushes only> OP_ENDIF. An envelope with an opcode inside, or no OP_ENDIF, is skipped.
    """
    items = script_pushes(script)
    found = []
    i = 0
    while i < len(items):
        if items[i] == b"" and items[i + 1:i + 3] == [OP_IF, _ORD]:
            payload: list[bytes] = []
            j = i + 3
            while j < len(items):
                item = items[j]
                if not isinstance(item, bytes):
                    break
                payload.append(item)
                j += 1
            if j < len(items) and items[j] == OP_ENDIF:
                found.append(payload)
            i = j
        i += 1
    return found


def _build(payload: list[bytes], inscription_id: str, input_index: int) -> Envelope:
    """
    Fields and body of an envelope, as ord's ParsedEnvelope: the body follows the first empty push at an
    even index; before it, pushes pair up as tag and value.
    """
    body_at = next((k for k in range(0, len(payload), 2) if payload[k] == b""), None)
    fields: dict[bytes, list[bytes]] = {}
    for k in range(0, body_at if body_at is not None else len(payload), 2):
        if k + 1 < len(payload):
            fields.setdefault(payload[k], []).append(payload[k + 1])
    body = b"".join(payload[body_at + 1:]) if body_at is not None else b""

    def first(tag: bytes) -> bytes | None:
        return fields.get(tag, [None])[0]

    delegate_raw = first(TAG_DELEGATE)
    return Envelope(
        inscription_id=inscription_id,
        input_index=input_index,
        content_type=_text(first(TAG_CONTENT_TYPE)),
        content_encoding=_text(first(TAG_CONTENT_ENCODING)),
        metaprotocol=_text(first(TAG_METAPROTOCOL)),
        pointer=_pointer(first(TAG_POINTER)),
        parents=[p for p in (_inscription_id(v) for v in fields.get(TAG_PARENT, [])) if p],
        delegate=_inscription_id(delegate_raw) if delegate_raw is not None else None,
        metadata_size=sum(len(v) for v in fields.get(TAG_METADATA, [])),
        body=body,
    )


def get_inscriptions(txid: str, network: str = "mainnet") -> list[Envelope]:
    """
    Find the inscription envelopes in a transaction's inputs.

    Raises:
        ValueError: If the txid format is invalid.
        TransactionNotFoundError: If the transaction does not exist.
        MempoolAPIError: On other API errors.
    """
    txid = _validate_txid(txid)
    data = fetch_transaction(txid, network)
    path = "/tx"
    found: list[Envelope] = []
    for index, vin in enumerate(field_objects(data, "vin", path)):
        if field_bool(vin, "is_coinbase", path):
            continue
        witness = vin.get("witness") or []
        if not isinstance(witness, list) or not all(isinstance(w, str) for w in witness):
            raise MempoolAPIError(f"Unexpected response from {path}: 'witness' is not a list of hex strings")
        try:
            items = [bytes.fromhex(w) for w in witness]
        except ValueError:
            raise MempoolAPIError(f"Unexpected response from {path}: a witness item is not hex") from None
        script = tapscript(items)
        if script is None:
            continue
        try:
            payloads = _envelopes_in(script)
        except TruncatedScript:
            continue  # ord ignores every envelope of an input whose script does not parse
        for payload in payloads:
            found.append(_build(payload, f"{txid}i{len(found)}", index))
    return found
