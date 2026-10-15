"""
Transaction inspector.

Fetches full transaction details from the Mempool.space API:
status, fees, size/weight, inputs/outputs, RBF signaling, coinbase.

Endpoints:
    GET /api/tx/:txid              -> the transaction
    GET /api/tx/:txid/outspends    -> whether each output is spent, and by what (--outputs)

Values are in satoshis. vsize is derived as ceil(weight / 4).
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from typing import Any
from .api import MempoolAPIError, field_bool, field_int, field_object, field_objects, field_opt_int, field_str
from .api import as_array, field_hash, field_opt_hash, field_opt_str, field_opt_timestamp, get_json
from .encoding import parse_address, script_address, script_type
from .opreturn import fetch_transaction, TransactionNotFoundError  # noqa: F401

# Inputs with sequence below this value signal BIP 125 replace-by-fee
_RBF_SEQUENCE_THRESHOLD = 0xFFFFFFFE


@dataclass
class TxInput:
    """One input: the output it spends, and that output's value and address."""

    index: int
    prev_txid: str
    prev_vout: int
    value: int
    address: str | None
    script_type: str
    sequence: int
    is_coinbase: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "prev_txid": self.prev_txid,
            "prev_vout": self.prev_vout,
            "value_sats": self.value,
            "address": self.address,
            "script_type": self.script_type,
            "sequence": self.sequence,
            "is_coinbase": self.is_coinbase,
        }


@dataclass
class TxOutput:
    """One output, and — when known — the input that spends it."""

    index: int
    value: int
    address: str | None
    script_type: str
    spent: bool | None = None  # None: not looked up
    spending_txid: str | None = None
    spending_vin: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "value_sats": self.value,
            "address": self.address,
            "script_type": self.script_type,
            "spent": self.spent,
            "spending_txid": self.spending_txid,
            "spending_vin": self.spending_vin,
        }


def _script(obj: dict[str, Any], path: str) -> bytes:
    """The scriptPubKey bytes of an output (hex in the API)."""
    hex_script = field_str(obj, "scriptpubkey", path)
    try:
        return bytes.fromhex(hex_script)
    except ValueError:
        raise MempoolAPIError(f"Unexpected response from {path}: 'scriptpubkey' is not hex") from None


def _address(obj: dict[str, Any], script: bytes, network: str, path: str) -> str | None:
    """
    The address an output pays to, computed locally from its script on a known network.
    With a custom API the chain is unknown: the API's address is used only if it is a valid address.
    """
    if network in ("mainnet", "testnet", "signet"):
        return script_address(script, network)
    claimed = field_opt_str(obj, "scriptpubkey_address", path)
    if claimed is None:
        return None
    try:
        return parse_address(claimed, "custom").address
    except ValueError:
        return None


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
    inputs: list[TxInput] | None = None  # filled when details are requested
    outputs: list[TxOutput] | None = None

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
            **({"inputs": [i.to_dict() for i in self.inputs]} if self.inputs is not None else {}),
            **({"outputs": [o.to_dict() for o in self.outputs]} if self.outputs is not None else {}),
        }


def _inputs(vin: list[dict[str, Any]], network: str, path: str) -> list[TxInput]:
    out = []
    for n, i in enumerate(vin):
        coinbase = field_bool(i, "is_coinbase", path)
        prevout = i.get("prevout") or {}
        if not isinstance(prevout, dict):
            raise MempoolAPIError(f"Unexpected response from {path}: 'prevout' is not an object")
        script = b"" if coinbase else _script(prevout, path)
        out.append(TxInput(
            index=n,
            prev_txid=field_hash(i, "txid", path),
            prev_vout=field_int(i, "vout", path),
            value=field_int(prevout, "value", path),
            address=None if coinbase else _address(prevout, script, network, path),
            script_type="coinbase" if coinbase else script_type(script),
            sequence=field_int(i, "sequence", path, default=0xFFFFFFFF),
            is_coinbase=coinbase,
        ))
    return out


def _outputs(txid: str, vout: list[dict[str, Any]], network: str, path: str) -> list[TxOutput]:
    outs = []
    for n, o in enumerate(vout):
        script = _script(o, path)
        outs.append(TxOutput(n, field_int(o, "value", path), _address(o, script, network, path), script_type(script)))
    spends_path = "/tx/outspends"
    spends = as_array(get_json(f"/tx/{txid}/outspends", network), spends_path)
    if len(spends) != len(outs):
        raise MempoolAPIError(f"Unexpected response from {spends_path}: {len(spends)} entries for {len(outs)} outputs")
    for out, s in zip(outs, spends, strict=True):
        if not isinstance(s, dict):
            raise MempoolAPIError(f"Unexpected response from {spends_path}: an entry is not an object")
        out.spent = field_bool(s, "spent", spends_path)
        if out.spent:
            # A self-hosted Mempool without a spender index reports only "spent": true.
            out.spending_txid = field_opt_hash(s, "txid", spends_path)
            out.spending_vin = field_opt_int(s, "vin", spends_path)
    return outs


def get_tx(txid: str, network: str = "mainnet", inputs: bool = False, outputs: bool = False) -> TxInfo:
    """
    Fetch full transaction details.

    Args:
        txid: The transaction ID (64-char hex).
        network: 'mainnet', 'testnet' or 'signet'.
        inputs: Also list each input (the output it spends, its value and address).
        outputs: Also list each output and whether it is spent (one more request).

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
        # A coinbase input cannot be replaced, whatever its sequence (BIP 125 covers spends only).
        if not field_bool(i, "is_coinbase", path) \
                and field_int(i, "sequence", path, default=0xFFFFFFFF) < _RBF_SEQUENCE_THRESHOLD:
            is_rbf = True

    total_output = sum(field_int(o, "value", path) for o in vout)

    confirmed = field_bool(status, "confirmed", path)
    block_height = field_opt_int(status, "block_height", path)
    if confirmed and block_height is None:
        raise MempoolAPIError(f"Unexpected response from {path}: confirmed without a block height")

    tx_id = field_hash(data, "txid", path, default=txid.strip().lower())
    return TxInfo(
        txid=tx_id,
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
        inputs=_inputs(vin, network, path) if inputs else None,
        outputs=_outputs(tx_id, vout, network, path) if outputs else None,
    )
