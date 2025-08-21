import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

# ----------------------------
# Screener scraping function (Fixed)
# ----------------------------
def get_screener_data(symbol):
    try:
        url = f"https://www.screener.in/company/{symbol}/consolidated/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/119.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        page = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(page.text, "html.parser")

        data = {}

        # Debt to Equity
        de = soup.find("li", text=lambda t: t and "Debt to equity" in t)
        if de:
            try:
                data["Debt/Equity"] = float(de.text.split(":")[-1].strip())
            except:
                pass

        # ROCE
        roce_el = soup.find("li", text=lambda t: t and "ROCE" in t)
        if roce_el:
            try:
                data["ROCE"] = float(roce_el.text.split(":")[-1].replace("%", "").strip())
            except:
                pass

        # Shareholding table parsing
        sh_table = soup.find("section", {"id": "shareholding"})
        if sh_table:
            rows = sh_table.find_all("tr")
            for row in rows:
                cols = [c.get_text(strip=True) for c in row.find_all("td")]
                if len(cols) >= 2:
                    if cols[0].startswith("Promoters"):
                        try:
                            data["Promoter Holding"] = float(cols[1].replace("%", ""))
                        except:
                            pass
                    elif cols[0].startswith("Pledged"):
                        try:
                            data["Pledge"] = float(cols[1].replace("%", ""))
                        except:
                            pass
                    elif cols[0].startswith("FIIs"):
                        try:
                            data["FII"] = float(cols[1].replace("%", ""))
                        except:
                            pass
                    elif cols[0].startswith("DIIs"):
                        try:
                            data["DII"] = float(cols[1].replace("%", ""))
                        except:
                            pass

        return data
    except Exception as e:
        print("Error in screener fetch:", e)
        return {}

# ----------------------------
# Helpers
# ----------------------------
PERCENT_METRICS = {"ROE (%)", "ROA (%)", "Revenue Growth (5Y %)", "Profit Growth (YoY %)"}

def compute_dividend_yield_percent(info):
    """
    Returns dividend yield in PERCENT (e.g., 0.65 for 0.65%).
    Handles yfinance inconsistencies:
    - Sometimes dividendYield is fraction (0.0065) -> 0.65%
    - Sometimes already percent-like (0.65) -> 0.65%
    - Fallback to dividendRate/price
    """
    y = info.get("dividendYield", None)
    if y is not None:
        try:
            if 0 < y <= 0.2:      # very likely a fraction (<=20%)
                return round(y * 100, 2)
            elif 0 < y <= 20:     # already percent-like
                return round(y, 2)
            else:                 # unusual, keep as is
                return round(y, 2)
        except:
            pass

    rate = info.get("dividendRate", None)
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if rate and price:
        try:
            return round((rate / price) * 100, 2)
        except:
            pass

    return None

# ----------------------------
# Stock checklist
# ----------------------------
def stock_checklist(symbol):
    stock = yf.Ticker(symbol)
    info = stock.info
    price = info.get("currentPrice") or info.get("regularMarketPrice")

    screener_data = get_screener_data(symbol.replace(".NS", ""))

    # Industry averages (if available)
    industry_pe = info.get("industryPE")
    industry_pb = info.get("industryPB")

    rules = {
        "PE Ratio": ("trailingPE", lambda x: 8 <= x <= 25, "8 – 25"),
        "PB Ratio": ("priceToBook", lambda x: x <= 5, "0 – 5"),
        "EPS": ("trailingEps", lambda x: x > 0, "> 0"),

        # Combined DMA rule
        "50DMA > 200DMA": (
            ("fiftyDayAverage", "twoHundredDayAverage"),
            lambda x: (x[0] is not None and x[1] is not None and x[0] > x[1]),
            "50DMA > 200DMA"
        ),

        "ROE (%)": ("returnOnEquity", lambda x: (x is not None) and (x * 100 >= 12), "> 12%"),
        "ROA (%)": ("returnOnAssets", lambda x: (x is not None) and (x * 100 >= 8), "> 8%"),
        "Revenue Growth (5Y %)": ("revenueGrowth", lambda x: (x is not None) and (x * 100 >= 8), "> 8%"),
        "Profit Growth (YoY %)": ("earningsGrowth", lambda x: (x is not None) and (x * 100 >= 10), "> 10%"),
        "PEG Ratio": ("pegRatio", lambda x: x is not None and x <= 1.5, "< 1.5"),

        # Dividend Yield handled specially (rule checks percent directly)
        "Dividend Yield (%)": ("dividendYield", None, "> 1%"),

        "Debt/Equity": ("Debt/Equity", lambda x: x < 1, "< 1"),  # from Screener
        "Market Cap (Cr)": ("marketCap", lambda x: (x is not None) and (x / 1e7 >= 500), "> 500 Cr"),
        "ROCE (%)": ("ROCE", lambda x: x is not None and x >= 12, "> 12%"),  # from Screener
        "Promoter Holding (%)": ("Promoter Holding", lambda x: x is not None and x >= 50, "> 50%"),
        "Pledge (%)": ("Pledge", lambda x: x is not None and x < 5, "< 5%"),
        "FII Holding (%)": ("FII", lambda x: x is not None and x >= 15, "> 15%"),
        "DII Holding (%)": ("DII", lambda x: x is not None and x >= 10, "> 10%"),
    }

    results = []
    score_pass = 0
    total = len(rules)

    for metric, (key, rule, healthy_range) in rules.items():
        value, ok, compare = None, "❓ NA", ""

        # ---- Special: DMA comparison
        if metric == "50DMA > 200DMA":
            f50 = info.get("fiftyDayAverage")
            f200 = info.get("twoHundredDayAverage")
            if f50 is not None and f200 is not None:
                ok = "✅ True" if (f50 > f200) else "❌ False"
                value = f"{round(f50,2)} vs {round(f200,2)}"

        # ---- Special: Dividend Yield normalization
        elif metric == "Dividend Yield (%)":
            dy_percent = compute_dividend_yield_percent(info)
            if dy_percent is not None:
                value = dy_percent
                ok = "✅ True" if dy_percent >= 1 else "❌ False"

        # ---- Screener has priority for those metrics
        elif metric in screener_data:
            val = screener_data.get(metric)
            if val is not None:
                ok = "✅ True" if rule and rule(val) else "❌ False"
                value = round(val, 2)

        # ---- Yahoo values
        else:
            val = info.get(key, None)
            if val is not None and rule is not None:
                ok = "✅ True" if rule(val) else "❌ False"
                if metric in PERCENT_METRICS:
                    value = round(val * 100, 2)
                else:
                    value = round(val, 2)

        if ok == "✅ True":
            score_pass += 1

        # Industry avg note
        if metric == "PE Ratio" and industry_pe:
            compare = f"Industry Avg: {round(industry_pe, 2)}"
        elif metric == "PB Ratio" and industry_pb:
            compare = f"Industry Avg: {round(industry_pb, 2)}"

        results.append([metric, value, ok, healthy_range, compare])

    df = pd.DataFrame(results, columns=["Parameter", "Value", "Result", "Healthy Range", "Industry Compare"])
    overall_score = f"{score_pass}/{total}  ({round((score_pass/total)*100, 2)}%)"
    return df, overall_score

# ----------------------------
# Streamlit UI
# ----------------------------
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
