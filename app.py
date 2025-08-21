import streamlit as st
import yfinance as yf
import pandas as pd

# -----------------------------
# Streamlit App Title
# -----------------------------
st.title("📊 Stock Screener (NSE)")

# Input box for NSE stock symbol
ticker = st.text_input("Enter NSE Symbol (e.g., RELIANCE.NS, TCS.NS, HDFCBANK.NS):", "RELIANCE.NS")

if ticker:
    try:
        # Fetch stock data
        stock = yf.Ticker(ticker)

        # Financial info
        eps = stock.info.get("trailingEps")
        pe_ratio = stock.info.get("trailingPE")
        pb_ratio = stock.info.get("priceToBook")
        div_yield = stock.info.get("dividendYield")
        roe = stock.info.get("returnOnEquity")
        de_ratio = stock.info.get("debtToEquity")

        # Historical prices for DMA & volume trend
        hist = stock.history(period="1y")
        hist["50dma"] = hist["Close"].rolling(50).mean()
        hist["200dma"] = hist["Close"].rolling(200).mean()
        dma_signal = hist["50dma"].iloc[-1] > hist["200dma"].iloc[-1]
        volume_trend = hist["Volume"].iloc[-1] > hist["Volume"].rolling(20).mean().iloc[-1]

        # Screening rules
        checks = []

        def verdict(param, value, condition, why):
            ok = "✅" if condition else "❌"
            checks.append([param, value, ok, why])

        verdict("EPS (TTM)", eps, eps and eps > 0, "EPS should be positive")
        verdict("P/E", pe_ratio, True, "Compare P/E with industry average")
        verdict("P/B", pb_ratio, pb_ratio and pb_ratio < 3, "P/B < 3 is healthy")
        verdict("Dividend Yield", div_yield, div_yield and div_yield > 0.02, "Dividend yield >2% preferred")
        verdict("ROE", roe, roe and roe > 0.15, "ROE >15% preferred")
        verdict("Debt/Equity", de_ratio, de_ratio and de_ratio < 1, "D/E <1 preferred")
        verdict("50DMA > 200DMA", dma_signal, dma_signal, "Golden cross bullish")
        verdict("Volume Trend", volume_trend, volume_trend, "Volume should trend up")

        # Convert to DataFrame
        df = pd.DataFrame(checks, columns=["Parameter", "Value", "Verdict", "Why it matters"])

        st.dataframe(df)

        # Show chart
        st.line_chart(hist[["Close", "50dma", "200dma"]])

    except Exception as e:
        st.error(f"Error fetching data: {e}")
