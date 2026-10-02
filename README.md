# Quotex Trading Platform

Plataforma profissional de trading automatizado: painel web com dashboard, Auto Bot, Strategy Lab (15 estratégias), backtesting, gestão de risco, histórico e base de conhecimento.

**Conta REAL por defeito** — liga à tua conta Quotex real via API não-oficial ([pyquotex](https://github.com/cleitonleonel/pyquotex)); conta DEMO disponível como opção para treino. Sem ligação, corre um Simulation Engine local (feed sintético com slippage/latência) para testar estratégias sem risco.

## Arranque

```bash
pip install -r requirements.txt
pip install git+https://github.com/cleitonleonel/pyquotex.git   # só para conta real
BOT_PASSWORD=a-tua-password python -m app.main                  # http://localhost:8000
```

Login do painel: `BOT_PASSWORD` (defeito `devin`).

## Arquitetura

| Módulo | Função |
|---|---|
| `app/broker.py` | `BrokerAdapter` (connect/getBalance/getMarketData/placeOrder/getOrderStatus/cancelOrder) + `QuotexAdapter` (real) + `SimAdapter`/`SimFeed` (simulação) |
| `app/strategies.py` | Strategy Engine — 15 estratégias, cada uma devolve `{signal, confidence, reasons, risk}` |
| `app/risk.py` | Risk Manager — perda diária, perdas consecutivas, simultâneas, cooldown, exposição, meta diária → pausa automática |
| `app/engine.py` | Execution Engine — trades manuais + Auto Bot (loop ANALISAR→SINAL→VALIDAR→ABRIR→COUNTDOWN→RESULTADO→HISTÓRICO) |
| `app/history.py` | History Engine — SQLite com entry/exit, win-rate, profit factor, drawdown, streaks |
| `app/backtest.py` | Backtesting — corre estratégias sobre candles históricos |
| `app/analytics.py` | AI Market Analyst — agrega sinais/indicadores em decisão e confiança |
| `app/knowledge.py` | Knowledge Base — referências e resumos (sem conteúdo protegido) |
| `static/` | SPA — Dashboard / Auto Bot / Strategy Lab / Backtest / Histórico / Risco / Knowledge / Conta |

## Ligação à Quotex (conta real)

Em **Conta & Ligação**: email+password, ou **SSID da sessão** se a Cloudflare bloquear (login em qxbroker.com → DevTools → Network → websocket → mensagem `42["authorization",{"session":"..."}]`).

## API

`POST /api/auth/login` · `POST /api/broker/connect` · `POST /api/broker/account/{REAL|PRACTICE}` · `GET /api/status` · `GET /api/assets` · `GET /api/strategies` · `POST /api/trades` · `GET /api/trades` · `GET /api/history/stats` · `POST /api/autobot/start|stop` · `POST /api/risk` · `POST /api/risk/resume` · `GET /api/analysis/{asset}` · `POST /api/backtest` · `GET /api/knowledge`

## Testes

```bash
pytest tests/   # contrato das 15 estratégias, sim, risco, backtest, histórico
```

> Aviso: trading automatizado com dinheiro real tem risco elevado de perda. Nenhuma estratégia garante lucro. A API da Quotex não é oficial e a automação pode violar os termos da plataforma.
