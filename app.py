import streamlit as st
import yfinance as yf
import pandas as pd
import requests

st.title("📊 Stock Screener (NSE + Yahoo Finance)")

# User input
symbol_input = st.text_input("Enter NSE Stock Symbol (e.g. RELIANCE, TCS, INFY)", "RELIANCE")

if symbol_input:
    try:
        # Clean symbol
        nse_symbol = symbol_input.replace(".NS", "").upper()
        yf_symbol = nse_symbol + ".NS"

        # ✅ NSE API for live price
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://www.nseindia.com/api/quote-equity?symbol={nse_symbol}"
        res = requests.get(url, headers=headers)
        live_price = res.json()["priceInfo"]["lastPrice"]

        st.subheader(f"💹 {nse_symbol} Live Price (NSE): ₹{live_price}")

        # ✅ Yahoo Finance data
        stock = yf.Ticker(yf_symbol)
        info = stock.info if stock.info else {}

        data = {
            "PE Ratio": info.get("trailingPE", "NA"),
            "PB Ratio": info.get("priceToBook", "NA"),
            "EPS": info.get("trailingEps", "NA"),
            "Dividend Yield": f"{info.get('dividendYield')*100:.2f}%" if info.get("dividendYield") else "NA",
            "ROE": f"{info.get('returnOnEquity')*100:.2f}%" if info.get("returnOnEquity") else "NA",
            "ROA": f"{info.get('returnOnAssets')*100:.2f}%" if info.get("returnOnAssets") else "NA",
            "Market Cap": f"{info.get('marketCap')/1e7:.2f} Cr" if info.get("marketCap") else "NA",
            "Revenue Growth": f"{info.get('revenueGrowth')*100:.2f}%" if info.get("revenueGrowth") else "NA",
            "Profit Growth": f"{info.get('earningsGrowth')*100:.2f}%" if info.get("earningsGrowth") else "NA",
            "PEG Ratio": info.get("pegRatio", "NA"),
        }

        df = pd.DataFrame(list(data.items()), columns=["Parameter", "Value"])
        st.dataframe(df)

        # Chart (if available)
        hist = stock.history(period="1y")
        if not hist.empty:
            hist["50DMA"] = hist["Close"].rolling(50).mean()
            hist["200DMA"] = hist["Close"].rolling(200).mean()
            st.line_chart(hist[["Close", "50DMA", "200DMA"]])

    except Exception as e:
        st.error(f"❌ Error: {e}")
