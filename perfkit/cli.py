import argparse
import json
import sys
from perfkit.loading import load_trades
from perfkit.metrics import compute_portfolio_metrics


def _print_text(metrics: dict, rejections: list) -> None:
    print("=== PORTFOLIO PERFORMANCE REPORT ===")
    for k, v in metrics.items():
        if k != "per_symbol":
            print(f"{k.replace('_', ' ').title():<24}: {v}")

    print("\n=== PER-SYMBOL BREAKDOWN ===")
    print(f"{'Symbol':<12} {'Trades':>8} {'Total Net P&L':>16} {'Win Rate %':>12}\n" + "-" * 52)
    for r in metrics["per_symbol"]:
        print(f"{r['symbol']:<12} {r['trades']:>8} {r['total_net_pnl']:>16.2f} {r['win_rate_pct']:>11.2f}%")

    print(f"\n=== REJECTED ROWS ({len(rejections)}) ===")
    for rej in rejections:
        print(f"- [{rej['trade_id']}] {rej['reason']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="perfkit")
    sub = parser.add_subparsers(dest="command", required=True)
    rep = sub.add_parser("report")
    rep.add_argument("csv_file")
    rep.add_argument("--format", choices=["text", "json"], default="text")
    rep.add_argument("--capital", type=float, default=1_000_000.0)
    args = parser.parse_args(argv)

    try:
        if args.capital <= 0:
            raise ValueError("Starting capital must be > 0")
        df, rejections = load_trades(args.csv_file)
        metrics = compute_portfolio_metrics(df, args.capital)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps({"metrics": metrics, "rejections": rejections}, indent=2))
    else:
        _print_text(metrics, rejections)
    return 0