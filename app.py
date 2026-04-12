import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")

WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA",
    "SAP.DE","ADS.DE","ALV.DE",
    "MC.PA","OR.PA","HSBA.L","BP.L",
    "^GSPC","^NDX"
]

ACCOUNT_SIZE = 10000
RISK = 0.01

# =========================
# DATA
# =========================
def load_data(ticker):
    try:
        df = yf.download(ticker, period="120d", interval="1h", progress=False)

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
    close = df["Close"]

    df["EMA20"] = close.ewm(span=20).mean()
    df["EMA50"] = close.ewm(span=50).mean()
    df["EMA200"] = close.ewm(span=200).mean()

    df["TR"] = np.maximum(
        df["High"] - df["Low"],
        np.maximum(
            abs(df["High"] - df["Close"].shift()),
            abs(df["Low"] - df["Close"].shift())
        )
    )
    df["ATR"] = df["TR"].rolling(14).mean()

    return df.dropna()

# =========================
# MARKET REGIME
# =========================
def regime(df):
    ema50 = df["EMA50"].iloc[-1]
    ema200 = df["EMA200"].iloc[-1]
    price = df["Close"].iloc[-1]

    strength = abs(ema50 - ema200) / price

    if ema50 > ema200 and strength > 0.02:
        return "UP"
    elif ema50 < ema200 and strength > 0.02:
        return "DOWN"
    else:
        return "RANGE"

# =========================
# SIGNAL ENGINE (PROBABILITY MODEL)
# =========================
def analyze(df):

    l = df.iloc[-1]

    price = float(l["Close"])
    ema20 = float(l["EMA20"])
    ema50 = float(l["EMA50"])
    atr = float(l["ATR"])

    reg = regime(df)

    # =========================
    # SIGNAL LOGIC
    # =========================
    long_score = 50
    short_score = 50

    # trend bias
    if price > ema50:
        long_score += 15
    else:
        short_score += 15

    # pullback logic
    if abs(price - ema20) < atr * 0.5:
        long_score += 10
        short_score += 10

    # breakout logic
    high20 = df["Close"].rolling(20).max().iloc[-1]
    low20 = df["Close"].rolling(20).min().iloc[-1]

    if price > high20 * 0.999:
        long_score += 25

    if price < low20 * 1.001:
        short_score += 25

    # regime filter
    if reg == "UP":
        long_score += 10
    elif reg == "DOWN":
        short_score += 10

    # =========================
    # PROBABILITY CONVERSION
    # =========================
    total = long_score + short_score

    long_prob = long_score / total
    short_prob = short_score / total

    # =========================
    # FINAL SIGNAL
    # =========================
    if long_prob > 0.60:
        direction = "LONG"
        color = "green"
        confidence = long_prob
    elif short_prob > 0.60:
        direction = "SHORT"
        color = "red"
        confidence = short_prob
    else:
        direction = "NO TRADE"
        color = "gray"
        confidence = 0.5

    # =========================
    # RISK MODEL
    # =========================
    sl = price - atr * 1.5 if direction == "LONG" else price + atr * 1.5
    tp = price + atr * 2.5 if direction == "LONG" else price - atr * 2.5

    risk = abs(price - sl)
    size = (ACCOUNT_SIZE * RISK) / risk if risk != 0 else 0

    rr = abs(tp - price) / risk if risk != 0 else 0

    return {
        "price": price,
        "direction": direction,
        "confidence": confidence,
        "long_prob": long_prob,
        "short_prob": short_prob,
        "sl": sl,
        "tp": tp,
        "rr": rr,
        "size": size,
        "ema20": ema20,
        "ema50": ema50,
        "df": df
    }

# =========================
# CHART
# =========================
def plot_chart(data, ema20, ema50, direction):

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data["Open"],
        high=data["High"],
        low=data["Low"],
        close=data["Close"],
        name="Price"
    ))

    fig.add_trace(go.Scatter(
        x=data.index,
        y=data["EMA20"],
        name="EMA20"
    ))

    fig.add_trace(go.Scatter(
        x=data.index,
        y=data["EMA50"],
        name="EMA50"
    ))

    fig.update_layout(height=500)

    return fig

# =========================
# UI
# =========================
st.title("🏦 Quant Hedge Fund v10 – Probability Engine")

custom = st.text_input("Tickers")

watchlist = [x.strip().upper() for x in custom.split(",")] if custom else WATCHLIST

if st.button("Scan starten"):

    results = []

    for ticker in watchlist:

        df = load_data(ticker)
        if df is None:
            continue

        df = indicators(df)

        res = analyze(df)

        emoji = "🟢" if res["direction"] == "LONG" else "🔴" if res["direction"] == "SHORT" else "⚪"

        results.append({
            "Ticker": f"{emoji} {ticker}",
            "Direction": res["direction"],
            "Confidence %": round(res["confidence"] * 100, 1),
            "Long Prob %": round(res["long_prob"] * 100, 1),
            "Short Prob %": round(res["short_prob"] * 100, 1),
            "Price": round(res["price"],2),
            "SL": round(res["sl"],2),
            "TP": round(res["tp"],2),
            "RR": round(res["rr"],2),
            "Size": round(res["size"],2)
        })

    df_out = pd.DataFrame(results).sort_values("Confidence %", ascending=False)

    st.dataframe(df_out, use_container_width=True)

    # =========================
    # DETAIL CHART (TOP TRADE)
    # =========================
    if len(results) > 0:
        top = results[0]

        st.subheader("📊 Top Setup Chart")

        df = load_data(top["Ticker"].replace("🟢 ","").replace("🔴 ",""))
        df = indicators(df)

        chart = plot_chart(df, df["EMA20"], df["EMA50"], top["Direction"])

        st.plotly_chart(chart, use_container_width=True)
