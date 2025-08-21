import streamlit as st
import yfinance as yf
import pandas as pd
from nsetools import Nse

# Init NSE client
nse = Nse()

st.title("📊 Stock Screener (NSE + Yahoo Finance)")

# User input
symbol_input = st.text_input("Enter NSE Stock Symbol (e.g. RELIANCE, TCS, INFY)", "RELIANCE")

if symbol_input:
    try:
        # ✅ nsetools ke liye .NS nahi chahiye
        nse_symbol = symbol_input.replace(".NS", "")

        # NSE live price
        quote = nse.get_quote(nse_symbol)
        live_price = quote["lastPrice"]

        st.subheader(f"💹 {nse_symbol} Live Price (NSE): ₹{live_price}")

        # ✅ Yahoo Finance ke liye .NS lagana zaruri hai
        yf_symbol = nse_symbol + ".NS"
        stock = yf.Ticker(yf_symbol)
        info = stock.info

        # Parameters
        data = {
            "PE Ratio": info.get("trailingPE"),
            "PB Ratio": info.get("priceToBook"),
            "EPS": info.get("trailingEps"),
            "Dividend Yield": f"{info.get('dividendYield')*100:.2f}%" if info.get("dividendYield") else "NA",
            "ROE": f"{info.get('returnOnEquity')*100:.2f}%" if info.get("returnOnEquity") else "NA",
            "ROA": f"{info.get('returnOnAssets')*100:.2f}%" if info.get("returnOnAssets") else "NA",
            "Market Cap": f"{info.get('marketCap')/1e7:.2f} Cr" if info.get("marketCap") else "NA",
            "Revenue Growth": f"{info.get('revenueGrowth')*100:.2f}%" if info.get("revenueGrowth") else "NA",
            "Profit Growth": f"{info.get('earningsGrowth')*100:.2f}%" if info.get("earningsGrowth") else "NA",
            "PEG Ratio": info.get("pegRatio"),
        }

        # Convert to DataFrame
        df = pd.DataFrame(list(data.items()), columns=["Parameter", "Value"])
        st.dataframe(df)

        # Chart
        hist = stock.history(period="1y")
        hist["50DMA"] = hist["Close"].rolling(50).mean()
        hist["200DMA"] = hist["Close"].rolling(200).mean()
        st.line_chart(hist[["Close", "50DMA", "200DMA"]])

    except Exception as e:
        st.error(f"❌ Error: {e}")
