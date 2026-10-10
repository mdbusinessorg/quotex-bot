"""Regime de mercado — filtro "não operar" validado em walk-forward.

Evidência (96h, 69k candles reais, 12 pares OTC, folds 6h):
a banda de volatilidade média (ATR entre percentis 33-66 do histórico
recente) é tóxica em todas as estratégias (~40-47% WR vs breakeven 53,5%).
O filtro rejeita entradas nesse regime; ATR alta ou baixa são mantidas.

Uso idêntico em live (engine) e backtest (_research) — mesma função.
"""


def atr(candles, i, n=14):
    """Average True Range no candle i (0-indexed)."""
    if i < 1:
        return 0.0
    lo = max(0, i - n + 1)
    trs = []
    for j in range(lo, i + 1):
        c = candles[j]
        prev_close = candles[j - 1]["close"]
        trs.append(max(c["high"] - c["low"],
                       abs(c["high"] - prev_close),
                       abs(c["low"] - prev_close)))
    return sum(trs) / len(trs)


def trend_strength(candles, i, n=20):
    """Eficiência do movimento: |deslocamento| / soma(|Δ|). 0=chop, 1=trend."""
    if i < n:
        return 0.0
    net = abs(candles[i]["close"] - candles[i - n]["close"])
    path = sum(abs(candles[j]["close"] - candles[j - 1]["close"])
               for j in range(i - n + 1, i + 1))
    return net / path if path else 0.0


def atr_percentile(candles, i, atr_n=14, window=500):
    """Percentil do ATR atual face aos últimos `window` candles (rolling,
    sem lookahead — só vê o passado)."""
    cur = atr(candles, i, atr_n)
    if cur <= 0:
        return 0.0
    lo = max(1, i - window + 1)
    hist = [atr(candles, j, atr_n) for j in range(lo, i)]
    hist = [h for h in hist if h > 0]
    if not hist:
        return 0.5
    return sum(1 for h in hist if h < cur) / len(hist)


def no_trade_regime(candles, i, lo_pct=0.33, hi_pct=0.66, trend_max=0.50):
    """True quando a entrada deve ser BLOQUEADA pelo regime:
    volatilidade média (ATR pct entre lo/hi) sem tendência forte.
    Parâmetros default = a banda validada no walk-forward."""
    pct = atr_percentile(candles, i)
    if lo_pct <= pct <= hi_pct and trend_strength(candles, i) < trend_max:
        return True
    return False
