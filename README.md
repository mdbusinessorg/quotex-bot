# Quotex Bot

Bot de trading automático para a Quotex com painel web: escolhes conta (DEMO/REAL), ativo, valor e expiração, escolhes uma das **15 estratégias** baseadas em literatura clássica de análise técnica, clicas **Iniciar** e o bot opera sozinho até clicares **Parar**. Saldo, sinais e resultados aparecem em tempo real no painel e o histórico fica guardado com estatísticas por estratégia.

> ⚠️ Usa uma API **não-oficial** da Quotex ([pyquotex](https://github.com/cleitonleonel/pyquotex)). Automação pode violar os termos da plataforma — testa sempre em DEMO primeiro.

## Instalação

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install git+https://github.com/cleitonleonel/pyquotex.git
python -m app.main
```

Abre **http://localhost:8000**.

## Login

Duas opções no painel:

1. **Email + password** — a pyquotex tenta autenticar diretamente.
2. **SSID da sessão** (mais fiável — a Cloudflare por vezes bloqueia o login automatizado):
   - Faz login em https://qxbroker.com no teu browser normal.
   - DevTools → Application → Cookies → copia o valor de `ssid` **ou** no separador Network, no websocket, a mensagem `42["authorization",{"session":"...","isDemo":0}]`.
   - Cola esse valor no campo SSID do painel.

Depois escolhe **DEMO** ou **REAL**.

## Estratégias (15)

| ID | Nome | Fonte |
|----|------|-------|
| sma_cross | Cruzamento SMA | Trend Following (Covel) |
| ema_cross | Cruzamento EMA | Trend Following |
| rsi_reversal | RSI Reversão | Wilder, *New Concepts* |
| rsi_trend | RSI Momentum | Wilder |
| bollinger_reversion | Bollinger Reversão à Média | Bollinger |
| bollinger_breakout | Bollinger Breakout | Bollinger |
| macd_cross | MACD Cruzamento | Appel / Elder |
| stochastic | Estocástico | George Lane |
| engulfing | Engolfo | Nison, candlesticks |
| hammer_star | Martelo / Shooting Star | Nison |
| three_soldiers | Três Soldados / Corvos | Nison |
| doji_reversal | Doji Reversão | Nison |
| adx_directional | ADX Direcional | Wilder |
| ema_pullback | Pullback à EMA | Price action em tendência |
| pinbar | Pin Bar | Price Action |

## Como funciona

- O motor busca velas de 1 min; no **fecho de cada vela** avalia a estratégia.
- Se houver sinal (`call`/`put`), executa a ordem com o valor e expiração definidos e espera o resultado via `check_win`.
- O resultado aparece no painel (ex.: `$10 → +$9,80`) e fica em `data/trades.json` com win-rate por estratégia.
- Corre em loop até clicares **Parar**.

## Testes

```bash
pip install pytest
pytest tests/
```
