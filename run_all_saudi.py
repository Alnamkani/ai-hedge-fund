import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src.main import run_hedge_fund

load_dotenv()

RESULTS_FILE = Path("results/all_saudi_signals.json")
BATCH_SIZE = 5

ANALYSTS = [
    "technical_analyst",
    "fundamentals_analyst",
    "valuation_analyst",
    "warren_buffett",
    "ben_graham",
    "peter_lynch",
    "charlie_munger",
    "growth_analyst",
]

MODEL = "claude-sonnet-4-20250514"
PROVIDER = "Anthropic"
START_DATE = "2025-12-16"
END_DATE = datetime.now().strftime("%Y-%m-%d")
INITIAL_CASH = 100_000.0


def load_all_tickers() -> list[str]:
    tickers_file = Path("../trader-agent/data/tickers.json")
    tickers = json.loads(tickers_file.read_text())
    return [t["symbol"] for t in tickers]


def load_existing_results() -> dict:
    if RESULTS_FILE.exists():
        return json.loads(RESULTS_FILE.read_text())
    return {"metadata": {}, "signals": {}}


def save_results(results: dict):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(results, indent=2, default=str))


def run_batch(tickers: list[str]) -> dict:
    portfolio = {
        "cash": INITIAL_CASH,
        "margin_requirement": 0.0,
        "margin_used": 0.0,
        "positions": {
            t: {"long": 0, "short": 0, "long_cost_basis": 0.0, "short_cost_basis": 0.0, "short_margin_used": 0.0}
            for t in tickers
        },
        "realized_gains": {t: {"long": 0.0, "short": 0.0} for t in tickers},
    }

    result = run_hedge_fund(
        tickers=tickers,
        start_date=START_DATE,
        end_date=END_DATE,
        portfolio=portfolio,
        show_reasoning=False,
        selected_analysts=ANALYSTS,
        model_name=MODEL,
        model_provider=PROVIDER,
    )
    return result


def main():
    all_tickers = load_all_tickers()
    results = load_existing_results()
    done = set(results.get("signals", {}).keys())

    remaining = [t for t in all_tickers if t not in done]
    total = len(all_tickers)
    completed = len(done)

    results["metadata"] = {
        "model": MODEL,
        "provider": PROVIDER,
        "analysts": ANALYSTS,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "total_tickers": total,
        "run_started": results.get("metadata", {}).get("run_started", datetime.now().isoformat()),
        "last_updated": datetime.now().isoformat(),
    }

    print(f"Saudi Market Full Scan")
    print(f"Total: {total} | Already done: {completed} | Remaining: {len(remaining)}")
    print(f"Model: {MODEL} | Analysts: {len(ANALYSTS)}")
    print(f"Batch size: {BATCH_SIZE}\n")

    for i in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[i : i + BATCH_SIZE]
        batch_num = (completed + i) // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"\n{'='*60}")
        print(f"Batch {batch_num}/{total_batches}: {', '.join(batch)}")
        print(f"Progress: {completed + i}/{total} ({(completed + i) / total * 100:.1f}%)")
        print(f"{'='*60}")

        try:
            result = run_batch(batch)
            decisions = result.get("decisions", {})
            analyst_signals = result.get("analyst_signals", {})

            for ticker in batch:
                decision = decisions.get(ticker, {}) if decisions else {}
                ticker_signals = {}
                for agent_id, agent_data in analyst_signals.items():
                    if ticker in agent_data:
                        sig = agent_data[ticker]
                        ticker_signals[agent_id] = {
                            "signal": sig.get("signal"),
                            "confidence": sig.get("confidence"),
                            "reasoning": sig.get("reasoning"),
                        }

                results["signals"][ticker] = {
                    "action": decision.get("action", "hold"),
                    "quantity": decision.get("quantity", 0),
                    "confidence": decision.get("confidence", 0),
                    "reasoning": decision.get("reasoning", ""),
                    "agent_signals": ticker_signals,
                    "timestamp": datetime.now().isoformat(),
                }

            results["metadata"]["last_updated"] = datetime.now().isoformat()
            results["metadata"]["completed"] = len(results["signals"])
            save_results(results)
            print(f"Saved {len(results['signals'])}/{total} results")

        except KeyboardInterrupt:
            print(f"\n\nInterrupted. Saved {len(results['signals'])}/{total} results to {RESULTS_FILE}")
            save_results(results)
            sys.exit(0)
        except Exception as e:
            print(f"Batch failed: {e}")
            traceback.print_exc()
            for ticker in batch:
                results["signals"][ticker] = {
                    "action": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            save_results(results)
            continue

    results["metadata"]["run_completed"] = datetime.now().isoformat()
    save_results(results)

    bullish = sum(1 for s in results["signals"].values() if s.get("action") == "buy")
    bearish = sum(1 for s in results["signals"].values() if s.get("action") in ("short", "sell"))
    hold = sum(1 for s in results["signals"].values() if s.get("action") == "hold")
    errors = sum(1 for s in results["signals"].values() if s.get("action") == "error")

    print(f"\n{'='*60}")
    print(f"SCAN COMPLETE")
    print(f"BUY: {bullish} | SHORT/SELL: {bearish} | HOLD: {hold} | ERRORS: {errors}")
    print(f"Results saved to: {RESULTS_FILE}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
