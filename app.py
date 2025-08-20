import streamlit as st
import yfinance as yf
import pandas as pd

st.title("📊 Nifty 50 Stock Screener (Checklist Based)")

# ✅ Nifty 50 stock list
nifty50_stocks = [
    "ADANIENT.NS","ADANIPORTS.NS","APOLLOHOSP.NS","ASIANPAINT.NS","AXISBANK.NS",
    "BAJAJ-AUTO.NS","BAJFINANCE.NS","BAJAJFINSV.NS","BHARTIARTL.NS","BPCL.NS",
    "BRITANNIA.NS","CIPLA.NS","COALINDIA.NS","DIVISLAB.NS","DRREDDY.NS",
    "EICHERMOT.NS","GRASIM.NS","HCLTECH.NS","HDFC.NS","HDFCBANK.NS",
    "HEROMOTOCO.NS","HINDALCO.NS","HINDUNILVR.NS","ICICIBANK.NS","INDUSINDBK.NS",
    "INFY.NS","IOC.NS","ITC.NS","JSWSTEEL.NS","KOTAKBANK.NS",
    "LT.NS","M&M.NS","MARUTI.NS","NESTLEIND.NS","NTPC.NS",
    "ONGC.NS","POWERGRID.NS","RELIANCE.NS","SBILIFE.NS","SBIN.NS",
    "SUNPHARMA.NS","TATACONSUM.NS","TATAMOTORS.NS","TATASTEEL.NS","TCS.NS",
    "TECHM.NS","TITAN.NS","ULTRACEMCO.NS","UPL.NS","WIPRO.NS"
]

def screen_stock(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info

        pe = info.get("trailingPE")
        pb = info.get("priceToBook")
        roe = (info.get("returnOnEquity") or 0) * 100 if info.get("returnOnEquity") else None
        de = info.get("debtToEquity")
        eps = info.get("trailingEps")
        rev_g = (info.get("revenueGrowth") or 0) * 100 if info.get("revenueGrowth") else None
        fcf = info.get("freeCashflow")

        passed = (
            (pe is not None and 0 < pe < 40) and
            (pb is not None and pb < 5) and
            (roe is not None and roe > 15) and
            (de is not None and de < 100) and
            (eps is not None and eps > 0) and
            (rev_g is not None and rev_g > 5) and
            (fcf is not None and fcf > 0)
        )

        status = "✅ Good" if passed else "❌ Fail"
        return {"Stock": symbol, "Status": status, "P/E": pe, "P/B": pb, "ROE%": roe, "D/E": de, "EPS": eps, "Rev.Growth%": rev_g}
    except Exception as e:
        return {"Stock": symbol, "Status": "Error", "Reason": str(e)}

# ---------------------------
# Section 1: Auto Nifty 50 Screening
# ---------------------------
st.subheader("🔎 Auto Screening of Nifty 50 Stocks")

results = [screen_stock(s) for s in nifty50_stocks]
df = pd.DataFrame(results)

passed_df = df[df["Status"] == "✅ Good"]

if not passed_df.empty:
    st.success("✅ Passed Stocks from Nifty 50")
    st.dataframe(passed_df, use_container_width=True)
else:
    st.warning("❌ Abhi koi bhi Nifty 50 stock checklist pass nahi kar raha.")

# ---------------------------
# Section 2: Manual Search Box
# ---------------------------
st.subheader("✍️ Check Custom Stocks")

symbols = st.text_input("Enter stock symbols (comma separated)", "RELIANCE.NS, TCS.NS")

if st.button("Run Custom Analysis"):
    custom_list = [s.strip() for s in symbols.split(",") if s.strip()]
    custom_results = [screen_stock(s) for s in custom_list]
    custom_df = pd.DataFrame(custom_results)
    st.dataframe(custom_df, use_container_width=True)
