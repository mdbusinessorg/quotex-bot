"""API + servidor do painel.

    python -m app.main  →  http://localhost:8000

Auth: login local simples (BOT_PASSWORD env ou 'devin' por defeito) → token em memória.
"""

import secrets
import os
import time
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import history
from .analytics import market_analysis
from .backtest import run_backtest
from .broker import ASSETS
from .engine import engine
from .knowledge import KNOWLEDGE
from .risk import risk
from .strategies import STRATEGIES

import logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Quotex Trading Platform")
STATIC = Path(__file__).resolve().parent.parent / "static"


@app.on_event("startup")
async def _auto_connect():
    """Se QUOTEX_SSID ou QUOTEX_EMAIL/QUOTEX_PASSWORD estiverem definidos, liga
    automaticamente ao arrancar (conta já logada)."""
    import os, asyncio
    engine._main_loop = asyncio.get_running_loop()
    ssid = history.kv_get("ssid") or os.getenv("QUOTEX_SSID")
    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")
    account = history.kv_get("account") or os.getenv("QUOTEX_ACCOUNT", "REAL")
    if ssid or (email and password):
        async def _retry():
            log = logging.getLogger("startup")
            for i in range(24):  # ~2h de tentativas (a cada 5 min)
                if engine.connected:
                    return
                try:
                    ok, msg = await engine.connect_real(
                        email, password, ssid, account)
                    log.info("auto-connect t%d: %s %s", i, ok, msg)
                    if ok:
                        return
                except Exception as e:
                    log.warning("auto-connect t%d falhou: %s", i, e)
                await asyncio.sleep(300)
        try:
            ok, msg = await engine.connect_real(email, password, ssid, account)
            logging.getLogger("startup").info("auto-connect: %s %s", ok, msg)
        except Exception as e:
            logging.getLogger("startup").warning("auto-connect falhou: %s", e)
        if not engine.connected:
            asyncio.create_task(_retry())

BOT_PASSWORD = os.getenv("BOT_PASSWORD", "devin")
TOKENS = set()


def auth(req: Request):
    tok = req.headers.get("x-token") or req.query_params.get("token")
    if tok not in TOKENS:
        raise HTTPException(401, "não autenticado")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


class LoginBody(BaseModel):
    password: str


@app.post("/api/auth/login")
def login(b: LoginBody):
    if b.password != BOT_PASSWORD:
        raise HTTPException(401, "password errada")
    tok = secrets.token_hex(16)
    TOKENS.add(tok)
    return {"token": tok}


class BrokerLogin(BaseModel):
    email: str | None = None
    password: str | None = None
    ssid: str | None = None
    account: str = "REAL"


@app.post("/api/broker/connect")
async def broker_connect(b: BrokerLogin, _=Depends(auth)):
    ok, msg = await engine.connect_real(b.email, b.password, b.ssid, b.account)
    if ok:
        if b.ssid:
            history.kv_set("ssid", b.ssid)
        history.kv_set("account", b.account)
    return {"ok": ok, "msg": str(msg), "balance": await engine.balance()}


@app.post("/api/broker/account/{mode}")
async def broker_account(mode: str, _=Depends(auth)):
    await engine.set_account(mode.upper())
    history.kv_set("account", mode.upper())
    return {"ok": True, "balance": await engine.balance()}


@app.get("/api/status")
async def status(_=Depends(auth)):
    st = engine.status()
    st["balance"] = await engine.balance()
    return st


