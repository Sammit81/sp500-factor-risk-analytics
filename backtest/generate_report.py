"""
Generates the results report: static plots + a markdown summary, both
written to reports/output/. Script, not a notebook — CI-reproducible and
diffable in git.

Run from project root:
    uv run python -m backtest.generate_report
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless — no display needed, this runs in CI
import matplotlib.pyplot as plt

from backtest import benchmark, engine, metrics
from backtest.compare_signals import SIGNAL_COLUMNS

OUTPUT_DIR = Path(__file__).parent.parent / "reports" / "output"


def plot_cumulative_returns(returns_by_label: dict, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    for label, returns in returns_by_label.items():
        cumulative = (1 + returns).cumprod()
        ax.plot(cumulative.index, cumulative.values, label=label)
    ax.set_title("Cumulative Growth of $1")
    ax.set_ylabel("Portfolio Value ($)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_drawdown(returns: dict, label: str, path: Path) -> None:
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(drawdown.index, drawdown.values * 100, 0, color="firebrick", alpha=0.5)
    ax.set_title(f"Drawdown — {label}")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_risk_return_scatter(results: dict, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    for label, s in results.items():
        ax.scatter(s["annualized_vol"] * 100, s["annualized_return"] * 100, s=60)
        ax.annotate(label, (s["annualized_vol"] * 100, s["annualized_return"] * 100),
                    fontsize=8, xytext=(5, 5), textcoords="offset points")
    ax.set_xlabel("Annualised Volatility (%)")
    ax.set_ylabel("Annualised Return (%)")
    ax.set_title("Risk vs. Return")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def write_summary_markdown(results: dict, path: Path) -> None:
    lines = ["# Backtest Results Summary\n"]
    lines.append("| Strategy | Ann. Return | Ann. Vol | Sharpe | Max DD | Excess Ret | Info Ratio |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for label, s in results.items():
        excess = s.get("excess_return_annualized")
        ir = s.get("information_ratio")
        lines.append(
            f"| {label} | {s['annualized_return']*100:.2f}% | {s['annualized_vol']*100:.2f}% | "
            f"{s['sharpe_ratio']:.2f} | {s['max_drawdown']*100:.2f}% | "
            f"{'-' if excess is None else f'{excess*100:.2f}%'} | "
            f"{'-' if ir is None else f'{ir:.2f}'} |"
        )
    lines.append("\nSee docs/decisions.md for methodology, assumptions, and known limitations "
                  "(survivorship bias, point-in-time Value signal construction, sample size).")
    path.write_text("\n".join(lines))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading data and running backtests...")
    price_returns, signal_scores = engine.run_all()
    spy = benchmark.spy_returns(price_returns)

    returns_by_label = {}
    results = {}
    for label, column in SIGNAL_COLUMNS.items():
        returns, _ = engine.run_backtest(price_returns, signal_scores, column)
        returns_by_label[label] = returns
        results[label] = metrics.summarize(returns, spy)
    returns_by_label["SPY (benchmark)"] = spy
    results["SPY (benchmark)"] = metrics.summarize(spy)

    print("Generating plots...")
    plot_cumulative_returns(returns_by_label, OUTPUT_DIR / "cumulative_returns.png")
    plot_drawdown(returns_by_label["Combined (all 4)"], "Combined (all 4)", OUTPUT_DIR / "drawdown_combined.png")
    plot_risk_return_scatter(results, OUTPUT_DIR / "risk_return_scatter.png")

    print("Writing summary...")
    write_summary_markdown(results, OUTPUT_DIR / "summary.md")

    print(f"Done — output in {OUTPUT_DIR.relative_to(Path(__file__).parent.parent)}/")


if __name__ == "__main__":
    main()
