"""
Address overview.

Aggregated view of a Bitcoin address in a single API call:
balance (confirmed + unconfirmed), transaction counts, lifetime
received/spent totals — plus offline address-type detection.

Endpoint:
    GET /api/address/:address

Type detection is done locally from the address prefix and length,
following BIP 13 (P2SH), BIP 173 (bech32) and BIP 350 (bech32m).
"""

from dataclasses import dataclass

from .balance import get_balance, AddressBalance  # noqa: F401


def detect_address_type(address: str, network: str = "mainnet") -> str:
    """
    Detect the address type from its prefix and length (offline).

    Returns one of: P2PKH, P2SH, P2WPKH, P2WSH, P2TR,
    or 'unknown' when the shape doesn't match any known format.
    """
    a = address.strip()
    lower = a.lower()

    if network == "testnet":
        if a.startswith(("m", "n")):
            return "P2PKH"
        if a.startswith("2"):
            return "P2SH"
        hrp = "tb1"
    else:
        if a.startswith("1"):
            return "P2PKH"
        if a.startswith("3"):
            return "P2SH"
        hrp = "bc1"

    if lower.startswith(hrp + "q"):
        # SegWit v0: length distinguishes key-hash from script-hash
        if len(a) == len(hrp) + 39:  # 42 chars on mainnet
            return "P2WPKH"
        if len(a) == len(hrp) + 59:  # 62 chars on mainnet
            return "P2WSH"
        return "unknown"
    if lower.startswith(hrp + "p"):
        return "P2TR"

    return "unknown"


@dataclass
class AddressOverview:
    """Aggregated address information."""

    balance: AddressBalance
    address_type: str

    def to_dict(self) -> dict:
        return {
            "address_type": self.address_type,
            **self.balance.to_dict(),
        }


def get_address_overview(address: str, network: str = "mainnet") -> AddressOverview:
    """
    Fetch the aggregated overview of a Bitcoin address.

    Single API call — reuses the balance endpoint (chain_stats +
    mempool_stats) and adds offline type detection.

    Raises:
        ValueError: If the address format is obviously invalid.
        AddressNotFoundError: If the address is not found upstream.
        MempoolAPIError: On other API errors.
    """
    balance = get_balance(address, network)
    return AddressOverview(
        balance=balance,
        address_type=detect_address_type(balance.address, network),
    )
