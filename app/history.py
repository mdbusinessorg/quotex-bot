"""History Engine — SQLite: trades com entry/exit, filtros e stats por estratégia."""

import os
import sqlite3
import time
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB = DATA_DIR / "trades.db"


def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS trades (
        id TEXT PRIMARY KEY, ts INTEGER, asset TEXT, direction TEXT,
        amount REAL, expiry INTEGER, strategy TEXT, account TEXT,
        entry REAL, exit REAL, result TEXT, pnl REAL,
        open_ts INTEGER, close_ts INTEGER, confidence INTEGER, mode TEXT)""")
    c.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT)")
    return c


def kv_set(k, v):
    conn = _conn()
    conn.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (k, str(v)))
    conn.commit(); conn.close()


def kv_get(k, default=None):
    conn = _conn()
    r = conn.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    conn.close()
    return r["v"] if r else default


def record(t: dict):
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (t["id"], int(t.get("ts", time.time())), t.get("asset"), t.get("direction"),
         t.get("amount"), t.get("expiry"), t.get("strategy"), t.get("account"),
         t.get("entry"), t.get("exit"), t.get("result"), t.get("pnl"),
         t.get("open_ts"), t.get("close_ts"), t.get("confidence"), t.get("mode")))
    conn.commit(); conn.close()
    return t


def list_trades(asset=None, strategy=None, result=None, days=None, limit=500):
    q, p = "SELECT * FROM trades", []
    conds = []
    if asset:
        conds.append("asset = ?"); p.append(asset)
    if strategy:
        conds.append("strategy = ?"); p.append(strategy)
    if result:
        conds.append("result = ?"); p.append(result)
    if days:
        conds.append("ts >= ?"); p.append(int(time.time()) - days * 86400)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY ts DESC LIMIT ?"
    p.append(limit)
    conn = _conn()
    rows = [dict(r) for r in conn.execute(q, p)]
    conn.close()
    return rows


def _agg(rows):
    trades = len(rows)
    wins = sum(1 for r in rows if r["result"] == "win")
    losses = sum(1 for r in rows if r["result"] == "loss")
    pnl = round(sum(r["pnl"] or 0 for r in rows), 2)
    gross_w = sum(r["pnl"] for r in rows if (r["pnl"] or 0) > 0)
    gross_l = abs(sum(r["pnl"] for r in rows if (r["pnl"] or 0) < 0))
    pf = round(gross_w / gross_l, 2) if gross_l else None
    # drawdown + streaks por ordem cronológica
    eq, peak, dd = 0.0, 0.0, 0.0
    wstreak = lstreak = mw = ml = 0
    for r in sorted(rows, key=lambda x: x["ts"]):
        eq += r["pnl"] or 0
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
        if r["result"] == "win":
            wstreak += 1; lstreak = 0
        elif r["result"] == "loss":
            lstreak += 1; wstreak = 0
        mw, ml = max(mw, wstreak), max(ml, lstreak)
    return {"trades": trades, "wins": wins, "losses": losses,
            "win_rate": round(100 * wins / trades, 1) if trades else 0,
            "pnl": pnl, "profit_factor": pf, "drawdown": round(dd, 2),
            "max_win_streak": mw, "max_loss_streak": ml}


def stats_by_strategy():
    conn = _conn()
    strategies = [r[0] for r in conn.execute("SELECT DISTINCT strategy FROM trades")]
    conn.close()
    return {s: _agg(list_trades(strategy=s)) for s in strategies if s}


def summary(days=None):
    return _agg(list_trades(days=days, limit=10000))
