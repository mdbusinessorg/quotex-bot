"""Testes: estratégias, simulação, risco, backtest, histórico, engine."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ["DATA_DIR"] = str(Path(__file__).resolve().parent / "_tmpdata")
Path(os.environ["DATA_DIR"]).mkdir(exist_ok=True)

from app import history
from app.backtest import run_backtest
from app.broker import SimAdapter
from app.risk import RiskManager
from app.strategies import STRATEGIES


def flat(n=80, price=1.10):
    return [{"open": price, "high": price + .001, "low": price - .001,
             "close": price, "time": i} for i in range(n)]


def uptrend(n=80):
    return [{"open": 1 + i * .01, "high": 1.005 + i * .01, "low": .995 + i * .01,
             "close": 1.008 + i * .01, "time": i} for i in range(n)]


def downtrend(n=80):
    return [{"open": 2 - i * .01, "high": 2.005 - i * .01, "low": 1.995 - i * .01,
             "close": 1.992 - i * .01, "time": i} for i in range(n)]


def test_strategies_contract():
    for candles in (flat(), uptrend(), downtrend(), flat(3)):
        for sid, s in STRATEGIES.items():
            r = s["fn"](candles)
            assert r["signal"] in ("call", "put", None), sid
            assert 0 <= r["confidence"] <= 100
            assert r["risk"] in ("LOW", "MEDIUM", "HIGH")
            assert isinstance(r["reasons"], list)


def test_15_strategies():
    assert len(STRATEGIES) >= 15


def test_sim_trade_win_loss_and_balance():
    async def go():
        a = SimAdapter(balance=1000, latency_ms=0)
        await a.connect()
        oid = await a.place_order("EURUSD", 10, "call", expiry=1)
        await asyncio.sleep(1.1)
        st = await a.get_order_status(oid)
        assert st["state"] == "closed" and st["result"] in ("win", "loss", "tie")
        bal = await a.get_balance()
        assert bal != 1000 or st["result"] == "tie"
    asyncio.run(go())


def test_insufficient_balance():
    async def go():
        a = SimAdapter(balance=5, latency_ms=0)
        await a.connect()
        try:
            await a.place_order("EURUSD", 10, "call", 60)
        except RuntimeError as e:
            assert "insuficiente" in str(e)
        else:
            assert False
    asyncio.run(go())


def test_risk_limits():
    r = RiskManager()
    r.configure(max_daily_loss=20, max_consecutive_losses=2, cooldown_sec=0,
                max_simultaneous=5, max_amount_per_trade=1000, max_exposure=10000)
    r.resume()
    assert r.check(10, [])[0]
    r.record_result(-10)
    r.st.last_trade_ts = 0
    r.record_result(-10)
    r.st.last_trade_ts = 0
    assert r.st.paused and "diária" in r.st.pause_reason
    r.configure(max_daily_loss=1000)
    r.resume()
    r.st.daily_pnl = 0
    r.record_result(-10); r.st.last_trade_ts = 0
    r.record_result(-10); r.st.last_trade_ts = 0
    assert r.st.paused and "consecutivas" in r.st.pause_reason


def test_backtest_runs_all():
    for sid in STRATEGIES:
        r = run_backtest(sid, n_candles=300)
        assert r["ok"] and r["trades"] >= 0


def test_history_roundtrip():
    history.record({"id": "t1", "asset": "EURUSD", "direction": "call",
                    "amount": 10, "expiry": 300, "strategy": "momentum",
                    "result": "win", "pnl": 9.2, "entry": 1.1, "exit": 1.2})
    rows = history.list_trades(strategy="momentum")
    assert rows and rows[0]["id"] == "t1"
    st = history.stats_by_strategy()["momentum"]
    assert st["wins"] == 1 and st["win_rate"] == 100
