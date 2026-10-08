"""
Fee estimator.

Queries the Mempool.space API for currently recommended fee rates and
mempool backlog statistics.

Fee rates are in sat/vB. Endpoints:
    GET /api/v1/fees/recommended -> fastestFee, halfHourFee, hourFee,
                                    economyFee, minimumFee
    GET /api/mempool             -> count, vsize, total_fee
"""

from dataclasses import dataclass

from typing import Any
from .api import get_json, as_object, field_int, field_number


@dataclass
class FeeEstimate:
    """Recommended fee rates (sat/vB) and mempool backlog stats."""

    fastest: float
    half_hour: float
    hour: float
    economy: float
    minimum: float
    mempool_tx_count: int
    mempool_vsize: int
    mempool_total_fee: int

    @property
    def mempool_vsize_mb(self) -> float:
        """Mempool virtual size in vMB (1 vMB = 1_000_000 vB)."""
        return self.mempool_vsize / 1_000_000

    @property
    def blocks_to_clear(self) -> float:
        """
        Rough estimate of full blocks needed to clear the current backlog.

        One block holds ~1M vB (4M weight units / 4). This is an
        approximation — actual clearance depends on incoming tx flow.
        """
        return self.mempool_vsize / 1_000_000

    def to_dict(self) -> dict[str, Any]:
        return {
            "fees_sat_vb": {
                "fastest": self.fastest,
                "half_hour": self.half_hour,
                "hour": self.hour,
                "economy": self.economy,
                "minimum": self.minimum,
            },
            "mempool": {
                "tx_count": self.mempool_tx_count,
                "vsize_vb": self.mempool_vsize,
                "vsize_vmb": round(self.mempool_vsize_mb, 2),
                "total_fee_sats": self.mempool_total_fee,
                "blocks_to_clear": round(self.blocks_to_clear, 1),
            },
        }


def get_fees(network: str = "mainnet") -> FeeEstimate:
    """
    Fetch recommended fee rates and mempool backlog statistics.

    Args:
        network: 'mainnet', 'testnet' or 'signet'.

    Returns:
        A FeeEstimate with rates in sat/vB and backlog stats.

    Raises:
        MempoolAPIError: On API or connection errors.
    """
    fees = as_object(get_json("/v1/fees/recommended", network), "/v1/fees/recommended")
    mempool = as_object(get_json("/mempool", network), "/mempool")

    f, m = "/v1/fees/recommended", "/mempool"
    return FeeEstimate(
        fastest=field_number(fees, "fastestFee", f),
        half_hour=field_number(fees, "halfHourFee", f),
        hour=field_number(fees, "hourFee", f),
        economy=field_number(fees, "economyFee", f),
        minimum=field_number(fees, "minimumFee", f),
        mempool_tx_count=field_int(mempool, "count", m),
        mempool_vsize=field_int(mempool, "vsize", m),
        mempool_total_fee=round(field_number(mempool, "total_fee", m)),  # sent as BTC * 1e8: 28999999.999999996
    )
