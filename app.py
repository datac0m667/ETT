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

START_CAPITAL = 10000
BASE_RISK = 0.01

# =========================
# LOAD DATA
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

    entry = price

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

    rr = abs(tp2 - entry) / abs(entry - sl) if sl != entry else 0

    return direction, entry, sl, tp1, tp2, rr, conf

# =========================
# REINFORCEMENT LEARNING LAYER
# =========================
class RLAgent:

    def __init__(self):
        self.weight = 1.0

    def update(self, reward):

        lr = 0.05

        self.weight += lr * reward

        self.weight = np.clip(self.weight, 0.3, 2.0)

agent = RLAgent()

# =========================
# POSITION SIZE
# =========================
def size(capital, entry, sl):

    risk = abs(entry - sl)

    if risk == 0:
        return 0

    return (capital * BASE_RISK) / risk

# =========================
# BACKTEST (RL CONTROLLED)
# =========================
def backtest(data):

    capital = START_CAPITAL
    equity = []

    trades = 0
    wins = 0

    for i in range(50, min([len(df) for df in data.values()]) - 1):

        step_pnl = 0

        for ticker, df in data.items():

            direction, entry, sl, tp1, tp2, rr, conf = signal(df, i)

            if direction == "NO TRADE":
                continue

            next_price = df["Close"].iloc[i + 1]

            s = size(capital, entry, sl)

            if direction == "LONG":
                pnl = (next_price - entry) * s
            else:
                pnl = (entry - next_price) * s

            # =========================
            # REWARD ENGINE (RL CORE)
            # =========================
            reward = np.tanh(pnl)

            agent.update(reward)

            pnl *= agent.weight

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
st.title("🧠🏦 Version 17 – Hedgefonds Reinforcement AI")

inp = st.text_input("Tickers")

watch = [x.strip().upper() for x in inp.split(",")] if inp else WATCHLIST

if st.button("Analyse starten"):

    data = {}

    for t in watch:

        df = load(t)

        if df is None:
            continue

        df = indicators(df)

        data[t] = df

    equity, capital, trades, winrate = backtest(data)

    st.subheader("📊 Portfolio Ergebnis")

    st.write({
        "Endkapital": round(capital, 2),
        "Trades": trades,
        "Winrate %": round(winrate, 2),
        "RL Gewicht": round(agent.weight, 2)
    })

    st.subheader("📈 Equity Curve")

    st.line_chart(equity)

    st.subheader("📉 Einzel Signale (V11 behalten)")

    for t, df in data.items():

        d, entry, sl, tp1, tp2, rr, conf = signal(df, len(df)-1)

        emoji = "🟢" if d == "LONG" else "🔴" if d == "SHORT" else "⚪"

        st.write(
            f"{emoji} {t} → {d} | Entry {round(entry,2)} | SL {round(sl,2)} | "
            f"TP1 {round(tp1,2)} | TP2 {round(tp2,2)} | RR {round(rr,2)}"
        )

        st.plotly_chart(chart(df), use_container_width=True)
