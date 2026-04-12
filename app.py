import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")

# =========================
# UNIVERSE (S&P500 + NASDAQ Proxy)
# =========================
WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA","AVGO","AMD","GOOGL","GOOG","NFLX",
    "BRK-B","JPM","V","MA","UNH","XOM","LLY","HD","PG","COST",
    "CRM","ADBE","ORCL","CSCO","QCOM","IBM",
    "^GSPC","^NDX"
]

# =========================
# COMPANY NAME CACHE
# =========================
name_cache = {}

def get_name(ticker):

    if ticker in name_cache:
        return name_cache[ticker]

    try:
        info = yf.Ticker(ticker).info
        name = info.get("longName") or info.get("shortName") or ticker
    except:
        name = ticker

    name_cache[ticker] = name
    return name

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

        return df[["Open","High","Low","Close"]].dropna()

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
# SCORE ENGINE
# =========================
def score(df, i):

    l = df.iloc[i]

    price = l["Close"]
    ema20 = l["EMA20"]
    ema50 = l["EMA50"]
    atr = l["ATR"]

    score = 50
    direction = "NO TRADE"

    # TREND
    if price > ema50:
        score += 20
        direction = "LONG"
    else:
        score += 20
        direction = "SHORT"

    # BREAKOUT
    high20 = df["Close"].iloc[max(0,i-20):i].max()
    low20 = df["Close"].iloc[max(0,i-20):i].min()

    if price > high20:
        score += 25
        direction = "LONG"

    if price < low20:
        score += 25
        direction = "SHORT"

    # ENTRY QUALITY
    if abs(price - ema20) < atr * 0.6:
        score += 10

    vol = atr / price
    score -= vol * 10

    return direction, max(0, min(100, score))

# =========================
# TRADE STRUCTURE
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

        if df is None or len(df) < 120:
            continue

        df = indicators(df)

        direction, sc = score(df, len(df)-1)

        if sc < 65:
            continue

        entry, sl, tp1, tp2, ko, rr = build_trade(df, len(df)-1, direction)

        results.append({
            "Ticker": t,
            "Unternehmen": get_name(t),   # 🆕 NEU
            "Direction": direction,
            "Score": round(sc,1),
            "Entry": round(entry,2),
            "SL": round(sl,2),
            "TP1": round(tp1,2),
            "TP2": round(tp2,2),
            "KO": round(ko,2),
            "RR": round(rr,2)
        })

    return pd.DataFrame(results)

# =========================
# UI
# =========================
st.title("📊🧠 Version 21 – Live Derivate Scanner (Pro Upgrade)")

page_size = 10
page = st.number_input("Seite", min_value=1, value=1, step=1)

if st.button("SCAN STARTEN"):

    df = scan(WATCHLIST)

    if df.empty:
        st.warning("Keine starken Setups gefunden.")
    else:

        df = df.sort_values("Score", ascending=False).reset_index(drop=True)

        start = (page - 1) * page_size
        end = start + page_size

        st.subheader(f"🏆 Top 10 Derivate Setups – Seite {page}")

        st.dataframe(df.iloc[start:end], use_container_width=True)
