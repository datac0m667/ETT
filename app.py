import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

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
# SAFE DATA LOADER
# =========================
def load_data(ticker):
    try:
        df = yf.download(ticker, period="6mo", interval="1h", progress=False)
        if df is None or df.empty:
            return None
        df = df.copy()
        df = df.dropna()
        return df
    except:
        return None

# =========================
# INDICATORS (NO LIBRARIES → SAFE)
# =========================
def indicators(df):
    df = df.copy()

    close = df["Close"].astype(float)

    # EMAs
    df["EMA9"] = close.ewm(span=9).mean()
    df["EMA21"] = close.ewm(span=21).mean()
    df["EMA50"] = close.ewm(span=50).mean()
    df["EMA200"] = close.ewm(span=200).mean()

    # RSI manual (no ta library)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD manual
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9).mean()

    df = df.dropna()
    return df

# =========================
# ANALYSE ENGINE
# =========================
def analyze(df):
    if df is None or df.empty or len(df) < 210:
        return None

    l = df.iloc[-1]

    def f(x):
        try:
            return float(x)
        except:
            return None

    price = f(l["Close"])
    ema9 = f(l["EMA9"])
    ema21 = f(l["EMA21"])
    ema50 = f(l["EMA50"])
    ema200 = f(l["EMA200"])
    rsi = f(l["RSI"])
    macd = f(l["MACD"])
    macd_sig = f(l["MACD_SIGNAL"])

    vals = [price, ema9, ema21, ema50, ema200, rsi, macd, macd_sig]

    if any(v is None or np.isnan(v) for v in vals):
        return None

    # =========================
    # SCORE ENGINE
    # =========================
    score = 0

    # Trend
    if ema50 > ema200:
        score += 30
    else:
        score -= 30

    # EMA structure
    if ema9 > ema21:
        score += 20

    # RSI logic
    if rsi < 35:
        score += 20
    elif rsi > 70:
        score -= 20

    # MACD
    if macd > macd_sig:
        score += 20
    else:
        score -= 20

    # =========================
    # TRADE SETUP
    # =========================
    entry = ema9
    sl = ema21

    tp = price + (price - sl) * 2 if price > sl else price - (sl - price) * 2

    rr = abs((tp - price) / (price - sl)) if price != sl else 0

    ko = sl * 0.995
    lev = price / (price - ko) if price > ko else 0

    return price, score, entry, sl, tp, rr, ko, lev

# =========================
# UI
# =========================
st.title("🚀 Institutional KO Scanner (Stable Build)")

custom = st.text_input("Tickers (comma separated)", "")

if custom:
    watchlist = [x.strip().upper() for x in custom.split(",")]
else:
    watchlist = WATCHLIST

if st.button("Scan starten"):

    results = []

    for ticker in watchlist:
        df = load_data(ticker)

        if df is None:
            continue

        df = indicators(df)
        result = analyze(df)

        if result is None:
            continue

        price, score, entry, sl, tp, rr, ko, lev = result

        # FILTER (quality control)
        if score < 50:
            continue
        if rr < 2:
            continue

        results.append({
            "Ticker": ticker,
            "Score": round(score, 1),
            "Price": round(price, 2),
            "Entry": round(entry, 2),
            "SL": round(sl, 2),
            "TP": round(tp, 2),
            "RR": round(rr, 2),
            "KO": round(ko, 2),
            "Leverage": round(lev, 1)
        })

    if results:
        df_out = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.dataframe(df_out, use_container_width=True)
        st.success("Top Setups gefunden")
    else:
        st.warning("Keine gültigen Trades aktuell")
