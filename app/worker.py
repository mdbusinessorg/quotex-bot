"""Worker headless — o mesmo motor do painel, sem servidor web.

Corre em GitHub Actions (repo público = minutos grátis). Lê quotex_feed
(velas reais do relay Supabase), calcula sinais com o código exacto do
/api/signals e grava os payloads em bot_state; a edge function qx-panel
serve esses dados ao painel. Também executa bot_cmds (ligar SSID, trocar
conta, trades manuais, autobot, risco).

Saída limpa ao fim de WORKER_SECONDS — o workflow re-despacha-se a si
mesmo para manter o processo 24h.
"""

import asyncio
import logging
import os
import time

from . import history, sigstore
from .engine import engine
from .risk import risk
from . import main as M

log = logging.getLogger("worker")
DEADLINE = time.time() + int(os.getenv("WORKER_SECONDS", "20400"))


async def _kv(k):
    try:
        r = await asyncio.to_thread(
            sigstore._req, "GET", f"bot_kv?k=eq.{k}&select=v")
        return r[0]["v"] if r else None
    except Exception:
        return None


async def _try_connect():
    ssid = (os.getenv("QUOTEX_SSID") or await _kv("quotex_ssid")
            or history.kv_get("ssid"))
    email = os.getenv("QUOTEX_EMAIL")
    pw = os.getenv("QUOTEX_PASSWORD")
    account = history.kv_get("account") or os.getenv("QUOTEX_ACCOUNT", "REAL")
    if not (ssid or (email and pw)):
        return
    i = 0
    while not engine.connected and time.time() < DEADLINE:
        i += 1
        try:
            ok, msg = await engine.connect_real(email, pw, ssid, account)
            log.info("connect t%d: %s %s", i, ok, msg)
            if ok:
                return
        except Exception as e:
            log.warning("connect t%d falhou: %s", i, e)
        await asyncio.sleep(300)


async def _cmds():
    for c in await sigstore.cmds_pending():
        res = None
        try:
            k, p = c.get("kind"), c.get("payload") or {}
            if k == "connect":
                ok, msg = await engine.connect_real(
                    p.get("email"), p.get("password"), p.get("ssid"),
                    p.get("account", "REAL"))
                if ok:
                    if p.get("ssid"):
                        history.kv_set("ssid", p["ssid"])
                        await sigstore.kv_put("quotex_ssid", p["ssid"])
                    history.kv_set("account", p.get("account", "REAL"))
                res = {"ok": ok, "msg": str(msg),
                       "balance": await engine.balance()}
            elif k == "account":
                mode = str(p.get("mode", "REAL")).upper()
                await engine.set_account(mode)
                history.kv_set("account", mode)
                res = {"ok": True, "balance": await engine.balance()}
            elif k in ("trade", "autobot_start"):
                res = {"ok": False,
                       "msg": "trading desactivado — painel só de sinais"}
            elif k == "autobot_stop":
                engine.autobot_stop()
                res = {"ok": True}
            elif k == "risk":
                res = {"ok": True, "config": risk.configure(**p)}
            elif k == "risk_resume":
                risk.resume()
                res = {"ok": True}
            else:
                res = {"ok": False, "msg": f"kind desconhecido {k}"}
        except Exception as e:
            res = {"ok": False, "msg": str(e)[:300]}
        await sigstore.cmd_done(c["id"], res)


async def _publish():
    """Corre a MESMA varredura do /api/signals e grava os payloads que a
    edge function serve ao painel."""
    await M.signals_ep(min_conf=0, _=None)
    await sigstore.state_put("signals", M.SIG_CACHE["data"])
    st = engine.status()
    try:
        st["balance"] = await engine.balance()
    except Exception:
        st["balance"] = None
    st["quotex_feed"] = sum(1 for e in M.CANDLE_CACHE.values()
                            if e.get("src") == "quotex")
    st["worker_ts"] = time.time()
    await sigstore.state_put("status", st)
    await sigstore.state_put("sigstats", M.sig_stats())


async def main():
    engine._main_loop = asyncio.get_running_loop()
    asyncio.create_task(M._relay_warmer())
    asyncio.create_task(M._sig_tracker())
    asyncio.create_task(M._tick_warmer())
    asyncio.create_task(M._candle_warmer())
    asyncio.create_task(_try_connect())
    await sigstore.state_put("assets", list(M.ASSETS.keys()))
    await sigstore.state_put(
        "strategies",
        {k: {"name": v["name"], "desc": v["desc"]}
         for k, v in M.STRATEGIES.items()})
    while time.time() < DEADLINE:
        try:
            await _publish()
            await _cmds()
        except Exception as e:
            log.warning("loop: %s", e)
        await asyncio.sleep(12)
    log.info("deadline — sair para o próximo run")


if __name__ == "__main__":
    asyncio.run(main())
