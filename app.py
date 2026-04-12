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

STARTKAPITAL = 10000
RISIKO_BASIS = 0.01

# =========================
# DATEN
# =========================
def load_data(ticker):
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

    close = df["Close"]

    df["EMA20"] = close.ewm(span=20).mean()
    df["EMA50"] = close.ewm(span=50).mean()

    tr = np.maximum(
        df["High"] - df["Low"],
        np.maximum(
            abs(df["High"] - close.shift()),
            abs(df["Low"] - close.shift())
        )
    )

    df["ATR"] = pd.Series(tr).rolling(14).mean()

    return df.dropna()

# =========================
# VERSION 11 SIGNAL ENGINE (UNCHANGED CORE)
# =========================
def signal(df, i):

    l = df.iloc[i]

    price = float(l["Close"])
    ema20 = float(l["EMA20"])
    ema50 = float(l["EMA50"])
    atr = float(l["ATR"])

    long_score = 50
    short_score = 50

    # Trend
    if price > ema50:
        long_score += 10
    else:
        short_score += 10

    # Pullback
    if abs(price - ema20) < atr * 0.6:
        long_score += 10
        short_score += 10

    # Breakout
    high20 = df["Close"].iloc[max(0, i-20):i].max()
    low20 = df["Close"].iloc[max(0, i-20):i].min()

    if price > high20:
        long_score += 25
    if price < low20:
        short_score += 25

    total = long_score + short_score
    long_p = long_score / total
    short_p = short_score / total

    # =========================
    # V11 SIGNAL (MUST STAY)
    # =========================
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
# "AI LAYER" (NEW IN V14)
# =========================
def ai_score(long_p, short_p, ema20, ema50, price):

    trend_bias = 1 if price > ema50 else -1
    pullback_factor = abs(price - ema20) / price

    score = (
        long_p * 100 if trend_bias == 1 else short_p * 100
    )

    score += max(0, (1 - pullback_factor) * 20)

    return min(100, max(0, score))

# =========================
# POSITION SIZE
# =========================
def size(account, price, sl, drawdown_factor):

    risk = abs(price - sl)
    if risk == 0:
        return 0

    adjusted_risk = account * RISIKO_BASIS * drawdown_factor

    return adjusted_risk / risk

# =========================
# PORTFOLIO BACKTEST
# =========================
def portfolio(data):

    capital = STARTKAPITAL
    equity = []

    trades = 0
    wins = 0

    drawdown_factor = 1.0

    for i in range(50, 120):

        step_pnl = 0

        for ticker, df in data.items():

            if i >= len(df):
                continue

            direction, price, sl, tp, lp, sp, conf = signal(df, i)

            if direction == "NO TRADE":
                continue

            next_price = df["Close"].iloc[i+1]

            # AI SCORE (NEW)
            ema20 = df["EMA20"].iloc[i]
            ema50 = df["EMA50"].iloc[i]

            ai = ai_score(lp, sp, ema20, ema50, price)

            # dynamic risk scaling
            drawdown_factor = max(0.5, min(1.0, capital / STARTKAPITAL))

            trade_size = size(capital, price, sl, drawdown_factor)

            if direction == "LONG":
                pnl = (next_price - price) * trade_size
            else:
                pnl = (price - next_price) * trade_size

            # AI filter impact
            pnl *= (0.5 + ai / 100)

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

    fig.update_layout(height=400)

    return fig

# =========================
# UI
# =========================
st.title("🧠🏦 Hedgefonds KI System v14")

inputs = st.text_input("Tickers (kommagetrennt)")

watch = [x.strip().upper() for x in inputs.split(",")] if inputs else WATCHLIST

if st.button("Analyse starten"):

    data = {}

    results = []

    for t in watch:

        df = load_data(t)
        if df is None:
            continue

        df = indicators(df)
        data[t] = df

    equity, capital, trades, winrate = portfolio(data)

    # =========================
    # SUMMARY
    # =========================
    st.subheader("📊 Portfolio Ergebnis")
    st.write({
        "Endkapital": round(capital,2),
        "Trades": trades,
        "Gewinnrate %": round(winrate,2)
    })

    st.subheader("📈 Equity Kurve")
    st.line_chart(equity)

    # =========================
    # INDIVIDUAL SIGNAL VIEW (V11 preserved)
    # =========================
    st.subheader("📡 Einzelanalyse (LONG / SHORT Signale bleiben erhalten)")

    for t, df in data.items():

        direction, price, sl, tp, lp, sp, conf = signal(df, len(df)-1)

        emoji = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚪"

        st.write(f"{emoji} {t} → {direction} | Konfidenz: {round(conf*100,1)}%")

        st.plotly_chart(chart(df), use_container_width=True)
