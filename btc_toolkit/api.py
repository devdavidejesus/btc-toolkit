"""
Shared Mempool.space API client.

Centralizes all HTTP communication with the Mempool.space REST API.
Every subcommand (opreturn, balance, fees, block, utxo) uses this module
instead of duplicating connection logic.

No external dependencies — standard library only.
"""

import json
import urllib.request
import urllib.error

from . import __version__

# Mempool.space API base URLs
MEMPOOL_API = "https://mempool.space/api"
MEMPOOL_TESTNET_API = "https://mempool.space/testnet/api"

SUPPORTED_NETWORKS = ("mainnet", "testnet")

_USER_AGENT = f"btc-toolkit/{__version__}"
_TIMEOUT = 15


class MempoolAPIError(Exception):
    """Raised when the Mempool.space API returns an error."""


class NotFoundError(MempoolAPIError):
    """Raised when a requested resource (tx, address, block) is not found."""


def get_api_base(network: str) -> str:
    """Return the correct API base URL for the given network."""
    if network not in SUPPORTED_NETWORKS:
        raise ValueError(
            f"Unsupported network: {network}. Use one of: {SUPPORTED_NETWORKS}"
        )
    if network == "testnet":
        return MEMPOOL_TESTNET_API
    return MEMPOOL_API


def get_json(path: str, network: str = "mainnet") -> dict | list:
    """
    GET a Mempool.space API endpoint and return parsed JSON.

    Args:
        path: API path beginning with '/', e.g. '/tx/<txid>' or '/address/<addr>'.
        network: 'mainnet' or 'testnet'.

    Returns:
        Parsed JSON (dict or list).

    Raises:
        NotFoundError: On HTTP 404.
        MempoolAPIError: On other HTTP or connection errors.
    """
    api_base = get_api_base(network)
    url = f"{api_base}{path}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise NotFoundError(f"Not found: {path}") from e
        raise MempoolAPIError(f"API error {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise MempoolAPIError(f"Connection error: {e.reason}") from e


def get_text(path: str, network: str = "mainnet") -> str:
    """
    GET a Mempool.space API endpoint that returns plain text (not JSON).

    Used for endpoints like /blocks/tip/height that return a bare number.
    """
    api_base = get_api_base(network)
    url = f"{api_base}{path}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.read().decode("utf-8").strip()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise NotFoundError(f"Not found: {path}") from e
        raise MempoolAPIError(f"API error {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise MempoolAPIError(f"Connection error: {e.reason}") from e
