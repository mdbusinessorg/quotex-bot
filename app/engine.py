"""Motor de trading: liga à Quotex via pyquotex (não-oficial), corre sinais por
vela fechada e executa ordens até ao utilizador clicar Parar.

Login: email/password OU ssid da sessão do browser (recomendado quando a
Cloudflare bloqueia login automatizado — ver README).
"""

import asyncio
import logging
import time

from . import history
from .strategies import STRATEGIES

log = logging.getLogger("engine")


def _candles_from(rows):
    """Normaliza candles da API para dicts {open,high,low,close,time}."""
    out = []
    for r in rows or []:
        if isinstance(r, dict):
            out.append({
                "time": r.get("time") or r.get("from") or r.get("timestamp"),
                "open": float(r.get("open", 0)),
                "high": float(r.get("high", 0)),
                "low": float(r.get("low", 0)),
                "close": float(r.get("close", 0)),
            })
        elif isinstance(r, (list, tuple)) and len(r) >= 5:
            out.append({"time": r[0], "open": float(r[1]), "high": float(r[2]),
                        "low": float(r[3]), "close": float(r[4])})
    return [c for c in out if c["close"]]


class Engine:
    def __init__(self):
        self.client = None
        self.task = None
        self.stop_flag = asyncio.Event()
        self.state = {
            "connected": False, "running": False, "account": None,
            "balance": None, "last_signal": None, "open_trade": None,
            "error": None, "session": {},
        }

    async def connect(self, email=None, password=None, ssid=None):
        from quotexapi.stable_api import Quotex
        kwargs = {"lang": "pt"}
        if ssid:
            kwargs["set_ssid"] = ssid
        else:
            kwargs.update(email=email, password=password)
        self.client = Quotex(**kwargs)
        ok, msg = await self.client.connect()
        self.state["connected"] = ok
        self.state["error"] = None if ok else str(msg)
        return ok, msg

    async def set_account(self, mode):
        """mode: 'PRACTICE' ou 'REAL'"""
        try:
            await self.client.change_account(mode)
        except AttributeError:
            self.client.change_balance(mode)
        self.state["account"] = mode

    async def balance(self):
        try:
            self.state["balance"] = await self.client.get_balance()
        except Exception:
            pass
        return self.state["balance"]

    async def get_candles(self, asset, period=60, n=120):
        for name in ("get_candles", "get_candle"):
            fn = getattr(self.client, name, None)
            if not fn:
                continue
            try:
                rows = await fn(asset, period, n, int(time.time()))
                candles = _candles_from(rows)
                if candles:
                    return candles
            except TypeError:
                try:
                    rows = await fn(asset, int(time.time()) - n * period, int(time.time()), period)
                    candles = _candles_from(rows)
                    if candles:
                        return candles
                except Exception:
                    continue
            except Exception:
                continue
        return []

    async def buy_and_wait(self, asset, amount, direction, expiry):
        status, info = await self.client.buy(amount, asset, direction, expiry)
        if not status:
            return {"result": "error", "info": info}
        order_id = info.get("id") if isinstance(info, dict) else None
        win, info2 = await self.client.check_win(order_id)
        profit = 0.0
        if isinstance(info2, dict):
            profit = float(info2.get("profitAmount", info2.get("win", 0)) or 0)
        return {"result": "win" if win else "loss", "profit": profit, "info": info2}

    def start(self, cfg):
        if self.task and not self.task.done():
            return False
        self.stop_flag.clear()
        self.state["session"] = cfg
        self.state["running"] = True
        self.task = asyncio.create_task(self._loop(cfg))
        return True

    def stop(self):
        self.stop_flag.set()
        self.state["running"] = False

    async def _loop(self, cfg):
        asset = cfg["asset"]
        amount = float(cfg["amount"])
        expiry = int(cfg["expiry"])          # segundos
        strategy_id = cfg["strategy"]
        candle_period = 60                    # velas de 1 min para sinais
        strat = STRATEGIES[strategy_id]
        last_candle_time = None
        try:
            while not self.stop_flag.is_set():
                candles = await self.get_candles(asset, candle_period, strat["min_candles"] + 50)
                if not candles:
                    await asyncio.sleep(5)
                    continue
                ct = candles[-1]["time"]
                if ct != last_candle_time:
                    last_candle_time = ct
                    sig = strat["fn"](candles[-(strat["min_candles"] + 30):], strat["params"])
                    self.state["last_signal"] = {"asset": asset, "signal": sig, "candle": ct}
                    if sig and not self.stop_flag.is_set():
                        self.state["open_trade"] = {"asset": asset, "dir": sig, "amount": amount}
                        res = await self.buy_and_wait(asset, amount, sig, expiry)
                        self.state["open_trade"] = None
                        history.record({
                            "strategy": strategy_id, "asset": asset, "direction": sig,
                            "amount": amount, "expiry": expiry,
                            "result": res.get("result"), "profit": res.get("profit", 0.0),
                            "account": self.state.get("account"),
                        })
                        await self.balance()
                await asyncio.sleep(2)
        except Exception as e:
            log.exception("loop error")
            self.state["error"] = str(e)
        finally:
            self.state["running"] = False

    def status(self):
        return {
            **self.state,
            "history_stats": history.stats(),
        }


engine = Engine()
