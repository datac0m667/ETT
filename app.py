import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from sklearn.linear_model import LogisticRegression

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
RISIKO = 0.01

# =========================
# DATA
# =========================
def load(ticker):
    try:
        df = yf.download(ticker, period="2y", interval="1d", progress=False)

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
# FEATURES (ML INPUT)
# =========================
def features(df):
    df = df.copy()

    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()

    df["RET"] = df["Close"].pct_change()

    df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

    df = df.dropna()

    return df

# =========================
# V11 SIGNAL ENGINE (UNCHANGED LOGIC)
# =========================
def v11_signal(df, i):

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

    high20 = df["Close"].iloc[max(0, i-20):i].max()
    low20 = df["Close"].iloc[max(0, i-20):i].min()

    if price > high20:
        long_score += 25
    if price < low20:
        short_score += 25

    total = long_score + short_score

    long_p = long_score / total
    short_p = short_score / total

    if long_p > 0.60:
        direction = "LONG"
    elif short_p > 0.60:
        direction = "SHORT"
    else:
        direction = "NO TRADE"

    return direction, long_p, short_p

# =========================
# ML TRAINING MODEL
# =========================
def train_ml(df):

    df = df.copy()

    df["target"] = np.where(df["Close"].shift(-1) > df["Close"], 1, 0)

    X = df[["EMA20","EMA50","RET","ATR"]]
    y = df["target"]

    model = LogisticRegression()

    model.fit(X[:-1], y[:-1])

    return model

# =========================
# ML PREDICTION
# =========================
def ml_signal(model, row):

    X = np.array([[row["EMA20"], row["EMA50"], row["RET"], row["ATR"]]])

    p_up = model.predict_proba(X)[0][1]

    if p_up > 0.55:
        return "LONG", p_up
    elif p_up < 0.45:
        return "SHORT", 1 - p_up
    else:
        return "NO TRADE", 0.5

# =========================
# PORTFOLIO BACKTEST
# =========================
def backtest(df, model):

    capital = STARTKAPITAL
    equity = []

    trades = 0
    wins = 0

    for i in range(50, len(df)-1):

        row = df.iloc[i]

        v11_dir, lp, sp = v11_signal(df, i)
        ml_dir, ml_conf = ml_signal(model, row)

        # HYBRID DECISION
        if v11_dir == ml_dir:
            direction = v11_dir
        else:
            direction = "NO TRADE"

        price = float(row["Close"])
        next_price = float(df["Close"].iloc[i+1])

        if direction == "NO TRADE":
            equity.append(capital)
            continue

        if direction == "LONG":
            pnl = next_price - price
        else:
            pnl = price - next_price

        capital += pnl

        trades += 1
        if pnl > 0:
            wins += 1

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
st.title("🧠🏦 Version 15 – Hedgefonds KI (ML Layer)")

input_t = st.text_input("Tickers (kommagetrennt)")

watch = [x.strip().upper() for x in input_t.split(",")] if input_t else WATCHLIST

if st.button("Start Analyse"):

    data = {}

    for t in watch:

        df = load(t)
        if df is None:
            continue

        df = features(df)
        data[t] = df

    results = []

    for t, df in data.items():

        model = train_ml(df)

        equity, capital, trades, winrate = backtest(df, model)

        results.append({
            "Ticker": t,
            "Endkapital": round(capital,2),
            "Trades": trades,
            "Winrate %": round(winrate,2)
        })

        st.subheader(f"📊 {t}")
        st.plotly_chart(chart(df), use_container_width=True)

        st.line_chart(equity)

    st.subheader("📋 Portfolio Ergebnis")
    st.dataframe(pd.DataFrame(results).sort_values("Endkapital", ascending=False))
