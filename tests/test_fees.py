"""Tests for the fee estimator."""

import unittest
from unittest.mock import patch

from btc_toolkit.fees import get_fees, FeeEstimate


def _mock_api(fees_response, mempool_response):
    """Return a side_effect function routing each endpoint to its response."""
    def side_effect(path, network="mainnet"):
        if path == "/v1/fees/recommended":
            return fees_response
        if path == "/mempool":
            return mempool_response
        raise AssertionError(f"Unexpected path: {path}")
    return side_effect


class TestGetFees(unittest.TestCase):
    @patch("btc_toolkit.fees.get_json")
    def test_typical_fees(self, mock_get):
        # Values from the mempool.space docs example
        mock_get.side_effect = _mock_api(
            {"fastestFee": 45, "halfHourFee": 35, "hourFee": 25,
             "economyFee": 15, "minimumFee": 8},
            {"count": 45000, "vsize": 85_000_000,
             "total_fee": 12_500_000_000, "fee_histogram": []},
        )
        est = get_fees()
        self.assertEqual(est.fastest, 45)
        self.assertEqual(est.half_hour, 35)
        self.assertEqual(est.hour, 25)
        self.assertEqual(est.economy, 15)
        self.assertEqual(est.minimum, 8)
        self.assertEqual(est.mempool_tx_count, 45000)
        self.assertEqual(est.mempool_vsize, 85_000_000)

    @patch("btc_toolkit.fees.get_json")
    def test_quiet_mempool(self, mock_get):
        # Low-activity scenario: all rates at 1 sat/vB
        mock_get.side_effect = _mock_api(
            {"fastestFee": 1, "halfHourFee": 1, "hourFee": 1,
             "economyFee": 1, "minimumFee": 1},
            {"count": 58, "vsize": 8008, "total_fee": 10407,
             "fee_histogram": [[1, 8008]]},
        )
        est = get_fees()
        self.assertEqual(est.fastest, 1)
        self.assertEqual(est.mempool_tx_count, 58)

    @patch("btc_toolkit.fees.get_json")
    def test_vsize_mb_conversion(self, mock_get):
        mock_get.side_effect = _mock_api(
            {"fastestFee": 10, "halfHourFee": 8, "hourFee": 5,
             "economyFee": 2, "minimumFee": 1},
            {"count": 1000, "vsize": 2_500_000, "total_fee": 100, "fee_histogram": []},
        )
        est = get_fees()
        self.assertEqual(est.mempool_vsize_mb, 2.5)
        self.assertEqual(est.blocks_to_clear, 2.5)

    @patch("btc_toolkit.fees.get_json")
    def test_precise_float_fees(self, mock_get):
        # API can return sub-sat float rates
        mock_get.side_effect = _mock_api(
            {"fastestFee": 1.5, "halfHourFee": 1.25, "hourFee": 1,
             "economyFee": 0.2, "minimumFee": 0.1},
            {"count": 16, "vsize": 2692, "total_fee": 46318, "fee_histogram": []},
        )
        est = get_fees()
        self.assertEqual(est.fastest, 1.5)
        self.assertEqual(est.economy, 0.2)

    @patch("btc_toolkit.fees.get_json")
    def test_to_dict_structure(self, mock_get):
        mock_get.side_effect = _mock_api(
            {"fastestFee": 12, "halfHourFee": 8, "hourFee": 5,
             "economyFee": 2, "minimumFee": 1},
            {"count": 5000, "vsize": 3_000_000, "total_fee": 50_000_000,
             "fee_histogram": []},
        )
        d = get_fees().to_dict()
        self.assertEqual(d["fees_sat_vb"]["fastest"], 12)
        self.assertEqual(d["fees_sat_vb"]["minimum"], 1)
        self.assertEqual(d["mempool"]["tx_count"], 5000)
        self.assertEqual(d["mempool"]["vsize_vmb"], 3.0)
        self.assertEqual(d["mempool"]["blocks_to_clear"], 3.0)

    @patch("btc_toolkit.fees.get_json")
    def test_missing_fields_default_zero(self, mock_get):
        # Defensive: partial API response doesn't crash
        mock_get.side_effect = _mock_api({}, {})
        est = get_fees()
        self.assertEqual(est.fastest, 0)
        self.assertEqual(est.mempool_tx_count, 0)


if __name__ == "__main__":
    unittest.main()
