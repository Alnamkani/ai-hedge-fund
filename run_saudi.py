import json
import sys
import argparse
from datetime import datetime

from dotenv import load_dotenv

from src.main import run_hedge_fund
from src.utils.display import print_trading_output

load_dotenv()

LIQUID_SAUDI_TICKERS = [
    "2222.SR",  # Aramco
    "1180.SR",  # Al Rajhi Bank
    "2010.SR",  # SABIC
    "1010.SR",  # Riyad Bank
    "2350.SR",  # Dar Al Arkan
    "2110.SR",  # SAIB
    "4200.SR",  # Ad-Dabbagh Group (Theeb)
    "1211.SR",  # Alinma Bank
    "4030.SR",  # Al Babtain
    "2020.SR",  # SAFCO
]

SAUDI_ANALYSTS = [
    "technical_analyst",
    "fundamentals_analyst",
    "valuation_analyst",
    "warren_buffett",
    "ben_graham",
    "peter_lynch",
    "charlie_munger",
    "growth_analyst",
]


def main():
    parser = argparse.ArgumentParser(description="Run AI hedge fund on Saudi market (Tadawul)")
    parser.add_argument("--tickers", type=str, help="Comma-separated Saudi tickers (e.g., 2222.SR,1180.SR)")
    parser.add_argument("--start-date", type=str, default="2025-12-16", help="Start date YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, default=datetime.now().strftime("%Y-%m-%d"), help="End date YYYY-MM-DD")
    parser.add_argument("--initial-cash", type=float, default=100000.0, help="Initial cash in SAR")
    parser.add_argument("--model", type=str, default="claude-sonnet-4-20250514", help="LLM model name")
    parser.add_argument("--provider", type=str, default="Anthropic", help="LLM provider")
    parser.add_argument("--analysts", type=str, help="Comma-separated analyst keys")
    parser.add_argument("--all-analysts", action="store_true", help="Use all available analysts")
    parser.add_argument("--show-reasoning", action="store_true", help="Show agent reasoning")
    args = parser.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else LIQUID_SAUDI_TICKERS[:5]
    analysts = SAUDI_ANALYSTS
    if args.analysts:
        analysts = [a.strip() for a in args.analysts.split(",")]
    elif args.all_analysts:
        analysts = []

    portfolio = {
        "cash": args.initial_cash,
        "margin_requirement": 0.0,
        "margin_used": 0.0,
        "positions": {
            ticker: {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
            for ticker in tickers
        },
        "realized_gains": {
            ticker: {"long": 0.0, "short": 0.0}
            for ticker in tickers
        },
    }

    print(f"\nSaudi Market AI Hedge Fund")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Date range: {args.start_date} to {args.end_date}")
    print(f"Model: {args.model} ({args.provider})")
    print(f"Analysts: {', '.join(analysts)}")
    print(f"Initial cash: {args.initial_cash:,.0f} SAR\n")

    result = run_hedge_fund(
        tickers=tickers,
        start_date=args.start_date,
        end_date=args.end_date,
        portfolio=portfolio,
        show_reasoning=args.show_reasoning,
        selected_analysts=analysts,
        model_name=args.model,
        model_provider=args.provider,
    )

    print_trading_output(result)


if __name__ == "__main__":
    main()
