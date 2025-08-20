import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

st.set_page_config(page_title="📊 Stock Analyzer — NSE + Screener", layout="wide")

# ============ SCRAPER FOR SCREENER ============
def get_screener_data(symbol, cookies=None):
    """
    Screener.in fundamentals scraper
    symbol: NSE symbol (without .NS)
    """
    url = f"https://www.screener.in/company/{symbol}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers, cookies=cookies)

    if res.status_code != 200:
        return {}

    soup = BeautifulSoup(res.text, "lxml")
    fundamentals = {}

    ratios = soup.find_all("li", {"class": "flex flex-space-between"})
    for r in ratios:
        try:
            key = r.find("span", {"class": "name"}).text.strip()
            val = r.find("span", {"class": "value"}).text.strip()
            fundamentals[key] = val
        except:
            pass

    return fundamentals


# ============ SCRAPER FOR NSE ============
def get_nse_data(symbol):
    url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
    headers = {"User-Agent": "Mozilla/5.0"}
    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers)
    res = session.get(url, headers=headers)

    if res.status_code != 200:
        return {}

    return res.json()


# ============ RULE CHECK ============
def check_rules(data):
    rules = [
        {"Parameter": "ROE", "Condition": lambda d: d.get("ROE", 0) > 15, "Why": "ROE > 15% preferred"},
        {"Parameter": "ROCE", "Condition": lambda d: d.get("ROCE", 0) > 15, "Why": "ROCE > 15% preferred"},
        {"Parameter": "Net Profit Margin", "Condition": lambda d: d.get("Net Profit Margin", 0) > 10, "Why": "Net margin >10% preferred"},
        {"Parameter": "P/E", "Condition": lambda d: d.get("P/E", 999) < 40, "Why": "P/E < 40 preferred"},
        {"Parameter": "P/B", "Condition": lambda d: d.get("P/B", 999) < 3, "Why": "P/B < 3 preferred"},
        {"Parameter": "PEG", "Condition": lambda d: d.get("PEG", 999) < 1, "Why": "PEG < 1 preferred"},
        {"Parameter": "Dividend Yield", "Condition": lambda d: d.get("Dividend Yield", 0) >= 2, "Why": "DY ≥ 2% preferred"},
        {"Parameter": "Promoter Holding", "Condition": lambda d: d.get("Promoter Holding", 0) > 50, "Why": "Promoter >50% preferred"},
        {"Parameter": "Pledged %", "Condition": lambda d: d.get("Pledged percentage", 100) == 0, "Why": "Prefer 0% pledged"},
        {"Parameter": "FI/DII Holding", "Condition": lambda d: d.get("FIIs", 0) + d.get("DIIs", 0) > 20, "Why": "Higher institutional holding preferred"},
    ]

    results = []
    score = 0
    for rule in rules:
        value = data.get(rule["Parameter"], None)
        try:
            # handle % and other symbols
            if isinstance(value, str):
                value = float(value.replace("%", "").replace(",", "").strip())
        except:
            value = None

        passed = rule["Condition"]({rule["Parameter"]: value}) if value is not None else False
        if passed:
            score += 1
        results.append({
            "Parameter": rule["Parameter"],
            "Value": value,
            "Verdict": "✅" if passed else "❌",
            "Why": rule["Why"]
        })

    overall_score = (score / len(rules)) * 100
    return results, overall_score


# ============ STREAMLIT UI ============
st.title("📊 Stock Analyzer — NSE + Screener.in")

symbol_input = st.text_input("Enter NSE symbol (without .NS)", "DIXON")
if symbol_input:
    symbol = symbol_input.upper()

    # NSE DATA
    try:
        nse_data = get_nse_data(symbol)
        info = nse_data.get("info", {})
        st.subheader(symbol)
        st.write(f"**Market Cap:** {info.get('mc')} | **Price:** {info.get('lastPrice')}")
    except:
        st.warning("NSE data not available")

    # SCREENER DATA
    screener_data = get_screener_data(symbol)
    st.subheader("Fundamentals (Screener)")
    st.json(screener_data if screener_data else {"error": "No data found"})

    # RULES CHECK
    if screener_data:
        results, overall_score = check_rules(screener_data)
        df = pd.DataFrame(results)
        st.subheader("Rules Check")
        st.dataframe(df)

        st.success(f"✅ Overall Score: {overall_score:.1f}%")
