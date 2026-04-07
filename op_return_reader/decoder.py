"""
Core decoder logic for OP_RETURN outputs.

Fetches raw transaction data from the Mempool.space API
and extracts human-readable messages from OP_RETURN outputs.

No Bitcoin Core dependency required.
"""

import json
import urllib.request
import urllib.error
from dataclasses import dataclass


# OP_RETURN opcode
OP_RETURN_HEX = "6a"

# Mempool.space API base URLs
MEMPOOL_API = "https://mempool.space/api"
MEMPOOL_TESTNET_API = "https://mempool.space/testnet/api"

SUPPORTED_NETWORKS = ("mainnet", "testnet")


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


class MempoolAPIError(Exception):
    """Raised when the Mempool.space API returns an error."""


class TransactionNotFoundError(MempoolAPIError):
    """Raised when a transaction ID is not found."""


def _get_api_base(network: str) -> str:
    """Return the correct API base URL for the given network."""
    if network == "testnet":
        return MEMPOOL_TESTNET_API
    return MEMPOOL_API


def fetch_transaction(txid: str, network: str = "mainnet") -> dict:
    """
    Fetch full transaction data from Mempool.space API.

    Args:
        txid: The transaction ID (hex string, 64 chars).
        network: 'mainnet' or 'testnet'.

    Returns:
        Parsed JSON response as a dictionary.

    Raises:
        TransactionNotFoundError: If the txid doesn't exist.
        MempoolAPIError: For other API errors.
    """
    txid = txid.strip().lower()

    if len(txid) != 64 or not all(c in "0123456789abcdef" for c in txid):
        raise ValueError(f"Invalid txid format: {txid}")

    if network not in SUPPORTED_NETWORKS:
        raise ValueError(f"Unsupported network: {network}. Use: {SUPPORTED_NETWORKS}")

    api_base = _get_api_base(network)
    url = f"{api_base}/tx/{txid}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "btc-toolkit/0.1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise TransactionNotFoundError(f"Transaction not found: {txid}") from e
        raise MempoolAPIError(f"API error {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise MempoolAPIError(f"Connection error: {e.reason}") from e


def _decode_hex_to_text(hex_data: str) -> str | None:
    """
    Attempt to decode hex data as UTF-8 text.

    Returns None if the data is not valid UTF-8 text.
    Strips null bytes and requires that at least 50% of
    non-null characters are printable to avoid false positives
    from binary data that happens to contain some ASCII.
    """
    try:
        raw = bytes.fromhex(hex_data)
        text = raw.decode("utf-8", errors="strict")

        # Strip null bytes — common padding in OP_RETURN data
        cleaned = text.replace("\x00", "")

        if not cleaned:
            return None

        # Require at least 50% printable characters in cleaned text
        printable_count = sum(1 for c in cleaned if c.isprintable())
        if printable_count / len(cleaned) < 0.5:
            return None

        return cleaned
    except (ValueError, UnicodeDecodeError):
        return None


def _parse_scriptpubkey_asm(asm: str) -> str | None:
    """
    Extract the data payload from an OP_RETURN scriptPubKey ASM string.

    Mempool.space returns ASM like: "OP_RETURN OP_PUSHBYTES_N <hex>"
    or just: "OP_RETURN <hex>"
    """
    parts = asm.split()
    if not parts or parts[0] != "OP_RETURN":
        return None

    # Collect all hex data parts after OP_RETURN (skip OP_PUSH* opcodes)
    hex_parts = []
    for part in parts[1:]:
        if part.startswith("OP_"):
            continue
        # Validate it looks like hex
        try:
            bytes.fromhex(part)
            hex_parts.append(part)
        except ValueError:
            continue

    return "".join(hex_parts) if hex_parts else None


def decode_op_return(txid: str, network: str = "mainnet") -> list[OPReturnData]:
    """
    Fetch a transaction and decode all OP_RETURN outputs.

    Args:
        txid: The transaction ID.
        network: 'mainnet' or 'testnet'.

    Returns:
        List of OPReturnData objects for each OP_RETURN output found.
    """
    tx_data = fetch_transaction(txid, network)
    results = []

    for i, vout in enumerate(tx_data.get("vout", [])):
        scriptpubkey_type = vout.get("scriptpubkey_type", "")
        if scriptpubkey_type != "op_return":
            continue

        # Try ASM first (cleaner extraction)
        asm = vout.get("scriptpubkey_asm", "")
        hex_data = _parse_scriptpubkey_asm(asm)

        # Fallback: parse raw scriptpubkey hex
        if not hex_data:
            raw_script = vout.get("scriptpubkey", "")
            if raw_script.startswith(OP_RETURN_HEX):
                # Skip the 6a opcode and any push data length bytes
                hex_data = _extract_pushdata(raw_script[2:])

        if hex_data:
            raw_bytes = bytes.fromhex(hex_data)
            decoded_text = _decode_hex_to_text(hex_data)

            results.append(
                OPReturnData(
                    txid=txid,
                    vout_index=i,
                    raw_hex=hex_data,
                    decoded_text=decoded_text,
                    raw_bytes=raw_bytes,
                    size=len(raw_bytes),
                )
            )

    return results


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
            # Direct push: length_byte is the number of bytes to push
            data_len = length_byte
        elif length_byte == 0x4C:
            # OP_PUSHDATA1: next byte is length
            if pos + 2 > len(script):
                break
            data_len = int(script[pos : pos + 2], 16)
            pos += 2
        elif length_byte == 0x4D:
            # OP_PUSHDATA2: next 2 bytes (little-endian) are length
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
