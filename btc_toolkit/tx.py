"""
Transaction inspector.

Fetches full transaction details from the Mempool.space API:
status, fees, size/weight, inputs/outputs, RBF signaling, coinbase.

Endpoint:
    GET /api/tx/:txid

Values are in satoshis. vsize is derived as ceil(weight / 4).
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from typing import Any
from .api import MempoolAPIError, field_bool, field_int, field_object, field_objects, field_opt_int, field_str
from .api import field_opt_timestamp
from .opreturn import fetch_transaction, TransactionNotFoundError  # noqa: F401

# Inputs with sequence below this value signal BIP 125 replace-by-fee
_RBF_SEQUENCE_THRESHOLD = 0xFFFFFFFE


@dataclass
class TxInfo:
    """Full metadata for a single transaction."""

    txid: str
    version: int
    locktime: int
    size: int
    weight: int
    fee: int
    confirmed: bool
    block_height: int | None
    block_time: int | None
    input_count: int
    output_count: int
    total_input: int
    total_output: int
    is_coinbase: bool
    is_rbf: bool

    @property
    def vsize(self) -> int:
        """Virtual size in vB: ceil(weight / 4)."""
        return (self.weight + 3) // 4

    @property
    def fee_rate(self) -> float:
        """Fee rate in sat/vB (0 for coinbase)."""
        if self.vsize == 0:
            return 0.0
        return self.fee / self.vsize

    @property
    def block_time_utc(self) -> str | None:
        if self.block_time is None:
            return None
        return datetime.fromtimestamp(self.block_time, tz=UTC).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "txid": self.txid,
            "status": "confirmed" if self.confirmed else "unconfirmed",
            "block_height": self.block_height,
            "block_time": self.block_time,
            "block_time_utc": self.block_time_utc,
            "version": self.version,
            "locktime": self.locktime,
            "size_bytes": self.size,
            "weight": self.weight,
            "vsize": self.vsize,
            "fee_sats": self.fee,
            "fee_rate_sat_vb": round(self.fee_rate, 2),
            "input_count": self.input_count,
            "output_count": self.output_count,
            "total_input_sats": self.total_input,
            "total_output_sats": self.total_output,
            "is_coinbase": self.is_coinbase,
            "is_rbf": self.is_rbf,
        }


def get_tx(txid: str, network: str = "mainnet") -> TxInfo:
    """
    Fetch full transaction details.

    Args:
        txid: The transaction ID (64-char hex).
        network: 'mainnet', 'testnet' or 'signet'.

    Returns:
        A TxInfo with status, fees, sizes, and I/O aggregates.

    Raises:
        ValueError: If the txid format is invalid.
        TransactionNotFoundError: If the transaction does not exist.
        MempoolAPIError: On other API errors.
    """
    data = fetch_transaction(txid, network)
    path = "/tx"

    vin = field_objects(data, "vin", path)
    vout = field_objects(data, "vout", path)
    status = field_object(data, "status", path)

    is_coinbase = bool(vin) and field_bool(vin[0], "is_coinbase", path)

    total_input = 0
    is_rbf = False
    for i in vin:
        prevout = i.get("prevout") or {}  # null for a coinbase input
        if not isinstance(prevout, dict):
            raise MempoolAPIError(f"Unexpected response from {path}: 'prevout' is not an object")
        total_input += field_int(prevout, "value", path)
        if field_int(i, "sequence", path, default=0xFFFFFFFF) < _RBF_SEQUENCE_THRESHOLD:
            is_rbf = True

    total_output = sum(field_int(o, "value", path) for o in vout)

    confirmed = field_bool(status, "confirmed", path)
    block_height = field_opt_int(status, "block_height", path)
    if confirmed and block_height is None:
        raise MempoolAPIError(f"Unexpected response from {path}: confirmed without a block height")

    return TxInfo(
        txid=field_str(data, "txid", path, default=txid),
        version=field_int(data, "version", path),
        locktime=field_int(data, "locktime", path),
        size=field_int(data, "size", path),
        weight=field_int(data, "weight", path),
        fee=field_int(data, "fee", path),
        confirmed=confirmed,
        block_height=block_height,
        block_time=field_opt_timestamp(status, "block_time", path),
        input_count=len(vin),
        output_count=len(vout),
        total_input=total_input,
        total_output=total_output,
        is_coinbase=is_coinbase,
        is_rbf=is_rbf,
    )
