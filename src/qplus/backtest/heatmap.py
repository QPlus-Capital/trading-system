"""Parameter-sensitivity heatmap from a sweep results CSV.

Visualizes how a metric varies across two parameters. A robust strategy shows a
broad, connected profitable region (a plateau); a single bright cell surrounded by
poor values is a hallmark of overfitting. Other swept parameters are averaged out.

Usage::

    uv run python -m qplus.backtest.heatmap reports/sweep_rsi_wpr_bb_xauusd.csv
    uv run python -m qplus.backtest.heatmap <csv> stop_loss_pct take_profit_pct profit_factor
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402


def pivot_metric(df: pd.DataFrame, x_param: str, y_param: str, metric: str) -> pd.DataFrame:
    """Pivot ``metric`` over the two parameters, averaging over any other columns."""
    return df.pivot_table(index=y_param, columns=x_param, values=metric, aggfunc="mean")


def plot_heatmap(
    pivot: pd.DataFrame,
    x_param: str,
    y_param: str,
    metric: str,
    out_png: Path,
    title: str,
) -> None:
    """Render and save a heatmap of the pivot table (rows = y, cols = x)."""
    fig, ax = plt.subplots(figsize=(8, 6))
    data = pivot.to_numpy(dtype=float)
    im = ax.imshow(data, aspect="auto", cmap="RdYlGn", origin="lower")
    ax.set_xticks(range(len(pivot.columns)), [str(c) for c in pivot.columns])
    ax.set_yticks(range(len(pivot.index)), [str(i) for i in pivot.index])
    ax.set_xlabel(x_param)
    ax.set_ylabel(y_param)
    ax.set_title(title)
    for r in range(data.shape[0]):
        for c in range(data.shape[1]):
            ax.text(c, r, f"{data[r, c]:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label=metric)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    """CLI: read a sweep CSV and save a parameter-sensitivity heatmap."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        raise SystemExit("usage: python -m qplus.backtest.heatmap <sweep_csv> [x] [y] [metric]")
    csv_path = Path(args[0])
    x_param = args[1] if len(args) > 1 else "stop_loss_pct"
    y_param = args[2] if len(args) > 2 else "take_profit_pct"
    metric = args[3] if len(args) > 3 else "profit_factor"

    df = pd.read_csv(csv_path)
    pivot = pivot_metric(df, x_param, y_param, metric)
    out_png = csv_path.with_name(f"heatmap_{csv_path.stem}_{metric}.png")
    plot_heatmap(pivot, x_param, y_param, metric, out_png, f"{metric} — {csv_path.stem}")

    print(f"Heatmap ({metric} over {x_param} x {y_param}): {out_png}")
    print(pivot.round(2).to_string())


if __name__ == "__main__":
    main()