@app.get("/api/diag")
async def diag(_=Depends(auth)):
    """Testa o handshake WS e a autorização SSID na Quotex; devolve as mensagens cruas do servidor."""
    import asyncio
    out = {}
    try:
        from curl_cffi.requests import AsyncSession
    except ImportError as e:
        return {"error": f"curl_cffi em falta: {e}"}
    ssid = os.getenv("QUOTEX_SSID", "")
    urls = [
        "wss://ws2.quotex.com/socket.io/?EIO=3&transport=websocket",
        "wss://ws2.quotex.com/socket.io/?EIO=4&transport=websocket",
    ]
    for u in urls:
        rec = {"msgs": []}
        try:
            s = AsyncSession(impersonate="chrome")
            ws = await s.ws_connect(u, timeout=15, headers={
                "Origin": "https://quotex.com",
                "Referer": "https://quotex.com/pt/trade",
                "Cookie": "lang=pt"})
            try:
                hello = await asyncio.wait_for(ws.recv(), 8)
                rec["hello"] = str(hello[0])[:120]
                if ssid:
                    await ws.send_str("40")
                    try:
                        m40 = await asyncio.wait_for(ws.recv(), 5)
                        rec["after40"] = str(m40[0])[:120]
                    except Exception as e:
                        rec["after40_err"] = str(e)[:120]
                    await ws.send_str('42["authorization",{"session":"%s","isDemo":1,"tournamentId":0}]' % ssid)
                    for _ in range(6):
                        try:
                            m = await asyncio.wait_for(ws.recv(), 6)
                            rec["msgs"].append(str(m[0])[:200])
                            if "uthoriz" in str(m[0]) or "eject" in str(m[0]):
                                break
                        except Exception as e:
                            rec["msgs"].append(f"recv-timeout/err: {e}")
                            break
                await ws.close()
            except Exception as e:
                rec["after_hello_err"] = str(e)[:160]
        except Exception as e:
            rec["err"] = str(e)[:160]
        out[u] = rec
    libtest = {}
    try:
        import traceback
        from .broker import QuotexAdapter
        ad = QuotexAdapter(email=os.getenv("QUOTEX_EMAIL"),
                           password=os.getenv("QUOTEX_PASSWORD"),
                           ssid=os.getenv("QUOTEX_SSID"))
        try:
            res = await asyncio.wait_for(ad.connect(), 90)
            libtest["connect"] = str(res)
        except Exception as e:
            libtest["connect_exc"] = f"{type(e).__name__}: {e}"
            libtest["tb"] = traceback.format_exc()[-1500:]
        try:
            api = getattr(ad.client, "api", None)
            if api is not None:
                libtest["state"] = {
                    "err": getattr(api.state, "websocket_error_reason", None),
                    "auth": str(getattr(api.state, "auth_status", None)),
                    "ssid": bool(getattr(api.state, "SSID", None)),
                }
        except Exception as e:
            libtest["state_exc"] = str(e)
    except Exception as e:
        libtest["import_exc"] = f"{type(e).__name__}: {e}"
    return {"ssid_set": bool(ssid), "tests": out, "lib": libtest}


@app.get("/api/assets")
def assets(_=Depends(auth)):
    from .broker import REAL_ASSETS
    if engine.connected and engine.broker.mode == "REAL":
        return REAL_ASSETS
    return list(ASSETS.keys())


@app.get("/api/strategies")
def strategies(_=Depends(auth)):
    return {k: {"name": v["name"], "desc": v["desc"]} for k, v in STRATEGIES.items()}


class ManualTrade(BaseModel):
    asset: str
    amount: float
    expiry: int
    direction: str
    strategy: str = "manual"


@app.post("/api/trades")
async def trade(b: ManualTrade, _=Depends(auth)):
    if b.direction not in ("call", "put"):
        raise HTTPException(400, "direction inválida")
    try:
        t = await engine.manual_trade(b.asset, b.amount, b.expiry, b.direction, b.strategy)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "trade": t}


@app.get("/api/trades")
def trades(asset: str | None = None, strategy: str | None = None,
           result: str | None = None, days: int | None = None, _=Depends(auth)):
    return history.list_trades(asset, strategy, result, days)


@app.get("/api/history/stats")
def stats(_=Depends(auth)):
    return {"by_strategy": history.stats_by_strategy(),
            "today": history.summary(days=1), "all": history.summary()}


class AutoCfg(BaseModel):
    asset: str = "EURUSD_otc"
    amount: float = 10
    expiry: int = 60
    strategy: str = "ai_turbo"
    min_confidence: int = 40
    analyze_sec: int = 30
    enter_delay: int = 5
    regime_filter: bool = False
    strategy_map: dict[str, str] | None = None


@app.post("/api/autobot/start")
def ab_start(cfg: AutoCfg, _=Depends(auth)):
    engine.autobot_start(cfg.dict())
    return {"ok": True}


@app.post("/api/autobot/stop")
def ab_stop(_=Depends(auth)):
    engine.autobot_stop()
    return {"ok": True}


@app.post("/api/risk")
def set_risk(cfg: dict, _=Depends(auth)):
    return {"ok": True, "config": risk.configure(**cfg)}


@app.post("/api/risk/resume")
def risk_resume(_=Depends(auth)):
    risk.resume()
    return {"ok": True}


@app.get("/api/analysis/{asset}")
async def analysis(asset: str, _=Depends(auth)):
    candles = await engine.broker.get_candles(asset, 60, 120)
    if not candles:
        return {"error": "sem dados"}
    return market_analysis(candles)


