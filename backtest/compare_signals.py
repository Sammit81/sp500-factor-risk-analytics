"""
Runs the backtest for the combined signal AND each standalone signal
separately, reports all on the same risk metrics side by side — proves the
4-signal combination actually earns its added complexity rather than
asserting it does. Same "ground truth, not vibes" standard as
fraud-transactions-analysis/python/agent/evaluate.py.

Run from project root:
    uv run python -m backtest.compare_signals
"""
import sys

from backtest import benchmark, engine, metrics

SIGNAL_COLUMNS = {
    "Momentum": "MOMENTUM_ZSCORE",
    "Mean Reversion": "MEAN_REVERSION_ZSCORE",
    "Low Volatility": "LOW_VOL_ZSCORE",
    "Value": "VALUE_ZSCORE",
    "Combined (all 4)": "COMBINED_SCORE",
}


def main() -> None:
    print("Loading data from BigQuery...")
    price_returns, signal_scores = engine.run_all()
    spy = benchmark.spy_returns(price_returns)

    results = {}
    for label, column in SIGNAL_COLUMNS.items():
        print(f"Running backtest: {label} ({column})...")
        returns, _ = engine.run_backtest(price_returns, signal_scores, column)
        results[label] = metrics.summarize(returns, spy)

    print("Running long-short diagnostic (combined score, top decile - bottom decile)...")
    top_returns, _ = engine.run_backtest(price_returns, signal_scores, "COMBINED_SCORE", bottom=False)
    bottom_returns, _ = engine.run_backtest(price_returns, signal_scores, "COMBINED_SCORE", bottom=True)
    aligned_top, aligned_bottom = metrics.align(top_returns, bottom_returns)
    long_short = aligned_top - aligned_bottom
    results["Long-Short (diagnostic, not tradable)"] = metrics.summarize(long_short)

    results["SPY (benchmark)"] = metrics.summarize(spy)

    print("\n" + "=" * 108)
    print(f"{'Strategy':<38} {'Ann.Return':>10} {'Ann.Vol':>9} {'Sharpe':>8} {'MaxDD':>8} "
          f"{'ExcessRet':>10} {'InfoRatio':>10}")
    print("-" * 108)
    for label, s in results.items():
        excess = s.get("excess_return_annualized")
        ir = s.get("information_ratio")
        print(f"{label:<38} {s['annualized_return']*100:>9.2f}% {s['annualized_vol']*100:>8.2f}% "
              f"{s['sharpe_ratio']:>8.2f} {s['max_drawdown']*100:>7.2f}% "
              f"{'' if excess is None else f'{excess*100:>9.2f}%'} "
              f"{'' if ir is None else f'{ir:>10.2f}'}")
    print("=" * 108)

    print("\nVaR (95%) and Kupiec exceedance backtest:")
    for label, s in results.items():
        p_value = s["kupiec_p_value"]
        p_value_str = "n/a" if p_value is None else f"{p_value:.3f}"
        print(f"  {label:<38} hist_VaR={s['historical_var_95']*100:>6.2f}%  "
              f"param_VaR={s['parametric_var_95']*100:>6.2f}%  "
              f"exceedances: {s['kupiec_exceedances']}  (p={p_value_str})")

    combined_sharpe = results["Combined (all 4)"]["sharpe_ratio"]
    standalone_sharpes = {
        k: v["sharpe_ratio"] for k, v in results.items()
        if k in SIGNAL_COLUMNS and k != "Combined (all 4)"
    }
    worse_than = {k: v for k, v in standalone_sharpes.items() if v >= combined_sharpe}

    print()
    if worse_than:
        print(f"WARNING: Combined signal (Sharpe={combined_sharpe:.2f}) did NOT beat every standalone "
              f"signal on risk-adjusted return. Underperformed vs: {worse_than}")
        print("This is a real, honest result — reported as-is, not hidden.")
        sys.exit(1)
    else:
        print(f"Combined signal (Sharpe={combined_sharpe:.2f}) beat every standalone signal on Sharpe ratio.")

    return results


if __name__ == "__main__":
    main()
