import streamlit as st
import yfinance as yf
import pandas as pd

st.title("📊 Stock Screener (Checklist Based)")

st.write("Example: RELIANCE.NS, TCS.NS, HDFCBANK.NS, INFY.NS, ICICIBANK.NS")

symbols = st.text_input("Enter stock symbols (comma separated)", "RELIANCE.NS, TCS.NS, HDFCBANK.NS")

def screen_stock(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info  # Note: yfinance info kabhi-kabhi slow/partial ho sakta hai

        pe = info.get("trailingPE")
        pb = info.get("priceToBook")
        roe = (info.get("returnOnEquity") or 0) * 100 if info.get("returnOnEquity") is not None else None
        de = info.get("debtToEquity")
        eps = info.get("trailingEps")
        rev_g = (info.get("revenueGrowth") or 0) * 100 if info.get("revenueGrowth") is not None else None
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

if st.button("Run Analysis"):
    stocks = [s.strip() for s in symbols.split(",") if s.strip()]
    results = [screen_stock(s) for s in stocks]
    df = pd.DataFrame(results)
    st.dataframe(df, use_container_width=True)
    good = df[df["Status"]=="✅ Good"]["Stock"].tolist() if "Status" in df else []
    if good:
        st.success(f"Passed: {', '.join(good)}")
    else:
        st.info("No stock passed the checklist yet.")
