"""Biblioteca de estratégias — 15 setups clássicos da literatura de análise técnica
(Trend Following / Covel, Wilder "New Concepts", Bollinger, George Lane, Nison
"Japanese Candlestick Charting", Elder, Price Action).

Cada estratégia recebe `candles` (lista ordenada antiga->nova de dicts
{"open","high","low","close","time"}) e devolve "call", "put" ou None.

O sinal deve ser avaliado no fecho da vela (última vela completa).
"""

from . import indicators as I


def s_trend_sma_cross(c, p):
    """Trend Following: cruzamento SMA rápida/lenta. Call quando rápida cruza acima."""
    closes = [x["close"] for x in c]
    fast_s = I.sma_series(closes, p["fast"])
    slow_s = I.sma_series(closes, p["slow"])
    if len(fast_s) < 2 or fast_s[-2] is None or slow_s[-2] is None:
        return None
    if fast_s[-2] <= slow_s[-2] and fast_s[-1] > slow_s[-1]:
        return "call"
    if fast_s[-2] >= slow_s[-2] and fast_s[-1] < slow_s[-1]:
        return "put"
    return None


def s_ema_cross(c, p):
    closes = [x["close"] for x in c]
    f = I.ema_series(closes, p["fast"])
    s = I.ema_series(closes, p["slow"])
    if len(f) < 2 or f[-2] is None or s[-2] is None:
        return None
    if f[-2] <= s[-2] and f[-1] > s[-1]:
        return "call"
    if f[-2] >= s[-2] and f[-1] < s[-1]:
        return "put"
    return None


def s_rsi_reversal(c, p):
    """Wilder RSI: reversão à média — compra em sobrevenda, venda em sobrecompra."""
    r = I.rsi([x["close"] for x in c], p["period"])
    if r is None:
        return None
    if r <= p["oversold"]:
        return "call"
    if r >= p["overbought"]:
        return "put"
    return None


def s_rsi_trend(c, p):
    """RSI como filtro de momentum: >55 call, <45 put (confirmação com vela)."""
    r = I.rsi([x["close"] for x in c], p["period"])
    if r is None:
        return None
    last = c[-1]
    if r > 55 and I.is_bull(last):
        return "call"
    if r < 45 and I.is_bear(last):
        return "put"
    return None


def s_bollinger_reversion(c, p):
    """Bollinger: fecho fora da banda -> regressão à média."""
    closes = [x["close"] for x in c]
    b = I.bollinger(closes, p["period"], p["mult"])
    if b is None:
        return None
    lo, mid, hi = b
    if closes[-1] < lo:
        return "call"
    if closes[-1] > hi:
        return "put"
    return None


def s_bollinger_breakout(c, p):
    """Bollinger breakout: fecho acima da banda superior com vela forte -> call."""
    closes = [x["close"] for x in c]
    b = I.bollinger(closes, p["period"], p["mult"])
    if b is None:
        return None
    lo, mid, hi = b
    last = c[-1]
    if closes[-1] > hi and I.is_bull(last):
        return "call"
    if closes[-1] < lo and I.is_bear(last):
        return "put"
    return None


def s_macd_cross(c, p):
    m = I.macd([x["close"] for x in c], p["fast"], p["slow"], p["signal"])
    if m is None or m["prev_hist"] is None:
        return None
    if m["prev_hist"] <= 0 < m["hist"]:
        return "call"
    if m["prev_hist"] >= 0 > m["hist"]:
        return "put"
    return None


def s_stochastic(c, p):
    """Lane Stochastic: %K cruza %D em zonas extremas."""
    st = I.stochastic(c, p["k"], p["d"])
    if st is None:
        return None
    if st["k"] < 20 and st["k"] > st["d"]:
        return "call"
    if st["k"] > 80 and st["k"] < st["d"]:
        return "put"
    return None


def s_engulfing(c, p):
    """Nison: padrão engolfo de 2 velas na última vela fechada."""
    if len(c) < 2:
        return None
    a, b = c[-2], c[-1]
    if I.is_bear(a) and I.is_bull(b) and b["close"] > a["open"] and b["open"] < a["close"]:
        return "call"
    if I.is_bull(a) and I.is_bear(b) and b["close"] < a["open"] and b["open"] > a["close"]:
        return "put"
    return None


def s_hammer_star(c, p):
    """Nison: martelo (fundo) / shooting star (topo)."""
    last = c[-1]
    rng = last["high"] - last["low"]
    if rng == 0:
        return None
    lower_wick = min(last["open"], last["close"]) - last["low"]
    upper_wick = last["high"] - max(last["open"], last["close"])
    if lower_wick > 2 * abs(I.body(last)) and upper_wick < 0.3 * rng:
        return "call"
    if upper_wick > 2 * abs(I.body(last)) and lower_wick < 0.3 * rng:
        return "put"
    return None


