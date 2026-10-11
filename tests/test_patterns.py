"""Testes unitários dos padrões de candles."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.patterns import detect_candle_patterns


def mk(o, h, l, c, t=0):
    return {"time": t, "open": o, "high": h, "low": l, "close": c}


def names(cds):
    return {p["pattern"] for p in detect_candle_patterns(cds)}


def flat_seq(n=12, px=100.0):
    return [mk(px, px + .1, px - .1, px, i) for i in range(n)]


def uptrend(n=12):
    return [mk(100 + i, 100 + i + .5, 99.5 + i, 100.4 + i, i) for i in range(n)]


def test_inside_bar():
    cds = flat_seq() + [mk(101, 102, 100, 101.5, 13),
                        mk(101.5, 101.8, 100.5, 101.2, 14)]  # dentro do anterior
    assert "Inside Bar" in names(cds)


def test_outside_bar():
    cds = flat_seq() + [mk(101, 102, 100, 101.5, 13),
                        mk(101.5, 103, 99.5, 102.5, 14)]   # cobre tudo
    assert "Outside Bar Bullish" in names(cds)


def test_rejection_lower():
    cds = flat_seq() + [mk(100, 100.3, 97, 100.2, 13)]      # pavio inferior enorme
    assert "Rejection Lower Wick" in names(cds)


def test_rejection_upper():
    cds = flat_seq() + [mk(100, 103.5, 99.8, 100.1, 13)]    # pavio superior enorme
    assert "Rejection Upper Wick" in names(cds)


def test_breakout_up():
    cds = flat_seq(14, 100.0) + [mk(100, 101.6, 100, 101.5, 15)]  # fecha acima do máximo
    assert "Breakout Up" in names(cds)


def test_breakout_down():
    cds = flat_seq(14, 100.0) + [mk(100, 100.2, 98.4, 98.6, 15)]  # fecha abaixo do mínimo
    assert "Breakout Down" in names(cds)


def test_momentum_seq():
    cds = [mk(100, 100.5, 99.9, 100.4, 0), mk(100.4, 101, 100.3, 100.9, 1),
           mk(100.9, 101.7, 100.8, 101.5, 2), mk(101.5, 102.8, 101.4, 102.6, 3)]
    assert "Momentum Up Sequence" in names(flat_seq() + cds)


def test_marubozu_soldiers():
    cds = flat_seq() + [mk(100, 101, 100, 101, 13), mk(101, 102, 101, 102, 14),
                        mk(102, 103, 102, 103, 15)]
    n = names(cds)
    assert "Three White Soldiers" in n or "Marubozu Bullish" in n


def run():
    fns = [v for k, v in globals().items() if k.startswith("test_")]
    for f in fns:
        f()
        print("ok", f.__name__)
    print(len(fns), "testes passaram")


if __name__ == "__main__":
    run()
