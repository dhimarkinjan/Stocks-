import streamlit as st
import yfinance as yf
import pandas as pd

# Function: Stock checklist with ranges
def stock_checklist(symbol):
    data = {}
    stock = yf.Ticker(symbol)
    info = stock.info

    # Define rules
    rules = {
        "PE Ratio": ("trailingPE", lambda x: 8 <= x <= 25),
        "PB Ratio": ("priceToBook", lambda x: x <= 5),
        "ROE (%)": ("returnOnEquity", lambda x: x*100 >= 12 if x else False),
        "ROA (%)": ("returnOnAssets", lambda x: x*100 >= 8 if x else False),
        "Revenue Growth (5Y %)": ("revenueGrowth", lambda x: x*100 >= 8 if x else False),
        "Profit Growth (YoY %)": ("earningsGrowth", lambda x: x*100 >= 10 if x else False),
        "PEG Ratio": ("pegRatio", lambda x: x <= 1.5),
        "Dividend Yield (%)": ("dividendYield", lambda x: x*100 >= 1 if x else False),
        "Debt/Equity": ("debtToEquity", lambda x: x < 1 if x else False),
        "Market Cap (Cr)": ("marketCap", lambda x: x/1e7 >= 500 if x else False),
    }

    results = []
    for metric, (key, rule) in rules.items():
        value = info.get(key, None)
        try:
            if value is None:
                status = "NA"
                ok = "❓"
            else:
                ok = "✅ True" if rule(value) else "❌ False"
                if "Yield" in metric or "Growth" in metric or "ROE" in metric or "ROA" in metric:
                    value = round(value*100, 2)
                elif metric == "Market Cap (Cr)":
                    value = round(value/1e7, 2)
                else:
                    value = round(value, 2)
        except Exception:
            status = "NA"
            ok = "❓"
        results.append([metric, value, ok])

    df = pd.DataFrame(results, columns=["Parameter", "Value", "Result"])
    return df

# Streamlit UI
st.title("📊 Stock Screener with True/False Validation")

symbol = st.text_input("Enter NSE Stock Symbol (e.g., RELIANCE.NS, TCS.NS, INFY.NS)", "RELIANCE.NS")

if st.button("Check Stock"):
    df = stock_checklist(symbol)
    st.dataframe(df, use_container_width=True)
