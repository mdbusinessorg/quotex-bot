"""Strategy Engine — 15 estratégias modulares.

Cada estratégia recebe `candles` (antiga->nova) e devolve:
    {"signal": "call"|"put"|None, "confidence": 0-100,
     "reasons": [...], "risk": "LOW"|"MEDIUM"|"HIGH"}
"""

from . import indicators as I


def _res(sig, conf, reasons, risk="MEDIUM"):
    return {"signal": sig, "confidence": conf, "reasons": reasons, "risk": risk}

NO = _res(None, 0, [])


def closes(c):
    return [x["close"] for x in c]


# 1. Trend Following (Covel)
def s_trend_following(c):
    cl = closes(c)
    f = I.sma(cl, 20); s = I.sma(cl, 50)
    if f is None or s is None:
        return NO
    if f > s and I.is_bull(c[-1]):
        return _res("call", 60, ["SMA20 acima de SMA50", "vela bullish em tendência"], "LOW")
    if f < s and I.is_bear(c[-1]):
        return _res("put", 60, ["SMA20 abaixo de SMA50", "vela bearish em tendência"], "LOW")
    return NO


# 2. Moving Average Cross
def s_ma_cross(c):
    f = I.sma_series(closes(c), 9); s = I.sma_series(closes(c), 21)
    if len(f) < 2 or f[-2] is None or s[-2] is None:
        return NO
    if f[-2] <= s[-2] and f[-1] > s[-1]:
        return _res("call", 65, ["cruzamento SMA9 > SMA21"])
    if f[-2] >= s[-2] and f[-1] < s[-1]:
        return _res("put", 65, ["cruzamento SMA9 < SMA21"])
    return NO