class BacktestReq(BaseModel):
    strategy: str
    asset: str = "EURUSD"
    n_candles: int = 500
    amount: float = 10
    expiry_candles: int = 5


@app.post("/api/backtest")
def backtest(b: BacktestReq, _=Depends(auth)):
    return run_backtest(b.strategy, b.asset, b.n_candles, 60, b.amount, b.expiry_candles)


@app.get("/api/knowledge")
def knowledge(_=Depends(auth)):
    return KNOWLEDGE


@app.get("/api/profile")
async def profile(_=Depends(auth)):
    """Dados do utilizador logado na Quotex (saldos demo/real)."""
    from .broker import QuotexAdapter
    if isinstance(engine.broker, QuotexAdapter):
        prof = await engine.broker.get_profile()
        prof["connected"] = True
        prof["current_balance"] = await engine.balance()
        return prof
    return {"connected": False, "broker_mode": "SIM",
            "balance": await engine.balance()}


@app.get("/api/candles/{asset}")
async def candles_ep(asset: str, period: int = 60, n: int = 120, _=Depends(auth)):
    """Candles em tempo real para o gráfico do painel."""
    rows = await engine.broker.get_candles(asset, period, n)
    return {"asset": asset, "period": period, "candles": rows}


@app.get("/api/patterns/{asset}")
async def patterns_ep(asset: str, period: int = 60, _=Depends(auth)):
    from . import patterns
    rows = await engine.broker.get_candles(asset, period, 150)
    if not rows:
        return {"error": "sem dados"}
    return patterns.scan_candles(rows)


@app.get("/api/signals")
async def signals_ep(min_conf: int = 50, _=Depends(auth)):
    """Varredura em tempo real de todos os pares — sinais para entrada manual."""
    from .broker import REAL_ASSETS
    import asyncio
    # Precisão: sinal só aparece com confluência de estratégias independentes
    VOTERS = ["ai_turbo", "multi_indicator", "rsi_momentum", "macd_momentum",
              "momentum", "bible_sr", "price_action", "breakout"]
    need = max(STRATEGIES[k]["min_candles"] for k in VOTERS) + 60
    import time as _t
    assets = ([a for a in REAL_ASSETS if engine.bad_assets.get(a, 0) < _t.time()]
              if engine.broker.mode == "REAL" else list(ASSETS))

    async def scan(a):
        try:
            cds = await engine.broker.get_candles(a, 60, need)
            if not cds:
                return None
            votes = {"call": 0, "put": 0}
            confs = {"call": [], "put": []}
            why = []
            for k in VOTERS:
                st = STRATEGIES[k]
                r = st["fn"](cds[-(st["min_candles"] + 45):])
                if not r["signal"]:
                    continue
                votes[r["signal"]] += 1
                confs[r["signal"]].append(r["confidence"])
                why.append(f"{st['name']}: {r['signal']} {r['confidence']}%")
            sig = "call" if votes["call"] > votes["put"] else "put"
            n = votes[sig]
            # >=3 votos E maioria clara (o resto não pode discordar mais)
            if n < 3 or n <= votes["put" if sig == "call" else "call"] * 2:
                return None
            conf = int(sum(confs[sig]) / len(confs[sig]))
            conf = min(96, conf + (n - 3) * 4)
            return {"asset": a, "signal": sig, "confidence": conf,
                    "votes": f"{n}/{len(VOTERS)}",
                    "action": "COMPRAR AGORA" if sig == "call" else "VENDER AGORA",
                    "reasons": why[:6],
                    "suggested_expiry": 300}
        except Exception:
            return None

    rows = [x for x in await asyncio.gather(*[scan(a) for a in assets]) if x]
    rows = [r for r in rows if r["confidence"] >= min_conf]
    rows.sort(key=lambda r: -r["confidence"])
    return {"signals": rows, "scanned": len(assets),
            "ts": __import__("time").time()}


@app.get("/api/ai/insight/{asset}")
async def ai_insight_ep(asset: str, _=Depends(auth)):
    from . import patterns, ai
    rows = await engine.broker.get_candles(asset, 60, 150)
    if not rows:
        return {"error": "sem dados"}
    pat = patterns.scan_candles(rows)
    ana = market_analysis(rows)
    return ai.ai_insight(asset, rows, pat, ana)


app.mount("/static", StaticFiles(directory=STATIC), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
