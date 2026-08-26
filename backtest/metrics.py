"""
Risk and performance metrics. Applies the same "prove it against ground
truth, don't assert it" standard to the risk metrics themselves, not just
the trading signal — see the Kupiec test below and docs/decisions.md.
"""
import numpy as np
import pandas as pd
from scipy import stats

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_ANNUAL = 0.04


def sharpe_ratio(daily_returns: pd.Series, risk_free_annual: float = RISK_FREE_ANNUAL) -> float:
    risk_free_daily = risk_free_annual / TRADING_DAYS_PER_YEAR
    excess = daily_returns - risk_free_daily
    if excess.std() == 0:
        return 0.0
    return (excess.mean() / excess.std()) * np.sqrt(TRADING_DAYS_PER_YEAR)


def max_drawdown(daily_returns: pd.Series) -> float:
    cumulative = (1 + daily_returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    return drawdown.min()


def historical_var(daily_returns: pd.Series, confidence: float = 0.95) -> float:
    """Nonparametric — the empirical (1-confidence) percentile of the
    return distribution. No normality assumption, the right call for
    fat-tailed equity returns (see docs/decisions.md)."""
    return daily_returns.quantile(1 - confidence)


def parametric_var(daily_returns: pd.Series, confidence: float = 0.95) -> float:
    """Variance-covariance VaR, assuming a normal return distribution.
    Computed alongside historical VaR specifically so the DISCREPANCY
    between the two is visible — informative on its own, not a nuisance."""
    z = stats.norm.ppf(1 - confidence)
    return daily_returns.mean() + z * daily_returns.std()


def kupiec_test(daily_returns: pd.Series, var_estimate: float, confidence: float = 0.95) -> dict:
    """Proportion-of-failures backtest: count actual daily loss exceedances
    against the VaR threshold, compare to the statistically expected rate.
    Applies the same 'ground truth, not vibes' standard used elsewhere in
    this project (see backtest/compare_signals.py) to the risk metric
    itself, not just the trading signal.

    Returns the observed/expected exceedance counts and a likelihood-ratio
    test statistic against the null hypothesis that the VaR model's
    exceedance rate is correct — under H0 this follows a chi-square(1)
    distribution, so a small p-value means the VaR estimate is likely
    miscalibrated (too tight or too loose), not just unlucky.
    """
    n = len(daily_returns)
    p = 1 - confidence  # expected exceedance rate
    exceedances = (daily_returns < var_estimate).sum()
    observed_rate = exceedances / n

    if exceedances == 0 or exceedances == n:
        # log(0) undefined at the boundary — report without a p-value rather
        # than crash or silently produce NaN.
        return {
            "n_observations": n, "n_exceedances": int(exceedances),
            "expected_exceedances": round(n * p, 2), "observed_rate": observed_rate,
            "expected_rate": p, "lr_statistic": None, "p_value": None,
        }

    log_likelihood_null = (n - exceedances) * np.log(1 - p) + exceedances * np.log(p)
    log_likelihood_alt = (n - exceedances) * np.log(1 - observed_rate) + exceedances * np.log(observed_rate)
    lr_stat = -2 * (log_likelihood_null - log_likelihood_alt)
    p_value = 1 - stats.chi2.cdf(lr_stat, df=1)

    return {
        "n_observations": n, "n_exceedances": int(exceedances),
        "expected_exceedances": round(n * p, 2), "observed_rate": observed_rate,
        "expected_rate": p, "lr_statistic": lr_stat, "p_value": p_value,
    }


def align(daily_returns: pd.Series, benchmark_returns: pd.Series) -> tuple[pd.Series, pd.Series]:
    joined = pd.concat([daily_returns.rename("p"), benchmark_returns.rename("b")], axis=1).dropna()
    return joined["p"], joined["b"]


def excess_return_annualized(daily_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    p, b = align(daily_returns, benchmark_returns)
    port_annual = (1 + p).prod() ** (TRADING_DAYS_PER_YEAR / len(p)) - 1
    bench_annual = (1 + b).prod() ** (TRADING_DAYS_PER_YEAR / len(b)) - 1
    return port_annual - bench_annual


def tracking_error(daily_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    p, b = align(daily_returns, benchmark_returns)
    return (p - b).std() * np.sqrt(TRADING_DAYS_PER_YEAR)


def information_ratio(daily_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    te = tracking_error(daily_returns, benchmark_returns)
    if te == 0:
        return 0.0
    return excess_return_annualized(daily_returns, benchmark_returns) / te


def summarize(daily_returns: pd.Series, benchmark_returns: pd.Series = None) -> dict:
    """One-stop summary dict — what compare_signals.py and generate_report.py use."""
    hist_var = historical_var(daily_returns)
    summary = {
        "n_days": len(daily_returns),
        "annualized_return": (1 + daily_returns).prod() ** (TRADING_DAYS_PER_YEAR / len(daily_returns)) - 1,
        "annualized_vol": daily_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR),
        "sharpe_ratio": sharpe_ratio(daily_returns),
        "max_drawdown": max_drawdown(daily_returns),
        "historical_var_95": hist_var,
        "parametric_var_95": parametric_var(daily_returns),
    }
    kupiec = kupiec_test(daily_returns, hist_var)
    summary["kupiec_exceedances"] = f"{kupiec['n_exceedances']} observed vs {kupiec['expected_exceedances']} expected"
    summary["kupiec_p_value"] = kupiec["p_value"]

    if benchmark_returns is not None:
        summary["excess_return_annualized"] = excess_return_annualized(daily_returns, benchmark_returns)
        summary["tracking_error"] = tracking_error(daily_returns, benchmark_returns)
        summary["information_ratio"] = information_ratio(daily_returns, benchmark_returns)

    return summary
