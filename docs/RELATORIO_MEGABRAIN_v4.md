# PINHANHA BOT — Relatório MEGABRAIN v4 (2026-10-11, parte 2)

Resposta ao brief "Missão de Engenharia Quantitativa" (auditoria → pesquisa →
padrões → backtest OOS → correções → testes → relatório). Só sinais; execução
real intocada; sem martingale.

## 1. Diagnóstico — porque o bot falhava

| Problema | Evidência | Correção |
|---|---|---|
| Confiança inventada (bónus +8 velas, +4 ctx5m, +3 slope, +4/voto) | Todas as "confirmações" medem ~50% em 69k velas reais OTC | confiança = acertividade medida por tipo de sinal (calib.py) |
| Deadlock de sinais | NO_TRADE a nível classe/estratégia com amostras pequenas escondia tudo (0 sinais, sem recolher evidência) | NO_TRADE só no conjunto exacto ≥60 amostras; regime volta a ser só etiqueta; fallback mostra melhores como OBSERVAÇÃO |
| Avaliação enviesada | saída usava `cds[-1]` (vela em formação) e preço parado = LOSS | saída = primeira vela com open ≥ vencimento; empate/ausência = `void` |
| Histórico volátil | SIG_RESULTS em memória zerava a cada deploy | Supabase `pinhanha_signals` (reposto no arranque) |
| Preços errados nos _otc | `yahoo_symbol()` tira `_OTC` → sinais OTC calculados em preços do mercado real, não nos preços sintéticos da corretora | etiqueta `aprox` na UI; com sessão Quotex ligada, ticks reais substituem |

## 2. Prova estatística (obrigatória pelo brief)

Dataset real: 69 100 velas 1m de 12 pares OTC descarregadas da Quotex (96h).
Split cronológico: treino 60% / teste 40%, sem look-ahead (a estratégia vê só
velas ≤ i; resultado = vela i+1). Breakeven Quotex a payout 0,87 = 53,5%.

### Todas as 22 estratégias + 5 compostas novas — global:

| estratégia | IS n | IS wr | OOS n | OOS wr |
|---|---|---|---|---|
| ai_turbo | 39 451 | 49,7% | 26 968 | 50,2% |
| candle_patterns | 25 257 | 50,0% | 17 157 | 50,0% |
| multi_indicator | 22 458 | 49,6% | 15 678 | 50,0% |
| trend_following | 19 184 | 49,9% | 13 325 | 50,6% |
| bible_engulfing | 1 509 | 51,2% | 995 | 50,6% |
| C_breakout (nova) | 2 435 | 52,0% | 1 574 | 50,6% |
| A_reversao (nova) | 3 565 | 50,7% | 2 468 | 49,3% |
| B_pullback (nova) | 6 675 | 48,9% | 4 475 | 49,2% |
| D_range (nova) | 947 | 50,5% | 659 | 48,7% |
| E_mtf (nova) | 3 179 | 50,0% | 2 120 | 49,9% |
| (restantes 15) | … | 48,7–51,1% | … | 46,0–52,6% |

### Células "vantajosas" in-sample → todas revertem OOS:

USDCAD bible_engulfing 59,3%→47,8% · GBPUSD breakout 55,9%→43,6% ·
EURJPY C_breakout 55,7%→45,8% · USDJPY A_reversao 57,2%→54,2% (o melhor caso,
n=201 — dentro do ruído de 264 células) · AUDUSD C_breakout 54,1%→59,6% (n=99,
único OOS "bom" — sobrevivência aleatória, não edge).

Contrário também falha: NZDUSD momentum 38,2% IS → 51,6% OOS (o "flip" não se
mantém). Conclusão: os desvios in-sample são ruído de comparações múltiplas.

**Veredito §13 do brief: nenhuma estratégia demonstra vantagem estatística
consistente em dados OTC 1m — reporta-se resultado negativo, sem forçar
conclusão positiva.** Por isso as 5 estratégias novas entraram como votantes
normais (medidos pela calibração live como todos) e não como "vencedoras".

## 3. O que mudou no código

- `app/strategies.py`: +5 estratégias compostas Quantum (regras Nison/bíblia):
  `q_reversao`, `q_pullback`, `q_breakout_retest`, `q_range_fade`, `q_mtf`.
- VOTERS 8 → 15 (as 5 novas + bible_engulfing/bible_pinbar já existentes).
- `app/calib.py`: grade() nunca esconde; `no_trade_exact()` só conjunto
  exacto ≥60 amostras p<45% (sem deadlock).
- `_sig_evaluate`: saída = primeira vela fechada ≥ vencimento; `void` correto.
- `app/sigstore.py`: histórico em Supabase (sobrevive a deploys).
- Sinais levam `src` (yahoo/quotex) e UI marca `aprox` em _otc com dados Yahoo.
- Fallback (commit anterior): <3 sinais → mostra melhores como OBSERVAÇÃO.
- `tests/test_calib.py` (13 testes) + suite existente: **24 passam**.

## 4. Porque falha ao vivo (resposta honesta à pergunta do utilizador)

1. **Não existe edge a 1 min nos dados OTC** — todas as abordagens (22 estratégias
   + 5 compostas + confluências) medem ~50%: lançamento de moeda vs breakeven
   de 53,5%. Não há "quase invencível" neste horizonte com estas features.
2. **Em SIM, os preços _otc são proxy** (mercado real Yahoo), não os preços
   sintéticos da corretora → sinais certos sobre a série errada.
3. **Antes dos fixes, a medição estava enviesada** (vela errada, ties=loss) —
   o WR medido 31-39% era em parte artefacto; espera-se ~50% honesto.
4. Expiração 60s: o modelo económico exige >53,5% só para empatar.

## 5. Caminhos reais para melhorar (por ordem de evidência)

- **Payout**: breakeven = 1/(1+R). Mostrar payout por ativo quando a sessão
  Quotex está ligada e priorizar os de payout alto (ex: 0,92 → 52,1%).
- **Mais dados**: 96h/69k velas é pouco; recolher semanas de OTC + ticks reais.
- **Microestrutura**: ticks (não velas) podem ter autocorrelação explorável —
  precisa de dados de tick da corretora.
- **Horizonte**: testar 3m/5m/15m quando houver dados — edge pode existir só
  em prazos maiores.
- Manter tracking live: a calibração esconde sozinha (NO_TRADE exacto) o que
  provar ser mau e promove (FORTE) o que provar ser bom.

## 6. Limitações

- Dataset só cobre 4 dias (Qui–Dom) e 12 pares OTC 1m — regimes novos podem
  mudar conclusões; o sistema live mede continuamente.
- Preços OTC são sintéticos por corretora; resultados não transferem para
  outros brokers/ativos sem re-teste.
- Groq não entra na votação (fase pendente — precisa de avaliação OOS própria).

## 7. Reversão

`git revert` nos commits 5efb0ca, acf9ed0, 5adad23, ccb6745, 5b500fc, 8ccdf41,
36a1d67 e no commit das estratégias Quantum; `PUT /env-vars` não é preciso
(sigstore é no-op sem envs).
