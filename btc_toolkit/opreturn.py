"""
OP_RETURN decoder.

Fetches a transaction from the Mempool.space API and extracts
human-readable messages from its OP_RETURN outputs.
"""

from dataclasses import dataclass

from typing import Any
from .api import get_json, as_object, field_objects, field_str, NotFoundError, MempoolAPIError

# OP_RETURN opcode
OP_RETURN_HEX = "6a"


class TransactionNotFoundError(NotFoundError):
    """Raised when a transaction ID is not found."""


@dataclass
class OPReturnData:
    """Represents a decoded OP_RETURN output."""

    txid: str
    vout_index: int
    raw_hex: str
    decoded_text: str | None
    raw_bytes: bytes
    size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "txid": self.txid,
            "vout_index": self.vout_index,
            "raw_hex": self.raw_hex,
            "decoded_text": self.decoded_text,
            "size_bytes": self.size,
        }


def _validate_txid(txid: str) -> str:
    """Normalize and validate a transaction ID."""
    txid = txid.strip().lower()
    if len(txid) != 64 or not all(c in "0123456789abcdef" for c in txid):
        raise ValueError(f"Invalid txid format: {txid}")
    return txid


def fetch_transaction(txid: str, network: str = "mainnet") -> dict[str, Any]:
    """Fetch full transaction data from the Mempool.space API."""
    txid = _validate_txid(txid)
    try:
        return as_object(get_json(f"/tx/{txid}", network), "/tx")
    except NotFoundError as e:
        raise TransactionNotFoundError(f"Transaction not found: {txid}") from e


def _is_hex(s: str) -> bool:
    """Strict hex check: even length, ASCII hex digits only."""
    return len(s) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in s)


def _decode_hex_to_text(hex_data: str) -> str | None:
    """
    Attempt to decode hex data as UTF-8 text.

    Strips null bytes and requires that at least 50% of non-null
    characters are printable, to avoid false positives from binary
    data that happens to contain some ASCII.
    """
    try:
        raw = bytes.fromhex(hex_data)
        text = raw.decode("utf-8", errors="strict")

        cleaned = text.replace("\x00", "")
        if not cleaned:
            return None

        printable_count = sum(1 for c in cleaned if c.isprintable())
        if printable_count / len(cleaned) < 0.5:
            return None

        return cleaned
    except (ValueError, UnicodeDecodeError):
        return None


def _parse_scriptpubkey_asm(asm: str) -> str | None:
    """
    Extract the data payload from an OP_RETURN scriptPubKey ASM string.

    Mempool.space returns ASM like "OP_RETURN OP_PUSHBYTES_N <hex>"
    or just "OP_RETURN <hex>".
    """
    parts = asm.split()
    if not parts or parts[0] != "OP_RETURN":
        return None

    hex_parts = []
    for part in parts[1:]:
        if part.startswith("OP_"):
            continue
        try:
            bytes.fromhex(part)
            hex_parts.append(part)
        except ValueError:
            continue

    return "".join(hex_parts) if hex_parts else None


def _extract_pushdata(script_after_opreturn: str) -> str | None:
    """
    Extract pushed data from script bytes following OP_RETURN.

    Handles OP_0 (an empty push), OP_PUSHBYTES_N (0x01-0x4b), OP_PUSHDATA1
    (0x4c), OP_PUSHDATA2 (0x4d) and OP_PUSHDATA4 (0x4e), and skips the
    small-number opcodes OP_1NEGATE and OP_1–OP_16 (0x4f, 0x51–0x60, e.g. the
    OP_13 that marks a Runestone), which push no data bytes.

    A non-standard script never looks empty: a push that runs past the end
    keeps the bytes that are there, and when nothing could be read as a push
    (an unknown opcode, a truncated length), the unparsed bytes are returned
    as they are. Returns None only for input that is not hex.
    """
    if not script_after_opreturn or not _is_hex(script_after_opreturn):
        return None

    data_parts = []
    pos = 0
    script = script_after_opreturn

    while pos < len(script):
        op_start = pos
        length_byte = int(script[pos : pos + 2], 16)
        pos += 2

        if length_byte == 0x00 or length_byte == 0x4F or 0x51 <= length_byte <= 0x60:
            continue  # OP_0 / OP_1NEGATE / OP_1..OP_16: no data bytes
        width = {0x4C: 1, 0x4D: 2, 0x4E: 4}.get(length_byte, 0)  # OP_PUSHDATA1/2/4 length field
        if not (0x01 <= length_byte <= 0x4B or width):
            pos = op_start  # an opcode that pushes nothing we can read
            break
        if pos + 2 * width > len(script):
            pos = op_start  # the length field itself is cut off
            break
        if width:
            data_len = int.from_bytes(bytes.fromhex(script[pos : pos + 2 * width]), "little")
            pos += 2 * width
        else:
            data_len = length_byte

        end = min(pos + data_len * 2, len(script))  # a push past the end keeps what is there
        data_parts.append(script[pos:end])
        pos = end

    if not "".join(data_parts) and pos < len(script):
        return script[pos:]  # nothing readable as pushes: the raw bytes, not an empty payload
    return "".join(data_parts) if data_parts else None


def decode_op_return(txid: str, network: str = "mainnet") -> list[OPReturnData]:
    """
    Fetch a transaction and decode all its OP_RETURN outputs.

    Returns a list of OPReturnData, one per OP_RETURN output — including an
    OP_RETURN that carries no data (raw_hex "", size 0), such as a bare
    OP_RETURN or a Runestone marker with nothing after it.
    """
    tx_data = fetch_transaction(txid, network)
    results = []

    for i, vout in enumerate(field_objects(tx_data, "vout", "/tx")):
        if field_str(vout, "scriptpubkey_type", "/tx") != "op_return":
            continue

        asm = field_str(vout, "scriptpubkey_asm", "/tx")
        hex_data = _parse_scriptpubkey_asm(asm)

        if not hex_data:
            raw_script = vout.get("scriptpubkey", "")
            if raw_script == "" and asm.strip() == "OP_RETURN":
                hex_data = ""  # a bare OP_RETURN, and the API left out the raw script
            elif not isinstance(raw_script, str) or not _is_hex(raw_script) \
                    or not raw_script.lower().startswith(OP_RETURN_HEX):
                raise MempoolAPIError(f"Unexpected response from /tx: output {i} has a malformed scriptpubkey")
            else:
                hex_data = _extract_pushdata(raw_script[2:].lower()) or ""

        raw_bytes = bytes.fromhex(hex_data)
        results.append(
            OPReturnData(
                txid=txid,
                vout_index=i,
                raw_hex=hex_data,
                decoded_text=_decode_hex_to_text(hex_data),
                raw_bytes=raw_bytes,
                size=len(raw_bytes),
            )
        )

    return results
