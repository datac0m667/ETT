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
BASIS_RISIKO = 0.01

# =========================
# DATEN
# =========================
def lade(ticker):
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
# SIGNAL ENGINE (CORE)
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

    if long_p > 0.6:
        direction = "LONG"
    elif short_p > 0.6:
        direction = "SHORT"
    else:
        direction = "NO TRADE"

    if direction == "LONG":
        sl = price - atr * 1.5
        tp = price + atr * 2.5
    elif direction == "SHORT":
        sl = price + atr * 1.5
        tp = price - atr * 2.5
    else:
        sl = tp = price

    return direction, price, sl, tp, long_p, short_p

# =========================
# POSITION SIZE (RISK PARITY)
# =========================
def size(account, price, sl):
    risk = abs(price - sl)
    if risk == 0:
        return 0
    return (account * BASIS_RISIKO) / risk

# =========================
# PORTFOLIO BACKTEST
# =========================
def portfolio_backtest(data_dict):

    capital = STARTKAPITAL
    equity = []

    trades = 0
    wins = 0

    for step in range(50, 120):

        step_pnl = 0

        for ticker, df in data_dict.items():

            if step >= len(df):
                continue

            direction, price, sl, tp, lp, sp = signal(df, step)

            if direction == "NO TRADE":
                continue

            next_price = df["Close"].iloc[step+1]

            trade_size = size(capital, price, sl)

            if direction == "LONG":
                pnl = (next_price - price) * trade_size
            else:
                pnl = (price - next_price) * trade_size

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
st.title("🏦 Institutionelles Portfolio System v13")

inputs = st.text_input("Tickers (kommagetrennt)")

watch = [x.strip().upper() for x in inputs.split(",")] if inputs else WATCHLIST

if st.button("Portfolio Analyse starten"):

    data = {}

    for t in watch:
        df = lade(t)
        if df is None:
            continue
        df = indicators(df)
        data[t] = df

    equity, capital, trades, winrate = portfolio_backtest(data)

    st.subheader("📊 Portfolio Ergebnis")
    st.write({
        "Endkapital": round(capital,2),
        "Trades": trades,
        "Gewinnrate %": round(winrate,2)
    })

    st.subheader("📈 Portfolio Equity Curve")
    st.line_chart(equity)

    st.subheader("📉 Einzelcharts")

    for t, df in data.items():
        st.write(f"📌 {t}")
        st.plotly_chart(chart(df), use_container_width=True)
