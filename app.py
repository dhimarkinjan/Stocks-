import streamlit as st
import requests
from bs4 import BeautifulSoup
import re

st.set_page_config(page_title="📊 Stock Analyzer — NSE + Screener.in", layout="wide")

st.title("📊 Stock Analyzer — NSE + Screener.in (Multi-stock)")

# ----------- Fetch NSE Data -------------
def get_nse_data(symbol):
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol.upper()}"
        headers = {"User-Agent": "Mozilla/5.0"}
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers)  # required for cookies
        data = session.get(url, headers=headers).json()

        return {
            "Market Cap": data["marketDeptOrderBook"]["meta"].get("marketCap", "N/A"),
            "Price": data["priceInfo"].get("lastPrice", "N/A"),
            "52W High": data["priceInfo"].get("weekHighLow", {}).get("max", "N/A"),
            "52W Low": data["priceInfo"].get("weekHighLow", {}).get("min", "N/A"),
        }
    except Exception as e:
        return {"Market Cap": "N/A", "Price": "N/A", "52W High": "N/A", "52W Low": "N/A"}


# ----------- Fetch Screener Data -------------
def get_screener_data(symbol):
    try:
        url = f"https://www.screener.in/company/{symbol.upper()}/consolidated/"
        headers = {"User-Agent": "Mozilla/5.0"}
        html = requests.get(url, headers=headers).text
        soup = BeautifulSoup(html, "html.parser")

        data = {}
        keys = ["Market Cap", "Current Price", "High / Low", "Stock P/E",
                "Book Value", "Dividend Yield", "ROCE", "ROE",
                "Face Value", "Promoter holding", "Pledged", "FII", "DII"]

        table = soup.find_all("li", {"class": "flex"})
        for row in table:
            try:
                key = row.find("span").text.strip()
                value = row.find("span", {"class": "number"}).text.strip()
                if key in keys:
                    data[key] = value
            except:
                pass

        return data
    except Exception as e:
        return {}


# ----------- Utility: Clean Numbers -------------
def to_number(val):
    if val is None or val == "N/A":
        return None
    try:
        val = re.sub(r"[₹,%]", "", str(val)).strip()
        val = val.replace(",", "")
        return float(val)
    except:
        return None


# ----------- Rules Engine -------------
def analyze(data):
    rules = []

    roe = to_number(data.get("ROE"))
    roce = to_number(data.get("ROCE"))
    pe = to_number(data.get("Stock P/E"))
    pb = None
    if "Book Value" in data and "Current Price" in data:
        try:
            pb = to_number(data.get("Current Price")) / to_number(data.get("Book Value"))
        except:
            pb = None
    dy = to_number(data.get("Dividend Yield"))
    promoter = to_number(data.get("Promoter holding"))
    pledged = to_number(data.get("Pledged"))
    fii = to_number(data.get("FII"))
    dii = to_number(data.get("DII"))

    checks = [
        ("ROE", roe, roe and roe > 15, "ROE > 15% preferred"),
        ("ROCE", roce, roce and roce > 15, "ROCE > 15% preferred"),
        ("P/E", pe, pe and pe < 40, "P/E < 40 preferred"),
        ("P/B", pb, pb and pb < 3, "P/B < 3 preferred"),
        ("Dividend Yield", dy, dy and dy >= 2, "DY ≥ 2% preferred"),
        ("Promoter Holding", promoter, promoter and promoter > 50, "Promoter >50% preferred"),
        ("Pledged %", pledged, pledged is not None and pledged == 0, "Prefer 0% pledged"),
        ("FII/DII Holding", fii, fii and fii > 10, "Higher institutional holding preferred"),
    ]

    score = 0
    for label, val, verdict, why in checks:
        if verdict: score += 1
        rules.append({
            "Parameter": label,
            "Value": val,
            "Verdict": "✅" if verdict else "❌",
            "Why": why
        })

    overall = round((score / len(checks)) * 100, 2)
    return rules, overall


# ----------- UI -------------
symbols = st.text_input("Enter NSE symbols (comma separated, without .NS)", "LT, RELIANCE, TCS")

if symbols:
    for sym in symbols.split(","):
        sym = sym.strip().upper()
        st.subheader(sym)

        nse_data = get_nse_data(sym)
        screener_data = get_screener_data(sym)

        st.write("**Market Cap:**", nse_data["Market Cap"])
        st.write("**Price:**", nse_data["Price"])
        st.write("**52W High:**", nse_data["52W High"])
        st.write("**52W Low:**", nse_data["52W Low"])

        st.write("### Fundamentals (Screener)")
        st.json(screener_data)

        rules, overall = analyze(screener_data)

        st.write("### Rules Check")
        st.table(rules)

        st.success(f"✅ Overall Score: {overall}%")
