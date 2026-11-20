import math


def position_size(capital: float, risk_pct: float, entry: float, stop: float, lot_size: int = 1) -> int:
    if capital <= 0 or not (0 < risk_pct <= 100) or entry <= 0 or stop <= 0 or entry == stop:
        raise ValueError("Invalid capital, risk_pct, entry, or stop price")
    if isinstance(lot_size, bool) or not isinstance(lot_size, int) or lot_size < 1:
        raise ValueError("lot_size must be an integer >= 1")

    raw_shares = (capital * risk_pct / 100.0) / abs(entry - stop)
    return int(math.floor(raw_shares / lot_size) * lot_size)