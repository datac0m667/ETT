import streamlit as st
import yfinance as yf
import pandas as pd

from ta.momentum import RSIIndicator
from ta.trend import MACD

st.set_page_config(layout="wide")

# =========================
# WATCHLIST GLOBAL
# =========================
WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA",
    "SAP.DE","ADS.DE","ALV.DE",
    "MC.PA","OR.PA","HSBA.L","BP.L",
    "^GSPC","^NDX"
]

# =========================
# DATA
# =========================
def load_data(ticker):
    df = yf.download(ticker, period="3mo", interval="1h", progress=False)
    return df

# =========================
# INDICATORS (SAFE)
# =========================
def indicators(df):
    df = df.copy()
    df = df.dropna()

    close = df["Close"]

    df["EMA9"] = close.ewm(span=9).mean()
    df["EMA21"] = close.ewm(span=21).mean()
    df["EMA50"] = close.ewm(span=50).mean()
    df["EMA200"] = close.ewm(span=200).mean()

    df["RSI"] = RSIIndicator(close).rsi()

    macd = MACD(close)
    df["MACD"] = macd.macd()
    df["MACD_SIGNAL"] = macd.macd_signal()

    df = df.dropna()
    return df

# =========================
# SAFE VALUE CONVERSION
# =========================
def safe(x):
    try:
        return float(x)
    except:
        return None

# =========================
# ANALYSE ENGINE
# =========================
def analyze(df):
    if df is None or df.empty:
        return None

    l = df.iloc[-1]

    ema9 = safe(l["EMA9"])
    ema21 = safe(l["EMA21"])
    ema50 = safe(l["EMA50"])
    ema200 = safe(l["EMA200"])
    rsi = safe(l["RSI"])
    macd = safe(l["MACD"])
    macd_sig = safe(l["MACD_SIGNAL"])
    price = safe(l["Close"])

    values = [ema9, ema21, ema50, ema200, rsi, macd, macd_sig, price]

    if any(v is None for v in values):
        return None

    score = 0

    # Trend
    if ema50 > ema200:
        score += 30
    elif ema50 < ema200:
        score -= 30

    # EMA Structure
    if ema9 > ema21:
        score += 20
    else:
        score -= 10

    # RSI
    if rsi < 35:
        score += 20
    elif rsi > 70:
        score -= 20

    # MACD
    if macd > macd_sig:
        score += 20
    else:
        score -= 20

    entry = ema9
    sl = ema21
    tp = price + (price - sl) * 2

    rr = abs((tp - price) / (price - sl)) if price != sl else 0

    ko = sl * 0.995
    lev = price / (price - ko) if price > ko else 0

    return price, score, entry, sl, tp, rr, ko, lev

# =========================
# UI
# =========================
st.title("🚀 Elite KO Trading Scanner (Stable Version)")

custom = st.text_input("Eigene Ticker (z.B. AAPL,TSLA,NVDA)")

if custom:
    watchlist = [x.strip().upper() for x in custom.split(",")]
else:
    watchlist = WATCHLIST

if st.button("Scanner starten"):

    results = []

    for ticker in watchlist:
        df = load_data(ticker)

        if df is None or df.empty:
            continue

        df = indicators(df)
        result = analyze(df)

        if result is None:
            continue

        price, score, entry, sl, tp, rr, ko, lev = result

        # Filter (nur gute Trades)
        if score < 50:
            continue
        if rr < 2:
            continue

        results.append({
            "Ticker": ticker,
            "Score": round(score, 1),
            "Preis": round(price, 2),
            "Entry": round(entry, 2),
            "SL": round(sl, 2),
            "TP": round(tp, 2),
            "RR": round(rr, 2),
            "KO": round(ko, 2),
            "Hebel": round(lev, 1)
        })

    if results:
        df_out = pd.DataFrame(results).sort_values(by="Score", ascending=False)
        st.dataframe(df_out, use_container_width=True)

        st.success("🔥 Nur hochwertige KO-Setups angezeigt")
    else:
        st.warning("Keine starken Setups aktuell")
