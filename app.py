# app.py
import io
import time
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt

# ---------- Page ----------
st.set_page_config(page_title="Stock Analyzer (Yahoo + Screener)", layout="wide")
st.title("📊 Stock Analyzer — Yahoo Finance + Screener.in (Multi-stock)")
st.caption(
    "Enter NSE symbols with .NS suffix (e.g., RELIANCE.NS). "
    "Prices & 52W stats use Yahoo Finance. Shareholding is best-effort from Screener.in."
)

# ---------- Helper: formatting ----------
def human_inr(n):
    """Pretty INR-style: Crore/Lakh, else plain with commas."""
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "N/A"
    try:
        n = float(n)
    except Exception:
        return str(n)

    absn = abs(n)
    if absn >= 1e7:
        return f"{n/1e7:.2f} Cr"
    if absn >= 1e5:
        return f"{n/1e5:.2f} L"
    if absn >= 1e3:
        return f"{n:,.0f}"
    # small numbers keep 2dp
    return f"{n:.2f}"

def pct(x, dp=2):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "N/A"
    try:
        return f"{float(x)*100:.{dp}f}%"
    except Exception:
        return str(x)

# ---------- NIFTY50 preset ----------
NIFTY50 = [
    "ADANIPORTS.NS","ASIANPAINT.NS","AXISBANK.NS","BAJAJ-AUTO.NS","BAJFINANCE.NS","BAJAJFINSV.NS",
    "BPCL.NS","BHARTIARTL.NS","BRITANNIA.NS","CIPLA.NS","COALINDIA.NS","DIVISLAB.NS",
    "DRREDDY.NS","EICHERMOT.NS","GAIL.NS","GRASIM.NS","HCLTECH.NS","HDFCBANK.NS","HDFCLIFE.NS",
    "HEROMOTOCO.NS","HINDALCO.NS","HINDUNILVR.NS","ICICIBANK.NS","INDUSINDBK.NS","INFY.NS","ITC.NS",
    "JSWSTEEL.NS","KOTAKBANK.NS","LT.NS","M&M.NS","MARUTI.NS","NESTLEIND.NS","NTPC.NS","ONGC.NS","POWERGRID.NS",
    "RELIANCE.NS","SBIN.NS","SUNPHARMA.NS","TATAMOTORS.NS","TATASTEEL.NS","TCS.NS","TECHM.NS","TITAN.NS",
    "ULTRACEMCO.NS","WIPRO.NS","INDIGO.NS","BANKBARODA.NS"
]

# keep input in session so the button can update it
if "symbols_text" not in st.session_state:
    st.session_state.symbols_text = "RELIANCE.NS,TCS.NS,INFY.NS"

col1, col2 = st.columns([3, 1])
with col1:
    new_text = st.text_input("Symbols (comma-separated)", st.session_state.symbols_text)
    # update session if user typed
    st.session_state.symbols_text = new_text
with col2:
    if st.button("Load NIFTY50 preset"):
        st.session_state.symbols_text = ",".join(NIFTY50)
        st.rerun()

raw_symbols = [s.strip().upper() for s in st.session_state.symbols_text.split(",") if s.strip()]
max_symbols = st.sidebar.number_input(
    "Max symbols to process (to avoid slow scraping)",
    min_value=1, max_value=50, value=6, step=1
)
symbols = raw_symbols[:max_symbols]

# ---------- Sidebar options ----------
st.sidebar.header("Options & Export")
min_score = st.sidebar.slider("Min score % to include in summary", 0, 100, 0)
export_csv = st.sidebar.checkbox("Enable CSV export of summary", True)
delay_between_scrapes = st.sidebar.slider("Delay between Screener requests (seconds)", 0, 3, 1, 1)

