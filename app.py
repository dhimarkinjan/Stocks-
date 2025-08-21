import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Screener scraping function
def get_screener_data(symbol):
    try:
        url = f"https://www.screener.in/company/{symbol}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        page = requests.get(url, headers=headers)
        soup = BeautifulSoup(page.text, "html.parser")

        data = {}

        # Debt to Equity
        de = soup.find("li", string=lambda t: t and "Debt to equity" in t)
        if de: data["Debt/Equity"] = float(de.text.split(":")[-1].strip())

        # ROCE
        roce = soup.find("li", string=lambda t: t and "ROCE" in t)
        if roce: data["ROCE"] = float(roce.text.split(":")[-1].strip().replace("%",""))

        # Promoter holding
        promoter = soup.find("td", string="Promoters")
        if promoter and promoter.find_next("td"):
            data["Promoter Holding"] = float(promoter.find_next("td").text.replace("%",""))

        # Pledge %
        pledge = soup.find("td", string="Pledged")
        if pledge and pledge.find_next("td"):
            data["Pledge"] = float(pledge.find_next("td").text.replace("%",""))

        # FII
        fii = soup.find("td", string="FIIs")
        if fii and fii.find_next("td"):
            data["FII"] = float(fii.find_next("td").text.replace("%",""))

        # DII
        dii = soup.find("td", string="DIIs")
        if dii and dii.find_next("td"):
            data["DII"] = float(dii.find_next("td").text.replace("%",""))

        return data
    except:
        return {}

# Stock checklist
def stock_checklist(symbol):
    stock = yf.Ticker(symbol)
    info = stock.info
    price = info.get("currentPrice", None)

    screener_data = get_screener_data(symbol.replace(".NS",""))

    # Industry averages
    industry_pe = info.get("industryPE")
    industry_pb = info.get("industryPB")

    rules = {
        "PE Ratio": ("trailingPE", lambda x: 8 <= x <= 25, "8 – 25"),
        "PB Ratio": ("priceToBook", lambda x: x <= 5, "0 – 5"),
        "EPS": ("trailingEps", lambda x: x > 0, "> 0"),
        "50DMA": ("fiftyDayAverage", lambda x: price > x if price and x else False, "Price > 50DMA"),
        "200DMA": ("twoHundredDayAverage", lambda x: price > x if price and x else False, "Price > 200DMA"),
        "ROE (%)": ("returnOnEquity", lambda x: x*100 >= 12 if x else False, "> 12%"),
        "ROA (%)": ("returnOnAssets", lambda x: x*100 >= 8 if x else False, "> 8%"),
        "Revenue Growth (5Y %)": ("revenueGrowth", lambda x: x*100 >= 8 if x else False, "> 8%"),
        "Profit Growth (YoY %)": ("earningsGrowth", lambda x: x*100 >= 10 if x else False, "> 10%"),
        "PEG Ratio": ("pegRatio", lambda x: x <= 1.5, "< 1.5"),
        "Dividend Yield (%)": ("dividendYield", lambda x: x*100 >= 1 if x else False, "> 1%"),
        "Debt/Equity": ("Debt/Equity", lambda x: x < 1, "< 1"),  # from Screener
        "Market Cap (Cr)": ("marketCap", lambda x: x/1e7 >= 500 if x else False, "> 500 Cr"),
        "ROCE (%)": ("ROCE", lambda x: x >= 12, "> 12%"),  # from Screener
        "Promoter Holding (%)": ("Promoter Holding", lambda x: x >= 50, "> 50%"),
        "Pledge (%)": ("Pledge", lambda x: x < 5, "< 5%"),
        "FII Holding (%)": ("FII", lambda x: x >= 15, "> 15%"),
        "DII Holding (%)": ("DII", lambda x: x >= 10, "> 10%"),
    }

    results = []
    score_pass = 0
    total = len(rules)

    for metric, (key, rule, healthy_range) in rules.items():
        value, ok, compare = None, "❓ NA", ""

        # Screener values first priority
        if metric in screener_data:
            value = screener_data.get(metric)
            if value is not None:
                ok = "✅ True" if rule(value) else "❌ False"
        else:
            val = info.get(key, None)
            if val is not None and rule is not None:
                ok = "✅ True" if rule(val) else "❌ False"
                value = round(val, 2)

        if ok == "✅ True":
            score_pass += 1

        # Industry avg for PE/PB
        if metric == "PE Ratio" and industry_pe:
            compare = f"Industry Avg: {round(industry_pe,2)}"
        elif metric == "PB Ratio" and industry_pb:
            compare = f"Industry Avg: {round(industry_pb,2)}"

        results.append([metric, value, ok, healthy_range, compare])

    df = pd.DataFrame(results, columns=["Parameter", "Value", "Result", "Healthy Range", "Industry Compare"])
    overall_score = f"{score_pass}/{total}  ({round((score_pass/total)*100,2)}%)"
    return df, overall_score

# Streamlit UI
st.title("📊 Advanced Stock Screener with Score")

symbol = st.text_input("Enter NSE Stock Symbol (e.g., RELIANCE.NS, TCS.NS)", "RELIANCE.NS")

if st.button("Check Stock"):
    df, score = stock_checklist(symbol)

    def highlight_result(val):
        if isinstance(val, str):
            if "✅" in val: return 'background-color: lightgreen; font-weight: bold'
            elif "❌" in val: return 'background-color: salmon; font-weight: bold'
            elif "❓" in val: return 'background-color: khaki; font-weight: bold'
        return ''

    st.dataframe(df.style.applymap(highlight_result, subset=["Result"]), use_container_width=True)

    st.subheader(f"📌 Overall Score: {score}")
