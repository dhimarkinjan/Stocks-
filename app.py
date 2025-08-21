import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

# ---------------- Screener Data Function ---------------- #
def get_screener_data(stock_symbol):
    try:
        url = f"https://www.screener.in/company/{stock_symbol}/consolidated/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/"
        }
        page = requests.get(url, headers=headers, timeout=15)

        if page.status_code != 200:
            return None

        soup = BeautifulSoup(page.text, "html.parser")
        data = {}

        # Debt/Equity
        try:
            de = soup.find("li", text=lambda t: t and "Debt to equity" in t)
            if de:
                data["Debt to Equity"] = de.find("span").text.strip()
        except:
            data["Debt to Equity"] = None

        # ROCE
        try:
            roce = soup.find("li", text=lambda t: t and "ROCE" in t)
            if roce:
                data["ROCE"] = roce.find("span").text.strip()
        except:
            data["ROCE"] = None

        return data
    except Exception as e:
        return {"error": str(e)}

# ---------------- Main Stock Function ---------------- #
def analyze_stock(stock_symbol):
    stock = yf.Ticker(stock_symbol)
    info = stock.info

    results = []

    # PE Ratio
    pe_ratio = info.get("trailingPE")
    results.append(["PE Ratio", pe_ratio, pe_ratio and 8 <= pe_ratio <= 25, "8 – 25"])

    # PB Ratio
    pb_ratio = info.get("priceToBook")
    results.append(["PB Ratio", pb_ratio, pb_ratio and 0 <= pb_ratio <= 5, "0 – 5"])

    # EPS
    eps = info.get("trailingEps")
    results.append(["EPS", eps, eps and eps > 0, "> 0"])

    # DMA Comparison
    hist = stock.history(period="1y")
    dma_50 = hist["Close"].rolling(50).mean().iloc[-1]
    dma_200 = hist["Close"].rolling(200).mean().iloc[-1]
    dma_result = dma_50 > dma_200
    dma_text = f"{'True ✅' if dma_result else 'False ❌'} ({dma_50:.2f} vs {dma_200:.2f})"
    results.append(["50DMA > 200DMA", dma_text, dma_result, "50DMA > 200DMA indicates bullish trend"])

    # ROE
    roe = info.get("returnOnEquity")
    if roe is not None:
        roe = roe * 100
    results.append(["ROE (%)", roe, roe and roe > 12, "> 12%"])

    # ROA
    roa = info.get("returnOnAssets")
    if roa is not None:
        roa = roa * 100
    results.append(["ROA (%)", roa, roa and roa > 8, "> 8%"])

    # Revenue Growth 5Y
    rev_growth = info.get("revenueGrowth")
    if rev_growth is not None:
        rev_growth = rev_growth * 100
    results.append(["Revenue Growth (5Y %)", rev_growth, rev_growth and rev_growth > 8, "> 8%"])

    # Profit Growth YoY
    profit_growth = info.get("earningsQuarterlyGrowth")
    if profit_growth is not None:
        profit_growth = profit_growth * 100
    results.append(["Profit Growth (YoY %)", profit_growth, profit_growth and profit_growth > 10, "> 10%"])

    # PEG Ratio
    peg = info.get("pegRatio")
    results.append(["PEG Ratio", peg, peg and peg < 1.5, "< 1.5"])

    # Dividend Yield FIX ✅
    dividend_yield = info.get("dividendYield")
    if dividend_yield is not None:
        dividend_yield = dividend_yield * 100  # Convert to %
    results.append(["Dividend Yield (%)", dividend_yield, dividend_yield and dividend_yield > 1, "> 1%"])

    # Merge Screener Data
    screener_data = get_screener_data(stock_symbol.replace(".NS", ""))
    if screener_data:
        results.append(["Debt to Equity", screener_data.get("Debt to Equity"), None, "Lower is better"])
        results.append(["ROCE", screener_data.get("ROCE"), None, "> 12%"])

    # Convert to DataFrame
    df = pd.DataFrame(results, columns=["Parameter", "Value", "Result", "Healthy Range"])
    return df

# ---------------- Streamlit UI ---------------- #
st.set_page_config(page_title="Advanced Stock Screener", layout="wide")

st.markdown("## 📊 Advanced Stock Screener with Score")
stock_symbol = st.text_input("Enter NSE Stock Symbol (e.g., RELIANCE.NS, TCS.NS)", "RELIANCE.NS")

if st.button("Check Stock"):
    df = analyze_stock(stock_symbol)

    # Score Calculation
    total = df["Result"].notna().sum()
    score = df["Result"].sum()
    percentage = (score / total) * 100 if total > 0 else 0

    st.dataframe(df, use_container_width=True)
    st.markdown(f"📌 **Overall Score: {score}/{total} ({percentage:.2f}%)**")