# ---------- Screener: Shareholding (solid & simple) ----------
def screener_shareholding(symbol: str):
    """
    Returns dict: {'Promoter': '46.32%', 'Pledged': '0.00%', 'FII/DII': '11.85%'}
    We pick the LAST (latest) numeric in 'Shareholding Pattern' table rows.
    """
    out = {"Promoter": None, "Pledged": None, "FII/DII": None}
    try:
        s = symbol.replace(".NS","").replace(".BO","").upper()
        url = f"https://www.screener.in/company/{s}/"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        }
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            return out

        # parse tables with pandas – more reliable than hand-rolling soup for numbers
        tables = pd.read_html(r.text)  # may raise if nothing parseable
        # find shareholding table by typical row names
        def pick_latest(row):
            # take the last numeric/% value in the row
            for val in reversed(row):
                if isinstance(val, str) and "%" in val:
                    return val.strip()
                if pd.api.types.is_number(val):
                    return f"{val:.2f}%"
            return None

        # heuristic: search tables that contain 'Promoters' or 'FII'
        for df in tables:
            cols_lower = [str(c).lower() for c in df.columns]
            text = " ".join(cols_lower + [str(x).lower() for x in df.to_numpy().flatten()])
            if ("promoter" in text or "promoters" in text) and "%" in text:
                # normalize header
                df.columns = [str(c) for c in df.columns]
                # row search
                for idx in range(len(df)):
                    rowname = str(df.iloc[idx, 0]).lower()
                    rowvals = list(df.iloc[idx].values)
                    if "promoter" in rowname:
                        out["Promoter"] = pick_latest(rowvals)
                    if "pledge" in rowname:
                        out["Pledged"] = pick_latest(rowvals)
                    if "fii" in rowname or "dii" in rowname or "institutions" in rowname:
                        out["FII/DII"] = pick_latest(rowvals)
        return out
    except Exception:
        return out

# ---------- Yahoo Finance metrics ----------
def yahoo_meta(symbol):
    """
    Returns dict with key metrics & a small DF of rule rows.
    We keep things that are reasonably reliable from yfinance .info.
    """
    tkr = yf.Ticker(symbol)
    info = getattr(tkr, "info", {}) or {}

    # quick price series for averages/plot
    hist = tkr.history(period="400d")
    ma50 = ma200 = avgvol20 = None
    if not hist.empty:
        close = hist["Close"]
        vol = hist["Volume"]
        ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
        ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
        avgvol20 = float(vol.rolling(20).mean().iloc[-1]) if len(vol) >= 20 else None

    dma_bull = (ma50 is not None and ma200 is not None and ma50 > ma200)

    fin = {
        "roe": info.get("returnOnEquity"),
        "pb": info.get("priceToBook"),
        "pe": info.get("trailingPE") or info.get("forwardPE"),
        "eps": info.get("trailingEps"),
        "op_margin": info.get("operatingMargins"),
        "np_margin": info.get("profitMargins"),
        "div_yield": info.get("dividendYield"),
        "de": info.get("debtToEquity"),
        "peg": info.get("pegRatio"),
        "mcap": info.get("marketCap"),
        "52wh": info.get("fiftyTwoWeekHigh"),
        "52wl": info.get("fiftyTwoWeekLow"),
        "ma50": ma50,
        "ma200": ma200,
        "avgvol20": avgvol20,
        "dma_bull": dma_bull,
    }
    return fin, hist

