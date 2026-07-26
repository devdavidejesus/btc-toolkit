"""
Transaction inspector.

Fetches full transaction details from the Mempool.space API:
status, fees, size/weight, inputs/outputs, RBF signaling, coinbase.

Endpoint:
    GET /api/tx/:txid

Values are in satoshis. vsize is derived as ceil(weight / 4).
"""

from dataclasses import dataclass
from datetime import datetime, timezone

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
        return datetime.fromtimestamp(self.block_time, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

    def to_dict(self) -> dict:
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
        network: 'mainnet' or 'testnet'.

    Returns:
        A TxInfo with status, fees, sizes, and I/O aggregates.

    Raises:
        ValueError: If the txid format is invalid.
        TransactionNotFoundError: If the transaction does not exist.
        MempoolAPIError: On other API errors.
    """
    data = fetch_transaction(txid, network)

    vin = data.get("vin", [])
    vout = data.get("vout", [])
    status = data.get("status", {})

    is_coinbase = bool(vin and vin[0].get("is_coinbase", False))

    total_input = 0
    is_rbf = False
    for i in vin:
        prevout = i.get("prevout") or {}
        total_input += prevout.get("value", 0)
        if i.get("sequence", 0xFFFFFFFF) < _RBF_SEQUENCE_THRESHOLD:
            is_rbf = True

    total_output = sum(o.get("value", 0) for o in vout)

    return TxInfo(
        txid=data.get("txid", txid),
        version=data.get("version", 0),
        locktime=data.get("locktime", 0),
        size=data.get("size", 0),
        weight=data.get("weight", 0),
        fee=data.get("fee", 0),
        confirmed=status.get("confirmed", False),
        block_height=status.get("block_height"),
        block_time=status.get("block_time"),
        input_count=len(vin),
        output_count=len(vout),
        total_input=total_input,
        total_output=total_output,
        is_coinbase=is_coinbase,
        is_rbf=is_rbf,
    )
