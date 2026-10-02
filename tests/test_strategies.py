"""Testes das estratégias com candles sintéticos."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.strategies import STRATEGIES


def flat(n=60, price=1.10):
    return [{"open": price, "high": price + 0.001, "low": price - 0.001,
             "close": price, "time": i} for i in range(n)]


def uptrend(n=60):
    return [{"open": 1.0 + i * 0.01, "high": 1.005 + i * 0.01,
             "low": 0.995 + i * 0.01, "close": 1.008 + i * 0.01, "time": i}
            for i in range(n)]


def downtrend(n=60):
    return [{"open": 1.6 - i * 0.01, "high": 1.605 - i * 0.01,
             "low": 1.595 - i * 0.01, "close": 1.592 - i * 0.01, "time": i}
            for i in range(n)]


def engulfing_bull():
    c = flat(10)
    c.append({"open": 1.10, "high": 1.101, "low": 1.08, "close": 1.09, "time": 10})
    c.append({"open": 1.088, "high": 1.12, "low": 1.087, "close": 1.115, "time": 11})
    return c


def test_all_strategies_run_without_error():
    for candles in (flat(), uptrend(), downtrend(), engulfing_bull()):
        for sid, s in STRATEGIES.items():
            sig = s["fn"](candles, s["params"])
            assert sig in ("call", "put", None), sid


def test_engulfing_detected():
    assert STRATEGIES["engulfing"]["fn"](engulfing_bull(), {}) == "call"


def test_rsi_reversal_extremes():
    # forte subida constante -> RSI ~100 -> put (reversão)
    assert STRATEGIES["rsi_reversal"]["fn"](uptrend(40), {"period": 14, "oversold": 30, "overbought": 70}) == "put"
    assert STRATEGIES["rsi_reversal"]["fn"](downtrend(40), {"period": 14, "oversold": 30, "overbought": 70}) == "call"


def test_three_soldiers():
    assert STRATEGIES["three_soldiers"]["fn"](uptrend(10)[-3:], {}) == "call"


def test_min_candles_enough():
    # estratégias não rebentam com poucas velas
    for sid, s in STRATEGIES.items():
        assert s["fn"](flat(3), s["params"]) in ("call", "put", None)
