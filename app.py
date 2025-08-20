import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
import io
from datetime import datetime
import time

st.set_page_config(page_title="Stock Analyzer (Yahoo + Screener)", layout="wide")
st.title("📊 Stock Analyzer — Yahoo Finance + Screener.in (Multi-stock)")

st.caption("Enter NSE symbols with .NS suffix (e.g., RELIANCE.NS). The app fetches financials from yfinance and shareholding from Screener.in (best-effort scraping).")

# Nifty50 preset (common tickers)
NIFTY50 = [
"ADANIPORTS.NS","ASIANPAINT.NS","AXISBANK.NS","BAJAJ-AUTO.NS","BAJFINANCE.NS","BAJAJFINSV.NS",
"BPCL.NS","BHARTIARTL.NS","BRITANNIA.NS","CIPLA.NS","COALINDIA.NS","DIVISLAB.NS",
"DRREDDY.NS","EICHERMOT.NS","GAIL.NS","GRASIM.NS","HCLTECH.NS","HDFC.NS","HDFCBANK.NS","HDFCLIFE.NS",
"HEROMOTOCO.NS","HINDALCO.NS","HINDUNILVR.NS","ICICIBANK.NS","INDUSINDBK.NS","INFY.NS","ITC.NS",
"JSWSTEEL.NS","KOTAKBANK.NS","LT.NS","M&M.NS","MARUTI.NS","NESTLEIND.NS","NTPC.NS","ONGC.NS","POWERGRID.NS",
"RELIANCE.NS","SBIN.NS","SUNPHARMA.NS","TATAMOTORS.NS","TATASTEEL.NS","TCS.NS","TECHM.NS","TITAN.NS",
"ULTRACEMCO.NS","UPL.NS","WIPRO.NS","INDIGO.NS","BANKBARODA.NS"
]

col1, col2 = st.columns([3,1])
with col1:
    symbols_input = st.text_input("Symbols (comma-separated)", "RELIANCE.NS,TCS.NS,INFY.NS")
with col2:
    if st.button("Load NIFTY50 preset"):
        symbols_input = ",".join(NIFTY50)
        st.experimental_rerun()

symbols = [s.strip().upper() for s in symbols_input.split(",") if s.strip()]
max_symbols = st.sidebar.number_input("Max symbols to process (to avoid slow scraping)", min_value=1, max_value=50, value=6, step=1)
symbols = symbols[:max_symbols]

# Sidebar options
st.sidebar.header("Options & Export")
min_score = st.sidebar.slider("Min score % to include in summary", 0, 100, 0)
export_csv = st.sidebar.checkbox("Enable CSV export of summary", True)
delay_between_scrapes = st.sidebar.slider("Delay between Screener requests (seconds)", 0, 3, 1, 1)

# Threshold rules
RULES = {
    "Revenue Growth (5Y CAGR)": {"op": ">", "threshold": 0.08},
    "Profit Growth (5Y CAGR)": {"op": ">", "threshold": 0.10},
    "EPS (TTM)": {"op": ">", "threshold": 0},
    "Debt-to-Equity": {"op": "<", "threshold": 1.0},
    "Interest Coverage": {"op": ">", "threshold": 3.0},
    "ROE": {"op": ">", "threshold": 0.15},
    "ROCE": {"op": ">", "threshold": 0.15},
    "Free Cash Flow": {"op": ">", "threshold": 0},
    "Operating Margin": {"op": ">", "threshold": 0.15},
    "Net Profit Margin": {"op": ">", "threshold": 0.10},
    "P/B": {"op": "<", "threshold": 3.0},
    "PEG": {"op": "<", "threshold": 1.0},
    "Dividend Yield": {"op": ">", "threshold": 0.02},
    "50DMA > 200DMA": {"op": "bool", "threshold": True},
    "Volume Trend": {"op": "bool", "threshold": True},
    "P/E (context)": {"op": "info", "threshold": None},
    "Promoter Holding": {"op": "external", "threshold": None},
    "FII/DII Holding": {"op": "external", "threshold": None},
}

