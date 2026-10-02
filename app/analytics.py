"""AI Market Analyst — agrega sinais de todas as estratégias num painel."""

from . import indicators as I
from .strategies import STRATEGIES


def market_analysis(candles):
    cl = [x["close"] for x in candles]
    r = I.rsi(cl, 14)
    m = I.macd(cl)
    e1, e2 = I.ema(cl, 12), I.ema(cl, 26)
    a = I.atr(candles, 14)
    adx = I.adx(candles, 14)

    votes = {"call": [], "put": []}
    for sid, s in STRATEGIES.items():
        res = s["fn"](candles)
        if res["signal"]:
            votes[res["signal"]].append((sid, res["confidence"]))

    trend = "Neutral"
    if e1 and e2:
        trend = "Bullish" if e1 > e2 else "Bearish"
    vol = "Low"
    if a and len(cl) > 20:
        vol = "High" if a > (sum(cl[-20:]) / 20) * 0.001 else "Medium"

    agree = max(len(votes["call"]), len(votes["put"]))
    total = len(votes["call"]) + len(votes["put"])
    conf = int(100 * agree / total) if total else 0
    decision = "WAIT"
    if conf >= 60 and agree >= 3:
        decision = "CALL" if len(votes["call"]) > len(votes["put"]) else "PUT"

    return {
        "trend": trend,
        "momentum": "Strong" if (adx and adx["adx"] > 25) else "Moderate",
        "volatility": vol,
        "rsi": round(r, 1) if r else None,
        "macd": "Positive" if (m and m["hist"] > 0) else "Negative" if m else None,
        "ema": "Bullish" if (e1 and e2 and e1 > e2) else "Bearish" if e1 and e2 else None,
        "signal_agreement": f"{agree}/{total}",
        "confidence": conf,
        "decision": decision,
        "disclaimer": "Educational analysis. Past performance does not guarantee future results.",
    }
