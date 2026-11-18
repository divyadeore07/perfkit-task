from backtesting.backtesting import Position


def fixed_pl_pct(position: Position) -> float:
    trades = position._Position__broker.trades
    total_cost = sum(abs(t.size) * t.entry_price for t in trades)
    return sum(t.pl for t in trades) / total_cost if total_cost else 0.0


def apply_patch() -> None:
    Position.pl_pct = property(fixed_pl_pct)