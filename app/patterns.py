"""Deteção de padrões de candles (cheatsheet Nison/Bulkowski) e padrões
gráficos de preço (H&S, double top/bottom, triângulos, wedges, flags).

Cada detetor recebe uma lista de candles dict {time,open,high,low,close}
e devolve {"pattern", "direction" ("call"|"put"), "strength" 0-1,
"note"}. scan_candles agrega tudo.
"""
import math


def _b(c):  # body
    return c["close"] - c["open"]

def _rng(c):  # range total
    return max(c["high"] - c["low"], 1e-10)

def _ush(c):  # upper shadow
    return c["high"] - max(c["open"], c["close"])

def _lsh(c):  # lower shadow
    return min(c["open"], c["close"]) - c["low"]

def _bull(c):
    return c["close"] > c["open"]

def _bear(c):
    return c["close"] < c["open"]

def _avg_body(cds, n=14):
    seg = cds[-n - 1:-1]
    return sum(abs(_b(c)) for c in seg) / max(len(seg), 1)


def _trend(cds, n=10):
    """'up' | 'down' | 'flat' dos últimos n candles antes do último."""
    if len(cds) < n + 2:
        return "flat"
    a, b = cds[-n - 1]["close"], cds[-2]["close"]
    if b > a * 1.0005:
        return "up"
    if b < a * 0.9995:
        return "down"
    return "flat"


# ---------------------------------------------------------- candles

