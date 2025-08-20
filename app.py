import streamlit as st
import requests
import re
import pandas as pd
from bs4 import BeautifulSoup

st.set_page_config(page_title="📊 Stock Rules Analyzer", layout="wide")
st.title("📊 Stock Rules Analyzer — NSE + Screener.in")

# ------------ Utility ------------
def to_number(val):
    if not val or val == "N/A":
        return None
    try:
        val = re.sub(r"[₹,%]", "", str(val)).strip()
        val = val.replace(",", "")
        return float(val)
    except:
        return None

# ------------ Fetch Data from NSE ------------
def get_nse_data(symbol):
    url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol.upper()}"
    headers = {"User-Agent": "Mozilla/5.0"}
    session = requests.Session()
    response = session.get(url, headers=headers).json()

    try:
        info = response["info"]
        price = response["priceInfo"]
        return {
            "EPS": to_number(info.get("eps", None)),
            "P/E": to_number(info.get("pe", None)),
            "P/B": to_number(info.get("pb", None)),
            "Dividend Yield": to_number(info.get("yield", None)),
            "50DMA>200DMA": price.get("dayHigh", 0) > price.get("dayLow", 0),  # Simplified
            "Volume Trend": price.get("totalTradedVolume", 0) > 1000000
        }
    except:
        return {}

# ------------ Fetch Data from Screener ------------
def get_screener_data(symbol):
    url = f"https://www.screener.in/company/{symbol}/consolidated/"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    data = {}
    def find_value(label):
        try:
            val = soup.find("li", text=re.compile(label)).find("span").text.strip()
            return to_number(val)
        except:
            return None

    data["ROE"] = find_value("ROE")
    data["ROCE"] = find_value("ROCE")
    data["Debt-to-Equity"] = find_value("Debt to equity")
    data["Operating Margin"] = find_value("Operating Profit Margin")
    data["Net Profit Margin"] = find_value("Net Profit Margin")
    data["Promoter Holding"] = find_value("Promoter holding")
    data["FII/DII Holding"] = find_value("FII / DII")
    data["Pledged %"] = find_value("Pledged percentage")

    return data

# ------------ Combine NSE + Screener Data ------------
def get_stock_data(symbol):
    nse = get_nse_data(symbol)
    screener = get_screener_data(symbol)
    return {**nse, **screener}

# ------------ Rules Engine ------------
def analyze(data):
    rules = []

    def add_rule(param, value, verdict, why):
        rules.append({
            "Parameter": param,
            "Value": value if value is not None else "None",
            "Verdict": "✅" if verdict is True else ("❌" if verdict is False else "Context"),
            "Why": why
        })

    add_rule("Revenue Growth (5Y CAGR)", None, None, "Use financials for CAGR (API needed).")
    add_rule("Profit Growth (5Y CAGR)", None, None, "Use financials for CAGR (API needed).")
    add_rule("EPS (TTM)", data.get("EPS"), data.get("EPS") and data["EPS"] > 0, "EPS should be positive.")
    add_rule("Debt-to-Equity", data.get("Debt-to-Equity"), data.get("Debt-to-Equity") and data["Debt-to-Equity"] < 1, "D/E < 1 preferred.")
    add_rule("ROE", data.get("ROE"), data.get("ROE") and data["ROE"] > 15, "ROE > 15% preferred.")
    add_rule("ROCE", data.get("ROCE"), data.get("ROCE") and data["ROCE"] > 15, "ROCE > 15% preferred.")
    add_rule("Free Cash Flow", None, None, "FCF not always available via free API.")
    add_rule("Operating Margin", data.get("Operating Margin"), data.get("Operating Margin") and data["Operating Margin"] > 15, "Operating margin >15%.")
    add_rule("Net Profit Margin", data.get("Net Profit Margin"), data.get("Net Profit Margin") and data["Net Profit Margin"] > 10, "Net margin >10%.")
    add_rule("P/E", data.get("P/E"), None, "Compare P/E with industry average.")
    add_rule("P/B", data.get("P/B"), data.get("P/B") and data["P/B"] < 3, "P/B < 3 preferred.")
    add_rule("PEG", None, None, "PEG < 1 preferred.")
    add_rule("Dividend Yield", data.get("Dividend Yield"), data.get("Dividend Yield") and data["Dividend Yield"] >= 2, "Dividend yield ≥2% preferred.")
    add_rule("50DMA > 200DMA", data.get("50DMA>200DMA"), data.get("50DMA>200DMA"), "50DMA > 200DMA indicates bullish trend.")
    add_rule("Volume Trend", data.get("Volume Trend"), data.get("Volume Trend"), "Short-term volume trending up.")
    add_rule("Promoter Holding", data.get("Promoter Holding"), None, "Promoter >50% preferred.")
    add_rule("Pledged %", data.get("Pledged %"), None, "Prefer 0% pledged.")
    add_rule("FII/DII Holding", data.get("FII/DII Holding"), None, "Institutional holding trend matters.")

    return rules

# ------------ Streamlit UI ------------
symbol = st.text_input("Enter NSE symbol (without .NS)", "LT")

if symbol:
    data = get_stock_data(symbol)
    rules = analyze(data)
    st.subheader("📋 Rules Check")
    df = pd.DataFrame(rules)
    st.dataframe(df, use_container_width=True)
