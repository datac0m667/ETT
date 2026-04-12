import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")

# =========================
# UNIVERSUM
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
# SCORING ENGINE (PRO LEVEL)
# =========================
def score(df, i):

    l = df.iloc[i]

    price = l["Close"]
    ema20 = l["EMA20"]
    ema50 = l["EMA50"]
    atr = l["ATR"]

    trend = 50
    momentum = 50
    entry_quality = 50
    vol_quality = 50

    # TREND
    if price > ema50:
        trend += 25
        direction = "LONG"
    else:
        trend -= 25
        direction = "SHORT"

    # MOMENTUM (Breakout)
    high20 = df["Close"].iloc[max(0, i-20):i].max()
    low20 = df["Close"].iloc[max(0, i-20):i].min()

    if price > high20:
        momentum += 25
        direction = "LONG"
    if price < low20:
        momentum += 25
        direction = "SHORT"

    # ENTRY QUALITY (Pullback zone)
    if abs(price - ema20) < atr * 0.6:
        entry_quality += 25

    # VOLATILITY QUALITY
    vol_quality += max(0, 25 - (atr / price) * 100)

    total = trend + momentum + entry_quality + vol_quality

    score = total / 4

    return direction, score

# =========================
# TRADE STRUCTURE (DERIVAT STYLE)
# =========================
def build_trade(df, i, direction):

    price = df.iloc[i]["Close"]
    atr = df.iloc[i]["ATR"]

    entry = price

    if direction == "LONG":
        sl = price - atr * 1.5
        tp1 = price + atr * 1.5
        tp2 = price + atr * 3.0
        ko = sl - atr * 0.5
    else:
        sl = price + atr * 1.5
        tp1 = price - atr * 1.5
        tp2 = price - atr * 3.0
        ko = sl + atr * 0.5

    rr = abs(tp2 - entry) / abs(entry - sl)

    return entry, sl, tp1, tp2, ko, rr

# =========================
# SCANNER
# =========================
def scan(universe):

    results = []

    for t in universe:

        df = load(t)

        if df is None or len(df) < 100:
            continue

        df = indicators(df)

        direction, sc = score(df, len(df)-1)

        if sc < 65:
            continue

        entry, sl, tp1, tp2, ko, rr = build_trade(df, len(df)-1, direction)

        results.append({
            "Ticker": t,
            "Direction": direction,
            "Score": round(sc, 1),
            "Entry": round(entry, 2),
            "SL": round(sl, 2),
            "TP1": round(tp1, 2),
            "TP2": round(tp2, 2),
            "KO": round(ko, 2),
            "RR": round(rr, 2)
        })

    return pd.DataFrame(results)

# =========================
# UI
# =========================
st.title("📊🧠 Version 20 – Pro Derivate Scanner")

inp = st.text_input("Tickers (optional)")

watch = [x.strip().upper() for x in inp.split(",")] if inp else WATCHLIST

if st.button("SCAN STARTEN"):

    df = scan(watch)

    if df.empty:
        st.warning("Keine starken Setups gefunden.")
    else:
        df = df.sort_values("Score", ascending=False)

        st.subheader("🏆 Top Derivate Setups")

        st.dataframe(df, use_container_width=True)
