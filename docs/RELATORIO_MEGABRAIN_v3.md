# PINHANHA BOT — Relatório MEGABRAIN v3 (2026-10-11)

Resposta ao brief "MEGABRAIN ULTRA". Só sinais; execução real intocada; sem martingale.

## 1. O que se passou ("os sinais sumiram")

Causa raiz: a auto-afinação por win-rate (deploy 3c4d2d3) começou a aplicar peso
0,5 às duas estratégias que mais votam (`ai_turbo` 40%, `multi_indicator` 38%
medidos). O código multiplicava a confiança bruta pelo peso **e dividia pelo
número de votantes** (`sum(conf*w)/len`), o que esmagava todos os sinais para
~30% — abaixo do filtro de 45%. Correção (36a1d67): média ponderada
(`sum(conf*w)/sum(w)`), afinação só com ≥30 amostras e piso 0,7.

Bugs secundários corrigidos no mesmo commit:
- `/api/sigstats` a falhar fazia a UI não desenhar card nenhum → cards passam
  a renderizar antes das estatísticas.
- Empate de preço (forex parado ao fim-de-semana) contava como LOSS →
  forex "6%" era artefacto. Agora `void` (indeterminado) e fora das métricas.

## 2. Evidência: as "confirmações" não têm vantagem

Teste nas 69 mil velas reais OTC 1m (`_research/data`, 12 pares, 96h), taxa de
acerto da vela seguinte:

| Regra | n | acerto |
|---|---|---|
| 3 velas a favor → continua | 16 898 | 50,2–50,6% |
| última vela a favor → continua | 67 120 | 50,0–50,2% |
| slope 20 velas a favor | 67 120 | 49,8–50,1% |
| contexto 5m a favor | 67 120 | 49,6–49,8% |
| RSI<30 → sobe / RSI>70 → desce | 16 281 | 50,2–50,3% |
| RSI<20 / RSI>80 | 4 768 | 50,1–51,0% |

Ao vivo (143 sinais antes do reset): faixa conf 45–65% = 59% acerto;
75–85% = 33%; 85–97% = 23%. Ou seja, os bónus de confiança (+8 velas, +4
contexto 5m, +3 slope, +4/voto) **inflacionavam** exactamente os sinais que
mais perdiam. Foram removidos como modificadores de confiança (ficam como
informação: `agree3`, `ctx5`).

## 3. Arquitetura final (o que mudou)

| Módulo | Antes | Agora |
|---|---|---|
| `app/calib.py` (novo) | — | Confiança = acertividade **medida** do tipo de sinal (classe → estratégia líder → conjunto exacto de votantes), shrink Beta para 50% com 30 pseudo-amostras; nível só é usado com ≥20 amostras |
| `app/sigstore.py` (novo) | histórico em memória (zerava a cada deploy) | Supabase `pinhanha_signals` (REST, best-effort, no-op sem env). Repõe avaliados+pendentes no arranque |
| `/api/signals` | conf = heurística + bónus | `confidence` = p calibrado; `score` = heurística (rotulado como não-probabilidade); `grade` ∈ forte/valido/obs/sem_dados; NO_TRADE (oculto) se histórico <47% com ≥40 amostras ou regime bloqueado |
| Tracking | win/loss, tie=loss | win/loss/void, re-tenta 10 min sem feed, `eval_ts` |
| UI | "conf X%" + OBSERVAÇÃO | "acerto medido X% · n=…", "score", etiqueta FORTE/VÁLIDO/OBSERVAÇÃO/SEM HISTÓRICO; filtro com 54% (breakeven) |

Categorias (fundamentação): breakeven Quotex a payout 0,87 = 53,5%.
`forte` p≥58% e n≥50 · `valido` p≥53,5% e n≥30 · `obs` 10≤n<30 ou p~50% ·
`sem_dados` n<10 · `no_trade` p<47% e n≥40 (não apresentado).

## 4. Testes

- `tests/test_calib.py` (6) + `tests/test_patterns.py` (8) + existentes: **21 passam**.
- Integração Supabase: upsert → patch → load → delete verificados contra o projeto real.
- Smoke local: 37 pares varridos, 12 sinais, sem excepções em `LAST_SCAN_ERRS`.

## 5. Limitações honestas

- Após o deploy o histórico começa do zero (os 143 anteriores viviam em memória):
  todos os sinais mostram 50% / SEM HISTÓRICO até acumular ≥20 por tipo (~1–2h
  de mercado activo). A partir daí a confiança passa a reflectir a realidade e
  os tipos com histórico contra desaparecem sozinhos (NO_TRADE).
- Nenhuma regra testada tem vantagem no dataset OTC 1m; a melhor vantagem
  demonstrada continua a ser ~55% (RandomForest walk-forward, instável). Não
  há evidência para 75–80%.
- Sessão Quotex em SIM (SSID expirado): sem ticks OTC reais, as velas vêm do
  Yahoo (forex fechado ao fim-de-semana → `void`).
- Groq não foi alterado nesta ronda (fase 3 do brief pendente).

## 6. Reversão

`git revert 8ccdf41 36a1d67` + deploy manual no Render. Sem envs
`SUPABASE_URL`/`SUPABASE_SERVICE_KEY` o sistema corre só em memória.
