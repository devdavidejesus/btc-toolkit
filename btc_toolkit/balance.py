"""
Address balance checker.

Queries the Mempool.space API for an address and computes its
confirmed and unconfirmed (mempool) balances.

Balance is derived as funded_txo_sum - spent_txo_sum, following the
Esplora/Mempool.space API model. All amounts are in satoshis, with
BTC conversion provided for display.
"""

from dataclasses import dataclass

from .api import get_json, NotFoundError

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

    def to_dict(self) -> dict:
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
        network: 'mainnet' or 'testnet'.

    Returns:
        An AddressBalance with confirmed and unconfirmed amounts.

    Raises:
        ValueError: If the address format is obviously invalid.
        AddressNotFoundError: If the address is not found upstream.
        MempoolAPIError: On other API errors.
    """
    address = _validate_address(address)

    try:
        data = get_json(f"/address/{address}", network)
    except NotFoundError as e:
        raise AddressNotFoundError(f"Address not found: {address}") from e

    chain = data.get("chain_stats", {})
    mempool = data.get("mempool_stats", {})

    confirmed = chain.get("funded_txo_sum", 0) - chain.get("spent_txo_sum", 0)
    unconfirmed = mempool.get("funded_txo_sum", 0) - mempool.get("spent_txo_sum", 0)

    return AddressBalance(
        address=data.get("address", address),
        confirmed_sats=confirmed,
        unconfirmed_sats=unconfirmed,
        confirmed_tx_count=chain.get("tx_count", 0),
        mempool_tx_count=mempool.get("tx_count", 0),
        funded_sats=chain.get("funded_txo_sum", 0),
        spent_sats=chain.get("spent_txo_sum", 0),
    )
