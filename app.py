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

START_CAPITAL = 10000
BASE_RISK = 0.01

# =========================
# DATA LOADER
# =========================
def load_data(ticker, interval="1h", period="180d"):
    try:
        df = yf.download(ticker, interval=interval, period=period, progress=False)

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
    df["EMA200"] = df["Close"].ewm(span=200).mean()

    df["RET"] = df["Close"].pct_change()

    df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

    return df.dropna()

# =========================
# REGIME DETECTION (INSTITUTIONAL)
# =========================
def regime(df):

    ema50 = df["EMA50"].iloc[-1]
    ema200 = df["EMA200"].iloc[-1]
    price = df["Close"].iloc[-1]

    trend_strength = (ema50 - ema200) / price

    if ema50 > ema200 and trend_strength > 0.01:
        return "BULL"
    elif ema50 < ema200 and trend_strength < -0.01:
        return "BEAR"
    else:
        return "SIDEWAYS"

# =========================
# V11 SIGNAL ENGINE (UNCHANGED CORE)
# =========================
def signal(df, i):

    l = df.iloc[i]

    price = float(l["Close"])
    ema20 = float(l["EMA20"])
    ema50 = float(l["EMA50"])
    atr = float(l["ATR"])

    long_score = 50
    short_score = 50

    if price > ema50:
        long_score += 10
    else:
        short_score += 10

    if abs(price - ema20) < atr * 0.6:
        long_score += 10
        short_score += 10

    start = max(0, i - 20)

    high20 = df["Close"].iloc[start:i].max()
    low20 = df["Close"].iloc[start:i].min()

    if price > high20:
        long_score += 25
    if price < low20:
        short_score += 25

    total = long_score + short_score
    long_p = long_score / total
    short_p = short_score / total

    if long_p > 0.60:
        direction = "LONG"
        conf = long_p
    elif short_p > 0.60:
        direction = "SHORT"
        conf = short_p
    else:
        direction = "NO TRADE"
        conf = 0.5

    if direction == "LONG":
        sl = price - atr * 1.5
        tp = price + atr * 2.5
    elif direction == "SHORT":
        sl = price + atr * 1.5
        tp = price - atr * 2.5
    else:
        sl = tp = price

    return direction, price, sl, tp, long_p, short_p, conf

# =========================
# AI SCORE (NO ML LIBS)
# =========================
def ai_score(df, i):

    l = df.iloc[i]

    price = l["Close"]
    ema20 = l["EMA20"]
    ema50 = l["EMA50"]
    atr = l["ATR"]

    trend = 1 if price > ema50 else -1
    momentum = (price - ema20) / price
    volatility = atr / price

    score = 50
    score += trend * 15
    score += momentum * 20
    score -= volatility * 10

    return np.clip(score, 0, 100)

# =========================
# POSITION SIZING (DYNAMIC RISK)
# =========================
def size(capital, price, sl, regime_state):

    risk = abs(price - sl)
    if risk == 0:
        return 0

    risk_multiplier = {
        "BULL": 1.0,
        "BEAR": 0.5,
        "SIDEWAYS": 0.7
    }[regime_state]

    return (capital * BASE_RISK * risk_multiplier) / risk

# =========================
# PORTFOLIO ENGINE
# =========================
def portfolio(data):

    capital = START_CAPITAL
    equity = []

    trades = 0
    wins = 0

    min_len = min([len(df) for df in data.values()]) if len(data) > 0 else 0

    for i in range(50, min_len - 1):

        step_pnl = 0

        for ticker, df in data.items():

            reg = regime(df)

            direction, price, sl, tp, lp, sp, conf = signal(df, i)

            if direction == "NO TRADE":
                continue

            next_price = df["Close"].iloc[i+1]

            s = size(capital, price, sl, reg)

            pnl = 0

            if direction == "LONG":
                pnl = (next_price - price) * s
            else:
                pnl = (price - next_price) * s

            ai = ai_score(df, i)

            pnl *= (0.6 + ai / 100)

            step_pnl += pnl

            trades += 1
            if pnl > 0:
                wins += 1

        capital += step_pnl
        equity.append(capital)

    winrate = (wins / trades * 100) if trades > 0 else 0

    return equity, capital, trades, winrate

# =========================
# CHART
# =========================
def chart(df):

    fig = go.Figure()

    fig.add_trace(go.Scatter(y=df["Close"], name="Preis"))
    fig.add_trace(go.Scatter(y=df["EMA20"], name="EMA20"))
    fig.add_trace(go.Scatter(y=df["EMA50"], name="EMA50"))
    fig.add_trace(go.Scatter(y=df["EMA200"], name="EMA200"))

    fig.update_layout(height=400)

    return fig

# =========================
# UI
# =========================
st.title("🧠🏦 Version 16 – Institutionelle KI Trading Plattform")

inp = st.text_input("Tickers (kommagetrennt)")

watch = [x.strip().upper() for x in inp.split(",")] if inp else WATCHLIST

if st.button("Analyse starten"):

    data = {}

    for t in watch:

        df = load_data(t, "1h", "180d")

        if df is None:
            continue

        df = indicators(df)

        data[t] = df

    equity, capital, trades, winrate = portfolio(data)

    st.subheader("📊 Portfolio Ergebnis")
    st.write({
        "Endkapital": round(capital,2),
        "Trades": trades,
        "Winrate %": round(winrate,2)
    })

    st.subheader("📈 Equity Curve")
    st.line_chart(equity)

    st.subheader("📉 Einzelanalyse")

    for t, df in data.items():

        direction, price, sl, tp, lp, sp, conf = signal(df, len(df)-1)

        emoji = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚪"

        st.write(f"{emoji} {t} → {direction} | Confidence {round(conf*100,1)}%")

        st.plotly_chart(chart(df), use_container_width=True)
