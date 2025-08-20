import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="📊 Stock Analyzer — Yahoo Finance + Screener.in (Multi-stock)", layout="wide")

st.title("📊 Stock Analyzer — Yahoo Finance + Screener.in (Multi-stock)")
st.caption("Fetch NSE stock data with Yahoo Finance + Screener.in (best-effort scraping).")

# -------------------------
# NIFTY50 preset list
# -------------------------
NIFTY50 = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","HINDUNILVR.NS","ICICIBANK.NS",
    "SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS","ITC.NS","LT.NS","HCLTECH.NS","AXISBANK.NS",
    "ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS","ULTRACEMCO.NS","WIPRO.NS","BAJFINANCE.NS",
    "NTPC.NS","NESTLEIND.NS","POWERGRID.NS","TITAN.NS","ONGC.NS","BAJAJFINSV.NS",
    "HDFCLIFE.NS","TECHM.NS","JSWSTEEL.NS","TATAMOTORS.NS","M&M.NS","HINDALCO.NS",
    "ADANIGREEN.NS","ADANIPORTS.NS","DIVISLAB.NS","BRITANNIA.NS","EICHERMOT.NS","CIPLA.NS",
    "GRASIM.NS","SHREECEM.NS","UPL.NS","COALINDIA.NS","SBILIFE.NS","HEROMOTOCO.NS",
    "BPCL.NS","TATACONSUM.NS","DRREDDY.NS","INDUSINDBK.NS","HAVELLS.NS","BAJAJ-AUTO.NS"
]

# -------------------------
# Input controls
# -------------------------
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

# -------------------------
# Options sidebar
# -------------------------
with st.sidebar:
    st.subheader("Options & Export")
    max_symbols = st.number_input("Max symbols to process (to avoid slow scraping)", 1, 50, 6)
    min_score = st.number_input("Min score % to include in summary", 0, 100, 0)
    enable_csv = st.checkbox("Enable CSV export of summary", value=True)
    delay = st.slider("Delay between Screener requests (seconds)", 0, 5, 1)

# -------------------------
# Helper functions
# -------------------------
def fetch_yahoo_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        hist = stock.history(period="1y")
        return info, hist
    except Exception as e:
        return {}, pd.DataFrame()

def fetch_screener_data(symbol):
    try:
        url = f"https://www.screener.in/company/{symbol.replace('.NS','')}/"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(r.text, 'html.parser')
        # Example: fetch promoter holding
        promoters = soup.find_all("li", string=lambda text: text and "Promoter" in text)
        return {"Promoter": promoters[0].text if promoters else "N/A"}
    except:
        return {}

# -------------------------
# Process each stock
# -------------------------
summary = []

for symbol in symbols[:max_symbols]:
    st.subheader(symbol)
    
    info, hist = fetch_yahoo_data(symbol)
    
    if info:
        colA, colB, colC = st.columns(3)
        colA.metric("Market Cap", info.get("marketCap", "N/A"))
        colB.metric("52W High", info.get("fiftyTwoWeekHigh", "N/A"))
        colC.metric("52W Low", info.get("fiftyTwoWeekLow", "N/A"))

    if not hist.empty:
        st.line_chart(hist["Close"])

    screener = fetch_screener_data(symbol)
    if screener:
        st.json(screener)
    
    summary.append({
        "Stock": symbol,
        "ROE": info.get("returnOnEquity", "N/A"),
        "P/E": info.get("trailingPE", "N/A"),
        "Promoter": screener.get("Promoter", "N/A")
    })

# -------------------------
# Summary table
# -------------------------
if summary:
    df_summary = pd.DataFrame(summary)
    st.subheader("📑 Summary Comparison")
    st.dataframe(df_summary)

    if enable_csv:
        csv = df_summary.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", data=csv, file_name="summary.csv", mime="text/csv")