# ---------- Build per-stock view ----------
def build_table(symbol):
    fin, hist = yahoo_meta(symbol)
    sh = screener_shareholding(symbol)

    rows = []
    # We keep “Context” for items we cannot compute robustly.
    rows.append(["EPS (TTM)", fin["eps"], "✅" if (fin["eps"] is not None and fin["eps"] > 0) else "❌", "EPS should be positive."])
    rows.append(["Debt-to-Equity", fin["de"], "✅" if (fin["de"] is not None and fin["de"] < 1) else "❌", "D/E < 1 preferred."])
    rows.append(["ROE", fin["roe"], "✅" if (fin["roe"] is not None and fin["roe"] > 0.15) else "❌", "ROE > 15% preferred."])
    rows.append(["Operating Margin", fin["op_margin"], "✅" if (fin["op_margin"] is not None and fin["op_margin"] > 0.15) else "❌", "Operating margin > 15%."])
    rows.append(["Net Profit Margin", fin["np_margin"], "✅" if (fin["np_margin"] is not None and fin["np_margin"] > 0.10) else "❌", "Net margin > 10%."])
    rows.append(["P/E (context)", fin["pe"], "Context", "Compare P/E with industry average."])
    rows.append(["P/B", fin["pb"], "✅" if (fin["pb"] is not None and fin["pb"] < 3) else "❌", "P/B < 3 preferred."])
    rows.append(["PEG (context)", fin["peg"], "Context", "PEG < 1 preferred."])
    rows.append(["Dividend Yield", fin["div_yield"], "✅" if (fin["div_yield"] is not None and fin["div_yield"] > 0.02) else "❌", "Dividend yield > 2% preferred."])
    rows.append(["50DMA > 200DMA", fin["dma_bull"], "✅" if fin["dma_bull"] else "❌", "50DMA > 200DMA indicates bullish trend."])
    rows.append(["Promoter Holding", sh.get("Promoter"), "Context", "Promoter > 50% preferred."])
    rows.append(["Pledged %", sh.get("Pledged"), "Context", "Prefer 0% pledged."])
    rows.append(["FII/DII Holding", sh.get("FII/DII"), "Context", "Institutional holding trend matters."])

    df = pd.DataFrame(rows, columns=["Parameter","Value","Verdict","Why it matters"])

    # score: only count ✅/❌
    passed = (df["Verdict"] == "✅").sum()
    considered = (df["Verdict"].isin(["✅","❌"])).sum()
    score = (passed / considered * 100) if considered else None

    meta = {
        "Market Cap": human_inr(fin["mcap"]),
        "52W High": human_inr(fin["52wh"]),
        "52W Low": human_inr(fin["52wl"]),
        "50DMA": human_inr(fin["ma50"]),
        "200DMA": human_inr(fin["ma200"]),
        "Avg Vol (20d)": human_inr(fin["avgvol20"]),
    }
    return df, score, meta, sh, hist

# ---------- MAIN ----------
summary_rows = []
for sym in symbols:
    with st.spinner(f"Fetching {sym} ..."):
        try:
            df, score, meta, sh, hist = build_table(sym)

            st.subheader(sym)
            # metrics row
            cols = st.columns(6)
            for i, k in enumerate(["Market Cap","52W High","52W Low","50DMA","200DMA","Avg Vol (20d)"]):
                with cols[i]:
                    st.metric(k, meta.get(k, "N/A"))

            if score is not None:
                st.success(f"Overall Score (rules passed): {score:.1f}%")

            st.dataframe(df, use_container_width=True)

            # shareholding raw (so user sees exactly what was parsed)
            if sh and any(sh.values()):
                st.markdown("**Shareholding (Screener.in - best effort)**")
                st.json(sh)

            # 1y price chart
            if hist is not None and not hist.empty:
                plt.figure()
                plt.plot(hist.index, hist["Close"], label=sym)
                plt.legend()
                st.pyplot(plt)

            # add to summary
            summary_rows.append({
                "Stock": sym,
                "Score %": round(score, 1) if score is not None else None,
                "ROE": pct(df.loc[df["Parameter"]=="ROE","Value"].values[0]) if "ROE" in df["Parameter"].values else "N/A",
                "P/E": df.loc[df["Parameter"]=="P/E (context)","Value"].values[0] if "P/E (context)" in df["Parameter"].values else "N/A",
                "P/B": df.loc[df["Parameter"]=="P/B","Value"].values[0] if "P/B" in df["Parameter"].values else "N/A",
                "Promoter": sh.get("Promoter"),
                "FII/DII": sh.get("FII/DII"),
            })

            time.sleep(delay_between_scrapes)
        except Exception as e:
            st.error(f"{sym}: {e}")

# ---------- Summary & CSV ----------
if summary_rows:
    sumdf = pd.DataFrame(summary_rows)
    if min_score > 0:
        sumdf = sumdf[(sumdf["Score %"].notna()) & (sumdf["Score %"] >= min_score)]
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
            mime="text/csv",
        )

st.info(
    "Notes: Screener scraping is best-effort and may break if their HTML changes. "
    "For authoritative fundamentals use company filings/APIs. "
    "Market cap & 52-week stats shown from Yahoo Finance (INR formatted)."
)
