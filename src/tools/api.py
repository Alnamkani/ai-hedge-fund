import datetime
import logging
from pathlib import Path

import pandas as pd
import yfinance as yf

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    FinancialMetrics,
    Price,
    LineItem,
    InsiderTrade,
)

logger = logging.getLogger(__name__)

_cache = get_cache()

TRADER_AGENT_DATA = Path(__file__).resolve().parents[2] / ".." / "trader-agent" / "data"
_ohlcv_df: pd.DataFrame | None = None
_tasi_df: pd.DataFrame | None = None


def _load_ohlcv() -> pd.DataFrame:
    global _ohlcv_df
    if _ohlcv_df is not None:
        return _ohlcv_df
    path = TRADER_AGENT_DATA / "all_ohlcv.parquet"
    if not path.exists():
        raise FileNotFoundError(f"OHLCV data not found at {path}. Run trader-agent download first.")
    _ohlcv_df = pd.read_parquet(path)
    _ohlcv_df["date"] = pd.to_datetime(_ohlcv_df["date"])
    return _ohlcv_df


def _load_tasi() -> pd.DataFrame:
    global _tasi_df
    if _tasi_df is not None:
        return _tasi_df
    path = TRADER_AGENT_DATA / "tasi_index.parquet"
    if not path.exists():
        raise FileNotFoundError(f"TASI index data not found at {path}.")
    _tasi_df = pd.read_parquet(path)
    _tasi_df["date"] = pd.to_datetime(_tasi_df["date"])
    return _tasi_df


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    cache_key = f"{ticker}_{start_date}_{end_date}"
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    if ticker == "^TASI.SR":
        df = _load_tasi()
    else:
        ohlcv = _load_ohlcv()
        df = ohlcv[ohlcv["symbol"] == ticker].copy()

    if df.empty:
        return []

    start_dt = pd.Timestamp(start_date)
    end_dt = pd.Timestamp(end_date)
    mask = (df["date"] >= start_dt) & (df["date"] <= end_dt)
    df = df.loc[mask].sort_values("date")

    if df.empty:
        return []

    prices = []
    for _, row in df.iterrows():
        prices.append(Price(
            open=float(row["open"]),
            close=float(row["close"]),
            high=float(row["high"]),
            low=float(row["low"]),
            volume=int(row["volume"]) if pd.notna(row["volume"]) else 0,
            time=row["date"].strftime("%Y-%m-%dT00:00:00Z"),
        ))

    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


def _get_yf_ticker(ticker: str) -> yf.Ticker:
    return yf.Ticker(ticker)


_yf_info_cache: dict[str, dict] = {}


def _get_yf_info(ticker: str) -> dict:
    if ticker in _yf_info_cache:
        return _yf_info_cache[ticker]
    try:
        info = _get_yf_ticker(ticker).info
        _yf_info_cache[ticker] = info
        return info
    except Exception as e:
        logger.warning("Failed to fetch yfinance info for %s: %s", ticker, e)
        _yf_info_cache[ticker] = {}
        return {}


def _safe_get(d: dict, key: str) -> float | None:
    val = d.get(key)
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    info = _get_yf_info(ticker)
    if not info:
        return []

    metrics = FinancialMetrics(
        ticker=ticker,
        report_period=end_date,
        period=period,
        currency=info.get("financialCurrency", "SAR"),
        market_cap=_safe_get(info, "marketCap"),
        enterprise_value=_safe_get(info, "enterpriseValue"),
        price_to_earnings_ratio=_safe_get(info, "trailingPE"),
        price_to_book_ratio=_safe_get(info, "priceToBook"),
        price_to_sales_ratio=_safe_get(info, "priceToSalesTrailing12Months"),
        enterprise_value_to_ebitda_ratio=_safe_get(info, "enterpriseToEbitda"),
        enterprise_value_to_revenue_ratio=_safe_get(info, "enterpriseToRevenue"),
        free_cash_flow_yield=None,
        peg_ratio=_safe_get(info, "pegRatio"),
        gross_margin=_safe_get(info, "grossMargins"),
        operating_margin=_safe_get(info, "operatingMargins"),
        net_margin=_safe_get(info, "profitMargins"),
        return_on_equity=_safe_get(info, "returnOnEquity"),
        return_on_assets=_safe_get(info, "returnOnAssets"),
        return_on_invested_capital=None,
        asset_turnover=None,
        inventory_turnover=None,
        receivables_turnover=None,
        days_sales_outstanding=None,
        operating_cycle=None,
        working_capital_turnover=None,
        current_ratio=_safe_get(info, "currentRatio"),
        quick_ratio=_safe_get(info, "quickRatio"),
        cash_ratio=None,
        operating_cash_flow_ratio=None,
        debt_to_equity=_safe_get(info, "debtToEquity"),
        debt_to_assets=None,
        interest_coverage=None,
        revenue_growth=_safe_get(info, "revenueGrowth"),
        earnings_growth=_safe_get(info, "earningsGrowth"),
        book_value_growth=None,
        earnings_per_share_growth=None,
        free_cash_flow_growth=None,
        operating_income_growth=None,
        ebitda_growth=None,
        payout_ratio=_safe_get(info, "payoutRatio"),
        earnings_per_share=_safe_get(info, "trailingEps"),
        book_value_per_share=_safe_get(info, "bookValue"),
        free_cash_flow_per_share=None,
    )

    fcf = _safe_get(info, "freeCashflow")
    mc = _safe_get(info, "marketCap")
    if fcf and mc and mc > 0:
        metrics.free_cash_flow_yield = fcf / mc

    result = [metrics]
    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in result])
    return result


