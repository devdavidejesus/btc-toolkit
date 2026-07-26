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
from datetime import datetime, timezone

from .api import get_json, get_text, NotFoundError


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
    previousblockhash: str
    nonce: int
    bits: int
    difficulty: float
    mediantime: int

    @property
    def timestamp_utc(self) -> str:
        """Block timestamp as an ISO-8601 UTC string."""
        return datetime.fromtimestamp(self.timestamp, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

    @property
    def size_mb(self) -> float:
        """Block size in MB (1 MB = 1_000_000 bytes)."""
        return self.size / 1_000_000

    def to_dict(self) -> dict:
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
    return ref.strip().isdigit()


def get_tip_height(network: str = "mainnet") -> int:
    """Return the current chain tip height."""
    return int(get_text("/blocks/tip/height", network))


def get_block(ref: str, network: str = "mainnet") -> BlockInfo:
    """
    Fetch block metadata by height, hash, or 'latest'.

    Args:
        ref: Block height (decimal), block hash (64 hex chars),
             or the literal string 'latest' for the chain tip.
        network: 'mainnet' or 'testnet'.

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
            block_hash = get_text(f"/block-height/{height}", network)
        elif _is_height(ref):
            block_hash = get_text(f"/block-height/{ref}", network)
        elif _is_block_hash(ref):
            block_hash = ref.lower()
        else:
            raise ValueError(
                f"Invalid block reference: {ref!r}. "
                "Use a height, a 64-char hash, or 'latest'."
            )

        data = get_json(f"/block/{block_hash}", network)
    except NotFoundError as e:
        raise BlockNotFoundError(f"Block not found: {ref}") from e

    return BlockInfo(
        hash=data.get("id", block_hash),
        height=data.get("height", 0),
        timestamp=data.get("timestamp", 0),
        tx_count=data.get("tx_count", 0),
        size=data.get("size", 0),
        weight=data.get("weight", 0),
        version=data.get("version", 0),
        merkle_root=data.get("merkle_root", ""),
        previousblockhash=data.get("previousblockhash", ""),
        nonce=data.get("nonce", 0),
        bits=data.get("bits", 0),
        difficulty=data.get("difficulty", 0),
        mediantime=data.get("mediantime", 0),
    )
