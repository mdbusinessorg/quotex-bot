"""Execution Engine — Auto Bot e execução manual.

Separação: DATA (broker.get_candles) → STRATEGY → RISK (check) → EXECUTION
(broker.place_order) → RESULT (broker.get_order_status) → HISTORY.

Conta por defeito: REAL. PRACTICE disponível para treino.
"""

import asyncio
import logging
import time
import uuid

from . import history
from .broker import BrokerAdapter, QuotexAdapter, SimAdapter
from .risk import risk
from .strategies import STRATEGIES

log = logging.getLogger("engine")


class Engine:
    def __init__(self):
        self.broker: BrokerAdapter = SimAdapter()   # começa em simulação até login
        self.account = "REAL"
        self.connected = False
        self.autobot_on = False
        self.autobot_cfg = {}
        self.open_trades = {}        # id -> info
        self.task = None
        self.stop_flag = asyncio.Event()
        self.state = {"last_signal": None, "phase": "IDLE", "error": None}
        self._main_loop = None

    # ------------------------------------------------ ligação
    async def connect_real(self, email=None, password=None, ssid=None, account="REAL"):
        self._main_loop = asyncio.get_running_loop()
        adapter = QuotexAdapter(email=email, password=password, ssid=ssid)
        ok, msg = await adapter.connect()
        if ok:
            self.broker = adapter
            await adapter.set_account(account)
            self.account = account
            self.connected = True
            self.state["error"] = None
        else:
            self.state["error"] = str(msg)
        return ok, msg

    async def set_account(self, mode):
        self.account = mode
        if isinstance(self.broker, QuotexAdapter):
            await self.broker.set_account(mode)

    async def balance(self):
        try:
            return await self.broker.get_balance()
        except Exception:
            return None

    # ------------------------------------------------ execução
    async def open_trade(self, asset, amount, expiry, direction, strategy):
        oid = await self.broker.place_order(asset, amount, direction, expiry)
        t = {"id": oid, "asset": asset, "direction": direction, "amount": amount,
             "expiry": expiry, "strategy": strategy, "account": self.account,
             "mode": self.broker.mode, "open_ts": time.time(), "entry": None}
        self.open_trades[oid] = t
        return t

    async def _watch_trade(self, oid):
        t = self.open_trades.get(oid)
        if not t:
            return
        # espera expiração + sonda de estado
        while not self.stop_flag.is_set():
            st = await self.broker.get_order_status(oid)
            if st.get("state") == "closed" and st.get("result"):
                break
            if isinstance(st, dict) and st.get("entry") is None and st.get("asset"):
                t["entry"] = st.get("entry")
            await asyncio.sleep(2)
        st = await self.broker.get_order_status(oid)
        pnl = st.get("profit", st.get("pnl", 0.0)) or 0.0
        if not pnl:  # broker real nem sempre devolve o lucro — estimar
            if st.get("result") == "win":
                pnl = round(float(t["amount"]) * 0.87, 2)
            elif st.get("result") == "loss":
                pnl = -float(t["amount"])
        t.update({
            "entry": st.get("entry", t.get("entry")), "exit": st.get("exit"),
            "result": st.get("result"), "pnl": pnl,
            "close_ts": time.time(), "ts": time.time(),
        })
        self.open_trades.pop(oid, None)
        history.record(t)
        risk.record_result(t["pnl"] or 0)

    async def manual_trade(self, asset, amount, expiry, direction, strategy="manual"):
        t = await self.open_trade(asset, amount, expiry, direction, strategy)
        asyncio.create_task(self._watch_trade(t["id"]))
        return t

    # ------------------------------------------------ auto bot
    def autobot_start(self, cfg):
        self.autobot_cfg = cfg
        self.autobot_on = True
        if not self.task or self.task.done():
            self.stop_flag.clear()
            loop = self._main_loop
            if loop and loop.is_running():
                # este endpoint corre numa thread — agendar a task no loop principal
                loop.call_soon_threadsafe(
                    lambda: setattr(self, "task",
                                    asyncio.ensure_future(self._loop())))
            else:
                self.task = asyncio.create_task(self._loop())
        return True

    def autobot_stop(self):
        """Pára novos trades; os abertos terminam naturalmente."""
        self.autobot_on = False
        self.state["phase"] = "STOPPING"

    async def _loop(self):
        while True:
            if not self.autobot_on:
                self.state["phase"] = "IDLE"
                if not self.open_trades:
                    return
                await asyncio.sleep(2)
                continue
            try:
                cfg = self.autobot_cfg
                sid = cfg.get("strategy", "ai_turbo")
                s = STRATEGIES.get(sid, STRATEGIES.get("ai_turbo"))
                win = int(cfg.get("analyze_sec", 30))
                minconf = cfg.get("min_confidence", 40)
                asset_sel = cfg.get("asset", "EURUSD_otc")
                if asset_sel == "ALL":
                    from .broker import REAL_ASSETS
                    assets = REAL_ASSETS
                else:
                    assets = [asset_sel]
                # janela de análise: varre os pares de ~3 em 3s; entra IMEDIATO
                # quando um sinal passa a confiança mínima
                best = None  # (res, asset)
                t0 = time.time()
                empty_rounds = 0
                while time.time() - t0 < win and self.autobot_on:
                    rem = int(win - (time.time() - t0))
                    self.state["phase"] = f"ANALYZING {max(0, rem)}s"
                    got = 0
                    for a in assets:
                        try:
                            candles = await self.broker.get_candles(
                                a, 60, s["min_candles"] + 50)
                        except Exception:
                            continue
                        if not candles:
                            continue
                        got += 1
                        res = s["fn"](candles[-(s["min_candles"] + 30):])
                        if res["signal"] and (
                                not best or res["confidence"] > best[0]["confidence"]):
                            best = (res, a)
                            self.state["last_signal"] = {"asset": a, **res}
                    # oportunidade encontrada → abre já
                    if best and best[0]["confidence"] >= minconf:
                        break
                    # feed morto (WS caiu) → reconecta e volta a tentar
                    if got == 0:
                        empty_rounds += 1
                        if empty_rounds >= 3:
                            rec = getattr(self.broker, "reconnect", None)
                            if rec:
                                self.state["phase"] = "RECONNECTING"
                                await rec()
                            empty_rounds = 0
                    else:
                        empty_rounds = 0
                    await asyncio.sleep(3)
                if not self.autobot_on:
                    continue
                self.state["phase"] = "VALIDATING"
                ok, reason = risk.check(float(cfg["amount"]),
                                        list(self.open_trades.values()))
                if ok and best and best[0]["confidence"] >= minconf:
                    res, asset = best
                    self.state["phase"] = "TRADE OPEN"
                    t = await self.open_trade(asset, float(cfg["amount"]),
                                              int(cfg["expiry"]), res["signal"], sid)
                    t["confidence"] = res["confidence"]
                    self.state["phase"] = "COUNTDOWN"
                    await self._watch_trade(t["id"])
                else:
                    self.state["phase"] = (
                        reason or f"sem sinal ≥{minconf}% — novo ciclo")
                    await asyncio.sleep(4)
            except Exception as e:
                log.exception("autobot error")
                self.state["error"] = str(e)
                await asyncio.sleep(5)

    def status(self):
        return {
            "connected": self.connected,
            "broker_mode": self.broker.mode,
            "account": self.account,
            "autobot": self.autobot_on,
            "phase": self.state["phase"],
            "last_signal": self.state.get("last_signal"),
            "error": self.state.get("error"),
            "open_trades": list(self.open_trades.values()),
            "risk": risk.snapshot(),
            "summary": history.summary(days=1),
        }


engine = Engine()