_YF_LINE_ITEM_MAP = {
    "revenue": "Total Revenue",
    "net_income": "Net Income",
    "gross_profit": "Gross Profit",
    "operating_income": "Operating Income",
    "ebitda": "EBITDA",
    "ebit": "EBIT",
    "interest_expense": "Interest Expense",
    "tax_provision": "Tax Provision",
    "depreciation_and_amortization": "Reconciled Depreciation",
    "earnings_per_share": "Basic EPS",
    "diluted_earnings_per_share": "Diluted EPS",
}

_YF_BS_MAP = {
    "total_assets": "Total Assets",
    "total_liabilities": "Total Liabilities Net Minority Interest",
    "current_assets": "Current Assets",
    "current_liabilities": "Current Liabilities",
    "total_debt": "Total Debt",
    "cash_and_equivalents": "Cash And Cash Equivalents",
    "shareholders_equity": "Stockholders Equity",
    "common_stock": "Common Stock",
    "retained_earnings": "Retained Earnings",
    "book_value_per_share": "Tangible Book Value",
    "outstanding_shares": "Ordinary Shares Number",
    "working_capital": "Working Capital",
    "invested_capital": "Invested Capital",
    "net_debt": "Net Debt",
}

_YF_CF_MAP = {
    "free_cash_flow": "Free Cash Flow",
    "capital_expenditure": "Capital Expenditure",
    "operating_cash_flow": "Operating Cash Flow",
    "dividends_and_other_cash_distributions": "Common Stock Dividend Paid",
    "issuance_or_purchase_of_equity_shares": "Repurchase Of Capital Stock",
}


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    cache_key = f"line_{ticker}_{period}_{end_date}_{','.join(sorted(line_items))}_{limit}"
    if cached_data := _cache.get_line_items(cache_key):
        return [LineItem(**item) for item in cached_data]

    try:
        yf_ticker = _get_yf_ticker(ticker)
        use_annual = period == "annual"

        financials = yf_ticker.financials if use_annual else yf_ticker.quarterly_financials
        balance = yf_ticker.balance_sheet if use_annual else yf_ticker.quarterly_balance_sheet
        cashflow = yf_ticker.cashflow if use_annual else yf_ticker.quarterly_cashflow
    except Exception as e:
        logger.warning("Failed to fetch financial statements for %s: %s", ticker, e)
        return []

    all_statements = {}
    for name, df in [("financials", financials), ("balance", balance), ("cashflow", cashflow)]:
        if df is not None and not df.empty:
            all_statements[name] = df

    if not all_statements:
        return []

    ref_df = next(iter(all_statements.values()))
    report_dates = sorted(ref_df.columns, reverse=True)

    end_dt = pd.Timestamp(end_date)
    report_dates = [d for d in report_dates if pd.Timestamp(d) <= end_dt]
    report_dates = report_dates[:limit]

    results = []
    for report_date in report_dates:
        extra = {}
        for item_name in line_items:
            value = None

            if item_name in _YF_LINE_ITEM_MAP:
                yf_key = _YF_LINE_ITEM_MAP[item_name]
                if "financials" in all_statements and yf_key in all_statements["financials"].index:
                    val = all_statements["financials"].loc[yf_key, report_date]
                    if pd.notna(val):
                        value = float(val)

            if value is None and item_name in _YF_BS_MAP:
                yf_key = _YF_BS_MAP[item_name]
                if "balance" in all_statements and yf_key in all_statements["balance"].index:
                    val = all_statements["balance"].loc[yf_key, report_date]
                    if pd.notna(val):
                        value = float(val)

            if value is None and item_name in _YF_CF_MAP:
                yf_key = _YF_CF_MAP[item_name]
                if "cashflow" in all_statements and yf_key in all_statements["cashflow"].index:
                    val = all_statements["cashflow"].loc[yf_key, report_date]
                    if pd.notna(val):
                        value = float(val)

            if value is None:
                for stmt_name, stmt_df in all_statements.items():
                    for idx_name in stmt_df.index:
                        normalized = idx_name.lower().replace(" ", "_")
                        if normalized == item_name or item_name in normalized:
                            val = stmt_df.loc[idx_name, report_date]
                            if pd.notna(val):
                                value = float(val)
                                break
                    if value is not None:
                        break

            extra[item_name] = value

        report_date_str = pd.Timestamp(report_date).strftime("%Y-%m-%d")
        line_item = LineItem(
            ticker=ticker,
            report_period=report_date_str,
            period="annual" if use_annual else "quarterly",
            currency="SAR",
            **extra,
        )
        results.append(line_item)

    _cache.set_line_items(cache_key, [item.model_dump() for item in results])
    return results


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    return []


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    return []


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    info = _get_yf_info(ticker)
    return _safe_get(info, "marketCap")


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
