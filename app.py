import yfinance as yf
import pandas as pd
import pandas_ta as ta

# --------------------------
# Config
# --------------------------
ticker = "RELIANCE.NS"   # Example NSE stock symbol

# --------------------------
# Fetch Data
# --------------------------
stock = yf.Ticker(ticker)

# Financials / Ratios
eps = stock.info.get("trailingEps")
pe_ratio = stock.info.get("trailingPE")
pb_ratio = stock.info.get("priceToBook")
div_yield = stock.info.get("dividendYield")
roe = stock.info.get("returnOnEquity")
de_ratio = stock.info.get("debtToEquity")

# Historical prices (for DMA, Volume trend)
hist = stock.history(period="1y")
hist["50dma"] = hist["Close"].rolling(50).mean()
hist["200dma"] = hist["Close"].rolling(200).mean()

dma_signal = hist["50dma"].iloc[-1] > hist["200dma"].iloc[-1]
volume_trend = hist["Volume"].iloc[-1] > hist["Volume"].rolling(20).mean().iloc[-1]

# --------------------------
# Screening Rules
# --------------------------
checks = []

def verdict(param, value, rule, condition, why):
    ok = "✅" if condition else "❌"
    checks.append([param, value, ok, why])

verdict("EPS (TTM)", eps, "EPS > 0", eps and eps > 0, "EPS should be positive")
verdict("P/E", pe_ratio, "Compare with industry", True, "High P/E may mean overvaluation")
verdict("P/B", pb_ratio, "< 3 preferred", pb_ratio and pb_ratio < 3, "P/B < 3 is healthy")
verdict("Dividend Yield", div_yield, ">2% preferred", div_yield and div_yield > 0.02, "Dividend yield >2%")
verdict("ROE", roe, ">15% preferred", roe and roe > 0.15, "Strong ROE >15%")
verdict("Debt/Equity", de_ratio, "<1 preferred", de_ratio and de_ratio < 1, "D/E <1 preferred")
verdict("50DMA > 200DMA", dma_signal, "Golden cross bullish", dma_signal, "50DMA > 200DMA indicates bullish")
verdict("Volume Trend", volume_trend, "Rising volume", volume_trend, "Volume should trend up")

# --------------------------
# Output Table
# --------------------------
df = pd.DataFrame(checks, columns=["Parameter", "Value", "Verdict", "Why it matters"])
print(df.to_string(index=False))
