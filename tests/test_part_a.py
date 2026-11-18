import pytest
from backtesting import Backtest, Strategy
from backtesting.backtesting import Position
from part_a.fix import apply_patch
from part_a.reproduce import MultiTradeDemo, make_data


@pytest.fixture(autouse=True)
def reset_patch():
    orig = Position.pl_pct
    yield
    Position.pl_pct = orig


def test_bug_reproduced():
    MultiTradeDemo.side = "buy"
    Backtest(make_data(), MultiTradeDemo, cash=10_000).run()
    pl, pl_pct = MultiTradeDemo.result
    assert pl == pytest.approx(-400.0)
    assert pl_pct > 0  # Bug: shows +0.20 instead of -0.10


@pytest.mark.parametrize("side,opens,closes", [
    ("buy",  (100, 100, 100, 300, 180), (100, 100, 300, 180, 180)),
    ("sell", (300, 300, 300, 100, 220), (300, 300, 100, 220, 220)),
])
def test_fix_long_and_short(side, opens, closes):
    apply_patch()
    MultiTradeDemo.side = side
    Backtest(make_data(opens, closes), MultiTradeDemo, cash=10_000).run()
    pl, pl_pct = MultiTradeDemo.result
    assert pl == pytest.approx(-400.0)
    assert pl_pct == pytest.approx(-0.10)


def test_fix_single_and_flat():
    apply_patch()
    seen = []

    class SingleFlat(Strategy):
        def init(self):
            self.step = 0

        def next(self):
            if self.step == 0:
                seen.append(self.position.pl_pct)  # Flat -> 0.0
                self.buy(size=5)                   # Fills on Bar 2 Open at 100
            elif self.step == 1:
                seen.append(self.position.pl_pct)  # Bar 2 Close is 300 -> +2.0
                self.position.close()
            elif self.step == 2:
                seen.append(self.position.pl_pct)  # Flat again -> 0.0
            self.step += 1

    Backtest(make_data(), SingleFlat, cash=10_000).run()
    assert seen == pytest.approx([0.0, 2.0, 0.0])