def s_three_soldiers(c, p):
    """Nison: três soldados brancos / três corvos negros."""
    if len(c) < 3:
        return None
    t = c[-3:]
    if all(I.is_bull(x) for x in t) and t[0]["close"] < t[1]["close"] < t[2]["close"]:
        return "call"
    if all(I.is_bear(x) for x in t) and t[0]["close"] > t[1]["close"] > t[2]["close"]:
        return "put"
    return None


def s_doji_reversal(c, p):
    """Doji após tendência de 3+ velas: indecisão -> reversão."""
    if len(c) < 4:
        return None
    if not I.is_doji(c[-1], p["tol"]):
        return None
    prev = c[-4:-1]
    if all(I.is_bear(x) for x in prev):
        return "call"
    if all(I.is_bull(x) for x in prev):
        return "put"
    return None


def s_adx_directional(c, p):
    """Wilder ADX: tendência forte (ADX>limiar) + DI dominante define direção."""
    a = I.adx(c, p["period"])
    if a is None or a["adx"] < p["threshold"]:
        return None
    if a["plus_di"] > a["minus_di"] and I.is_bull(c[-1]):
        return "call"
    if a["minus_di"] > a["plus_di"] and I.is_bear(c[-1]):
        return "put"
    return None


def s_ema_pullback(c, p):
    """Pullback à EMA em tendência: preço toca EMA lenta e retoma direção."""
    closes = [x["close"] for x in c]
    e = I.ema_series(closes, p["ema"])
    if len(e) < 3 or e[-1] is None:
        return None
    trend_up = closes[-3] > closes[-6 if len(closes) >= 6 else 0] and e[-1] < closes[-1]
    trend_dn = closes[-3] < closes[-6 if len(closes) >= 6 else 0] and e[-1] > closes[-1]
    prev, last = c[-2], c[-1]
    if trend_up and prev["low"] <= e[-2] and I.is_bull(last):
        return "call"
    if trend_dn and prev["high"] >= e[-2] and I.is_bear(last):
        return "put"
    return None


def s_pinbar(c, p):
    """Price Action: pin bar — pavio longo rejeitando nível."""
    last = c[-1]
    rng = last["high"] - last["low"]
    if rng == 0:
        return None
    b = abs(I.body(last))
    upper = last["high"] - max(last["open"], last["close"])
    lower = min(last["open"], last["close"]) - last["low"]
    if lower >= p["wick_ratio"] * rng and b <= 0.3 * rng:
        return "call"
    if upper >= p["wick_ratio"] * rng and b <= 0.3 * rng:
        return "put"
    return None


STRATEGIES = {
    "sma_cross": {"name": "Cruzamento SMA (Trend Following)", "fn": s_trend_sma_cross,
                  "params": {"fast": 9, "slow": 21}, "min_candles": 25},
    "ema_cross": {"name": "Cruzamento EMA", "fn": s_ema_cross,
                  "params": {"fast": 12, "slow": 26}, "min_candles": 30},
    "rsi_reversal": {"name": "RSI Reversão (Wilder)", "fn": s_rsi_reversal,
                     "params": {"period": 14, "oversold": 30, "overbought": 70}, "min_candles": 20},
    "rsi_trend": {"name": "RSI Momentum", "fn": s_rsi_trend,
                  "params": {"period": 14}, "min_candles": 20},
    "bollinger_reversion": {"name": "Bollinger Reversão à Média", "fn": s_bollinger_reversion,
                            "params": {"period": 20, "mult": 2.0}, "min_candles": 25},
    "bollinger_breakout": {"name": "Bollinger Breakout", "fn": s_bollinger_breakout,
                           "params": {"period": 20, "mult": 2.0}, "min_candles": 25},
    "macd_cross": {"name": "MACD Cruzamento", "fn": s_macd_cross,
                   "params": {"fast": 12, "slow": 26, "signal": 9}, "min_candles": 40},
    "stochastic": {"name": "Estocástico (Lane)", "fn": s_stochastic,
                   "params": {"k": 14, "d": 3}, "min_candles": 20},
    "engulfing": {"name": "Engolfo (Nison)", "fn": s_engulfing,
                  "params": {}, "min_candles": 5},
    "hammer_star": {"name": "Martelo / Shooting Star", "fn": s_hammer_star,
                    "params": {}, "min_candles": 5},
    "three_soldiers": {"name": "Três Soldados / Corvos", "fn": s_three_soldiers,
                       "params": {}, "min_candles": 6},
    "doji_reversal": {"name": "Doji Reversão", "fn": s_doji_reversal,
                      "params": {"tol": 0.1}, "min_candles": 8},
    "adx_directional": {"name": "ADX Direcional (Wilder)", "fn": s_adx_directional,
                        "params": {"period": 14, "threshold": 25}, "min_candles": 35},
    "ema_pullback": {"name": "Pullback à EMA", "fn": s_ema_pullback,
                     "params": {"ema": 20}, "min_candles": 25},
    "pinbar": {"name": "Pin Bar (Price Action)", "fn": s_pinbar,
               "params": {"wick_ratio": 0.6}, "min_candles": 5},
}