def verdict(op, value, threshold):
    if value is None:
        return "N/A", None
    try:
        if op == ">":
            ok = value > threshold
        elif op == "<":
            ok = value < threshold
        elif op == "bool":
            ok = bool(value) == bool(threshold)
        elif op in ("info", "external"):
            return "Context", None
        else:
            return "N/A", None
        return ("✅" if ok else "❌"), ok
    except Exception:
        return "N/A", None

def pct_fmt(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "N/A"
    try:
        return f"{x:.2%}"
    except Exception:
        return str(x)

def num_fmt(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "N/A"
    if isinstance(x, (int, float)):
        absx = abs(x)
        if absx >= 1e12:
            return f"{x/1e12:.2f}T"
        if absx >= 1e9:
            return f"{x/1e9:.2f}B"
        if absx >= 1e7:
            return f"{x/1e7:.2f}Cr"
        if absx >= 1e5:
            return f"{x/1e5:.2f}L"
        return f"{x:,.0f}"
    return str(x)

def compute_cagr(series):
    try:
        series = [float(v) for v in series if v is not None and not np.isnan(v)]
        if len(series) < 2:
            return None
        start, end = series[0], series[-1]
        years = len(series) - 1
        if start <= 0 or years <= 0:
            return None
        return (end / start) ** (1/years) - 1
    except Exception:
        return None

def get_screener_holdings(symbol):
    """Best-effort: scrape Screener.in for shareholding values"""
    result = {"Promoter": None, "Pledged": None, "FII/DII": None}
    try:
        s = symbol.replace(".NS","").replace(".BO","").upper()
        # Try multiple Screener URL patterns
        urls = [
            f"https://www.screener.in/company/{s}/consolidated/",
            f"https://www.screener.in/company/{s}/",
            f"https://www.screener.in/company/{s}/share-holding/",
        ]
        headers = {"User-Agent":"Mozilla/5.0"}
        for url in urls:
            try:
                r = requests.get(url, headers=headers, timeout=10)
            except Exception:
                continue
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            # Look for shareholding tables
            # Many screener pages show tables with "Promoters", "Institutions", "FIIs/DIIs"
            text = soup.get_text(separator="|").lower()
            if "promoters" in text or "promoter" in text:
                # Try parse numeric percentages from text near keywords
                # Search table rows
                tables = soup.find_all("table")
                for tbl in tables:
                    txt = tbl.get_text("|").lower()
                    if "promoters" in txt or "promoter" in txt:
                        rows = tbl.find_all("tr")
                        for row in rows:
                            cols = [c.get_text(strip=True) for c in row.find_all(["th","td"])]
                            cols_lower = [c.lower() for c in cols]
                            if any("promoter" in c for c in cols_lower) and len(cols) >= 2:
                                # find percentage in cols
                                for part in cols:
                                    if "%" in part:
                                        result["Promoter"] = part
                                        break
                            if any("pledge" in c for c in cols_lower) and len(cols) >= 2:
                                for part in cols:
                                    if "%" in part:
                                        result["Pledged"] = part
                                        break
                            if any("fii" in c or "dii" in c or "institut" in c for c in cols_lower) and len(cols) >= 2:
                                for part in cols:
                                    if "%" in part:
                                        result["FII/DII"] = part
                                        break
                # If parsed something, return
                if any(result.values()):
                    return result
            # fallback: look for "shareholding pattern" section text
            if "shareholding" in text:
                # attempt simple extraction near keywords
                for keyword in ["promoters", "pledged", "fiis", "diis", "institutions"]:
                    if keyword in text:
                        # naive search for nearest percentage pattern like '34.56%'
                        import re
                        m = re.search(r"(\d{1,3}\.\d+%|\d{1,3}%|\d{1,3}\.\d+ %)", text)
                        if m:
                            # assign to promoter if promoters mentioned
                            if "promoter" in text and result["Promoter"] is None:
                                result["Promoter"] = m.group(0)
        return result
    except Exception:
        return result

def get_financial_points(tkr: yf.Ticker):
    # minimal robust fetch
    info = getattr(tkr, "info", {}) or {}
    fin = {}
    fin["roe"] = info.get("returnOnEquity")
    fin["roce"] = info.get("returnOnAssets")  # fallback; true ROCE calculation not always available
    fin["pb"] = info.get("priceToBook")
    fin["pe"] = info.get("trailingPE") or info.get("forwardPE")
    fin["eps"] = info.get("trailingEps")
    fin["op_margin"] = info.get("operatingMargins")
    fin["np_margin"] = info.get("profitMargins")
    fin["div_yield"] = info.get("dividendYield")
    fin["de"] = info.get("debtToEquity")
    return fin

def price_indicators(symbol):
    try:
        hist = yf.Ticker(symbol).history(period="400d")
        if hist.empty:
            return None, None, None, None, None
        close = hist["Close"]
        vol = hist["Volume"]
        ma50 = close.rolling(50).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1]
        dma_bull = bool(ma50 > ma200) if (not np.isnan(ma50) and not np.isnan(ma200)) else None

        vol5 = vol.rolling(5).mean().iloc[-1]
        vol20 = vol.rolling(20).mean().iloc[-1]
        vol_trend = bool(vol5 > vol20) if (not np.isnan(vol5) and not np.isnan(vol20)) else None

        return ma50, ma200, dma_bull, vol5, vol20
    except Exception:
        return None, None, None, None, None

def build_table_for(symbol):
    tkr = yf.Ticker(symbol)
    info = getattr(tkr, "info", {}) or {}
    mcap = info.get("marketCap")
    wkhi = info.get("fiftyTwoWeekHigh")
    wklo = info.get("fiftyTwoWeekLow")

    fin = get_financial_points(tkr)
    screener = get_screener_holdings(symbol)
    ma50, ma200, dma_bull, vol5, vol20 = price_indicators(symbol)

    rows = []
    rows.append(["Revenue Growth (5Y CAGR)", None, "Context", "Use financials for CAGR (Yahoo may not provide full series)."])
    rows.append(["Profit Growth (5Y CAGR)", None, "Context", "Use financials for CAGR (Yahoo may not provide full series)."])
    rows.append(["EPS (TTM)", fin.get("eps"), "✅" if fin.get("eps") and fin.get("eps")>0 else "❌", "EPS should be positive."])
    rows.append(["Debt-to-Equity", fin.get("de"), "✅" if fin.get("de") is not None and fin.get("de")<1 else "❌", "D/E <1 preferred."])
    rows.append(["ROE", fin.get("roe"), "✅" if fin.get("roe") and fin.get("roe")>0.15 else "❌", "ROE >15% preferred."])
    rows.append(["ROCE", fin.get("roce"), "Context", "ROCE calculation may need company statements."])
    rows.append(["Free Cash Flow", None, "Context", "FCF not always available via yfinance."])
    rows.append(["Operating Margin", fin.get("op_margin"), "✅" if fin.get("op_margin") and fin.get("op_margin")>0.15 else "❌", "Operating margin >15%."])
    rows.append(["Net Profit Margin", fin.get("np_margin"), "✅" if fin.get("np_margin") and fin.get("np_margin")>0.10 else "❌", "Net margin >10%."])
    rows.append(["P/E (context)", fin.get("pe"), "Context", "Compare P/E with industry average."])
    rows.append(["P/B", fin.get("pb"), "✅" if fin.get("pb") and fin.get("pb")<3 else "❌", "P/B <3 preferred."])
    rows.append(["PEG", info.get("pegRatio") if (info := getattr(tkr,'info',None)) else None, "Context", "PEG <1 preferred."])
    rows.append(["Dividend Yield", fin.get("div_yield"), "✅" if fin.get("div_yield") and fin.get("div_yield")>0.02 else "❌", "Dividend yield >2% preferred."])
    rows.append(["50DMA > 200DMA", dma_bull, "✅" if dma_bull else "❌", "50DMA > 200DMA indicates bullish trend."])
    rows.append(["Volume Trend", bool(vol5 is not None and vol20 is not None and vol5 > vol20), "✅" if (vol5 is not None and vol20 is not None and vol5 > vol20) else "❌", "Short-term volume trending up."])
    rows.append(["Promoter Holding", screener.get("Promoter"), "Context", "Promoter >50% preferred."])
    rows.append(["Pledged %", screener.get("Pledged"), "Context", "Prefer 0% pledged."])
    rows.append(["FII/DII Holding", screener.get("FII/DII"), "Context", "Institutional holding trend matters."])

    df = pd.DataFrame(rows, columns=["Parameter","Value","Verdict","Why it matters"])

    # Score - count only explicit ✅/❌
    passed = sum(1 for v in df["Verdict"] if v == "✅")
    considered = sum(1 for v in df["Verdict"] if v in ("✅","❌"))
    score = (passed / considered)*100 if considered > 0 else None

    meta = {
        "Market Cap": num_fmt(mcap),
        "52W High": num_fmt(wkhi),
        "52W Low": num_fmt(wklo),
        "50DMA": num_fmt(ma50),
        "200DMA": num_fmt(ma200),
        "Avg Vol (20d)": num_fmt(vol20),
    }

    return df, score, meta, screener

# MAIN LOOP - process symbols
summary_rows = []
for sym in symbols:
    with st.spinner(f"Fetching {sym} ..."):
        try:
            df, score, meta, screener = build_table_for(sym)
            st.subheader(sym)
            cols = st.columns(6)
            meta_keys = ["Market Cap", "52W High", "52W Low", "50DMA", "200DMA", "Avg Vol (20d)"]
            for i, k in enumerate(meta_keys):
                with cols[i]:
                    st.metric(k, meta.get(k, "N/A"))
            if score is not None:
                st.success(f"Overall Score (rules passed): {score:.1f}%")
            st.dataframe(df, use_container_width=True)

            # Show screener holder raw text if available
            if screener and any(screener.values()):
                st.markdown("**Shareholding (Screener.in - best-effort)**")
                st.write(screener)

            # Price chart (1 year)
            hist = yf.Ticker(sym).history(period="1y")
            if not hist.empty:
                plt.figure()
                plt.plot(hist.index, hist["Close"], label=sym)
                plt.legend()
                st.pyplot(plt)

                summary_rows.append({
                "Stock": sym,
                "Score %": round(score,1) if score is not None else None,
                "ROE": pct_fmt(df.loc[df["Parameter"]=="ROE","Value"].values[0]) if "ROE" in df["Parameter"].values else "N/A",
                "D/E": df.loc[df["Parameter"]=="Debt-to-Equity","Value"].values[0] if "Debt-to-Equity" in df["Parameter"].values else "N/A",
                "P/E": df.loc[df["Parameter"]=="P/E (context)","Value"].values[0] if "P/E (context)" in df["Parameter"].values else "N/A",
                "P/B": df.loc[df["Parameter"]=="P/B","Value"].values[0] if "P/B" in df["Parameter"].values else "N/A",
                "Promoter": screener.get("Promoter"),
                "FII/DII": screener.get("FII/DII"),
            })

            # polite delay to avoid hammering Screener
            time.sleep(delay_between_scrapes)
        except Exception as e:
            st.error(f"{sym}: {e}")

# Summary table and CSV export
if summary_rows:
    sumdf = pd.DataFrame(summary_rows)
    if min_score > 0:
        sumdf = sumdf[sumdf["Score %"] >= min_score]
    st.markdown("## 📋 Summary Comparison")
    st.dataframe(sumdf, use_container_width=True)

    if export_csv and not sumdf.empty:
        csv_io = io.StringIO()
        sumdf.to_csv(csv_io, index=False)
        b = csv_io.getvalue().encode()
        st.download_button("Download summary as CSV", data=b, file_name=f"stock_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv")

st.info("Notes: Screener.in scraping is best-effort. If Screener's HTML changes the parsing may fail. For reliable official shareholding use company filings or paid APIs.")