# 3. RSI Momentum (Wilder)
def s_rsi_momentum(c):
    r = I.rsi(closes(c), 14)
    if r is None:
        return NO
    if r > 55 and I.is_bull(c[-1]):
        return _res("call", min(90, 40 + r // 2), [f"RSI {r:.0f} > 55", "vela bullish"])
    if r < 45 and I.is_bear(c[-1]):
        return _res("put", min(90, 40 + (100 - r) // 2), [f"RSI {r:.0f} < 45", "vela bearish"])
    return NO


# 4. MACD Momentum
def s_macd_momentum(c):
    m = I.macd(closes(c))
    if m is None or m["prev_hist"] is None:
        return NO
    if m["prev_hist"] <= 0 < m["hist"]:
        return _res("call", 62, ["histograma MACD cruzou positivo"])
    if m["prev_hist"] >= 0 > m["hist"]:
        return _res("put", 62, ["histograma MACD cruzou negativo"])
    return NO


# 5. Bollinger Bands
def s_bollinger(c):
    cl = closes(c)
    b = I.bollinger(cl, 20, 2.0)
    if b is None:
        return NO
    lo, mid, hi = b
    if cl[-1] < lo:
        return _res("call", 58, ["preço abaixo da banda inferior → reversão"])
    if cl[-1] > hi:
        return _res("put", 58, ["preço acima da banda superior → reversão"])
    return NO


# 6. Support & Resistance
def s_support_resistance(c):
    if len(c) < 30:
        return NO
    hi = max(x["high"] for x in c[-30:-1]); lo = min(x["low"] for x in c[-30:-1])
    last = c[-1]
    if last["low"] <= lo * 1.001 and I.is_bull(last):
        return _res("call", 60, ["rejeição no suporte de 30 velas"])
    if last["high"] >= hi * 0.999 and I.is_bear(last):
        return _res("put", 60, ["rejeição na resistência de 30 velas"])
    return NO


# 7. Breakout
def s_breakout(c):
    if len(c) < 25:
        return NO
    hi = max(x["high"] for x in c[-25:-1]); lo = min(x["low"] for x in c[-25:-1])
    last = c[-1]
    if last["close"] > hi and I.is_bull(last):
        return _res("call", 63, ["breakout acima do máximo de 25 velas"], "HIGH")
    if last["close"] < lo and I.is_bear(last):
        return _res("put", 63, ["breakout abaixo do mínimo de 25 velas"], "HIGH")
    return NO


# 8. Mean Reversion
def s_mean_reversion(c):
    cl = closes(c)
    m = I.sma(cl, 20)
    if m is None:
        return NO
    dev = (cl[-1] - m) / m
    if dev < -0.004:
        return _res("call", 55, [f"preço {abs(dev)*100:.1f}% abaixo da média → reversão"])
    if dev > 0.004:
        return _res("put", 55, [f"preço {dev*100:.1f}% acima da média → reversão"])
    return NO


# 9. Volatility
def s_volatility(c):
    a = I.atr(c, 14)
    if a is None or len(c) < 16:
        return NO
    prev_atr = I.atr(c[:-1], 14) or a
    if a > prev_atr * 1.5:
        # spike de volatilidade: segue a direção da última vela
        if I.is_bull(c[-1]):
            return _res("call", 52, ["ATR spike + vela bullish"], "HIGH")
        if I.is_bear(c[-1]):
            return _res("put", 52, ["ATR spike + vela bearish"], "HIGH")
    return NO


# 10. Momentum (ROC)
def s_momentum(c):
    cl = closes(c)
    if len(cl) < 15:
        return NO
    roc = (cl[-1] - cl[-10]) / cl[-10]
    if roc > 0.003:
        return _res("call", 57, [f"ROC(10) +{roc*100:.2f}%"])
    if roc < -0.003:
        return _res("put", 57, [f"ROC(10) {roc*100:.2f}%"])
    return NO


# 11. EMA Trend
def s_ema_trend(c):
    f = I.ema_series(closes(c), 12); s = I.ema_series(closes(c), 26)
    if len(f) < 2 or f[-1] is None or s[-1] is None:
        return NO
    if f[-1] > s[-1] and f[-2] <= s[-2]:
        return _res("call", 64, ["EMA12 cruzou EMA26 para cima"])
    if f[-1] < s[-1] and f[-2] >= s[-2]:
        return _res("put", 64, ["EMA12 cruzou EMA26 para baixo"])
    return NO


# 12. Multi-Indicator Confirmation (RSI + MACD + EMA)
def s_multi_indicator(c):
    cl = closes(c)
    r = I.rsi(cl, 14); m = I.macd(cl)
    e1 = I.ema(cl, 12); e2 = I.ema(cl, 26)
    if r is None or m is None or e1 is None:
        return NO
    bull = sum([r > 50, m["hist"] > 0, e1 > e2])
    bear = sum([r < 50, m["hist"] < 0, e1 < e2])
    if bull == 3:
        return _res("call", 70, ["RSI>50", "MACD positivo", "EMA bullish"], "LOW")
    if bear == 3:
        return _res("put", 70, ["RSI<50", "MACD negativo", "EMA bearish"], "LOW")
    return NO


# 13. Price Action (engolfo / martelo / pin bar / 3 soldados)
def s_price_action(c):
    if len(c) < 4:
        return NO
    a, b = c[-2], c[-1]
    if I.is_bear(a) and I.is_bull(b) and b["close"] > a["open"] and b["open"] < a["close"]:
        return _res("call", 66, ["engolfo bullish (Nison)"])
    if I.is_bull(a) and I.is_bear(b) and b["close"] < a["open"] and b["open"] > a["close"]:
        return _res("put", 66, ["engolfo bearish (Nison)"])
    rng = b["high"] - b["low"]
    if rng:
        lower = min(b["open"], b["close"]) - b["low"]
        upper = b["high"] - max(b["open"], b["close"])
        if lower > 2 * abs(I.body(b)) and upper < 0.3 * rng:
            return _res("call", 61, ["martelo/pin bar bullish"])
        if upper > 2 * abs(I.body(b)) and lower < 0.3 * rng:
            return _res("put", 61, ["shooting star/pin bar bearish"])
    t = c[-3:]
    if all(I.is_bull(x) for x in t) and t[0]["close"] < t[1]["close"] < t[2]["close"]:
        return _res("call", 63, ["três soldados brancos"])
    if all(I.is_bear(x) for x in t) and t[0]["close"] > t[1]["close"] > t[2]["close"]:
        return _res("put", 63, ["três corvos negros"])
    return NO


# 14. Adaptive (escolhe reversão vs momentum consoante ADX)
def s_adaptive(c):
    a = I.adx(c, 14)
    if a is None:
        return NO
    if a["adx"] > 25:  # mercado em tendência → momentum
        if a["plus_di"] > a["minus_di"] and I.is_bull(c[-1]):
            return _res("call", 62, [f"ADX {a['adx']:.0f}: tendência forte +DI"], "MEDIUM")
        if a["minus_di"] > a["plus_di"] and I.is_bear(c[-1]):
            return _res("put", 62, [f"ADX {a['adx']:.0f}: tendência forte -DI"], "MEDIUM")
    else:  # range → reversão à média
        return s_mean_reversion(c)
    return NO


# 15. AI Ensemble — voto ponderado de todas as estratégias
def s_ai_ensemble(c):
    votes, reasons = {"call": 0.0, "put": 0.0}, []
    for sid, s in STRATEGIES.items():
        if s["fn"] is s_ai_ensemble:
            continue
        r = s["fn"](c)
        if r["signal"]:
            votes[r["signal"]] += r["confidence"]
            reasons.append(f"{sid}:{r['signal']}")
    total = votes["call"] + votes["put"]
    if total < 180:  # exige consenso mínimo
        return NO
    sig = "call" if votes["call"] > votes["put"] else "put"
    conf = int(100 * max(votes.values()) / total)
    return _res(sig, min(90, conf), [f"consenso {len(reasons)} estratégias"] + reasons[:5],
                "LOW" if conf > 70 else "MEDIUM")


# 16. Candlestick Pattern Scanner — os padrões das cheatsheets
def s_candle_patterns(c):
    from . import patterns
    found = patterns.detect_candle_patterns(c)
    if not found:
        return NO
    score = sum((1 if p["direction"] == "call" else -1) * p["strength"] for p in found)
    if abs(score) < 0.4:
        return NO
    top = sorted(found, key=lambda p: -p["strength"])[:3]
    return _res("call" if score > 0 else "put",
                min(85, int(40 + abs(score) * 30)),
                [f"{p['pattern']} ({p['direction']})" for p in top],
                "MEDIUM" if abs(score) < 1 else "LOW")


# 17. Chart Patterns — H&S, double top/bottom, triângulos, wedges, flags
def s_chart_patterns(c):
    from . import patterns
    found = patterns.detect_chart_patterns(c)
    if not found:
        return NO
    score = sum((1 if p["direction"] == "call" else -1) * p["strength"] for p in found)
    if abs(score) < 0.5:
        return NO
    top = sorted(found, key=lambda p: -p["strength"])[:3]
    return _res("call" if score > 0 else "put",
                min(85, int(45 + abs(score) * 30)),
                [f"{p['pattern']}" for p in top],
                "MEDIUM" if abs(score) < 1 else "LOW")


# 18. AI Turbo — sinal por pontuação contínua (sempre dá direção; p/ ciclos de 30s)
def s_ai_turbo(c):
    cl = closes(c)
    score, reasons = 0.0, []
    r = I.rsi(cl, 14)
    if r is not None:
        score += (r - 50) / 50 * 1.2
        reasons.append(f"RSI {r:.0f}")
    m = I.macd(cl)
    if m and m["hist"] is not None:
        score += (1.0 if m["hist"] > 0 else -1.0) * 0.8
        reasons.append("MACD+" if m["hist"] > 0 else "MACD-")
    e1 = I.ema(cl, 9); e2 = I.ema(cl, 21)
    if e1 and e2:
        score += (1.0 if e1 > e2 else -1.0)
        reasons.append("EMA9>21" if e1 > e2 else "EMA9<21")
    if len(cl) >= 6:
        mom = (cl[-1] - cl[-5]) / cl[-5]
        score += max(-1.5, min(1.5, mom * 500))
        reasons.append(f"mom {mom*100:+.2f}%")
    last = c[-1]
    if I.is_bull(last):
        score += 0.5
    elif I.is_bear(last):
        score -= 0.5
    try:
        from . import patterns
        found = patterns.detect_candle_patterns(c[-8:])
        ps = sum((1 if p["direction"] == "call" else -1) * p["strength"]
                 for p in found)
        score += ps
        if found:
            reasons.append(found[-1]["pattern"])
    except Exception:
        pass
    conf = int(min(95, 45 + abs(score) * 18))
    sig = "call" if score > 0 else "put"
    return _res(sig, conf, reasons or ["médio de scores"], "MEDIUM")


STRATEGIES = {
    "trend_following": {"name": "Trend Following", "fn": s_trend_following,
                        "desc": "Segue a tendência definida por SMA20/SMA50 (Covel).", "min_candles": 55},
    "ma_cross": {"name": "Moving Average Cross", "fn": s_ma_cross,
                 "desc": "Cruzamento de médias simples 9/21.", "min_candles": 25},
    "rsi_momentum": {"name": "RSI Momentum", "fn": s_rsi_momentum,
                     "desc": "Momentum confirmado por RSI (Wilder).", "min_candles": 20},
    "macd_momentum": {"name": "MACD Momentum", "fn": s_macd_momentum,
                      "desc": "Cruzamento do histograma MACD (Appel).", "min_candles": 40},
    "bollinger": {"name": "Bollinger Bands", "fn": s_bollinger,
                  "desc": "Reversão à média nos extremos das bandas.", "min_candles": 25},
    "support_resistance": {"name": "Support & Resistance", "fn": s_support_resistance,
                           "desc": "Rejeição em suportes/resistências de 30 velas.", "min_candles": 32},
    "breakout": {"name": "Breakout", "fn": s_breakout,
                 "desc": "Rutura do máximo/mínimo de 25 velas.", "min_candles": 28},
    "mean_reversion": {"name": "Mean Reversion", "fn": s_mean_reversion,
                       "desc": "Regressão à média de 20 períodos.", "min_candles": 22},
    "volatility": {"name": "Volatility", "fn": s_volatility,
                   "desc": "Spikes de ATR com direção da vela.", "min_candles": 20},
    "momentum": {"name": "Momentum (ROC)", "fn": s_momentum,
                 "desc": "Rate of change de 10 períodos.", "min_candles": 15},
    "ema_trend": {"name": "EMA Trend", "fn": s_ema_trend,
                  "desc": "Cruzamento EMA12/EMA26.", "min_candles": 30},
    "multi_indicator": {"name": "Multi-Indicator Confirmation", "fn": s_multi_indicator,
                        "desc": "Consenso RSI + MACD + EMA.", "min_candles": 40},
    "price_action": {"name": "Price Action", "fn": s_price_action,
                     "desc": "Padrões de velas Nison (engolfo, martelo, pin bar, 3 soldados).", "min_candles": 8},
    "adaptive": {"name": "Adaptive Strategy", "fn": s_adaptive,
                 "desc": "Alterna momentum/reversão consoante o ADX.", "min_candles": 35},
    "ai_ensemble": {"name": "AI Ensemble", "fn": s_ai_ensemble,
                    "desc": "Voto ponderado de todas as estratégias.", "min_candles": 55},
    "candle_patterns": {"name": "Candlestick Patterns", "fn": s_candle_patterns,
                        "desc": "Scanner dos ~70 padrões de velas das cheatsheets "
                                "(engulfing, doji, harami, stars, soldados, gaps…).",
                        "min_candles": 20},
    "chart_patterns": {"name": "Chart Patterns", "fn": s_chart_patterns,
                       "desc": "Padrões gráficos: H&S, double/triple top, triângulos, "
                               "wedges, flags, cup & handle.",
                       "min_candles": 60},
    "ai_turbo": {"name": "AI Turbo (35s)", "fn": s_ai_turbo,
                 "desc": "Score contínuo RSI+MACD+EMA+momentum+velas — sempre dá "
                         "direção; feita para o ciclo 30s análise + 5s entrada.",
                 "min_candles": 40},
}
