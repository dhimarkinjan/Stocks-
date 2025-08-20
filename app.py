import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
import io
from datetime import datetime
import time
import yfinance as yf  # fallback & price history

# ---------------------------- App chrome ----------------------------
st.set_page_config(page_title="Stock Analyzer (NSE + Screener)", layout="wide")
st.title("📊 Stock Analyzer — Yahoo Finance + Screener.in (Multi-stock)")
st.caption(
    "Enter NSE symbols with .NS suffix (e.g., RELIANCE.NS). "
    "Prices & 52W stats try NSE (more accurate for India) with Yahoo fallback. "
    "Shareholding best-effort from Screener.in."
)

# ---------------------------- Preset tickers ----------------------------
NIFTY50 = [
    "ADANIPORTS.NS","ASIANPAINT.NS","AXISBANK.NS","BAJAJ-AUTO.NS","BAJFINANCE.NS","BAJAJFINSV.NS",
    "BPCL.NS","BHARTIARTL.NS","BRITANNIA.NS","CIPLA.NS","COALINDIA.NS","DIVISLAB.NS",
    "DRREDDY.NS","EICHERMOT.NS","GAIL.NS","GRASIM.NS","HCLTECH.NS","HDFCBANK.NS","HDFCLIFE.NS",
    "HEROMOTOCO.NS","HINDALCO.NS","HINDUNILVR.NS","ICICIBANK.NS","INDUSINDBK.NS","INFY.NS","ITC.NS",
    "JSWSTEEL.NS","KOTAKBANK.NS","LT.NS","M&M.NS","MARUTI.NS","NESTLEIND.NS","NTPC.NS","ONGC.NS","POWERGRID.NS",
    "RELIANCE.NS","SBIN.NS","SUNPHARMA.NS","TATAMOTORS.NS","TATASTEEL.NS","TCS.NS","TECHM.NS","TITAN.NS",
    "ULTRACEMCO.NS","UPL.NS","WIPRO.NS","INDIGO.NS","BANKBARODA.NS"
]

# ---------------------------- Inputs (session_state) ----------------------------
col1, col2 = st.columns([3,1])
if "symbols_input" not in st.session_state:
    st.session_state.symbols_input = "RELIANCE.NS,TCS.NS,INFY.NS"

with col1:
    symbols_input = st.text_input(
        "Symbols (comma-separated)",
        value=st.session_state.symbols_input,
        key="symbols_input"
    )
with col2:
    if st.button("Load NIFTY50 preset"):
        st.session_state.symbols_input = ",".join(NIFTY50)
        st.rerun()

symbols = [s.strip().upper() for s in st.session_state.symbols_input.split(",") if s.strip()]
max_symbols = st.sidebar.number_input("Max symbols to process (to avoid slow scraping)", 1, 50, 6, step=1)
symbols = symbols[:max_symbols]

# ---------------------------- Sidebar options ----------------------------
st.sidebar.header("Options & Export")
min_score = st.sidebar.slider("Min score % to include in summary", 0, 100, 0)
export_csv = st.sidebar.checkbox("Enable CSV export of summary", True)
delay_between_scrapes = st.sidebar.slider("Delay between Screener requests (seconds)", 0, 3, 1, 1)

# ---------------------------- Rules (unchanged) ----------------------------
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

def pct_fmt(x):
    if x is None or (isinstance(x, float) and np.isnan(x)): return "N/A"
    try: return f"{x:.2%}"
    except: return str(x)

def num_fmt(x):
    if x is None or (isinstance(x, float) and np.isnan(x)): return "N/A"
    if isinstance(x, (int, float)):
        absx = abs(x)
        if absx >= 1e12: return f"{x/1e12:.2f}T"
        if absx >= 1e9:  return f"{x/1e9:.2f}B"
        if absx >= 1e7:  return f"{x/1e7:.2f}Cr"
        if absx >= 1e5:  return f"{x/1e5:.2f}L"
        return f"{x:,.0f}"
    return str(x)

# ---------------------------- NSE India helpers ----------------------------
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/"
}

