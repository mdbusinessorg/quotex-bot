"""Knowledge Base — metadados e resumos próprios de fontes legítimas.
Não copia conteúdo protegido; guarda referências e resumos."""

KNOWLEDGE = [
    {
        "category": "Technical Analysis",
        "items": [
            {"title": "Technical Analysis of the Financial Markets", "author": "John J. Murphy",
             "summary": "Referência base de AT: tendências, médias, padrões gráficos e indicadores. Conceito-chave: 'the trend is your friend'.",
             "source": "Livro (1999), Prentice Hall"},
            {"title": "New Concepts in Technical Trading Systems", "author": "J. Welles Wilder",
             "summary": "Origem do RSI, ADX, ATR e Parabolic SAR. Fórmulas e interpretação originais usadas neste projeto.",
             "source": "Livro (1978), Trend Research"},
        ],
    },
    {
        "category": "Price Action",
        "items": [
            {"title": "Japanese Candlestick Charting Techniques", "author": "Steve Nison",
             "summary": "Padrões de velas: engolfo, martelo, estrela, doji, três soldados/corvos. Base das estratégias de price action.",
             "source": "Livro (1991), NYIF"},
            {"title": "Encyclopedia of Chart Patterns", "author": "Thomas Bulkowski",
             "summary": "Catálogo estatístico de padrões gráficos com taxas de sucesso medidas.",
             "source": "Livro (2000), Wiley"},
        ],
    },
    {
        "category": "Risk Management",
        "items": [
            {"title": "Trade Your Way to Financial Freedom", "author": "Van K. Tharp",
             "summary": "Position sizing, R-multiples e expectativa. Base do Risk Manager: limites diários e exposição.",
             "source": "Livro (1998), McGraw-Hill"},
        ],
    },
    {
        "category": "Trading Psychology",
        "items": [
            {"title": "Trading in the Zone", "author": "Mark Douglas",
             "summary": "Pensamento probabilístico: cada trade é um evento aleatório numa série — nenhuma estratégia garante lucro.",
             "source": "Livro (2000), Prentice Hall"},
        ],
    },
    {
        "category": "Market Structure",
        "items": [
            {"title": "Support & Resistance", "author": "Conceito clássico",
             "summary": "Níveis onde a pressão compradora/vendedora historicamente inverteu o preço; usados na estratégia S&R.",
             "source": "Domínio público / literatura de AT"},
        ],
    },
    {
        "category": "Indicators",
        "items": [
            {"title": "Bollinger on Bollinger Bands", "author": "John Bollinger",
             "summary": "Bandas de desvio padrão: reversão à média e squeezes de volatilidade.",
             "source": "Livro (2001), McGraw-Hill"},
            {"title": "Stochastic Oscillator", "author": "George Lane",
             "summary": "%K/%D medem a posição do fecho dentro do range recente; extremos marcam reversões.",
             "source": "Conferências de Lane (anos 50-60), amplamente documentado"},
        ],
    },
    {
        "category": "Probability",
        "items": [
            {"title": "Expectativa matemática em trading", "author": "Conceito estatístico",
             "summary": "EV = win_rate × ganho médio − loss_rate × perda média. Com payout <100%, a win rate necessária > 50%.",
             "source": "Domínio público"},
        ],
    },
    {
        "category": "Backtesting",
        "items": [
            {"title": "Evidence-Based Technical Analysis", "author": "David Aronson",
             "summary": "Metodologia rigorosa de backtest: evitar data-snooping, overfitting e viés de sobrevivência.",
             "source": "Livro (2006), Wiley"},
        ],
    },
    {
        "category": "Portfolio/Risk Control",
        "items": [
            {"title": "Against the Gods: The Remarkable Story of Risk", "author": "Peter L. Bernstein",
             "summary": "História e fundamentos da gestão de risco aplicável a qualquer mercado.",
             "source": "Livro (1996), Wiley"},
        ],
    },
]
