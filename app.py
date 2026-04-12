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
# DATA LOADER
# =========================
def load_data(ticker):
    try:
        df = yf.download(ticker, period="90d", interval="1h", progress=False)
        if df is None or df.empty:
            return None
        return df.dropna()
    except:
        return None

# =========================
# INDICATORS
# =========================
def indicators(df):
    df = df.copy()
    close = df["Close"].astype(float)

    # EMAs
    df["EMA9"] = close.ewm(span=9).mean()
    df["EMA21"] = close.ewm(span=21).mean()
    df["EMA50"] = close.ewm(span=50).mean()
    df["EMA200"] = close.ewm(span=200).mean()

    # RSI (manual)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD (manual)
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9).mean()

    return df.dropna()

# =========================
# SAFE CONVERSION
# =========================
def f(x):
    try:
        return float(x)
    except:
        return None

# =========================
# MARKET PHASE
# =========================
def market_phase(df):
    close = df["Close"]

    ema50 = close.ewm(span=50).mean()
    ema200 = close.ewm(span=200).mean()

    last_price = close.iloc[-1]

    trend_strength = abs(ema50.iloc[-1] - ema200.iloc[-1]) / last_price

    if ema50.iloc[-1] > ema200.iloc[-1] and trend_strength > 0.02:
        return "TREND_UP"
    elif ema50.iloc[-1] < ema200.iloc[-1] and trend_strength > 0.02:
        return "TREND_DOWN"
    else:
        return "RANGE"

# =========================
# ANALYSE ENGINE (FINAL)
# =========================
def analyze(df):
    if df is None or df.empty:
        return None

    l = df.iloc[-1]

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

    phase = market_phase(df)

    score = 50  # baseline

    # ======================
    # TREND MODE
    # ======================
    if phase in ["TREND_UP", "TREND_DOWN"]:

        if ema9 > ema21:
            score += 15
        else:
            score -= 10

        if price > ema50:
            score += 10
        else:
            score -= 5

        if rsi < 45:
            score += 10
        elif rsi > 70:
            score -= 10

    # ======================
    # RANGE MODE
    # ======================
    if phase == "RANGE":

        if rsi < 30:
            score += 20
        elif rsi > 70:
            score += 20

    # ======================
    # MACD (universal)
    # ======================
    if macd > macd_sig:
        score += 10
    else:
        score -= 5

    # ======================
    # TRADE STRUCTURE
    # ======================
    entry = ema21
    sl = ema50

    tp = price + (price - sl) * 1.5 if price > sl else price - (sl - price) * 1.5

    rr = abs((tp - price) / (price - sl)) if price != sl else 0

    ko = sl * 0.995
    lev = price / (price - ko) if price > ko else 0

    return price, score, entry, sl, tp, rr, ko, lev, phase

# =========================
# UI
# =========================
st.title("🚀 Institutional KO Scanner v4 (Market Phase Engine)")

custom = st.text_input("Tickers (comma separated)")

if custom:
    watchlist = [x.strip().upper() for x in custom.split(",")]
else:
    watchlist = WATCHLIST

if st.button("Scanner starten"):

    results = []

    for ticker in watchlist:

        df = load_data(ticker)

        if df is None:
            continue

        df = indicators(df)
        result = analyze(df)

        if result is None:
            continue

        price, score, entry, sl, tp, rr, ko, lev, phase = result

        # ======================
        # FILTER (REALISTIC)
        # ======================
        if score < 35:
            continue

        if rr < 1.2:
            continue

        results.append({
            "Ticker": ticker,
            "Phase": phase,
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
        st.success("🔥 Markt hat aktuell handelbare Setups")
    else:
        st.warning("Keine starken Setups aktuell (alle Marktphasen berücksichtigt)")
