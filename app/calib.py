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
            bump(t["set"], (cls, tuple(voters)), won)
            if len(voters) == 1:
                bump(t["lead"], (cls, voters[0]), won)
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


def set_stats(tables, cls, voters):
    """(n, wins, p encolhido) do conjunto EXACTO de votantes — a prova
    empírica daquela combinação específica, sem fallback hierárquico."""
    voters = sorted(voters or [])
    if not voters:
        return 0, 0, PRIOR
    n, w = tables.get("set", {}).get((cls, tuple(voters)), [0, 0])
    return n, w, _shrink(n, w, PRIOR, 30)


def no_trade_exact(tables, cls, voters):
    """NO_TRADE só com evidência forte a nível exacto — nunca por classe
    inteira (deadlock: sem sinais → sem amostras → nunca destranca).
    2+ estratégias a votar → conjunto p<45% com ≥60 amostras;
    1 estratégia → líder p<45% com ≥80 (a 'líder' é o conjunto inteiro)."""
    voters = sorted(voters or [])
    if not voters:
        return False
    s = tables.get("set", {}).get((cls, tuple(voters)), [0, 0])
    if s[0] >= 60 and _shrink(s[0], s[1], PRIOR, 30) < 0.45:
        return True
    if len(voters) == 1:
        l = tables.get("lead", {}).get((cls, voters[0]), [0, 0])
        if l[0] >= 80 and _shrink(l[0], l[1], PRIOR, 30) < 0.45:
            return True
    return False


def grade_set(n, p):
    """Categoria baseada APENAS na prova do conjunto exacto:
    forte  — p ≥ 58% com ≥50 amostras
    valido — p ≥ breakeven (53,5%) com ≥30 amostras
    obs    — sem prova suficiente do conjunto
    (no_trade é decidido por no_trade_exact, não aqui)"""
    if n >= 50 and p >= 0.58:
        return "forte"
    if n >= 30 and p >= BREAKEVEN:
        return "valido"
    return "obs" if n >= 10 else "sem_dados"


def grade(p, n_eff):
    """Categoria fundamentada (ver RELATORIO_QUANTUM_v3):
    forte  — p ≥ 58% com ≥50 amostras do mesmo tipo
    valido — p ≥ breakeven (53,5%) com ≥30 amostras
    obs    — sem vantagem demonstrada ainda (poucas amostras ou p ~50%)
    no_trade — p < 47% com ≥40 amostras: histórico contra, não apresentar"""
    # "no_trade" nunca por grade(): esconder é só decisão de no_trade_exact()
    # (conjunto exacto ≥60 amostras) — caso contrário o sistema bloqueia-se
    # num estado de onde já não recolhe evidência para melhorar.
    if n_eff >= 50 and p >= 0.58:
        return "forte"
    if n_eff >= 30 and p >= BREAKEVEN:
        return "valido"
    return "obs" if n_eff >= 10 else "sem_dados"


LABEL = {"forte": "FORTE", "valido": "VÁLIDO", "obs": "OBSERVAÇÃO",
         "sem_dados": "SEM HISTÓRICO", "no_trade": "NO TRADE"}
