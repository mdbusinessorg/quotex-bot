"""Painel web + API do bot Quotex.

    python -m app.main   →  http://localhost:8000
"""

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import history
from .engine import engine
from .strategies import STRATEGIES

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Quotex Bot")
STATIC = Path(__file__).resolve().parent.parent / "static"


class LoginReq(BaseModel):
    email: str | None = None
    password: str | None = None
    ssid: str | None = None
    account: str = "PRACTICE"


class StartReq(BaseModel):
    asset: str
    amount: float
    expiry: int            # segundos (60, 120, 300...)
    strategy: str


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/api/login")
async def login(req: LoginReq):
    ok, msg = await engine.connect(email=req.email, password=req.password, ssid=req.ssid)
    if ok:
        await engine.set_account(req.account)
        await engine.balance()
    return {"ok": ok, "msg": str(msg), "balance": engine.state.get("balance")}


@app.post("/api/account/{mode}")
async def account(mode: str):
    await engine.set_account(mode.upper())
    await engine.balance()
    return {"ok": True, "balance": engine.state.get("balance")}


@app.get("/api/strategies")
def strategies():
    return {k: {"name": v["name"], "params": v["params"]} for k, v in STRATEGIES.items()}


@app.post("/api/start")
async def start(req: StartReq):
    if req.strategy not in STRATEGIES:
        return {"ok": False, "msg": "Estratégia desconhecida"}
    ok = engine.start(req.dict())
    return {"ok": ok}


@app.post("/api/stop")
async def stop():
    engine.stop()
    return {"ok": True}


@app.get("/api/status")
def status():
    return engine.status()


@app.get("/api/history")
def get_history():
    return {"trades": history.list_trades(), "stats": history.stats()}


app.mount("/static", StaticFiles(directory=STATIC), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
