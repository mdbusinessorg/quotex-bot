"""BrokerAdapter — camada única de acesso ao broker.

Interface pedida pelo spec:
    connect() / getBalance() / getMarketData() / placeOrder() /
    getOrderStatus() / cancelOrder()

Implementações:
  - QuotexAdapter: execução REAL via pyquotex (não-oficial).
  - SimAdapter: motor de simulação local (dados sintéticos) — usado como
    fallback quando não há ligação à Quotex e para backtests.
"""

import asyncio
import os
import random
import time
import uuid


class BrokerAdapter:
    mode = "base"

    async def connect(self):
        raise NotImplementedError

    async def get_balance(self):
        raise NotImplementedError

    async def get_candles(self, asset, period, n):
        raise NotImplementedError

    async def place_order(self, asset, amount, direction, expiry):
        """Devolve order_id."""
        raise NotImplementedError

    async def get_order_status(self, order_id):
        """Devolve {state: open|closed, result: win|loss|None, profit: float}."""
        raise NotImplementedError

    async def cancel_order(self, order_id):
        raise NotImplementedError


# ---------------------------------------------------------------- Quotex real

class QuotexAdapter(BrokerAdapter):
    mode = "REAL"

    def __init__(self, email=None, password=None, ssid=None):
        self._kw = {"lang": "pt", "email": email or "",
                    "password": password or "",
                    "host": os.getenv("QUOTEX_HOST", "quotex.io")}
        self._ssid = ssid
        self.client = None
        self.account = "REAL"

    async def connect(self):
        try:
            from pyquotex.stable_api import Quotex
            from pyquotex.network.login import Login
            # a lib hardcoded qxbroker.com no Login — alinhar com o host configurado
            Login.base_url = self._kw["host"]
            Login.https_base_url = f'https://{self._kw["host"]}'
        except ImportError:
            from quotexapi.stable_api import Quotex
        self.client = Quotex(**self._kw)
        if self._ssid:
            ssid = self._ssid
            if '"session"' in ssid:  # aceita a mensagem completa do websocket
                import re, json
                m = re.search(r'"session"\s*:\s*"([^"]+)"', ssid)
                if m:
                    ssid = m.group(1)
            try:
                self.client.set_session(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                    cookies=os.getenv("QUOTEX_COOKIES") or None,
                    ssid=ssid)
            except Exception:
                self.client.set_ssid = ssid
        # Cloudflare recusa o upgrade WS com header Cookie vazio — qualquer
        # cookie não-vazio passa (o auth vai na mensagem, não na cookie)
        try:
            if not self.client.session_data.get("cookies"):
                self.client.session_data["cookies"] = (
                    os.getenv("QUOTEX_COOKIES") or "lang=pt")
        except Exception:
            pass
        host = self._kw["host"]
        eps = [os.getenv("QUOTEX_WS_URL") or f"wss://ws2.{host}/socket.io/?EIO=3&transport=websocket",
               f"wss://ws.{host}/socket.io/?EIO=3&transport=websocket"]
        ok, msg = False, "no endpoint"
        for ep in eps:
            try:
                self.client.wss_url_override = ep
            except Exception:
                pass
            try:
                ok, msg = await self.client.connect()
            except Exception as e:
                msg = str(e)
            if ok:
                break
        if not ok and self._kw.get("password"):
            # SSID expirado/rejeitado → limpar token e deixar o authenticate()
            # fazer login por email/password (cookies + SSID frescos)
            try:
                self.client.session_data["token"] = None
                ok, msg = await self.client.connect()
            except Exception as e:
                msg = str(e)
        if ok:
            # get_profile().offset vem a None nesta lib → get_server_time rebenta
            # (timedelta seconds=NoneType). Usar timestamp local: o request_id do
            # buy só precisa de um timestamp razoável.
            async def _local_server_time():
                return int(time.time())
            self.client.get_server_time = _local_server_time
        return ok, msg

    async def set_account(self, mode):
        try:
            await self.client.change_account(mode)
        except AttributeError:
            self.client.change_balance(mode)
        self.account = mode

    async def get_balance(self):
        try:
            return await self.client.get_balance()
        except Exception:
            await self.reconnect()
            return await self.client.get_balance()

    async def get_profile(self):
        """Dados da conta logada. Em modo SSID o profile da lib vem vazio,
        então lemos os saldos do estado ws (account_balance)."""
        bal = getattr(getattr(self.client, "api", None), "account_balance", None) or {}
        prof = {"email": self._kw.get("email") or None,
                "nickname": None,
                "demo_balance": float(bal.get("demoBalance") or 0),
                "live_balance": float(bal.get("liveBalance") or 0),
                "tournaments": bal.get("tournamentsBalances") or {},
                "account": self.account}
        try:
            p = await self.client.get_profile()
            if p and getattr(p, "nick_name", None):
                prof["nickname"] = p.nick_name
                prof["profile_id"] = getattr(p, "profile_id", None)
        except Exception:
            pass
        return prof

    async def get_candles(self, asset, period, n):
        try:
            rows = await self.client.get_candles(
                asset, int(time.time()), max(n, 30) * period, period)
            out = _norm(rows)
            if len(out) >= n:
                return out[-n:]
        except Exception:
            pass
        # janela curta insuficiente → paginação profunda
        return await self.get_candles_deep(asset, n * period + 120, period)[-n:] \
            if n > 0 else await self.get_candles_deep(asset, 1800, period)

    async def get_candles_deep(self, asset, seconds, period=60):
        """Histórico paginado (regime/backtest — muito mais candles que a
        janela curta de get_candles)."""
        try:
            rows = await self.client.get_historical_candles(
                asset, seconds, period, timeout=60)
            return _norm(rows)
        except Exception:
            return []

    async def reconnect(self):
        """Re-liga o cliente WS da Quotex (sessão cai silenciosamente)."""
        try:
            await self.client.connect()
            return True
        except Exception:
            pass
        try:
            self.client = None
            ok, _ = await self.connect()
            return ok
        except Exception:
            return False

    async def place_order(self, asset, amount, direction, expiry):
        status, info = await self.client.buy(amount, asset, direction, expiry)
        if not status:
            # WS morto → reconecta e tenta uma vez mais
            await self.reconnect()
            status, info = await self.client.buy(amount, asset, direction, expiry)
        if not status:
            raise RuntimeError(f"Ordem rejeitada: {info}")
        return info.get("id") if isinstance(info, dict) else info

    async def get_order_status(self, order_id):
        win, info = await self.client.check_win(order_id)
        profit = 0.0
        if isinstance(info, dict):
            profit = float(info.get("profitAmount", info.get("win", 0)) or 0)
        return {"state": "closed", "result": "win" if win else "loss", "profit": profit}

    async def cancel_order(self, order_id):
        return None


