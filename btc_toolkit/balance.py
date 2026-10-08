"""
Address balance checker.

Queries the Mempool.space API for an address and computes its
confirmed and unconfirmed (mempool) balances.

Balance is derived as funded_txo_sum - spent_txo_sum, following the
Esplora/Mempool.space API model. All amounts are in satoshis, with
BTC conversion provided for display.
"""

from dataclasses import dataclass

from typing import Any
from .api import get_json, as_object, field_int, field_object, field_str, NotFoundError

SATS_PER_BTC = 100_000_000


class AddressNotFoundError(NotFoundError):
    """Raised when an address has no data or is invalid upstream."""


@dataclass
class AddressBalance:
    """Confirmed and unconfirmed balance for a Bitcoin address."""

    address: str
    confirmed_sats: int
    unconfirmed_sats: int
    confirmed_tx_count: int
    mempool_tx_count: int
    funded_sats: int
    spent_sats: int

    @property
    def total_sats(self) -> int:
        """Confirmed + unconfirmed balance."""
        return self.confirmed_sats + self.unconfirmed_sats

    @staticmethod
    def sats_to_btc(sats: int) -> str:
        """Format a satoshi amount as a BTC string with 8 decimals."""
        # Use integer arithmetic to avoid float precision issues
        sign = "-" if sats < 0 else ""
        sats = abs(sats)
        whole = sats // SATS_PER_BTC
        frac = sats % SATS_PER_BTC
        return f"{sign}{whole}.{frac:08d}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "confirmed": {
                "sats": self.confirmed_sats,
                "btc": self.sats_to_btc(self.confirmed_sats),
            },
            "unconfirmed": {
                "sats": self.unconfirmed_sats,
                "btc": self.sats_to_btc(self.unconfirmed_sats),
            },
            "total": {
                "sats": self.total_sats,
                "btc": self.sats_to_btc(self.total_sats),
            },
            "confirmed_tx_count": self.confirmed_tx_count,
            "mempool_tx_count": self.mempool_tx_count,
            "funded_sats": self.funded_sats,
            "spent_sats": self.spent_sats,
        }


def _validate_address(address: str) -> str:
    """
    Basic sanity check on a Bitcoin address.

    This is a lightweight format guard, not full validation — the
    Mempool.space API is the source of truth and will reject malformed
    addresses. We only catch obviously bad input early.
    """
    address = address.strip()
    if not address:
        raise ValueError("Address cannot be empty")

    # Bitcoin addresses are alphanumeric and within a reasonable length range.
    # Bech32 (bc1...) can be up to 90 chars; legacy is ~26-35.
    if len(address) < 14 or len(address) > 100:
        raise ValueError(f"Invalid address length: {address}")

    if not all(c.isalnum() for c in address):
        raise ValueError(f"Invalid characters in address: {address}")

    return address


def get_balance(address: str, network: str = "mainnet") -> AddressBalance:
    """
    Fetch and compute the balance for a Bitcoin address.

    Args:
        address: The Bitcoin address (any type: P2PKH, P2SH, Bech32, Taproot).
        network: 'mainnet', 'testnet' or 'signet'.

    Returns:
        An AddressBalance with confirmed and unconfirmed amounts.

    Raises:
        ValueError: If the address format is obviously invalid.
        AddressNotFoundError: If the address is not found upstream.
        MempoolAPIError: On other API errors.
    """
    address = _validate_address(address)

    try:
        data = as_object(get_json(f"/address/{address}", network), "/address")
    except NotFoundError as e:
        raise AddressNotFoundError(f"Address not found: {address}") from e

    path = "/address"
    chain = field_object(data, "chain_stats", path)
    mempool = field_object(data, "mempool_stats", path)
    funded = field_int(chain, "funded_txo_sum", path)
    spent = field_int(chain, "spent_txo_sum", path)
    unconfirmed = field_int(mempool, "funded_txo_sum", path) - field_int(mempool, "spent_txo_sum", path)

    return AddressBalance(
        address=field_str(data, "address", path, default=address),
        confirmed_sats=funded - spent,
        unconfirmed_sats=unconfirmed,
        confirmed_tx_count=field_int(chain, "tx_count", path),
        mempool_tx_count=field_int(mempool, "tx_count", path),
        funded_sats=funded,
        spent_sats=spent,
    )
