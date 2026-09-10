"""
Shared Mempool.space API client.

Centralizes all HTTP communication with the Mempool.space REST API.
Every subcommand uses this module instead of duplicating connection logic.

Transient failures (HTTP 429, 5xx, network errors) are retried up to
3 attempts with exponential backoff. Definitive client errors (400, 404)
are never retried.

No external dependencies — standard library only.
"""

import json
import time
import urllib.request
import urllib.error

from . import __version__

# Mempool.space API base URLs
MEMPOOL_API = "https://mempool.space/api"
MEMPOOL_TESTNET_API = "https://mempool.space/testnet/api"
MEMPOOL_SIGNET_API = "https://mempool.space/signet/api"

SUPPORTED_NETWORKS = ("mainnet", "testnet", "signet")

# Optional user-supplied API base (--api-url). When set, it wins over
# the network presets — sovereignty first: point at your own instance.
_custom_api_base: str | None = None

_USER_AGENT = f"btc-toolkit/{__version__}"
DEFAULT_TIMEOUT = 15
_TIMEOUT: float = DEFAULT_TIMEOUT

# Retry policy — transient failures only
_MAX_ATTEMPTS = 3
_BACKOFF_BASE = 0.5  # seconds between attempts: 0.5, then 1.0
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class MempoolAPIError(Exception):
    """Raised when the Mempool.space API returns an error."""


class NotFoundError(MempoolAPIError):
    """Raised when a requested resource (tx, address, block) is not found."""


def set_timeout(seconds: float | None) -> None:
    """Override the per-request timeout (seconds). None resets the default."""
    global _TIMEOUT
    if seconds is None:
        _TIMEOUT = DEFAULT_TIMEOUT
        return
    if seconds <= 0:
        raise ValueError("timeout must be positive")
    _TIMEOUT = float(seconds)


def get_timeout() -> float:
    """Current per-request timeout in seconds."""
    return _TIMEOUT


def set_api_base(url: str | None) -> None:
    """
    Override the API base with a custom Mempool instance URL.

    Pass the full API root, e.g. http://umbrel.local:3006/api or
    https://my-node.example/api. A trailing slash is stripped.
    Pass None to reset to the public presets.
    """
    global _custom_api_base
    _custom_api_base = url.rstrip("/") if url else None


def get_api_base(network: str) -> str:
    """
    Return the API base URL: the custom instance when set via
    set_api_base()/--api-url, otherwise the preset for the network.
    """
    if _custom_api_base:
        return _custom_api_base
    if network not in SUPPORTED_NETWORKS:
        raise ValueError(
            f"Unsupported network: {network}. Use one of: {SUPPORTED_NETWORKS}"
        )
    if network == "testnet":
        return MEMPOOL_TESTNET_API
    if network == "signet":
        return MEMPOOL_SIGNET_API
    return MEMPOOL_API


def _fetch(path: str, network: str) -> bytes:
    """
    GET an API path and return the raw response body.

    Retries transient failures (429/5xx/connection errors) up to
    _MAX_ATTEMPTS with exponential backoff. 400/404 fail immediately.
    """
    url = f"{get_api_base(network)}{path}"

    for attempt in range(_MAX_ATTEMPTS):
        last_attempt = attempt == _MAX_ATTEMPTS - 1
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NotFoundError(f"Not found: {path}") from e
            if e.code in _RETRYABLE_STATUS and not last_attempt:
                time.sleep(_BACKOFF_BASE * (2 ** attempt))
                continue
            raise MempoolAPIError(f"API error {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            if not last_attempt:
                time.sleep(_BACKOFF_BASE * (2 ** attempt))
                continue
            raise MempoolAPIError(f"Connection error: {e.reason}") from e

    raise MempoolAPIError(f"Request failed after {_MAX_ATTEMPTS} attempts")


def get_json(path: str, network: str = "mainnet") -> dict | list:
    """
    GET a Mempool.space API endpoint and return parsed JSON.

    Raises:
        NotFoundError: On HTTP 404 (never retried).
        MempoolAPIError: On other HTTP/connection errors after retries.
    """
    return json.loads(_fetch(path, network).decode("utf-8"))


def get_text(path: str, network: str = "mainnet") -> str:
    """
    GET a Mempool.space API endpoint that returns plain text (not JSON).

    Used for endpoints like /blocks/tip/height that return a bare number.
    """
    return _fetch(path, network).decode("utf-8").strip()
