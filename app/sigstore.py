"""Histórico persistente de sinais (Supabase REST) — sobrevive a redeploys.

Sem SUPABASE_URL/SUPABASE_SERVICE_KEY fica em modo no-op (memória apenas).
Todas as chamadas são best-effort: nunca bloqueiam nem derrubam o scan."""

import asyncio
import json
import logging
import os
import urllib.request
import urllib.error

log = logging.getLogger("sigstore")
URL = os.getenv("SUPABASE_URL", "").rstrip("/")
KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
TABLE = "pinhanha_signals"
FIELDS = ("emit_ts", "asset", "signal", "cls", "entry", "conf", "watch",
          "voters", "ctx5", "due", "exit", "result", "eval_ts")


def enabled():
    return bool(URL and KEY)


def _req(method, path, body=None, prefer=None):
    hdr = {"apikey": KEY, "Authorization": f"Bearer {KEY}",
           "Content-Type": "application/json"}
    if prefer:
        hdr["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{URL}/rest/v1/{path}", data=data,
                                 headers=hdr, method=method)
    with urllib.request.urlopen(req, timeout=12) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def _row(t):
    r = {k: t.get(k) for k in FIELDS}
    r["id"] = t["id"]
    return r


def _to_track(r):
    t = {k: r.get(k) for k in FIELDS}
    t["id"] = r["id"]
    t["voters"] = t.get("voters") or []
    t["watch"] = bool(t.get("watch"))
    return t


async def _run(fn, *a):
    if not enabled():
        return None
    try:
        return await asyncio.to_thread(fn, *a)
    except urllib.error.HTTPError as e:
        log.warning("sigstore %s: %s", e.code, e.read()[:200])
    except Exception as e:
        log.warning("sigstore: %s", e)
    return None


async def save_emitted(tracks):
    """Upsert em lote dos sinais acabados de emitir (result='pending')."""
    if not tracks:
        return
    await _run(_req, "POST", f"{TABLE}?on_conflict=id",
               [_row(t) for t in tracks], "resolution=merge-duplicates,return=minimal")


async def save_results(tracks):
    """Grava exit/result dos sinais avaliados (um PATCH por sinal)."""
    for t in tracks:
        await _run(_req, "PATCH", f"{TABLE}?id=eq.{t['id']}",
                   {"exit": t.get("exit"), "result": t.get("result"),
                    "eval_ts": t.get("eval_ts")}, "return=minimal")


async def load_recent(limit=2000):
    """Devolve (avaliados, pendentes) mais recentes para repor o estado em memória."""
    rows = await _run(_req, "GET",
                      f"{TABLE}?select=*&order=emit_ts.desc&limit={limit}")
    if not rows:
        return [], []
    rows = [_to_track(r) for r in reversed(rows)]
    done = [r for r in rows if r["result"] in ("win", "loss", "void")]
    pend = [r for r in rows if r["result"] == "pending"]
    return done, pend
