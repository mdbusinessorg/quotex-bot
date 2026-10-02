"""Persistência simples em JSON do histórico de trades e stats por estratégia."""

import json
import os
import time
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
FILE = DATA_DIR / "trades.json"


def _load():
    if FILE.exists():
        try:
            return json.loads(FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save(rows):
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FILE)


def record(trade: dict):
    rows = _load()
    trade = dict(trade)
    trade.setdefault("ts", int(time.time()))
    rows.append(trade)
    _save(rows)
    return trade


def list_trades(limit=200):
    return _load()[-limit:][::-1]


def stats():
    """Win rate e P&L por estratégia."""
    agg = {}
    for t in _load():
        s = agg.setdefault(t.get("strategy", "?"), {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0})
        s["trades"] += 1
        profit = t.get("profit", 0.0) or 0.0
        s["pnl"] += profit
        if t.get("result") == "win":
            s["wins"] += 1
        elif t.get("result") == "loss":
            s["losses"] += 1
    for s in agg.values():
        s["win_rate"] = round(100 * s["wins"] / s["trades"], 1) if s["trades"] else 0
        s["pnl"] = round(s["pnl"], 2)
    return agg