def detect_candle_patterns(cds):
    out = []
    if len(cds) < 5:
        return out
    c = cds[-1]
    p = cds[-2]
    p2 = cds[-3] if len(cds) >= 3 else p
    tr = _trend(cds)
    ab = _avg_body(cds)
    body = abs(_b(c))
    rng = _rng(c)

    def add(name, direction, strength=0.6, note=""):
        out.append({"pattern": name, "direction": direction,
                    "strength": round(strength, 2), "note": note})

    # --- padrões de 1 candle ---
    if body <= rng * 0.1:
        if _ush(c) < rng * 0.1 and _lsh(c) > rng * 0.6:
            add("Dragonfly Doji", "call" if tr == "down" else "call", 0.55, "reversão de fundo")
        elif _lsh(c) < rng * 0.1 and _ush(c) > rng * 0.6:
            add("Gravestone Doji", "put", 0.55, "reversão de topo")
        elif _ush(c) > rng * 0.4 and _lsh(c) > rng * 0.4:
            add("Long Legged Doji", "put" if tr == "up" else "call", 0.4, "indecisão extrema")
        else:
            add("Doji", "put" if tr == "up" else "call", 0.35, "indecisão")
    if body >= rng * 0.9 and body > ab * 1.5:
        add("Marubozu Bullish" if _bull(c) else "Marubozu Bearish",
            "call" if _bull(c) else "put", 0.7, "corpo cheio — momentum")
    if _lsh(c) > body * 2 and _ush(c) < body * 0.7 and body > 0:
        if tr == "down" and _bull(c):
            add("Hammer", "call", 0.7, "reversão de fundo")
        elif tr == "up":
            add("Hanging Man", "put", 0.6, "reversão de topo")
    if _ush(c) > body * 2 and _lsh(c) < body * 0.7 and body > 0:
        if tr == "up" and _bear(c):
            add("Shooting Star", "put", 0.7, "reversão de topo")
        elif tr == "down":
            add("Inverted Hammer", "call", 0.55, "reversão de fundo")
    if body < ab * 0.4 and _ush(c) > body and _lsh(c) > body and body > 0:
        add("Spinning Top", "call" if tr == "down" else "put", 0.35, "indecisão")
    if rng > sum(_rng(x) for x in cds[-15:-1]) / 14 * 2 and body < rng * 0.3:
        add("High Wave", "put" if tr == "up" else "call", 0.4, "confusão/volatilidade")

    # --- padrões de 2 candles ---
    if _bear(p) and _bull(c) and c["close"] > p["open"] and c["open"] < p["close"]:
        add("Bullish Engulfing", "call", 0.75, "engolfo de alta")
    if _bull(p) and _bear(c) and c["close"] < p["open"] and c["open"] > p["close"]:
        add("Bearish Engulfing", "put", 0.75, "engolfo de baixa")
    if _bear(p) and _bull(c) and c["open"] > p["open"] and c["close"] < p["close"]:
        add("Bullish Harami", "call", 0.55, "compressão de alta")
    if _bull(p) and _bear(c) and c["open"] < p["open"] and c["close"] > p["close"]:
        add("Bearish Harami", "put", 0.55, "compressão de baixa")
    if _bear(p) and _bull(c) and c["close"] > (p["open"] + p["close"]) / 2 and c["close"] < p["open"]:
        add("Piercing Bullish", "call", 0.65, "perfuração")
    if _bull(p) and _bear(c) and c["close"] < (p["open"] + p["close"]) / 2 and c["close"] > p["open"]:
        add("Dark Cloud Cover", "put", 0.65, "cobertura de nuvem negra")
    if abs(c["low"] - p["low"]) < rng * 0.05 and tr == "down":
        add("Tweezer Bottom", "call", 0.5, "duplo fundo de pavio")
    if abs(c["high"] - p["high"]) < rng * 0.05 and tr == "up":
        add("Tweezer Top", "put", 0.5, "duplo topo de pavio")
    if _bear(p) and _bull(c) and c["open"] > p["close"] and c["close"] > p["open"]:
        add("Kicking Bullish", "call", 0.8, "reversão forte")
    if _bull(p) and _bear(c) and c["open"] < p["close"] and c["close"] < p["open"]:
        add("Kicking Bearish", "put", 0.8, "reversão forte")
    if _bull(p) and _bull(c) and abs(c["open"] - p["open"]) / rng < 0.15 and abs(c["close"] - p["close"]) / rng < 0.15:
        add("Bullish Meeting Line", "call", 0.4, "continuação")
    if tr == "up" and body < ab * 0.5 and c["low"] > p["high"]:
        add("Doji Gapping Up", "call", 0.5, "exaustão de topo")
    if tr == "down" and body < ab * 0.5 and c["high"] < p["low"]:
        add("Doji Gapping Down", "call", 0.5, "exaustão de fundo")
    if _bear(p) and _bull(c) and c["open"] < p["low"] and c["close"] > p["close"] and c["close"] < p["open"]:
        add("Bullish Belt Hold", "call", 0.5, "reversão")
    if _bull(p) and _bear(c) and c["open"] > p["high"] and c["close"] < p["open"] and c["close"] > p["close"]:
        add("Bearish Belt Hold", "put", 0.5, "reversão")

    # --- padrões de 3 candles ---
    if len(cds) >= 3:
        a1, a2, a3 = p2, p, c
        if (_bull(a1) and abs(_b(a2)) <= _rng(a2) * 0.25 and _bull(a3)
                and a3["close"] > a1["close"] and tr == "down"):
            add("Morning Star", "call", 0.75, "reversão de fundo")
        if (_bear(a1) and abs(_b(a2)) <= _rng(a2) * 0.25 and _bear(a3)
                and a3["close"] < a1["close"] and tr == "up"):
            add("Evening Star", "put", 0.75, "reversão de topo")
        if (all(_bull(x) for x in (a1, a2, a3))
                and a2["open"] > a1["open"] and a3["open"] > a2["open"]
                and a3["close"] > a2["close"] > a1["close"]):
            add("Three White Soldiers", "call", 0.8, "subida sustentada")
        if (all(_bear(x) for x in (a1, a2, a3))
                and a2["open"] < a1["open"] and a3["open"] < a2["open"]
                and a3["close"] < a2["close"] < a1["close"]):
            add("Three Black Crows", "put", 0.8, "queda sustentada")
        if (_bear(a1) and _bear(a2) and a2["open"] > a1["close"] and a2["close"] < a1["close"]
                and _bull(a3) and a3["close"] > a1["open"]):
            add("Three Inside Up", "call", 0.6, "reversão")
        if (_bull(a1) and _bull(a2) and a2["open"] < a1["close"] and a2["close"] > a1["close"]
                and _bear(a3) and a3["close"] < a1["open"]):
            add("Three Inside Down", "put", 0.6, "reversão")
        if (_bear(a1) and _bull(a2) and a2["open"] < a1["close"] and a2["close"] > a1["open"]
                and _bull(a3) and a3["close"] > a2["close"]):
            add("Three Outside Up", "call", 0.6, "reversão")
        if (_bull(a1) and _bear(a2) and a2["open"] > a1["close"] and a2["close"] < a1["open"]
                and _bear(a3) and a3["close"] < a2["close"]):
            add("Three Outside Down", "put", 0.6, "reversão")
        if (_bull(a1) and _bull(a2) and _bear(a3)
                and abs(_b(a3)) > abs(_b(a1)) + abs(_b(a2))
                and a3["close"] < a1["open"]):
            add("Three Line Strike Bearish", "call", 0.45, "exaustão de venda")
        if (all(_bull(x) for x in (a1, a2, a3)) and a3["open"] > a2["high"]
                and _ush(a3) > abs(_b(a3)) * 1.5):
            add("Advance Block", "put", 0.55, "perda de momentum")
        if (_bull(a1) and _bull(a2) and a3["open"] < a2["open"]
                and _bull(a3) and a3["close"] > a2["close"]):
            add("Mat Hold", "call", 0.55, "continuação de alta")

    # janelas/gaps (8 new lines, breakaway…)
    if c["low"] > p["high"]:
        add("Gap Up / Window Rising", "call" if tr == "up" else "call", 0.5, "janela de alta")
    if c["high"] < p["low"]:
        add("Gap Down / Window Falling", "put" if tr == "down" else "put", 0.5, "janela de baixa")

    return out


