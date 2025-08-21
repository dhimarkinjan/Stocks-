import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Function: Get Debt/Equity from Screener.in
def get_debt_to_equity_from_screener(symbol):
    try:
        url = f"https://www.screener.in/company/{symbol}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        page = requests.get(url, headers=headers)
        soup = BeautifulSoup(page.text, "html.parser")

        # Debt to equity ratio search
        element = soup.find("li", string=lambda text: text and "Debt to equity" in text)
        if element:
            value = element.text.split(":")[-1].strip()
            return float(value)
    except Exception:
        return None

# Function: Stock checklist
def stock_checklist(symbol):
    stock = yf.Ticker(symbol)
    info = stock.info

    # Industry averages
    industry_pe = info.get("industryPE")
    industry_pb = info.get("industryPB")

    # Define rules + healthy ranges
    rules = {
        "PE Ratio": ("trailingPE", lambda x: 8 <= x <= 25, "8 – 25"),
        "PB Ratio": ("priceToBook", lambda x: x <= 5, "0 – 5"),
        "ROE (%)": ("returnOnEquity", lambda x: x*100 >= 12 if x else False, "> 12%"),
        "ROA (%)": ("returnOnAssets", lambda x: x*100 >= 8 if x else False, "> 8%"),
        "Revenue Growth (5Y %)": ("revenueGrowth", lambda x: x*100 >= 8 if x else False, "> 8%"),
        "Profit Growth (YoY %)": ("earningsGrowth", lambda x: x*100 >= 10 if x else False, "> 10%"),
        "PEG Ratio": ("pegRatio", lambda x: x <= 1.5, "< 1.5"),
        "Dividend Yield (%)": ("dividendYield", lambda x: x*100 >= 1 if x else False, "> 1%"),
        # Debt/Equity will be fetched from Screener
        "Debt/Equity": ("debtToEquity", None, "< 1"),
        "Market Cap (Cr)": ("marketCap", lambda x: x/1e7 >= 500 if x else False, "> 500 Cr"),
    }

    results = []
    for metric, (key, rule, healthy_range) in rules.items():
        value = None
        ok = "❓ NA"
        compare = ""

        try:
            if metric == "Debt/Equity":
                # Fetch from Screener
                value = get_debt_to_equity_from_screener(symbol.replace(".NS", ""))
                if value is not None:
                    ok = "✅ True" if value < 1 else "❌ False"
            else:
                value = info.get(key, None)
                if value is not None:
                    ok = "✅ True" if rule(value) else "❌ False"
                    if "Yield" in metric or "Growth" in metric or "ROE" in metric or "ROA" in metric:
                        value = round(value*100, 2)
                    elif metric == "Market Cap (Cr)":
                        value = round(value/1e7, 2)
                    else:
                        value = round(value, 2)

            # Industry Avg for PE/PB
            if metric == "PE Ratio" and industry_pe:
                compare = f"Industry Avg: {round(industry_pe,2)}"
            elif metric == "PB Ratio" and industry_pb:
                compare = f"Industry Avg: {round(industry_pb,2)}"

        except Exception:
            pass

        results.append([metric, value, ok, healthy_range, compare])

    df = pd.DataFrame(results, columns=["Parameter", "Value", "Result", "Healthy Range", "Industry Compare"])
    return df

# Streamlit UI
st.title("📊 Stock Screener (Yahoo + Screener Debt/Equity)")

symbol = st.text_input("Enter NSE Stock Symbol (e.g., RELIANCE.NS, TCS.NS, INFY.NS)", "RELIANCE.NS")

if st.button("Check Stock"):
    df = stock_checklist(symbol)

    # Highlighting
    def highlight_result(val):
        if isinstance(val, str):
            if "✅" in val:
                return 'background-color: lightgreen; font-weight: bold'
            elif "❌" in val:
                return 'background-color: salmon; font-weight: bold'
            elif "❓" in val:
                return 'background-color: khaki; font-weight: bold'
        return ''

    st.dataframe(df.style.applymap(highlight_result, subset=["Result"]), use_container_width=True)
