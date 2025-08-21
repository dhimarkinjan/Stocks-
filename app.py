import time
import re
import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

# =========================
# Utility helpers
# =========================
def _to_float(txt):
    """Convert '12.3%', '1,234.5', '—', None -> float or None"""
    if txt is None:
        return None
    s = str(txt).strip().replace(",", "")
    if not s or s in {"-", "—", "N/A", "NA"}:
        return None
    try:
        if s.endswith("%"):
            return float(s[:-1].strip())
        return float(s)
    except:
        # last try: pick first number from string
        m = re.search(r"-?\d+(\.\d+)?", s)
        return float(m.group()) if m else None

def compute_dividend_yield_percent(info):
    """
    Returns dividend yield in PERCENT (e.g., 0.65 for 0.65%).
    yfinance कभी fraction (0.0065) देता है, कभी percent-like (0.65)।
    """
    y = info.get("dividendYield", None)
    if y is not None:
        try:
            # typical fraction range
            if 0 < y <= 0.2:
                return round(y * 100, 2)
            # percent-like already
            elif 0 < y <= 20:
                return round(y, 2)
            else:
                return round(y, 2)
        except:
            pass

    # fallback: rate/price
    rate = info.get("dividendRate")
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if rate and price:
        try:
            return round((rate / price) * 100, 2)
        except:
            pass
    return None

# =========================
# Screener scraping (hybrid)
# =========================
def get_screener_data(symbol):
    """
    Screener से:
      - Debt/Equity
      - ROCE (%)
      - PEG
      - Promoter Holding (%)
      - Pledge (%)
      - FII (%)
      - DII (%)
    को निकालता है। selectors flexible रखे हैं ताकि छोटे UI changes में भी काम करे।
    """
    base = f"https://www.screener.in/company/{symbol}/consolidated/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }

    # simple retry (Screener कभी-कभी throttle करता है)
    for i in range(2):
        try:
            resp = requests.get(base, headers=headers, timeout=20)
            if resp.status_code == 200 and len(resp.text) > 5000:
                break
        except:
            pass
        time.sleep(1.2)
    else:
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    data = {}

    # -------- Key ratios list (Debt/Equity, ROCE, PEG) --------
    # बहुत pages पर ये <li> में "Name: Value" जैसा होता है
    for li in soup.find_all("li"):
        t = li.get_text(" ", strip=True)
        if not t or ":" not in t:
            continue
        name, val = t.split(":", 1)
        name = name.strip().lower()
        val = val.strip()

        if "debt to equity" in name:
            data["Debt/Equity"] = _to_float(val)
        elif name == "roce" or "roce" in name:
            data["ROCE"] = _to_float(val)
        elif "peg" in name:
            # "PEG ratio" / "PEG" दोनों cover
            data["PEG"] = _to_float(val)

    # -------- Shareholding section (Promoter, Pledge, FII, DII) --------
    # section id अक्सर 'shareholding' होता है; वरना table headings देखो
    share_sec = soup.find(id=re.compile("shareholding", re.I)) or soup.find(
        "section", id=lambda x: x and "share" in x
    )
    # fallback: कोई भी table जिसमें 'Promoter', 'FII', 'DII' शब्द हों
    candidate_tables = []
    if share_sec:
        candidate_tables.extend(share_sec.find_all("table"))
    candidate_tables.extend(soup.find_all("table"))

    for tbl in candidate_tables:
        text = tbl.get_text(" ", strip=True).lower()
        if any(k in text for k in ["promoter", "fii", "dii", "pledge"]):
            for tr in tbl.find_all("tr"):
                cols = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if len(cols) < 2:
                    continue
                key = cols[0].strip().lower()
                val = _to_float(cols[1])

                if key.startswith("promoter"):
                    data["Promoter Holding"] = val
                elif key.startswith("pledged") or "pledge" in key:
                    data["Pledge"] = val
                elif key.startswith("fiis") or key.startswith("fii"):
                    data["FII"] = val
                elif key.startswith("diis") or key.startswith("dii"):
                    data["DII"] = val

    return data

# =========================
# Stock checklist
# =========================
PERCENT_METRICS = {"ROE (%)", "ROA (%)", "Revenue Growth (5Y %)", "Profit Growth (YoY %)"}

