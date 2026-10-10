"""Feed público de candles 1m — sem login (Yahoo Finance chart API).

Garante que a análise de sinais continua a disparar mesmo com a sessão da
Quotex em baixo, e cobre os pares para os quais a API de histórico da Quotex
não devolve dados. Só serve análise — as ordens reais continuam a ir pela
ligação autenticada.
"""

import asyncio
import json
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"}

# símbolos Yahoo para activos que não são forex de 6 letras
_SPECIAL = {
    "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD", "LTCUSD": "LTC-USD",
    "XAUUSD": "GC=F", "XAGUSD": "SI=F",
}


def yahoo_symbol(asset):
    a = asset.upper().replace("_OTC", "")
    if a in _SPECIAL:
        return _SPECIAL[a]
    if len(a) == 6 and a.isalpha():
        return a + "=X"
    return None


def _fetch(sym):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           "?interval=1m&range=1d")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _parse(js):
    res = (js.get("chart") or {}).get("result") or []
    if not res:
        return []
    r0 = res[0]
    ts = r0.get("timestamp") or []
    q = ((r0.get("indicators") or {}).get("quote") or [{}])[0]
    out = []
    for i, t in enumerate(ts):
        try:
            c = q["close"][i]
        except Exception:
            c = None
        if c is None:
            continue
        out.append({"time": t,
                    "open": q["open"][i] or c, "high": q["high"][i] or c,
                    "low": q["low"][i] or c, "close": c})
    return out


async def fetch_candles(asset, n=100):
    sym = yahoo_symbol(asset)
    if not sym:
        return []
    try:
        js = await asyncio.to_thread(_fetch, sym)
        return _parse(js)[-n:]
    except Exception:
        return []
