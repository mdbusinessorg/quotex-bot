"""Calibração empírica da confiança dos sinais.

A confiança apresentada deixa de ser um bónus heurístico e passa a ser a
acertividade MEDIDA (WIN/LOSS reais) do tipo de sinal, com shrinkage
hierárquico para 50% enquanto há poucas amostras:
    global → classe (forex/cripto) → estratégia líder → conjunto exacto.
Breakeven Quotex com payout 0,87 ≈ 53,5%."""

BREAKEVEN = 0.535
PRIOR = 0.50


def _shrink(n, w, prior, k):
    """Estimativa bayesiana (Beta) com k pseudo-amostras no prior."""
    return (w + k * prior) / (n + k)


def build(results):
    """Tabelas de contagem (n, wins) por nível a partir dos sinais avaliados."""
    t = {"global": [0, 0], "cls": {}, "lead": {}, "set": {}}

    def bump(d, key, won):
        c = d.setdefault(key, [0, 0])
        c[0] += 1
        c[1] += won
    for r in results:
        if r.get("result") not in ("win", "loss"):
            continue
        won = 1 if r["result"] == "win" else 0
        voters = sorted(r.get("voters") or [])
        cls = r.get("cls") or "forex"
        t["global"][0] += 1
        t["global"][1] += won
        bump(t["cls"], cls, won)
        if voters:
            bump(t["lead"], (cls, voters[0]), won)
            bump(t["set"], (cls, tuple(voters)), won)
    return t


def estimate(tables, cls, voters):
    """→ (p calibrado 0..1, n_eff amostras relevantes).
    Usa o nível mais específico com ≥20 amostras (conjunto exacto → estratégia
    líder → classe), encolhido para 50% com 30 pseudo-amostras; sem nada,
    recorre ao global com shrink pesado (classes comportam-se muito diferente)."""
    voters = sorted(voters or [])
    levels = []
    if voters:
        levels.append(tables.get("set", {}).get((cls, tuple(voters)), [0, 0]))
        levels.append(tables.get("lead", {}).get((cls, voters[0]), [0, 0]))
    levels.append(tables.get("cls", {}).get(cls, [0, 0]))
    for n, w in levels:
        if n >= 20:
            return _shrink(n, w, PRIOR, 30), n
    g = tables.get("global", [0, 0])
    return _shrink(g[0], g[1], PRIOR, 100), 0


def grade(p, n_eff):
    """Categoria fundamentada (ver RELATORIO_QUANTUM_v3):
    forte  — p ≥ 58% com ≥50 amostras do mesmo tipo
    valido — p ≥ breakeven (53,5%) com ≥30 amostras
    obs    — sem vantagem demonstrada ainda (poucas amostras ou p ~50%)
    no_trade — p < 47% com ≥40 amostras: histórico contra, não apresentar"""
    if n_eff >= 40 and p < 0.47:
        return "no_trade"
    if n_eff >= 50 and p >= 0.58:
        return "forte"
    if n_eff >= 30 and p >= BREAKEVEN:
        return "valido"
    return "obs" if n_eff >= 10 else "sem_dados"


LABEL = {"forte": "FORTE", "valido": "VÁLIDO", "obs": "OBSERVAÇÃO",
         "sem_dados": "SEM HISTÓRICO", "no_trade": "NO TRADE"}
