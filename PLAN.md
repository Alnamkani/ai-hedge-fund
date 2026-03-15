# Saudi Market Adaptation Plan

## What Changed

### Data Layer (`src/tools/api.py`) — Complete Rewrite
Replaced the Financial Datasets API with Saudi market data sources:

| Function | Original Source | New Source |
|---|---|---|
| `get_prices()` | financialdatasets.ai API | Local parquet from trader-agent (`data/all_ohlcv.parquet`) |
| `get_financial_metrics()` | financialdatasets.ai API | yfinance `Ticker.info` (live) |
| `search_line_items()` | financialdatasets.ai API | yfinance `.financials`, `.balance_sheet`, `.cashflow` |
| `get_insider_trades()` | financialdatasets.ai API | Returns `[]` (no Saudi insider data) |
| `get_company_news()` | financialdatasets.ai API | Returns `[]` (no Saudi news API) |
| `get_market_cap()` | financialdatasets.ai API | yfinance `Ticker.info["marketCap"]` |

### Agents — Disabled 2, Kept 16
- **Removed:** `sentiment_analyst`, `news_sentiment_analyst` (depend on insider trades + news)
- **Kept as-is:** All 12 famous investor agents, technical_analyst, fundamentals_analyst, growth_analyst, valuation_analyst
- All agents handle `None` fields gracefully — partial data is fine

### Backtester — TASI Benchmark
- Replaced `SPY` with `^TASI.SR` as the benchmark
- Removed prefetching of insider trades and news (no data)

### Dependencies
- Added `yfinance >= 1.2.0` and `pyarrow >= 14.0.0` to pyproject.toml

### New Files
- `run_saudi.py` — convenience script with Saudi defaults (top 5 liquid tickers, Anthropic Claude, pre-selected analysts)

## What Was Skipped
- Insider trade data (not publicly available for Tadawul)
- News sentiment (no free news API with sentiment for Saudi stocks)
- Short selling (not common on Tadawul, but the framework still supports it)

## How to Run

### Prerequisites
1. OHLCV data from trader-agent: `cd ../trader-agent && uv run python main.py download`
2. An LLM API key in `.env` (e.g., `ANTHROPIC_API_KEY=sk-ant-...`)

### Quick Start
```bash
cd ai-hedge-fund

# Run with defaults (top 5 Saudi stocks, Claude Sonnet, 8 analysts)
poetry run python run_saudi.py

# Specify tickers
poetry run python run_saudi.py --tickers "2222.SR,1180.SR,2010.SR"

# Use all analysts
poetry run python run_saudi.py --all-analysts

# Show reasoning from each agent
poetry run python run_saudi.py --show-reasoning

# Use a different model
poetry run python run_saudi.py --model "gpt-4.1" --provider "OpenAI"
```

### Backtesting
```bash
poetry run python -m src.backtester --tickers "2222.SR,1180.SR,2010.SR" --start-date 2025-01-01
```

## Data Coverage

### What yfinance provides for Saudi stocks (tested with 2222.SR Aramco):
- **Prices:** Full OHLCV from 2010 via parquet
- **Metrics:** PE, PB, P/S, ROE, ROA, margins, current ratio, debt/equity, revenue growth, earnings growth, EPS, book value
- **Financials:** Revenue, net income, EBITDA, gross profit, operating income, interest expense
- **Balance Sheet:** Total assets, total liabilities, equity, debt, cash, working capital, shares outstanding
- **Cash Flow:** FCF, capex, operating cash flow, dividends paid

### What's missing:
- Historical fundamental data (yfinance only returns current/TTM — not time series)
- Insider trading activity
- News with pre-tagged sentiment
- Some efficiency ratios (asset turnover, inventory turnover, receivables turnover)

## Next Steps
1. Add SAHMK Starter API for real-time quotes and market mood
2. Build a TASI regime filter agent (bull/bear based on 200-day SMA)
3. Integrate breakout scoring from trader-agent as a custom agent
4. Consider caching yfinance fundamentals to disk to avoid rate limits during backtesting
5. Add historical fundamental data source for proper time-series valuation
