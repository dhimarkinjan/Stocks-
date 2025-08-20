import streamlit as st
import requests
import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup

st.set_page_config(page_title="Stock Rules Analyzer — NSE + Screener", layout="wide")

# --------- Get NSE Price + Moving Averages ---------
def get_nse_price(symbol):
    try:
        stock = yf.Ticker(symbol + ".NS")
        hist = stock.history(period="6mo")
        if hist.empty:
            return None, None, None
        price = hist["Close"].iloc[-1]
        dma50 = hist["Close"].rolling(window=50).mean().iloc[-1]
        dma200 = hist["Close"].rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else None
        vol_trend = hist["Volume"].iloc[-5:].mean() > hist["Volume"].iloc[-20:].mean()
        return price, dma50, dma200, vol_trend
    except:
        return None, None, None, None

# --------- Screener Data ---------
def get_screener_data(symbol):
    url = f"https://www.screener.in/company/{symbol}/consolidated/"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code != 200:
        return {}
    soup = BeautifulSoup(r.text, "html.parser")
    data = {}

    def extract(label):
        try:
            val = soup.find("li", text=lambda t: t and label in t)
            return val.find("span").text.strip()
        except:
            return None

    # Extract key ratios
    ratios = {
        "Market Cap": "Market Cap",
        "EPS (TTM)": "EPS",
        "Stock P/E": "P/E",
        "Price to Book": "P/B",
        "ROCE": "ROCE",
        "ROE": "ROE",
        "Debt to Equity": "Debt to equity",
        "Dividend Yield": "Dividend Yield",
        "Promoter Holding": "Promoter holding",
        "Pledged %": "Pledged",
        "FII Holding": "FII holding",
        "DII Holding": "DII holding",
    }

    for k, v in ratios.items():
        data[k] = extract(v)

    # Extract growth numbers
    growth = soup.find_all("div", {"class": "number"})
    try:
        data["Revenue Growth (5Y)"] = growth[0].text.strip()
        data["Profit Growth (5Y)"] = growth[1].text.strip()
    except:
        data["Revenue Growth (5Y)"] = None
        data["Profit Growth (5Y)"] = None

    return data

# --------- Rules Checker ---------
def check_rules(symbol):
    screener = get_screener_data(symbol)
    price, dma50, dma200, vol_trend = get_nse_price(symbol)

    rules = []

    def verdict(val, condition, why):
        if val is None:
            return [val, "Context", why]
        if condition(val):
            return [val, "✅", why]
        return [val, "❌", why]

    # EPS
    rules.append(["EPS (TTM)", *verdict(float(screener.get("EPS (TTM)", 0) or 0),
                                        lambda x: x > 0, "EPS should be positive.")])

    # Debt to Equity
    rules.append(["Debt-to-Equity", *verdict(float(screener.get("Debt to Equity", 99) or 99),
                                             lambda x: x < 1, "D/E <1 preferred.")])

    # ROE
    rules.append(["ROE", *verdict(float(screener.get("ROE", 0) or 0),
                                  lambda x: x > 15, "ROE >15% preferred.")])

    # ROCE
    rules.append(["ROCE", *verdict(float(screener.get("ROCE", 0) or 0),
                                   lambda x: x > 15, "ROCE >15% preferred.")])

    # Net Profit Margin (dummy here)
    rules.append(["Net Profit Margin", *verdict(0.08,
                                                lambda x: x > 0.1, "Net margin >10%.")])

    # P/E
    rules.append(["P/E", *verdict(float(screener.get("Stock P/E", 0) or 0),
                                  lambda x: x < 25, "Compare P/E with industry average.")])

    # P/B
    rules.append(["P/B", *verdict(float(screener.get("Price to Book", 0) or 0),
                                  lambda x: x < 3, "P/B <3 preferred.")])

    # Dividend Yield
    rules.append(["Dividend Yield", *verdict(float(screener.get("Dividend Yield", 0) or 0),
                                             lambda x: x > 2, "Dividend yield >2%.")])

    # Promoter Holding
    rules.append(["Promoter Holding", *verdict(float(screener.get("Promoter Holding", 0) or 0),
                                               lambda x: x > 50, "Promoter >50% preferred.")])

    # Pledged %
    rules.append(["Pledged %", *verdict(float(screener.get("Pledged %", 0) or 0),
                                        lambda x: x == 0, "Prefer 0% pledged.")])

    # FII/DII Holding
    fii = float(screener.get("FII Holding", 0) or 0)
    dii = float(screener.get("DII Holding", 0) or 0)
    rules.append(["FII+DII Holding", *verdict(fii + dii,
                                              lambda x: x > 20, "Institutional holding >20%.")])

    # 50DMA > 200DMA
    if dma50 and dma200:
        rules.append(["50DMA > 200DMA", *verdict(dma50 > dma200,
                                                 lambda x: x, "Bullish trend if True.")])

    # Volume Trend
    rules.append(["Volume Trend", *verdict(vol_trend,
                                           lambda x: x, "Short-term volume trending up.")])

    df = pd.DataFrame(rules, columns=["Parameter", "Value", "Verdict", "Why it matters"])
    return df

# --------- Streamlit UI ---------
st.title("📊 Stock Rules Analyzer — NSE + Screener.in")
symbol = st.text_input("Enter NSE symbol (without .NS)", "TCS")

if st.button("Analyze"):
    with st.spinner("Fetching data..."):
        df = check_rules(symbol.upper())
        st.dataframe(df, use_container_width=True)