def _norm(rows):
    out = []
    for r in rows or []:
        if isinstance(r, dict):
            out.append({"time": r.get("time") or r.get("from") or r.get("timestamp"),
                        "open": float(r.get("open", 0)), "high": float(r.get("high", 0)),
                        "low": float(r.get("low", 0)), "close": float(r.get("close", 0))})
        elif isinstance(r, (list, tuple)) and len(r) >= 5:
            out.append({"time": r[0], "open": float(r[1]), "high": float(r[2]),
                        "low": float(r[3]), "close": float(r[4])})
    return [c for c in out if c["close"]]


# ---------------------------------------------------------------- Simulation

ASSETS = {
    "EURUSD": 1.0850, "GBPUSD": 1.2650, "USDJPY": 151.20, "AUDUSD": 0.6550,
    "USDCAD": 1.3580, "EURGBP": 0.8570, "BTCUSD": 67000.0, "XAUUSD": 2380.0,
}

# Pares negociáveis na Quotex — OTC primeiro: corre sempre (inclui fins de
# semana, quando o forex está fechado e pares normais não têm preço ao vivo)
REAL_ASSETS = [
    "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc", "USDCAD_otc",
    "USDCHF_otc", "EURGBP_otc", "EURJPY_otc", "GBPJPY_otc", "NZDUSD_otc",
    "AUDCAD_otc", "AUDCHF_otc",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "EURGBP",
    "EURJPY", "GBPJPY", "NZDUSD", "AUDCAD", "AUDCHF",
]

