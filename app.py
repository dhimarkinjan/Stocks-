import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

st.set_page_config(page_title="Stock Analyzer", layout="wide")

st.title("📊 Stock Analyzer — Yahoo Finance + Screener.in (Multi-stock)")
st.write("Enter NSE symbols with .NS suffix (e.g., RELIANCE.NS). The app fetches financials from yfinance and shareholding from Screener.in (best-effort scraping).")

# Default symbols
DEFAULT_SYMBOLS = "RELIANCE.NS,TCS.NS,INFY.NS"

col1, col2 = st.columns([3,1])
with col1:
    symbols_input = st.text_input("Symbols (comma-separated)", DEFAULT_SYMBOLS)

with col2:
    if st.button("Load NIFTY50 preset"):
        symbols_input = ",".join([
            "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS","HINDUNILVR.NS","SBIN.NS","BHARTIARTL.NS",
            "ITC.NS","LICI.NS","LT.NS","BAJFINANCE.NS","KOTAKBANK.NS","HCLTECH.NS","ASIANPAINT.NS","MARUTI.NS","AXISBANK.NS",
            "SUNPHARMA.NS","ONGC.NS","NTPC.NS","TITAN.NS","ULTRACEMCO.NS","WIPRO.NS","POWERGRID.NS","BAJAJFINSV.NS",
            "ADANIGREEN.NS","ADANIPORTS.NS","JSWSTEEL.NS","TATAMOTORS.NS","COALINDIA.NS","TECHM.NS","NESTLEIND.NS",
            "TATASTEEL.NS","HDFCLIFE.NS","GRASIM.NS","CIPLA.NS","ADANIENT.NS","M&M.NS","BPCL.NS","HEROMOTOCO.NS",
            "HINDZINC.NS","DIVISLAB.NS","BRITANNIA.NS","DRREDDY.NS","BAJAJ-AUTO.NS","EICHERMOT.NS","SHREECEM.NS","SBILIFE.NS"
        ])
        st.rerun()

symbols = [s.strip().upper() for s in symbols_input.split(",") if s.strip()]

# Sidebar options
st.sidebar.header("Options & Export")
max_symbols = st.sidebar.number_input("Max symbols to process (to avoid slow scraping)", min_value=1, max_value=50, value=6)
min_score = st.sidebar.number_input("Min score % to include in summary", min_value=0, max_value=100, value=0)
enable_csv = st.sidebar.checkbox("Enable CSV export of summary", value=True)
delay_sec = st.sidebar.slider("Delay between Screener requests (seconds)", 0, 5, 1)

# Function to fetch screener shareholding
def fetch_screener_shareholding(symbol):
    try:
        url = f"https://www.screener.in/company/{symbol.replace('.NS','')}/"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find("section", {"id": "shareholding"})
        if table:
            return table.text.strip()
    except:
        return None
    return None

summary_data = []
for idx, symbol in enumerate(symbols[:max_symbols]):
    st.subheader(symbol)

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="1y")

        # Display basic info
        st.write(f"**Market Cap**: {info.get('marketCap', 'N/A')}")
        st.write(f"**52W High**: {info.get('fiftyTwoWeekHigh', 'N/A')}")
        st.write(f"**52W Low**: {info.get('fiftyTwoWeekLow', 'N/A')}")

        # Chart
        st.line_chart(hist['Close'])

        # Screener data
        sh = fetch_screener_shareholding(symbol)
        if sh:
            st.json({"Promoter": sh[:200]+"..."})  # showing snippet
        else:
            st.write("_No Screener data_")

        # Add to summary
        summary_data.append({
            "Stock": symbol,
            "ROE": info.get("returnOnEquity", None),
            "P/E": info.get("trailingPE", None),
            "Promoter": sh[:50] if sh else None
        })

    except Exception as e:
        st.error(f"Error loading {symbol}: {e}")

    time.sleep(delay_sec)

if summary_data:
    st.subheader("📋 Summary Comparison")
    df_summary = pd.DataFrame(summary_data)
    if min_score > 0 and "Score %" in df_summary.columns:
        df_summary = df_summary[df_summary["Score %"] >= min_score]
    st.dataframe(df_summary)

    if enable_csv:
        csv = df_summary.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, "summary.csv", "text/csv")
