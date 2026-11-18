import pandas as pd
from backtesting import Backtest, Strategy


def make_data(opens=(100, 100, 100, 300, 180), closes=(100, 100, 300, 180, 180)) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=len(opens), freq="D")
    o, c = list(map(float, opens)), list(map(float, closes))
    hi = [max(x, y) + 5 for x, y in zip(o, c)]
    lo = [min(x, y) - 5 for x, y in zip(o, c)]
    return pd.DataFrame({"Open": o, "High": hi, "Low": lo, "Close": c, "Volume": 1000}, index=dates)


class MultiTradeDemo(Strategy):
    side = "buy"
    result = ()

    def init(self):
        self.step = 0

    def next(self):
        act = self.buy if self.side == "buy" else self.sell
        if self.step in (0, 1):
            act(size=10)
        elif self.step == 2:
            MultiTradeDemo.result = (self.position.pl, self.position.pl_pct)
        self.step += 1


if __name__ == "__main__":
    Backtest(make_data(), MultiTradeDemo, cash=10_000).run()
    pl, pl_pct = MultiTradeDemo.result
    print(f"Buggy -> pl: {pl:.2f}, pl_pct: {pl_pct:.4f}")