def stock_checklist(symbol):
    stock = yf.Ticker(symbol)
    info = stock.info
    price = info.get("currentPrice") or info.get("regularMarketPrice")

    # Screener symbol बिना .NS
    screener_symbol = symbol.replace(".NS", "")
    sdata = get_screener_data(screener_symbol)

    # Industry averages (अगर मिले)
    industry_pe = info.get("industryPE")
    industry_pb = info.get("industryPB")

    rules = {
        "PE Ratio": ("trailingPE", lambda x: x is not None and 8 <= x <= 25, "8 – 25"),
        "PB Ratio": ("priceToBook", lambda x: x is not None and x <= 5, "0 – 5"),
        "EPS": ("trailingEps", lambda x: x is not None and x > 0, "> 0"),

        # DMA combined
        "50DMA > 200DMA": (
            ("fiftyDayAverage", "twoHundredDayAverage"),
            lambda x: (x[0] is not None and x[1] is not None and x[0] > x[1]),
            "50DMA > 200DMA"
        ),

        "ROE (%)": ("returnOnEquity", lambda x: x is not None and x*100 >= 12, "> 12%"),
        "ROA (%)": ("returnOnAssets", lambda x: x is not None and x*100 >= 8, "> 8%"),
        "Revenue Growth (5Y %)": ("revenueGrowth", lambda x: x is not None and x*100 >= 8, "> 8%"),
        "Profit Growth (YoY %)": ("earningsGrowth", lambda x: x is not None and x*100 >= 10, "> 10%"),

        # Yahoo PEG कभी-कभी missing होता है; Screener से भरेंगे
        "PEG Ratio": ("pegRatio", lambda x: x is not None and x <= 1.5, "< 1.5"),

        # Dividend (percent में)
        "Dividend Yield (%)": ("dividendYield", None, "> 1%"),

        # Screener-only (priority)
        "Debt/Equity": ("Debt/Equity", lambda x: x is not None and x < 1, "< 1"),
        "ROCE (%)": ("ROCE", lambda x: x is not None and x >= 12, "> 12%"),
        "Promoter Holding (%)": ("Promoter Holding", lambda x: x is not None and x >= 50, "> 50%"),
        "Pledge (%)": ("Pledge", lambda x: x is not None and x < 5, "< 5%"),
        "FII Holding (%)": ("FII", lambda x: x is not None and x >= 15, "> 15%"),
        "DII Holding (%)": ("DII", lambda x: x is not None and x >= 10, "> 10%"),

        # Market cap (Cr)
        "Market Cap (Cr)": ("marketCap", lambda x: x is not None and (x/1e7) >= 500, "> 500 Cr"),
    }

    results = []
    score_pass = 0
    total = len(rules)

    for metric, (key, rule, healthy_range) in rules.items():
        value, ok, compare = None, "❓ NA", ""

        # DMA special
        if metric == "50DMA > 200DMA":
            f50 = info.get("fiftyDayAverage")
            f200 = info.get("twoHundredDayAverage")
            if f50 is not None and f200 is not None:
                ok_bool = f50 > f200
                ok = "✅ True" if ok_bool else "❌ False"
                value = f"{round(f50,2)} vs {round(f200,2)}"

        # Dividend special
        elif metric == "Dividend Yield (%)":
            dy = compute_dividend_yield_percent(info)
            if dy is not None:
                value = dy
                ok = "✅ True" if dy >= 1 else "❌ False"

        # Screener priority for specific metrics
        elif metric in ["Debt/Equity", "ROCE (%)", "Promoter Holding (%)", "Pledge (%)",
                        "FII Holding (%)", "DII Holding (%)", "PEG Ratio"]:
            # PEG भी screener से भरने की कोशिश
            key_map = {
                "Debt/Equity": "Debt/Equity",
                "ROCE (%)": "ROCE",
                "Promoter Holding (%)": "Promoter Holding",
                "Pledge (%)": "Pledge",
                "FII Holding (%)": "FII",
                "DII Holding (%)": "DII",
                "PEG Ratio": "PEG",
            }
            s_key = key_map[metric]
            s_val = sdata.get(s_key)
            if s_val is not None:
                value = round(s_val, 2)
                ok = "✅ True" if (rule and rule(s_val)) else "❌ False"
            else:
                # fallback to Yahoo if PEG available
                if metric == "PEG Ratio":
                    y_val = info.get("pegRatio")
                    if y_val is not None:
                        value = round(y_val, 2)
                        ok = "✅ True" if rule(y_val) else "❌ False"

        # Yahoo values
        else:
            val = info.get(key, None)
            if val is not None and rule is not None:
                ok = "✅ True" if rule(val) else "❌ False"
                if metric in PERCENT_METRICS:
                    value = round(val * 100, 2)
                elif metric == "Market Cap (Cr)":
                    value = round(val / 1e7, 2)
                else:
                    value = round(val, 2)

        if ok == "✅ True":
            score_pass += 1

        # Industry compare
        if metric == "PE Ratio" and industry_pe:
            compare = f"Industry Avg: {round(industry_pe,2)}"
        elif metric == "PB Ratio" and industry_pb:
            compare = f"Industry Avg: {round(industry_pb,2)}"

        results.append([metric, value, ok, healthy_range, compare])

    df = pd.DataFrame(results, columns=["Parameter", "Value", "Result", "Healthy Range", "Industry Compare"])
    overall_score = f"{score_pass}/{total}  ({round((score_pass/total)*100, 2)}%)"
    return df, overall_score

# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="Advanced Stock Screener with Score", layout="wide")
st.title("📊 Advanced Stock Screener with Score")

symbol = st.text_input("Enter NSE Stock Symbol (e.g., RELIANCE.NS, TCS.NS)", "RELIANCE.NS")

if st.button("Check Stock"):
    df, score = stock_checklist(symbol)

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
    st.subheader(f"📌 Overall Score: {score}")
