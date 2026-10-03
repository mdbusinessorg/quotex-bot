"""AI Analyst via Groq (LLM). Se GROQ_API_KEY não existir, devolve análise local."""
import json
import os
import urllib.request

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


def ai_insight(asset, candles, patterns, analytics):
    key = os.getenv("GROQ_API_KEY")
    summary = {
        "asset": asset,
        "last_close": candles[-1]["close"] if candles else None,
        "decision": analytics.get("decision"),
        "score": analytics.get("score"),
        "patterns": [f"{p['pattern']}({p['direction']},{p['strength']})"
                     for p in patterns.get("patterns", [])][:12],
        "votes": analytics.get("votes"),
    }
    if not key:
        return {"text": _local_insight(asset, patterns, analytics), "source": "local"}
    prompt = (
        "És um analista técnico sénior de opções binárias. Em 3-5 frases curtas em português, "
        "diz se o contexto favorece CALL, PUT ou WAIT nos próximos 1-5 minutos e porquê "
        "(menciona 1-2 padrões/indicadores relevantes). Dados: " + json.dumps(summary))
    try:
        req = urllib.request.Request(
            GROQ_URL,
            data=json.dumps({
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 220,
            }).encode(),
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
        return {"text": d["choices"][0]["message"]["content"].strip(),
                "source": "groq"}
    except Exception as e:
        return {"text": _local_insight(asset, patterns, analytics),
                "source": "local", "error": str(e)}


def _local_insight(asset, patterns, analytics):
    pats = patterns.get("patterns", [])
    dec = analytics.get("decision", "WAIT")
    if not pats:
        return f"{asset}: sem padrões fortes agora — {dec}."
    top = sorted(pats, key=lambda p: -p["strength"])[:3]
    names = ", ".join(p["pattern"] for p in top)
    return f"{asset}: {dec}. Padrões dominantes: {names}."
