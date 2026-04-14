import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from urllib.parse import quote
import math

st.set_page_config(page_title="Trading Scanner", page_icon="📡", layout="wide")

# ─────────────────────────────────────────────────────────
# WATCHLIST
# ─────────────────────────────────────────────────────────
WATCHLIST = {
    "Tech": ["AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","NFLX"],
    "Semis": ["AMD","AVGO","QCOM","INTC","MU","AMAT","LRCX","TXN"],
    "Finance": ["JPM","BAC","GS","MS","V","MA"],
}
ALL_TICKERS = [t for g in WATCHLIST.values() for t in g]

# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────
def sf(x):
    try:
        if isinstance(x, pd.Series):
            x = x.iloc[0]
        if pd.isna(x):
            return None
        return float(x)
    except:
        return None

# ─────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load(ticker):
    try:
        df = yf.download(ticker, period="120d", interval="1h", progress=False)
        if df.empty:
            return None
        df = df.reset_index()
        df = df[["Datetime","Open","High","Low","Close","Volume"]].dropna()
        return df
    except:
        return None

# ─────────────────────────────────────────────────────────
# INDICATORS
# ─────────────────────────────────────────────────────────
def add_indicators(df):
    df = df.copy()
    c = df["Close"]

    df["EMA20"] = c.ewm(span=20).mean()
    df["EMA50"] = c.ewm(span=50).mean()
    df["EMA200"] = c.ewm(span=200).mean()

    df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    return df.dropna()

# ─────────────────────────────────────────────────────────
# TREND SCORE
# ─────────────────────────────────────────────────────────
def trend_score(df):
    r = df.iloc[-1]

    price = sf(r["Close"])
    ema20 = sf(r["EMA20"])
    ema50 = sf(r["EMA50"])
    ema200 = sf(r["EMA200"])
    rsi = sf(r["RSI"])

    if None in [price, ema20, ema50, ema200, rsi]:
        return None, 0

    direction = "LONG" if price > ema50 else "SHORT"
    score = 0

    if direction == "LONG":
        if price > ema200: score += 30
        if ema20 > ema50: score += 20
    else:
        if price < ema200: score += 30
        if ema20 < ema50: score += 20

    if 40 < rsi < 70:
        score += 20

    return direction, score

# ─────────────────────────────────────────────────────────
# LEVELS (FIXED)
# ─────────────────────────────────────────────────────────
def build_levels(price, atr, direction):
    if not price or not atr:
        return {}

    if direction == "LONG":
        sl = price - 1.5 * atr
        tp = price + 3 * atr
    else:
        sl = price + 1.5 * atr
        tp = price - 3 * atr

    risk = abs(price - sl)
    reward = abs(tp - price)

    rr = reward / risk if risk != 0 else 0

    return {"sl": sl, "tp": tp, "rr": rr}

# ─────────────────────────────────────────────────────────
# RULES (FIXED)
# ─────────────────────────────────────────────────────────
def evaluate_rules(df, direction, price, atr):
    reasons = []
    ok = True

    ema20 = sf(df["EMA20"].iloc[-1])
    ema50 = sf(df["EMA50"].iloc[-1])
    ema200 = sf(df["EMA200"].iloc[-1])
    rsi = sf(df["RSI"].iloc[-1])

    atr_pct = (atr / price * 100) if price and atr else None

    # FIXED LINE
    if atr_pct is None or not (0.5 <= atr_pct <= 3):
        ok = False
        atr_str = f"{atr_pct:.2f}" if atr_pct is not None and not math.isnan(atr_pct) else "n/a"
        reasons.append(f"ATR nicht ok ({atr_str})")

    if rsi is None or rsi < 40 or rsi > 70:
        ok = False
        reasons.append("RSI schlecht")

    return ok, reasons

# ─────────────────────────────────────────────────────────
# SCAN (FIXED)
# ─────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def run_scan(min_score):
    results = []

    for ticker in ALL_TICKERS:
        df = load(ticker)
        if df is None:
            continue

        df = add_indicators(df)
        direction, ts = trend_score(df)

        if direction is None or ts < min_score:
            continue

        r = df.iloc[-1]
        price = sf(r["Close"])
        atr = sf(r["ATR"])
        rsi = sf(r["RSI"])

        if price is None or atr is None:
            continue

        levels = build_levels(price, atr, direction)
        rules_ok, reasons = evaluate_rules(df, direction, price, atr)

        results.append({
            "Ticker": ticker,
            "Dir": direction,
            "Trend": ts,
            "Price": round(price, 2),
            "RSI": round(rsi, 1) if rsi else None,
            "ATR%": round(atr / price * 100, 2) if price else None,
            "RR": round(levels.get("rr", 0), 1),
            "Rules_OK": rules_ok,
            "Fail": "; ".join(reasons)
        })

    return pd.DataFrame(results)

# ─────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────
st.title("📡 Trading Scanner")

min_score = st.slider("Min Score", 0, 100, 40)

results = run_scan(min_score)

if results.empty:
    st.warning("Keine Signale")
else:
    st.dataframe(results)

    sel = st.selectbox("Ticker wählen", results["Ticker"])

    df = load(sel)
    df = add_indicators(df)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Datetime"], y=df["Close"], name="Price"))
    fig.add_trace(go.Scatter(x=df["Datetime"], y=df["EMA20"], name="EMA20"))
    fig.add_trace(go.Scatter(x=df["Datetime"], y=df["EMA50"], name="EMA50"))

    st.plotly_chart(fig, use_container_width=True)
