# pip install streamlit requests beautifulsoup4 pandas matplotlib jugaad_data lxml

import streamlit as st
from jugaad_data.nse import NSELive, stock_df
import pandas as pd
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
from datetime import date

# ---------- Helper: Format INR ----------
def human_inr(n):
    try:
        n = float(str(n).replace(",",""))
    except:
        return "N/A"
    if n >= 1e7:
        return f"{n/1e7:.2f} Cr"
    if n >= 1e5:
        return f"{n/1e5:.2f} L"
    return f"{n:,.2f}"

# ---------- NSE Live Data ----------
nse = NSELive()

def get_nse_data(symbol):
    try:
        symbol_clean = symbol.replace(".NS", "")
        q = nse.stock_quote(symbol_clean)
        price = q["priceInfo"]["lastPrice"]
        high52 = q["priceInfo"]["weekHighLow"]["max"]
        low52 = q["priceInfo"]["weekHighLow"]["min"]
        vol = q["securityInfo"]["issuedSize"]
        mcap = price * vol if price and vol else None
        return price, high52, low52, mcap
    except:
        return None, None, None, None

def get_hist(symbol):
    try:
        df = stock_df(symbol.replace(".NS",""),
                      from_date=date.today().replace(year=date.today().year-1),
                      to_date=date.today(),
                      series="EQ")
        return df
    except:
        return pd.DataFrame()

# ---------- Screener.in Fundamentals ----------
def get_screener_data(symbol):
    data = {}
    try:
        url = f"https://www.screener.in/company/{symbol.replace('.NS','')}/consolidated/"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "lxml")

        # Key ratios
        ratios = soup.find("section", {"id":"ratios"})
        if ratios:
            rows = ratios.find_all("li")
            for row in rows:
                text = row.get_text(" ", strip=True)
                if "ROE" in text: data["ROE"] = text.split()[-1]
                if "ROCE" in text: data["ROCE"] = text.split()[-1]
                if "Dividend Yield" in text: data["Dividend Yield"] = text.split()[-1]
                if "PEG Ratio" in text: data["PEG"] = text.split()[-1]
                if "P/E" in text: data["PE"] = text.split()[-1]
                if "P/B" in text: data["PB"] = text.split()[-1]
                if "Net Profit Margin" in text: data["Net Profit Margin"] = text.split()[-1]

        # Shareholding
        share_data = {}
        tables = soup.find_all("table")
        for t in tables:
            if "Shareholding" in str(t):
                rows = t.find_all("tr")
                for row in rows:
                    cols = [c.get_text(strip=True) for c in row.find_all("td")]
                    if len(cols)==2:
                        share_data[cols[0]] = cols[1]
        data.update(share_data)
    except:
        pass
    return data

# ---------- Rule Evaluation with Score ----------
def evaluate_rules(metrics):
    rules = []

    def verdict(val, cond, why):
        return {
            "Value": val,
            "Verdict": "✔️" if cond else "❌",
            "Why": why,
            "Score": 1 if cond else 0
        }

    rules.append({
        "Parameter":"ROE",
        **verdict(metrics.get("ROE"), float(str(metrics.get("ROE","0")).replace("%","") or 0) > 15, "ROE > 15% preferred")
    })
    rules.append({
        "Parameter":"ROCE",
        **verdict(metrics.get("ROCE"), float(str(metrics.get("ROCE","0")).replace("%","") or 0) > 15, "ROCE > 15% preferred")
    })
    rules.append({
        "Parameter":"Net Profit Margin",
        **verdict(metrics.get("Net Profit Margin"), float(str(metrics.get("Net Profit Margin","0")).replace("%","") or 0) > 10, "Net margin >10% preferred")
    })
    rules.append({
        "Parameter":"P/E",
        **verdict(metrics.get("PE"), float(str(metrics.get("PE","999")).replace(",","")) < 40, "P/E < 40 preferred")
    })
    rules.append({
        "Parameter":"P/B",
        **verdict(metrics.get("PB"), float(str(metrics.get("PB","999")).replace(",","")) < 3, "P/B < 3 preferred")
    })
    rules.append({
        "Parameter":"PEG",
        **verdict(metrics.get("PEG"), float(str(metrics.get("PEG","999")).replace(",","")) < 1, "PEG < 1 preferred")
    })
    rules.append({
        "Parameter":"Dividend Yield",
        **verdict(metrics.get("Dividend Yield"), float(str(metrics.get("Dividend Yield","0")).replace("%","") or 0) >= 2, "DY ≥ 2% preferred")
    })
    rules.append({
        "Parameter":"Promoter Holding",
        **verdict(metrics.get("Promoter"), float(str(metrics.get("Promoter","0")).replace("%","") or 0) > 50, "Promoter >50% preferred")
    })
    rules.append({
        "Parameter":"Pledged %",
        **verdict(metrics.get("Pledged"), str(metrics.get("Pledged","0")) in ["0","0.0","0%","None","-"], "Prefer 0% pledged")
    })
    rules.append({
        "Parameter":"FII/DII Holding",
        **verdict(metrics.get("FII/DII"), float(str(metrics.get("FII/DII","0")).replace("%","") or 0) > 10, "Higher institutional holding preferred")
    })

    df = pd.DataFrame(rules)

    # Overall Score
    total = df["Score"].sum()
    max_score = len(df)
    overall = round((total / max_score) * 100, 2)

    return df.drop(columns=["Score"]), overall

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Stock Analyzer - NSE + Screener", layout="wide")

st.title("📊 Stock Analyzer — NSE + Screener.in (Multi-stock)")
symbols = st.text_input("Enter NSE symbols (.NS suffix)", "RELIANCE.NS,TCS.NS,INFY.NS").split(",")

for sym in [s.strip().upper() for s in symbols if s.strip()]:
    st.header(sym)

    # NSE Data
    price, h52, l52, mcap = get_nse_data(sym)
    st.markdown(f"**Market Cap:** {human_inr(mcap)} | **Price:** {human_inr(price)} | **52W High:** {human_inr(h52)} | **52W Low:** {human_inr(l52)}")

    # Screener Data
    screener = get_screener_data(sym)

    st.write("### Fundamentals (Screener)")
    st.json(screener)

    # Rules + Overall Score
    st.write("### Rules Check")
    df_rules, score = evaluate_rules(screener)
    st.dataframe(df_rules)
    st.success(f"✅ Overall Score: {score}%")

    # Chart
    hist = get_hist(sym)
    if not hist.empty:
        fig, ax = plt.subplots()
        ax.plot(hist["DATE"], hist["CLOSE"], label=sym)
        ax.legend()
        st.pyplot(fig)
