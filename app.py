import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")

WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA",
    "SAP.DE","ADS.DE","ALV.DE",
    "MC.PA","OR.PA","HSBA.L","BP.L",
    "^GSPC","^NDX"
]

# =========================
# DATA LOADER (SAFE)
# =========================
def load_data(ticker):
    try:
        df = yf.download(ticker, period="90d", interval="1h", progress=False)
        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return df.dropna()

    except:
        return None

# =========================
# INDICATORS
# =========================
def indicators(df):
    df = df.copy()
    close = df["Close"].astype(float)

    df["EMA20"] = close.ewm(span=20).mean()
    df["EMA50"] = close.ewm(span=50).mean()
    df["EMA200"] = close.ewm(span=200).mean()

    # volatility proxy
    df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

    return df.dropna()

# =========================
# MARKET REGIME
# =========================
def regime(df):
    ema50 = df["EMA50"]
    ema200 = df["EMA200"]

    trend_strength = abs(ema50.iloc[-1] - ema200.iloc[-1]) / df["Close"].iloc[-1]

    if ema50.iloc[-1] > ema200.iloc[-1] and trend_strength > 0.015:
        return "UPTREND"
    elif ema50.iloc[-1] < ema200.iloc[-1] and trend_strength > 0.015:
        return "DOWNTREND"
    else:
        return "RANGE"

# =========================
# SIGNAL ENGINE (CORE)
# =========================
def signal(df):
    l = df.iloc[-1]

    price = float(l["Close"])
    ema20 = float(l["EMA20"])
    ema50 = float(l["EMA50"])
    ema200 = float(l["EMA200"])
    atr = float(l["ATR"])

    reg = regime(df)

    score = 50
    signal_type = "NONE"

    # =========================
    # TREND MODE
    # =========================
    if reg in ["UPTREND", "DOWNTREND"]:

        # Pullback Entry
        if abs(price - ema20) < atr * 0.5:
            signal_type = "TREND_PULLBACK"
            score += 25

        if price > ema50:
            score += 10

        if price < ema50 and reg == "UPTREND":
            score -= 15

    # =========================
    # BREAKOUT MODE
    # =========================
    high_20 = df["Close"].rolling(20).max().iloc[-1]
    low_20 = df["Close"].rolling(20).min().iloc[-1]

    if price > high_20 * 0.998:
        signal_type = "BREAKOUT_UP"
        score += 30

    if price < low_20 * 1.002:
        signal_type = "BREAKOUT_DOWN"
        score += 30

    # =========================
    # RANGE MODE
    # =========================
    if reg == "RANGE":

        if price < ema20:
            signal_type = "MEAN_REVERSION_LONG"
            score += 20

        if price > ema20:
            signal_type = "MEAN_REVERSION_SHORT"
            score += 20

    # =========================
    # FINAL FILTER
    # =========================
    if score < 55:
        signal_type = "NO_TRADE"

    entry = ema20
    sl = ema50

    tp = price + (price - sl) * 1.5 if price > sl else price - (sl - price) * 1.5

    rr = abs((tp - price) / (price - sl)) if price != sl else 0

    return price, score, signal_type, reg, entry, sl, tp, rr

# =========================
# UI
# =========================
st.title("🚀 Version 7 – Real Trading Signal Engine")

custom = st.text_input("Tickers (comma separated)")

watchlist = [x.strip().upper() for x in custom.split(",")] if custom else WATCHLIST

if st.button("Scan starten"):

    results = []

    for ticker in watchlist:

        df = load_data(ticker)
        if df is None:
            continue

        df = indicators(df)

        price, score, sig, reg, entry, sl, tp, rr = signal(df)

        results.append({
            "Ticker": ticker,
            "Regime": reg,
            "Signal": sig,
            "Score": round(score,1),
            "Price": round(price,2),
            "Entry": round(entry,2),
            "SL": round(sl,2),
            "TP": round(tp,2),
            "RR": round(rr,2)
        })

    df_out = pd.DataFrame(results)

    st.dataframe(df_out.sort_values("Score", ascending=False))

    st.success("Scan abgeschlossen – Signale klassifiziert")
