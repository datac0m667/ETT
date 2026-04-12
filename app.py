import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")

# =========================
# WATCHLIST
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
def load(ticker):
    try:
        df = yf.download(ticker, period="180d", interval="1h", progress=False)

        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        for c in ["Open","High","Low","Close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        return df.dropna()

    except:
        return None

# =========================
# INDICATORS
# =========================
def indicators(df):
    df = df.copy()

    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()

    tr = np.maximum(
        df["High"] - df["Low"],
        np.maximum(
            abs(df["High"] - df["Close"].shift()),
            abs(df["Low"] - df["Close"].shift())
        )
    )

    df["ATR"] = pd.Series(tr).rolling(14).mean()

    return df.dropna()

# =========================
# CORE SIGNAL ENGINE (VERSION 11 BASIS)
# =========================
def signal(df, i):

    l = df.iloc[i]

    price = float(l["Close"])
    ema20 = float(l["EMA20"])
    ema50 = float(l["EMA50"])
    atr = float(l["ATR"])

    score_long = 50
    score_short = 50

    # Trend
    if price > ema50:
        score_long += 15
    else:
        score_short += 15

    # Pullback
    if abs(price - ema20) < atr * 0.6:
        score_long += 10
        score_short += 10

    # Breakout
    start = max(0, i - 20)
    high20 = df["Close"].iloc[start:i].max()
    low20 = df["Close"].iloc[start:i].min()

    if price > high20:
        score_long += 25
    if price < low20:
        score_short += 25

    total = score_long + score_short
    long_p = score_long / total
    short_p = score_short / total

    if long_p > 0.60:
        direction = "LONG"
        score = long_p
    elif short_p > 0.60:
        direction = "SHORT"
        score = short_p
    else:
        direction = "NO TRADE"
        score = 0.5

    entry = price

    # =========================
    # DERIVAT STRUCTURE
    # =========================
    if direction == "LONG":
        sl = price - atr * 1.5
        tp1 = price + atr * 1.5
        tp2 = price + atr * 3.0
    elif direction == "SHORT":
        sl = price + atr * 1.5
        tp1 = price - atr * 1.5
        tp2 = price - atr * 3.0
    else:
        sl = tp1 = tp2 = price

    # KO LEVEL (IMPORTANT FOR DERIVATES)
    buffer = atr * 0.5

    if direction == "LONG":
        ko = sl - buffer
    elif direction == "SHORT":
        ko = sl + buffer
    else:
        ko = price

    rr = abs(tp2 - entry) / abs(entry - sl) if sl != entry else 0

    return direction, entry, sl, tp1, tp2, ko, rr, score

# =========================
# CHART
# =========================
def chart(df):

    fig = go.Figure()

    fig.add_trace(go.Scatter(y=df["Close"], name="Preis"))
    fig.add_trace(go.Scatter(y=df["EMA20"], name="EMA20"))
    fig.add_trace(go.Scatter(y=df["EMA50"], name="EMA50"))

    fig.update_layout(height=400)

    return fig

# =========================
# UI
# =========================
st.title("🧠🏦 Version 19 – Derivate / KO Trading System")

inp = st.text_input("Tickers (kommagetrennt)")

watch = [x.strip().upper() for x in inp.split(",")] if inp else WATCHLIST

if st.button("Analyse starten"):

    for t in watch:

        df = load(t)

        if df is None:
            continue

        df = indicators(df)

        direction, entry, sl, tp1, tp2, ko, rr, score = signal(df, len(df)-1)

        emoji = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚪"

        st.subheader(f"{emoji} {t} → {direction}")

        st.write({
            "Entry": round(entry, 2),
            "Stop Loss": round(sl, 2),
            "Take Profit 1": round(tp1, 2),
            "Take Profit 2": round(tp2, 2),
            "KO Level": round(ko, 2),
            "Risk/Reward": round(rr, 2),
            "Signal Score": round(score * 100, 1)
        })

        st.plotly_chart(chart(df), use_container_width=True)
