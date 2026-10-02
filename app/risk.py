"""Risk Manager independente — pausa o Auto Bot quando limites são atingidos."""

import time
from dataclasses import dataclass, field, asdict


@dataclass
class RiskConfig:
    max_amount_per_trade: float = 100.0
    max_daily_loss: float = 50.0
    max_consecutive_losses: int = 3
    max_simultaneous: int = 1
    cooldown_sec: int = 30
    max_exposure: float = 200.0
    daily_target: float = 100.0


@dataclass
class RiskState:
    day: str = ""
    daily_pnl: float = 0.0
    consecutive_losses: int = 0
    last_trade_ts: float = 0.0
    paused: bool = False
    pause_reason: str = ""


class RiskManager:
    def __init__(self):
        self.cfg = RiskConfig()
        self.st = RiskState()

    def configure(self, **kw):
        for k, v in kw.items():
            if hasattr(self.cfg, k):
                setattr(self.cfg, k, type(getattr(self.cfg, k))(v))
        return asdict(self.cfg)

    def _roll_day(self):
        today = time.strftime("%Y-%m-%d")
        if self.st.day != today:
            self.st.day = today
            self.st.daily_pnl = 0.0
            self.st.consecutive_losses = 0

    def check(self, amount, open_trades):
        """Devolve (ok, reason)."""
        self._roll_day()
        if self.st.paused:
            return False, self.st.pause_reason
        if amount > self.cfg.max_amount_per_trade:
            return False, "valor por operação acima do máximo configurado"
        if time.time() - self.st.last_trade_ts < self.cfg.cooldown_sec:
            return False, "cooldown entre operações"
        if len(open_trades) >= self.cfg.max_simultaneous:
            return False, "máximo de operações simultâneas atingido"
        exposure = sum(t["amount"] for t in open_trades)
        if exposure + amount > self.cfg.max_exposure:
            return False, "exposição máxima atingida"
        return True, ""

    def record_result(self, pnl):
        """Regista resultado; pausa se limites diários forem atingidos."""
        self._roll_day()
        self.st.daily_pnl += pnl
        self.st.last_trade_ts = time.time()
        if pnl < 0:
            self.st.consecutive_losses += 1
        else:
            self.st.consecutive_losses = 0
        if self.st.daily_pnl <= -self.cfg.max_daily_loss:
            self._pause("limite de perda diária atingido")
        elif self.st.consecutive_losses >= self.cfg.max_consecutive_losses:
            self._pause("máximo de perdas consecutivas atingido")
        elif self.st.daily_pnl >= self.cfg.daily_target:
            self._pause("meta diária atingida")

    def _pause(self, reason):
        self.st.paused = True
        self.st.pause_reason = f"Auto Bot pausado: {reason}."

    def resume(self):
        self.st.paused = False
        self.st.pause_reason = ""
        self.st.consecutive_losses = 0

    def snapshot(self):
        return {"config": asdict(self.cfg), "state": asdict(self.st)}


risk = RiskManager()