# payout típico Quotex ~ 80-98%
PAYOUT = 0.92


class SimFeed:
    """Feed sintético: random walk com regimes de tendência/volatilidade."""

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.prices = {a: p for a, p in ASSETS.items()}
        self.trend = {a: 0.0 for a in ASSETS}
        self.candles = {}

    def _step(self, asset, dt=1.0):
        r = self.rng
        if r.random() < 0.02:  # muda de regime
            self.trend[asset] = r.uniform(-0.0004, 0.0004)
        vol = self.prices[asset] * 0.0006
        drift = self.trend[asset] * self.prices[asset] * dt
        shock = r.gauss(0, vol * (dt ** 0.5))
        self.prices[asset] = max(self.prices[asset] * 0.2, self.prices[asset] + drift + shock)
        return self.prices[asset]

    def tick(self, asset):
        return self._step(asset)

    def build_candles(self, asset, period, n):
        """Gera n candles de `period` segundos até agora."""
        now = int(time.time())
        candles = []
        price = self.prices.get(asset, ASSETS.get(asset, 1.0))
        # backfill histórico
        hist = []
        for i in range(n):
            p = price
            o = p
            drift = self.rng.gauss(0, p * 0.0004)
            cl = p + drift
            hi = max(o, cl) + abs(self.rng.gauss(0, p * 0.0002))
            lo = min(o, cl) - abs(self.rng.gauss(0, p * 0.0002))
            hist.append({"time": now - (n - i) * period, "open": o, "high": hi,
                         "low": lo, "close": cl})
            price = cl
        return hist


class SimAdapter(BrokerAdapter):
    """Execução virtual: saldo simulado, latência e slippage configuráveis."""

    mode = "SIM"

    def __init__(self, balance=1000.0, latency_ms=150, slippage=0.0001):
        self.balance = balance
        self.feed = SimFeed()
        self.orders = {}
        self.latency_ms = latency_ms
        self.slippage = slippage

    async def connect(self):
        return True, "simulated feed"

    async def get_balance(self):
        return round(self.balance, 2)

    async def get_candles(self, asset, period, n):
        return self.feed.build_candles(asset, period, n)

    def price(self, asset):
        return self.feed.prices.get(asset) or self.feed.tick(asset)

    async def place_order(self, asset, amount, direction, expiry):
        if amount > self.balance:
            raise RuntimeError("Saldo insuficiente")
        await asyncio.sleep(self.latency_ms / 1000)
        entry = self.price(asset) * (1 + self.rng_slip(direction))
        oid = str(uuid.uuid4())[:12]
        self.balance -= amount
        self.orders[oid] = {
            "asset": asset, "amount": amount, "direction": direction,
            "entry": entry, "open_ts": time.time(), "expiry": expiry, "state": "open",
        }
        return oid

    def rng_slip(self, direction):
        s = self.feed.rng.uniform(-self.slippage, self.slippage)
        return s if direction == "call" else -s

    async def get_order_status(self, order_id):
        o = self.orders.get(order_id)
        if not o:
            return {"state": "closed", "result": None, "profit": 0}
        if o["state"] == "open" and time.time() - o["open_ts"] >= o["expiry"]:
            exit_price = self.price(o["asset"])
            diff = exit_price - o["entry"] if o["direction"] == "call" else o["entry"] - exit_price
            if diff > 0:
                o.update(state="closed", result="win",
                         profit=round(o["amount"] * PAYOUT, 2), exit=exit_price)
                self.balance += o["amount"] + o["profit"]
            elif diff < 0:
                o.update(state="closed", result="loss", profit=-o["amount"], exit=exit_price)
            else:
                o.update(state="closed", result="tie", profit=0.0, exit=exit_price)
                self.balance += o["amount"]
        return o

    async def cancel_order(self, order_id):
        o = self.orders.pop(order_id, None)
        if o:
            self.balance += o["amount"]
