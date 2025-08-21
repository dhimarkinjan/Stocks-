import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

# ---------------- Screener Fetch Function ---------------- #
def get_screener_data(stock_symbol):
    try:
        url = f"https://www.screener.in/company/{stock_symbol.replace('.NS','')}/consolidated/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/"
        }
        page = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(page.text, "html.parser")

        ratios = {}
        for row in soup.select("li.flex.flex-space-between"):
            try:
                key = row.select_one("span.name").text.strip()
                value = row.select_one("span.value").text.strip()
                ratios[key] = value
            except:
                continue
        return ratios
    except Exception as e:
        return {"error": str(e)}

# ---------------- Stock Analysis Function ---------------- #
def analyze_stock(stock_symbol):
    stock = yf.Ticker(stock_symbol)
    info = stock.info
    screener_data = get_screener_data(stock_symbol)

    metrics = {
        "PE Ratio": (info.get("trailingPE"), "8 – 25"),
        "PB Ratio": (info.get("priceToBook"), "0 – 5"),
        "EPS": (info.get("trailingEps"), "> 0"),
        "50DMA > 200DMA": (None, "50DMA > 200DMA indicates bullish trend"),
        "ROE (%)": (info.get("returnOnEquity")*100 if info.get("returnOnEquity") else None, "> 12%"),
        "ROA (%)": (info.get("returnOnAssets")*100 if info.get("returnOnAssets") else None, "> 8%"),
        "Revenue Growth (5Y %)": (screener_data.get("Compounded Sales Growth"), "> 8%"),
        "Profit Growth (YoY %)": (screener_data.get("Profit growth"), "> 10%"),
        "PEG Ratio": (info.get("pegRatio"), "< 1.5"),
        "Dividend Yield (%)": (info.get("dividendYield")*100 if info.get("dividendYield") else None, "> 1%")
    }

    results = []
    for metric, (value, healthy_range) in metrics.items():
        ok = None
        if value is not None:
            if metric == "PE Ratio":
                ok = 8 <= value <= 25
            elif metric == "PB Ratio":
                ok = 0 <= value <= 5
            elif metric == "EPS":
                ok = value > 0
            elif metric == "50DMA > 200DMA":
                f50 = info.get("fiftyDayAverage")
                f200 = info.get("twoHundredDayAverage")
                if f50 and f200:
                    ok = f50 > f200
                    value = f"{f50:.2f} vs {f200:.2f}"
            elif metric == "ROE (%)":
                ok = value > 12
            elif metric == "ROA (%)":
                ok = value > 8
            elif metric == "Revenue Growth (5Y %)":
                try:
                    val = float(value.replace("%", ""))
                    ok = val > 8
                    value = val
                except:
                    pass
            elif metric == "Profit Growth (YoY %)":
                try:
                    val = float(value.replace("%", ""))
                    ok = val > 10
                    value = val
                except:
                    pass
            elif metric == "PEG Ratio":
                ok = value < 1.5
            elif metric == "Dividend Yield (%)":
                ok = value > 1

        results.append({
            "Parameter": metric,
            "Value": value,
            "Result": ok,
            "Healthy Range": healthy_range
        })

    return pd.DataFrame(results)

# ---------------- Streamlit UI ---------------- #
st.set_page_config(page_title="Advanced Stock Screener", layout="wide")
st.markdown("## 📊 Advanced Stock Screener with Score")

stock_symbol = st.text_input("Enter NSE Stock Symbol (e.g., RELIANCE.NS, TCS.NS)", "RELIANCE.NS")

if st.button("Check Stock"):
    df = analyze_stock(stock_symbol)

    total = df["Result"].notna().sum()
    score = df["Result"].sum()
    percentage = (score / total) * 100 if total > 0 else 0

    st.dataframe(df, use_container_width=True)
    st.markdown(f"📌 **Overall Score: {score}/{total} ({percentage:.2f}%)**")
