import math
import numpy as np
import pandas as pd


def compute_trade_pnl(trades: pd.DataFrame) -> pd.DataFrame:
    df = trades.copy()
    if df.empty:
        return df.assign(gross_pnl=pd.Series(dtype=float), net_pnl=pd.Series(dtype=float), return_pct=pd.Series(dtype=float))

    direction = np.where(df["side"] == "LONG", 1.0, -1.0)
    df["gross_pnl"] = direction * (df["exit_price"] - df["entry_price"]) * df["quantity"]
    df["net_pnl"] = df["gross_pnl"] - df["fees"]
    df["return_pct"] = (df["net_pnl"] / (df["entry_price"] * df["quantity"])) * 100.0
    return df


def build_equity_curve(df: pd.DataFrame, starting_capital: float = 1_000_000.0) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)

    bdays = pd.bdate_range(df["entry_date"].min(), df["exit_date"].max())
    if len(bdays) == 0:
        bdays = pd.DatetimeIndex([df["entry_date"].min()])

    pnl = pd.Series(0.0, index=bdays)
    for dt, val in df.groupby("exit_date")["net_pnl"].sum().items():
        target = dt if dt in pnl.index else (bdays[bdays >= dt][0] if any(bdays >= dt) else bdays[-1])
        pnl.loc[target] += val

    return (starting_capital + pnl.cumsum()).rename("equity")


def compute_portfolio_metrics(trades: pd.DataFrame, starting_capital: float = 1_000_000.0) -> dict:
    if starting_capital <= 0:
        raise ValueError("starting_capital must be > 0")

    df = compute_trade_pnl(trades)
    if df.empty:
        return {
            "starting_capital": starting_capital, "ending_capital": starting_capital,
            "total_trades": 0, "total_net_pnl": 0.0, "win_rate_pct": 0.0,
            "profit_factor": None, "expectancy": 0.0, "average_win": 0.0,
            "average_loss": 0.0, "largest_win": 0.0, "largest_loss": 0.0,
            "longest_losing_streak": 0, "max_drawdown_pct": 0.0, "sharpe_ratio": 0.0,
            "per_symbol": [],
        }

    wins, losses = df[df["net_pnl"] > 0]["net_pnl"], df[df["net_pnl"] < 0]["net_pnl"]
    loss_sum = abs(float(losses.sum()))
    pf = ("inf" if wins.sum() > 0 else 0.0) if loss_sum == 0 else round(float(wins.sum()) / loss_sum, 4)

    # Longest consecutive losing streak ordered by (exit_date, trade_id)
    streak = max_streak = 0
    for net in df.sort_values(["exit_date", "trade_id"])["net_pnl"]:
        streak = streak + 1 if net < 0 else 0
        max_streak = max(max_streak, streak)

    equity = build_equity_curve(df, starting_capital)
    peaks = np.maximum(starting_capital, equity.cummax())
    max_dd = float(((peaks - equity) / peaks * 100.0).max())

    rets = pd.concat([pd.Series([starting_capital]), equity.reset_index(drop=True)]).pct_change().dropna()
    sharpe = (float(rets.mean()) / float(rets.std(ddof=1))) * math.sqrt(252) if len(rets) >= 2 and rets.std(ddof=1) > 0 else 0.0

    per_symbol = [
        {
            "symbol": sym,
            "trades": len(g),
            "total_net_pnl": round(float(g["net_pnl"].sum()), 2),
            "win_rate_pct": round(float((g["net_pnl"] > 0).mean()) * 100.0, 2),
        }
        for sym, g in df.groupby("symbol", sort=True)
    ]

    return {
        "starting_capital": round(starting_capital, 2),
        "ending_capital": round(float(equity.iloc[-1]), 2),
        "total_trades": len(df),
        "total_net_pnl": round(float(df["net_pnl"].sum()), 2),
        "win_rate_pct": round(len(wins) / len(df) * 100.0, 2),
        "profit_factor": pf,
        "expectancy": round(float(df["net_pnl"].mean()), 2),
        "average_win": round(float(wins.mean()), 2) if len(wins) else 0.0,
        "average_loss": round(float(losses.mean()), 2) if len(losses) else 0.0,
        "largest_win": round(float(wins.max()), 2) if len(wins) else 0.0,
        "largest_loss": round(float(losses.min()), 2) if len(losses) else 0.0,
        "longest_losing_streak": max_streak,
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 4),
        "per_symbol": per_symbol,
    }