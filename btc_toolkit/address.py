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

from typing import Any
from .balance import get_balance, AddressBalance  # noqa: F401


def detect_address_type(address: str, network: str = "mainnet") -> str:
    """
    Detect the address type from its prefix and length (offline).

    Mainnet uses 1 / 3 / bc1; testnet and signet share m, n / 2 / tb1. With a
    custom API (network 'custom') the chain is unknown, so the prefixes of
    every network are accepted, including regtest's bcrt1.

    Returns one of: P2PKH, P2SH, P2WPKH, P2WSH, P2TR,
    or 'unknown' when the shape doesn't match any known format.
    """
    a = address.strip()
    lower = a.lower()

    p2pkh: tuple[str, ...]
    p2sh: tuple[str, ...]
    hrps: tuple[str, ...]
    if network == "mainnet":
        p2pkh, p2sh, hrps = ("1",), ("3",), ("bc1",)
    elif network in ("testnet", "signet"):
        p2pkh, p2sh, hrps = ("m", "n"), ("2",), ("tb1",)
    else:
        p2pkh, p2sh, hrps = ("1", "m", "n"), ("3", "2"), ("bcrt1", "bc1", "tb1")

    if a.startswith(p2pkh):
        return "P2PKH"
    if a.startswith(p2sh):
        return "P2SH"

    for hrp in hrps:
        if not lower.startswith(hrp):
            continue
        # After "<hrp>": witness version, program and a 6-char checksum.
        # A 20-byte program takes 39 chars after the hrp, a 32-byte one 59.
        if lower.startswith(hrp + "q"):  # SegWit v0 (BIP 173)
            if len(a) == len(hrp) + 39:
                return "P2WPKH"
            if len(a) == len(hrp) + 59:
                return "P2WSH"
        elif lower.startswith(hrp + "p") and len(a) == len(hrp) + 59:  # Taproot: v1, 32-byte key (BIP 341/350)
            return "P2TR"
        return "unknown"

    return "unknown"


@dataclass
class AddressOverview:
    """Aggregated address information."""

    balance: AddressBalance
    address_type: str

    def to_dict(self) -> dict[str, Any]:
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
