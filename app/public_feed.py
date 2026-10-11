"""Feed público de candles 1m — sem login (Yahoo Finance chart API).

Garante que a análise de sinais continua a disparar mesmo com a sessão da
Quotex em baixo, e cobre os pares para os quais a API de histórico da Quotex
não devolve dados. Só serve análise — as ordens reais continuam a ir pela
ligação autenticada.
"""

import asyncio
import json
import time
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"}

# símbolos Yahoo para activos que não são forex de 6 letras
_SPECIAL = {
    "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD", "LTCUSD": "LTC-USD",
    "XRPUSD": "XRP-USD", "SOLUSD": "SOL-USD", "DOGEUSD": "DOGE-USD",
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
    last = None
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        try:
            url = (f"https://{host}/v8/finance/chart/{sym}"
                   "?interval=1m&range=1d")
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except Exception as e:
            last = e
    raise last or RuntimeError("fetch falhou")


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


_SEM = asyncio.Semaphore(4)   # Yahoo corta rajadas — espaçar pedidos


async def fetch_candles(asset, n=100):
    sym = yahoo_symbol(asset)
    if not sym:
        return []
    try:
        async with _SEM:
            js = await asyncio.to_thread(_fetch, sym)
        return _parse(js)[-n:]
    except Exception:
        return []


# ---------------------------------------------------------------- ticks RT

def _fetch_quotes(syms):
    """Um único pedido batch: último preço de todos os símbolos."""
    url = ("https://query1.finance.yahoo.com/v7/finance/quote?symbols="
           + ",".join(syms))
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _fetch_price1(sym):
    """Fallback: meta do chart v8 traz regularMarketPrice."""
    js = _fetch(sym)
    res = (js.get("chart") or {}).get("result") or []
    if not res:
        return None
    meta = res[0].get("meta") or {}
    return meta.get("regularMarketPrice")


async def fetch_prices(assets):
    """{asset: {"time": ts, "price": p}} — último preço real (forex/cripto/ouro).

    Alimenta o candle de 1m em formação quando não há stream da Quotex,
    para os sinais de moedas atualizarem tão rápido como os de cripto.
    """
    out = {}
    pairs = [(a, yahoo_symbol(a)) for a in assets]
    pairs = [(a, s) for a, s in pairs if s]
    if not pairs:
        return out
    try:
        js = await asyncio.to_thread(_fetch_quotes, [s for _, s in pairs])
        by_sym = {q.get("symbol"): q
                  for q in ((js.get("quoteResponse") or {}).get("result") or [])}
        now = time.time()
        for a, s in pairs:
            q = by_sym.get(s) or {}
            p = q.get("regularMarketPrice")
            if p:
                out[a] = {"time": now, "price": float(p)}
        if out:
            return out
    except Exception:
        pass
    # fallback um-a-um (lento — só se o batch falhar)
    async def one(a, s):
        try:
            async with _SEM:
                p = await asyncio.to_thread(_fetch_price1, s)
            if p:
                out[a] = {"time": time.time(), "price": float(p)}
        except Exception:
            pass
    await asyncio.gather(*[one(a, s) for a, s in pairs])
    return out
