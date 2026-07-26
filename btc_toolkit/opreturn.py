"""
OP_RETURN decoder.

Fetches a transaction from the Mempool.space API and extracts
human-readable messages from its OP_RETURN outputs.
"""

from dataclasses import dataclass

from .api import get_json, NotFoundError, MempoolAPIError  # noqa: F401

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

    def to_dict(self) -> dict:
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


def fetch_transaction(txid: str, network: str = "mainnet") -> dict:
    """Fetch full transaction data from the Mempool.space API."""
    txid = _validate_txid(txid)
    try:
        return get_json(f"/tx/{txid}", network)
    except NotFoundError as e:
        raise TransactionNotFoundError(f"Transaction not found: {txid}") from e


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

    Handles OP_PUSHBYTES_N (0x01-0x4b), OP_PUSHDATA1 (0x4c),
    OP_PUSHDATA2 (0x4d).
    """
    if len(script_after_opreturn) < 2:
        return None

    data_parts = []
    pos = 0
    script = script_after_opreturn

    while pos < len(script):
        if pos + 2 > len(script):
            break

        length_byte = int(script[pos : pos + 2], 16)
        pos += 2

        if 0x01 <= length_byte <= 0x4B:
            data_len = length_byte
        elif length_byte == 0x4C:
            if pos + 2 > len(script):
                break
            data_len = int(script[pos : pos + 2], 16)
            pos += 2
        elif length_byte == 0x4D:
            if pos + 4 > len(script):
                break
            data_len = int(script[pos + 2 : pos + 4] + script[pos : pos + 2], 16)
            pos += 4
        else:
            break

        end = pos + data_len * 2
        if end > len(script):
            break

        data_parts.append(script[pos:end])
        pos = end

    return "".join(data_parts) if data_parts else None


def decode_op_return(txid: str, network: str = "mainnet") -> list[OPReturnData]:
    """
    Fetch a transaction and decode all its OP_RETURN outputs.

    Returns a list of OPReturnData, one per OP_RETURN output found.
    """
    tx_data = fetch_transaction(txid, network)
    results = []

    for i, vout in enumerate(tx_data.get("vout", [])):
        if vout.get("scriptpubkey_type", "") != "op_return":
            continue

        asm = vout.get("scriptpubkey_asm", "")
        hex_data = _parse_scriptpubkey_asm(asm)

        if not hex_data:
            raw_script = vout.get("scriptpubkey", "")
            if raw_script.startswith(OP_RETURN_HEX):
                hex_data = _extract_pushdata(raw_script[2:])

        if hex_data:
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
