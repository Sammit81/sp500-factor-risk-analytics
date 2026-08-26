"""Risk/performance metrics checked against hand-computed known values."""
import numpy as np
import pandas as pd

from backtest import metrics


def test_sharpe_ratio_known_value():
    returns = pd.Series([0.02, -0.01] * 126)  # 252 values
    rf_daily = metrics.RISK_FREE_ANNUAL / metrics.TRADING_DAYS_PER_YEAR
    excess = returns - rf_daily
    expected = (excess.mean() / excess.std()) * np.sqrt(metrics.TRADING_DAYS_PER_YEAR)
    assert abs(metrics.sharpe_ratio(returns) - expected) < 1e-9


def test_max_drawdown_known_value():
    prices = pd.Series([100.0, 110.0, 90.0, 95.0, 120.0])
    returns = prices.pct_change().dropna()
    expected = (90.0 - 110.0) / 110.0  # peak 110, trough 90
    assert abs(metrics.max_drawdown(returns) - expected) < 1e-9


def test_historical_var_matches_pandas_quantile():
    returns = pd.Series(range(1, 101)) / 1000
    expected = returns.quantile(0.05)
    assert abs(metrics.historical_var(returns, confidence=0.95) - expected) < 1e-9


def test_kupiec_exceedance_count_and_expected_rate():
    returns = pd.Series([-0.05] * 5 + [0.01] * 95)  # exactly 5% breach a -0.02 threshold
    result = metrics.kupiec_test(returns, var_estimate=-0.02, confidence=0.95)
    assert result["n_observations"] == 100
    assert result["n_exceedances"] == 5
    assert abs(result["expected_exceedances"] - 5.0) < 1e-9
    # Observed rate exactly matches the expected rate here -> LR statistic should be ~0
    assert result["lr_statistic"] < 1e-6
    assert result["p_value"] > 0.99


def test_kupiec_flags_miscalibrated_var():
    """Far more exceedances than expected -> should produce a small p-value
    (statistically significant miscalibration), not a silent pass."""
    returns = pd.Series([-0.05] * 30 + [0.01] * 70)  # 30% breach a 5%-expected threshold
    result = metrics.kupiec_test(returns, var_estimate=-0.02, confidence=0.95)
    assert result["n_exceedances"] == 30
    assert result["p_value"] < 0.01


def test_excess_return_and_tracking_error_known_values():
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    portfolio = pd.Series([0.01, 0.01, 0.01], index=dates)
    benchmark = pd.Series([0.00, 0.00, 0.00], index=dates)

    port_annual = 1.01 ** metrics.TRADING_DAYS_PER_YEAR - 1
    bench_annual = 0.0
    expected_excess = port_annual - bench_annual
    assert abs(metrics.excess_return_annualized(portfolio, benchmark) - expected_excess) < 1e-6

    expected_te = (portfolio - benchmark).std() * np.sqrt(metrics.TRADING_DAYS_PER_YEAR)
    assert abs(metrics.tracking_error(portfolio, benchmark) - expected_te) < 1e-9


def test_align_drops_dates_present_in_only_one_series():
    dates_p = pd.date_range("2024-01-01", periods=4, freq="D")
    dates_b = pd.date_range("2024-01-02", periods=4, freq="D")  # offset by 1 day
    portfolio = pd.Series([0.01, 0.02, 0.03, 0.04], index=dates_p)
    benchmark = pd.Series([0.00, 0.00, 0.00, 0.00], index=dates_b)

    aligned_p, aligned_b = metrics.align(portfolio, benchmark)
    assert len(aligned_p) == 3  # only the 3 overlapping dates survive
