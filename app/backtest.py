"""Backtesting Engine — corre uma estratégia sobre candles históricos/sintéticos."""

from .broker import SimFeed, PAYOUT
from .strategies import STRATEGIES


def run_backtest(strategy_id, asset="EURUSD", n_candles=500, period=60,
                 amount=10.0, expiry_candles=5):
    """Simula trades: sinal na vela i → resultado no fecho da vela i+expiry_candles."""
    if strategy_id not in STRATEGIES:
        return {"ok": False, "error": "estrategia desconhecida"}
    s = STRATEGIES[strategy_id]
    feed = SimFeed(seed=42)
    candles = feed.build_candles(asset, period, n_candles)
    lookback = s["min_candles"]
    trades = []
    eq = 0.0
    curve = []
    i = lookback
    while i < len(candles) - expiry_candles:
        window = candles[max(0, i - lookback - 30): i + 1]
        r = s["fn"](window)
        if r["signal"]:
            entry = candles[i + 1]["open"]
            exit_ = candles[i + expiry_candles]["close"]
            diff = (exit_ - entry) if r["signal"] == "call" else (entry - exit_)
            pnl = round(amount * PAYOUT, 2) if diff > 0 else (-amount if diff < 0 else 0)
            eq += pnl
            trades.append({"i": i, "signal": r["signal"], "entry": entry,
                           "exit": exit_, "pnl": pnl, "confidence": r["confidence"]})
            i += expiry_candles
            continue
        i += 1
        curve.append(round(eq, 2))
    wins = sum(1 for t in trades if t["pnl"] > 0)
    return {
        "ok": True, "strategy": strategy_id, "asset": asset,
        "period_analyzed": f"{n_candles} candles de {period}s",
        "n_candles": n_candles, "trades": len(trades), "wins": wins,
        "losses": len(trades) - wins,
        "win_rate": round(100 * wins / len(trades), 1) if trades else 0,
        "pnl": round(eq, 2), "curve": curve[-200:], "trades_sample": trades[-20:],
        "disclaimer": "Backtest sobre dados sintéticos — desempenho passado não garante resultados futuros.",
    }