# ---------------------------------------------------------- swings / chart patterns

def _pivots(cds, left=3, right=3):
    highs, lows = [], []
    for i in range(left, len(cds) - right):
        h = cds[i]["high"]
        l = cds[i]["low"]
        if all(h >= cds[j]["high"] for j in range(i - left, i + right + 1) if j != i):
            highs.append((i, h))
        if all(l <= cds[j]["low"] for j in range(i - left, i + right + 1) if j != i):
            lows.append((i, l))
    return highs, lows


def _slope(pts):
    n = len(pts)
    if n < 2:
        return 0.0
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    xm, ym = sum(xs) / n, sum(ys) / n
    den = sum((x - xm) ** 2 for x in xs) or 1
    return sum((x - xm) * (y - ym) for x, y in pts) / den


def detect_chart_patterns(cds):
    out = []
    if len(cds) < 40:
        return out
    hi, lo = _pivots(cds)
    last_close = cds[-1]["close"]

    def add(name, direction, strength=0.6, note=""):
        out.append({"pattern": name, "direction": direction,
                    "strength": round(strength, 2), "note": note})

    # Double / Triple top-bottom
    if len(hi) >= 2:
        (i1, h1), (i2, h2) = hi[-2], hi[-1]
        if abs(h1 - h2) / max(h1, 1e-9) < 0.002 and i2 - i1 >= 8 and last_close < min(h1, h2) - 0.001 * h1:
            add("Double Top", "put", 0.7, "dois topos + quebra do suporte")
        if len(hi) >= 3:
            (i0, h0), (i1, h1), (i2, h2) = hi[-3], hi[-2], hi[-1]
            if max(h0, h1, h2) - min(h0, h1, h2) < 0.003 * h1 and last_close < h2:
                add("Triple Top", "put", 0.65, "três topos")
    if len(lo) >= 2:
        (i1, l1), (i2, l2) = lo[-2], lo[-1]
        if abs(l1 - l2) / max(l1, 1e-9) < 0.002 and i2 - i1 >= 8 and last_close > max(l1, l2) + 0.001 * l1:
            add("Double Bottom", "call", 0.7, "dois fundos + quebra da resistência")
        if len(lo) >= 3:
            (i0, l0), (i1, l1), (i2, l2) = lo[-3], lo[-2], lo[-1]
            if max(l0, l1, l2) - min(l0, l1, l2) < 0.003 * l1 and last_close > l2:
                add("Triple Bottom", "call", 0.65, "três fundos")

    # Head & Shoulders (3 topos, o do meio mais alto + neckline)
    if len(hi) >= 3 and len(lo) >= 2:
        (i1, h1), (i2, h2), (i3, h3) = hi[-3], hi[-2], hi[-1]
        if h2 > h1 and h2 > h3 and abs(h1 - h3) / h2 < 0.02:
            neck = min(x[1] for x in lo if x[0] > i1 and x[0] < i3) if any(i1 < x[0] < i3 for x in lo) else None
            if neck and last_close < neck:
                add("Head & Shoulders", "put", 0.75, "quebra da neckline")
            elif neck:
                add("Head & Shoulders (formação)", "put", 0.45, "ombro direito formado")
        if len(lo) >= 3:
            (j1, l1), (j2, l2), (j3, l3) = lo[-3], lo[-2], lo[-1]
            if l2 < l1 and l2 < l3 and abs(l1 - l3) / l2 < 0.02:
                necks = [x[1] for x in hi if j1 < x[0] < j3]
                if necks and last_close > min(necks):
                    add("Inverted Head & Shoulders", "call", 0.75, "quebra da neckline")

    # Triângulos / wedges via regressão dos pivôs recentes
    rh, rl = hi[-5:], lo[-5:]
    if len(rh) >= 3 and len(rl) >= 3:
        sh, sl = _slope(rh), _slope(rl)
        span = rh[-1][1] - rl[-1][1]
        if abs(sh) < span * 0.02 and sl > span * 0.02:
            add("Ascending Triangle", "call", 0.6, "resistência plana + fundos a subir")
        elif abs(sl) < span * 0.02 and sh < -span * 0.02:
            add("Descending Triangle", "put", 0.6, "suporte plano + topos a descer")
        elif sh < 0 and sl > 0:
            add("Symmetrical Triangle", "call" if _trend(cds, 20) == "up" else "put",
                0.5, "consolidação — seguir a quebra")
        elif sh > 0 and sl > 0 and sh < sl:
            add("Rising Wedge", "put", 0.6, "cunha ascendente — reversão de baixa")
        elif sh < 0 and sl < 0 and abs(sh) < abs(sl):
            add("Falling Wedge", "call", 0.6, "cunha descendente — reversão de alta")
        elif abs(sh) < span * 0.02 and abs(sl) < span * 0.02:
            add("Rectangle / Consolidation", "call" if _trend(cds, 20) == "up" else "put",
                0.4, "canal lateral")

    # Flag/pennant: impulso forte + consolidação curta contrária
    if len(cds) >= 30:
        impulse = cds[-30]["close"] - cds[-15]["close"]
        consol = cds[-15:]
        cslope = _slope([(i, c["close"]) for i, c in enumerate(consol)])
        scale = abs(impulse) or 1
        if impulse > 0 and cslope < 0 and abs(cslope) * 15 < scale * 0.5:
            add("Flag Bullish", "call", 0.55, "impulso + consolidação leve")
        if impulse < 0 and cslope > 0 and abs(cslope) * 15 < scale * 0.5:
            add("Flag Bearish", "put", 0.55, "queda + consolidação leve")

    # Cup & Handle (arredondamento + pullback curto) — aproximação
    if len(cds) >= 60:
        seg = cds[-60:]
        mn = min(c["low"] for c in seg)
        imn = [c["low"] for c in seg].index(mn)
        if 15 < imn < 50 and seg[-1]["close"] > (seg[0]["close"] + mn) / 2:
            left_h = seg[0]["close"]
            right_h = max(c["close"] for c in seg[imn:])
            if abs(right_h - left_h) / left_h < 0.02:
                add("Cup & Handle", "call", 0.6, "arredondamento + continuação")
            elif right_h < left_h * 0.99:
                add("Rounding Top", "put", 0.5, "topo arredondado")

    return out


def scan_candles(cds):
    """Scan completo: candle + chart patterns e sinal agregado."""
    cp = detect_candle_patterns(cds)
    gp = detect_chart_patterns(cds)
    allp = cp + gp
    score = sum((1 if p["direction"] == "call" else -1) * p["strength"] for p in allp)
    if score > 0.5:
        agg = "call"
    elif score < -0.5:
        agg = "put"
    else:
        agg = "neutral"
    return {"patterns": allp, "aggregate": agg, "score": round(score, 2),
            "bullish": sum(1 for p in allp if p["direction"] == "call"),
            "bearish": sum(1 for p in allp if p["direction"] == "put")}