def nse_session():
    s = requests.Session()
    s.headers.update(NSE_HEADERS)
    # warm-up to set cookies
    try:
        s.get("https://www.nseindia.com", timeout=10)
    except:
        pass
    return s

def get_nse_quote(symbol_ns):
    """
    Returns dict with keys: lastPrice, weekHigh, weekLow, marketCap (approx), success flag.
    symbol_ns: 'RELIANCE.NS' -> NSE symbol 'RELIANCE'
    """
    sym = symbol_ns.replace(".NS", "").replace(".BO", "")
    out = {"success": False, "lastPrice": None, "weekHigh": None, "weekLow": None, "marketCap": None}
    try:
        s = nse_session()
        url = f"https://www.nseindia.com/api/quote-equity?symbol={sym}"
        r = s.get(url, timeout=12)
        if r.status_code != 200:
            return out
        data = r.json()
        pi = (data or {}).get("priceInfo", {}) or {}
        whl = pi.get("weekHighLow", {}) or {}
        out["lastPrice"] = pi.get("lastPrice")
        out["weekHigh"] = whl.get("max")
        out["weekLow"]  = whl.get("min")

        # Market cap best-effort: issuedSize (no. of shares) * lastPrice
        sec = (data or {}).get("securityInfo", {}) or {}
        issued = sec.get("issuedSize")  # may be None
        if issued and out["lastPrice"]:
            try:
                out["marketCap"] = float(issued) * float(out["lastPrice"])
            except:
                out["marketCap"] = None
        out["success"] = True
        return out
    except:
        return out

# ---------------------------- Screener scraping (unchanged) ----------------------------
def get_screener_holdings(symbol):
    result = {"Promoter": None, "Pledged": None, "FII/DII": None}
    try:
        s = symbol.replace(".NS","").replace(".BO","").upper()
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
            text = soup.get_text(separator="|").lower()
            tables = soup.find_all("table")
            for tbl in tables:
                txt = tbl.get_text("|").lower()
                if any(key in txt for key in ["promoter","promoters","fii","dii","pledge","pledged","institut"]):
                    rows = tbl.find_all("tr")
                    for row in rows:
                        cols = [c.get_text(strip=True) for c in row.find_all(["th","td"])]
                        low = [c.lower() for c in cols]
                        if any("promoter" in c for c in low):
                            for part in cols:
                                if "%" in part: result["Promoter"] = part; break
                        if any("pledge" in c for c in low):
                            for part in cols:
                                if "%" in part: result["Pledged"] = part; break
                        if any(("fii" in c) or ("dii" in c) or ("institut" in c) for c in low):
                            for part in cols:
                                if "%" in part: result["FII/DII"] = part; break
            if any(result.values()):
                return result
        return result
    except Exception:
        return result

# ---------------------------- Financials (Yahoo for ratios) ----------------------------
def get_financial_points(symbol):
    # Use Yahoo as a convenience for ratios not easily available for free.
    try:
        info = yf.Ticker(symbol).info or {}
    except Exception:
        info = {}
    fin = {
        "roe": info.get("returnOnEquity"),
        "roce": info.get("returnOnAssets"),     # proxy; true ROCE not available
        "pb": info.get("priceToBook"),
        "pe": info.get("trailingPE") or info.get("forwardPE"),
        "eps": info.get("trailingEps"),
        "op_margin": info.get("operatingMargins"),
        "np_margin": info.get("profitMargins"),
        "div_yield": info.get("dividendYield"),
        "de": info.get("debtToEquity"),
        "peg": info.get("pegRatio"),
    }
    return fin

def price_indicators(symbol):
    try:
        hist = yf.Ticker(symbol).history(period="400d")
        if hist.empty: return None, None, None, None, None
        close = hist["Close"]; vol = hist["Volume"]
        ma50 = close.rolling(50).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1]
        dma_bull = bool(ma50 > ma200) if (not np.isnan(ma50) and not np.isnan(ma200)) else None
        vol5 = vol.rolling(5).mean().iloc[-1]
        vol20 = vol.rolling(20).mean().iloc[-1]
        return ma50, ma200, dma_bull, vol5, vol20
    except Exception:
        return None, None, None, None, None

