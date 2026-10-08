"""
Block info explorer.

Queries the Mempool.space API for block metadata by height, hash,
or the chain tip.

Endpoints:
    GET /api/block/:hash          -> block details (JSON)
    GET /api/block-height/:height -> block hash (plain text)
    GET /api/blocks/tip/height    -> current tip height (plain text)
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from typing import Any
from .api import get_json, get_text, as_object, MempoolAPIError, NotFoundError
from .api import field_int, field_number, field_opt_str, field_str, field_timestamp


class BlockNotFoundError(NotFoundError):
    """Raised when a block height or hash is not found."""


@dataclass
class BlockInfo:
    """Metadata for a single Bitcoin block."""

    hash: str
    height: int
    timestamp: int
    tx_count: int
    size: int
    weight: int
    version: int
    merkle_root: str
    previousblockhash: str | None  # None for the genesis block
    nonce: int
    bits: int
    difficulty: float
    mediantime: int

    @property
    def timestamp_utc(self) -> str:
        """Block timestamp in UTC, formatted "YYYY-MM-DD HH:MM:SS UTC"."""
        return datetime.fromtimestamp(self.timestamp, tz=UTC).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

    @property
    def size_mb(self) -> float:
        """Block size in MB (1 MB = 1_000_000 bytes)."""
        return self.size / 1_000_000

    def to_dict(self) -> dict[str, Any]:
        return {
            "hash": self.hash,
            "height": self.height,
            "timestamp": self.timestamp,
            "timestamp_utc": self.timestamp_utc,
            "tx_count": self.tx_count,
            "size_bytes": self.size,
            "size_mb": round(self.size_mb, 2),
            "weight": self.weight,
            "version": self.version,
            "merkle_root": self.merkle_root,
            "previousblockhash": self.previousblockhash,
            "nonce": self.nonce,
            "bits": self.bits,
            "difficulty": self.difficulty,
            "mediantime": self.mediantime,
        }


def _is_block_hash(ref: str) -> bool:
    """A block hash is 64 hex chars; a height is a decimal number."""
    ref = ref.strip().lower()
    return len(ref) == 64 and all(c in "0123456789abcdef" for c in ref)


def _is_height(ref: str) -> bool:
    ref = ref.strip()
    return ref.isascii() and ref.isdigit()


def get_tip_height(network: str = "mainnet") -> int:
    """Return the current chain tip height."""
    text = get_text("/blocks/tip/height", network)
    if not (text.isascii() and text.isdigit()):
        raise MempoolAPIError(f"Unexpected response from /blocks/tip/height: {text[:40]!r}")
    return int(text)


def _block_hash_from(text: str, path: str) -> str:
    """The /block-height endpoint answers with a bare block hash."""
    if not _is_block_hash(text):
        raise MempoolAPIError(f"Unexpected response from {path}: {text[:40]!r}")
    return text.lower()


def get_block(ref: str, network: str = "mainnet") -> BlockInfo:
    """
    Fetch block metadata by height, hash, or 'latest'.

    Args:
        ref: Block height (decimal), block hash (64 hex chars),
             or the literal string 'latest' for the chain tip.
        network: 'mainnet', 'testnet' or 'signet'.

    Returns:
        A BlockInfo with the block's metadata.

    Raises:
        ValueError: If ref is neither a height, a hash, nor 'latest'.
        BlockNotFoundError: If the block does not exist.
        MempoolAPIError: On other API errors.
    """
    ref = ref.strip()

    try:
        if ref.lower() == "latest":
            height = get_tip_height(network)
            block_hash = _block_hash_from(get_text(f"/block-height/{height}", network), "/block-height")
        elif _is_block_hash(ref):  # before the height check: a 64-digit hash is all decimal digits
            block_hash = ref.lower()
        elif _is_height(ref):
            block_hash = _block_hash_from(get_text(f"/block-height/{ref}", network), "/block-height")
        else:
            raise ValueError(
                f"Invalid block reference: {ref!r}. "
                "Use a height, a 64-char hash, or 'latest'."
            )

        data = as_object(get_json(f"/block/{block_hash}", network), "/block")
    except NotFoundError as e:
        raise BlockNotFoundError(f"Block not found: {ref}") from e

    path = "/block"
    return BlockInfo(
        hash=field_str(data, "id", path, default=block_hash),
        height=field_int(data, "height", path),
        timestamp=field_timestamp(data, "timestamp", path),
        tx_count=field_int(data, "tx_count", path),
        size=field_int(data, "size", path),
        weight=field_int(data, "weight", path),
        version=field_int(data, "version", path),
        merkle_root=field_str(data, "merkle_root", path),
        previousblockhash=field_opt_str(data, "previousblockhash", path),
        nonce=field_int(data, "nonce", path),
        bits=field_int(data, "bits", path),
        difficulty=field_number(data, "difficulty", path),
        mediantime=field_timestamp(data, "mediantime", path),
    )
