import yfinance as yf
from nsepython import nse_eq_quote_ltp

def stock_checklist(symbol):
    data = {}

    # Yahoo Finance data
    stock = yf.Ticker(symbol)
    info = stock.info

    # NSE price (Live)
    try:
        nse_data = nse_eq_quote_ltp(symbol.replace(".NS", ""))
        data["Live Price"] = nse_data["priceInfo"]["lastPrice"]
    except:
        data["Live Price"] = "NA"

    # PE Ratio
    pe = info.get("trailingPE")
    data["PE"] = f"{pe:.2f}" if pe else "NA"

    # PB Ratio
    pb = info.get("priceToBook")
    data["PB"] = f"{pb:.2f}" if pb else "NA"

    # EPS
    eps = info.get("trailingEps")
    data["EPS"] = f"{eps:.2f}" if eps else "NA"

    # Dividend Yield
    dy = info.get("dividendYield")
    data["Dividend Yield"] = f"{dy*100:.2f}%" if dy else "NA"

    # Debt / Equity (approx using totalDebt / totalAssets)
    debt = info.get("totalDebt")
    assets = info.get("totalAssets")
    if debt and assets:
        de = debt / assets
        data["Debt/Equity"] = f"{de:.2f}"
    else:
        data["Debt/Equity"] = "NA"

    # ROE
    roe = info.get("returnOnEquity")
    data["ROE"] = f"{roe*100:.2f}%" if roe else "NA"

    # ROA
    roa = info.get("returnOnAssets")
    data["ROA"] = f"{roa*100:.2f}%" if roa else "NA"

    # Market Cap
    mc = info.get("marketCap")
    data["Market Cap"] = f"{mc/1e7:.2f} Cr" if mc else "NA"

    # 5Y Revenue CAGR (approx growth)
    rev = info.get("revenueGrowth")
    data["Revenue Growth"] = f"{rev*100:.2f}%" if rev else "NA"

    # Profit Growth (y-o-y)
    pg = info.get("earningsGrowth")
    data["Profit Growth"] = f"{pg*100:.2f}%" if pg else "NA"

    # PEG Ratio
    peg = info.get("pegRatio")
    data["PEG Ratio"] = f"{peg:.2f}" if peg else "NA"

    return data


# -----------------------
# Example Run
# -----------------------
symbol = "RELIANCE.NS"
result = stock_checklist(symbol)

print(f"Checklist for {symbol}\n")
for k, v in result.items():
    print(f"{k}: {v}")
