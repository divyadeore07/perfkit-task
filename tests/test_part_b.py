import json
import pytest
import pandas as pd
from perfkit.loading import load_trades
from perfkit.metrics import build_equity_curve, compute_portfolio_metrics, compute_trade_pnl
from perfkit.sizing import position_size
from perfkit.cli import main


def test_load_trades_real_csv():
    df, rejections = load_trades("trades.csv")
    assert len(df) == 61
    assert len(rejections) == 5
    rejected_ids = [r["trade_id"] for r in rejections]
    assert rejected_ids == ["T010", "T061", "T062", "T063", "T064"]


def test_load_trades_validation_rules(tmp_path):
    csv_file = tmp_path / "sample.csv"
    csv_file.write_text(
        "trade_id,symbol,side,quantity,entry_price,exit_price,entry_date,exit_date,fees\n"
        "T1,INFY,long,10,100,110,2026-01-01,02/01/2026,5\n"          # valid (mixed case + DD/MM/YYYY)
        "T1,INFY,long,10,100,110,2026-01-01,02/01/2026,5\n"          # duplicate
        "T2,TCS,SHORT,5,200,190,2026-01-03,2026-01-03,2\n"           # valid same-day short
        "T3,SBIN,LONG,2.5,100,105,2026-01-04,2026-01-05,1\n"         # fractional qty
        "T4,SBIN,LONG,5,0,105,2026-01-04,2026-01-05,1\n"             # zero entry_price
        "T5,SBIN,LONG,5,100,105,2026-01-05,2026-01-04,1\n",          # exit < entry
        encoding="utf-8",
    )
    df, rejections = load_trades(csv_file)
    assert list(df["trade_id"]) == ["T1", "T2"]
    assert list(df["side"]) == ["LONG", "SHORT"]
    assert len(rejections) == 4


def test_load_trades_missing_column(tmp_path):
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("trade_id,symbol\nT1,INFY\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Missing required columns"):
        load_trades(bad_csv)


def test_trade_pnl_and_portfolio_metrics():
    trades = pd.DataFrame(
        [
            {
                "trade_id": "T1",
                "symbol": "INFY",
                "side": "LONG",
                "quantity": 10,
                "entry_price": 100.0,
                "exit_price": 120.0,
                "entry_date": pd.Timestamp("2026-01-05"),  # Mon
                "exit_date": pd.Timestamp("2026-01-06"),   # Tue -> +190 net
                "fees": 10.0,
            },
            {
                "trade_id": "T2",
                "symbol": "INFY",
                "side": "SHORT",
                "quantity": 10,
                "entry_price": 100.0,
                "exit_price": 110.0,
                "entry_date": pd.Timestamp("2026-01-06"),  # Tue
                "exit_date": pd.Timestamp("2026-01-08"),   # Thu -> -110 net
                "fees": 10.0,
            },
            {
                "trade_id": "T3",
                "symbol": "TCS",
                "side": "SHORT",
                "quantity": 5,
                "entry_price": 200.0,
                "exit_price": 210.0,
                "entry_date": pd.Timestamp("2026-01-08"),  # Thu
                "exit_date": pd.Timestamp("2026-01-09"),   # Fri -> -55 net
                "fees": 5.0,
            },
        ]
    )

    pnl_df = compute_trade_pnl(trades)
    assert list(pnl_df["gross_pnl"]) == pytest.approx([200.0, -100.0, -50.0])
    assert list(pnl_df["net_pnl"]) == pytest.approx([190.0, -110.0, -55.0])
    assert list(pnl_df["return_pct"]) == pytest.approx([19.0, -11.0, -5.5])

    equity = build_equity_curve(pnl_df, starting_capital=10_000.0)
    assert len(equity) == 5  # Mon Jan 5 to Fri Jan 9
    assert list(equity.values) == pytest.approx([10_000.0, 10_190.0, 10_190.0, 10_080.0, 10_025.0])

    metrics = compute_portfolio_metrics(pnl_df, starting_capital=10_000.0)
    assert metrics["total_trades"] == 3
    assert metrics["total_net_pnl"] == pytest.approx(25.0)
    assert metrics["win_rate_pct"] == pytest.approx(33.33)
    assert metrics["profit_factor"] == pytest.approx(190.0 / 165.0, rel=1e-3)
    assert metrics["longest_losing_streak"] == 2
    # Peak is 10190, trough is 10025 -> (165 / 10190) * 100 = 1.6192%
    assert metrics["max_drawdown_pct"] == pytest.approx(1.62)


def test_position_size():
    # Risk 1% of 100,000 = 1,000; stop distance = 5 -> 200 shares; lot_size=75 -> 150
    assert position_size(100_000, 1.0, 100.0, 95.0, lot_size=75) == 150
    assert position_size(100_000, 1.0, 100.0, 105.0, lot_size=1) == 200
    assert position_size(1_000, 0.5, 100.0, 90.0, lot_size=10) == 0

    with pytest.raises(ValueError):
        position_size(-100, 1.0, 100.0, 95.0)
    with pytest.raises(ValueError):
        position_size(100_000, 0.0, 100.0, 95.0)
    with pytest.raises(ValueError):
        position_size(100_000, 1.0, 100.0, 100.0)
    with pytest.raises(ValueError):
        position_size(100_000, 1.0, 100.0, 95.0, lot_size=0)


def test_cli_json_output(capsys):
    exit_code = main(["report", "trades.csv", "--format", "json", "--capital", "500000"])
    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["metrics"]["starting_capital"] == 500000.0
    assert payload["metrics"]["total_trades"] == 61
    assert len(payload["rejections"]) == 5