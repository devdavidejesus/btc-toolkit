"""
UTXO set inspector.

Lists the unspent transaction outputs (UTXOs) of a Bitcoin address
via the Mempool.space API.

Endpoint:
    GET /api/address/:address/utxo
        -> [ { txid, vout, value, status: { confirmed,
               block_height?, block_hash?, block_time? } }, ... ]

Values are in satoshis.
"""

from dataclasses import dataclass

from .api import get_json, NotFoundError
from .balance import _validate_address, AddressNotFoundError, SATS_PER_BTC


@dataclass
class Utxo:
    """A single unspent transaction output."""

    txid: str
    vout: int
    value: int
    confirmed: bool
    block_height: int | None

    def to_dict(self) -> dict:
        return {
            "txid": self.txid,
            "vout": self.vout,
            "value_sats": self.value,
            "confirmed": self.confirmed,
            "block_height": self.block_height,
        }


@dataclass
class UtxoSet:
    """The full UTXO set of an address, with aggregates."""

    address: str
    utxos: list[Utxo]

    @property
    def total_sats(self) -> int:
        return sum(u.value for u in self.utxos)

    @property
    def confirmed_count(self) -> int:
        return sum(1 for u in self.utxos if u.confirmed)

    @property
    def unconfirmed_count(self) -> int:
        return sum(1 for u in self.utxos if not u.confirmed)

    @staticmethod
    def sats_to_btc(sats: int) -> str:
        """Format satoshis as a BTC string (integer arithmetic)."""
        sign = "-" if sats < 0 else ""
        sats = abs(sats)
        return f"{sign}{sats // SATS_PER_BTC}.{sats % SATS_PER_BTC:08d}"

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "utxo_count": len(self.utxos),
            "confirmed_count": self.confirmed_count,
            "unconfirmed_count": self.unconfirmed_count,
            "total": {
                "sats": self.total_sats,
                "btc": self.sats_to_btc(self.total_sats),
            },
            "utxos": [u.to_dict() for u in self.utxos],
        }


def get_utxos(
    address: str,
    network: str = "mainnet",
    confirmed_only: bool = False,
) -> UtxoSet:
    """
    Fetch the UTXO set for a Bitcoin address.

    Args:
        address: The Bitcoin address (any type).
        network: 'mainnet' or 'testnet'.
        confirmed_only: If True, drop mempool (unconfirmed) UTXOs.

    Returns:
        A UtxoSet sorted by value, largest first.

    Raises:
        ValueError: If the address format is obviously invalid.
        AddressNotFoundError: If the address is not found upstream.
        MempoolAPIError: On other API errors.
    """
    address = _validate_address(address)

    try:
        data = get_json(f"/address/{address}/utxo", network)
    except NotFoundError as e:
        raise AddressNotFoundError(f"Address not found: {address}") from e

    utxos = []
    for item in data:
        status = item.get("status", {})
        confirmed = status.get("confirmed", False)
        if confirmed_only and not confirmed:
            continue
        utxos.append(
            Utxo(
                txid=item.get("txid", ""),
                vout=item.get("vout", 0),
                value=item.get("value", 0),
                confirmed=confirmed,
                block_height=status.get("block_height"),
            )
        )

    utxos.sort(key=lambda u: u.value, reverse=True)
    return UtxoSet(address=address, utxos=utxos)