# ---------------------------- Build one symbol ----------------------------
def build_table_for(symbol):
    # NSE for price meta (fallback Yahoo)
    q = get_nse_quote(symbol)
    if not q["success"]:
        info_y = yf.Ticker(symbol).info or {}
        mcap = info_y.get("marketCap"); wkhi = info_y.get("fiftyTwoWeekHigh"); wklo = info_y.get("fiftyTwoWeekLow")
    else:
        mcap = q["marketCap"]; wkhi = q["weekHigh"]; wklo = q["weekLow"]

    fin = get_financial_points(symbol)
    screener = get_screener_holdings(symbol)
    ma50, ma200, dma_bull, vol5, vol20 = price_indicators(symbol)

    rows = []
    rows.append(["Revenue Growth (5Y CAGR)", None, "Context", "Use financials for CAGR (free API may not provide full series)."])
    rows.append(["Profit Growth (5Y CAGR)", None, "Context", "Use financials for CAGR (free API may not provide full series)."])
    rows.append(["EPS (TTM)", fin.get("eps"), "✅" if fin.get("eps") and fin.get("eps")>0 else "❌", "EPS should be positive."])
    rows.append(["Debt-to-Equity", fin.get("de"), "✅" if fin.get("de") is not None and fin.get("de")<1 else "❌", "D/E <1 preferred."])
    rows.append(["ROE", fin.get("roe"), "✅" if fin.get("roe") and fin.get("roe")>0.15 else "❌", "ROE >15% preferred."])
    rows.append(["ROCE", fin.get("roce"), "Context", "ROCE calculation may need company statements."])
    rows.append(["Free Cash Flow", None, "Context", "FCF not always available via free APIs."])
    rows.append(["Operating Margin", fin.get("op_margin"), "✅" if fin.get("op_margin") and fin.get("op_margin")>0.15 else "❌", "Operating margin >15%."])
    rows.append(["Net Profit Margin", fin.get("np_margin"), "✅" if fin.get("np_margin") and fin.get("np_margin")>0.10 else "❌", "Net margin >10%."])
    rows.append(["P/E (context)", fin.get("pe"), "Context", "Compare P/E with industry average."])
    rows.append(["P/B", fin.get("pb"), "✅" if fin.get("pb") and fin.get("pb")<3 else "❌", "P/B <3 preferred."])
    rows.append(["PEG", fin.get("peg"), "Context", "PEG <1 preferred."])
    rows.append(["Dividend Yield", fin.get("div_yield"), "✅" if fin.get("div_yield") and fin.get("div_yield")>0.02 else "❌", "Dividend yield >2% preferred."])
    rows.append(["50DMA > 200DMA", dma_bull, "✅" if dma_bull else "❌", "50DMA > 200DMA indicates bullish trend."])
    rows.append(["Volume Trend", bool(vol5 is not None and vol20 is not None and vol5 > vol20), "✅" if (vol5 is not None and vol20 is not None and vol5 > vol20) else "❌", "Short-term volume trending up."])
    rows.append(["Promoter Holding", screener.get("Promoter"), "Context", "Promoter >50% preferred."])
    rows.append(["Pledged %", screener.get("Pledged"), "Context", "Prefer 0% pledged."])
    rows.append(["FII/DII Holding", screener.get("FII/DII"), "Context", "Institutional holding trend matters."])

    df = pd.DataFrame(rows, columns=["Parameter","Value","Verdict","Why it matters"])

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

# ---------------------------- MAIN LOOP ----------------------------
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

            if screener and any(screener.values()):
                st.markdown("**Shareholding (Screener.in - best-effort)**")
                st.write(screener)

            # Price chart (1 year) from Yahoo (chart only)
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

            time.sleep(delay_between_scrapes)  # be polite to Screener
        except Exception as e:
            st.error(f"{sym}: {e}")

# ---------------------------- Summary + Export ----------------------------
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
        st.download_button(
            "Download summary as CSV",
            data=b,
            file_name=f"stock_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

st.info(
    "Notes: NSE prices/52W via unofficial API (with Yahoo fallback). "
    "Screener.in scraping is best-effort; HTML changes may break it. "
    "For audited fundamentals, rely on filings or paid APIs."
)
