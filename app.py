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

ACCOUNT = 10000
RISK_PER_TRADE = 0.01

# =========================
# SAFE DATA LOADER (HARD FIX)
# =========================
def load_data(ticker):
    try:
        df = yf.download(ticker, period="120d", interval="1h", progress=False)

        if df is None or df.empty:
            return None

        # flatten multiindex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        df = df.copy()
        df = df.dropna()

        # ensure numeric safety
        for col in ["Open","High","Low","Close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.dropna()

    except:
        return None


# =========================
# INDICATORS (FULL SAFE)
# =========================
def indicators(df):
    df = df.copy()

    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)

    # EMA
    df["EMA20"] = close.ewm(span=20).mean()
    df["EMA50"] = close.ewm(span=50).mean()
    df["EMA200"] = close.ewm(span=200).mean()

    # ATR (TRUE RANGE)
    tr = np.maximum(
        high - low,
        np.maximum(
            abs(high - close.shift()),
            abs(low - close.shift())
        )
    )

    df["ATR"] = pd.Series(tr).rolling(14).mean()

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
# POSITION SIZING
# =========================
def position_size(entry, sl):
    risk = abs(entry - sl)
    if risk == 0:
        return 0
    return (ACCOUNT * RISK_PER_TRADE) / risk


# =========================
# SIGNAL ENGINE (FINAL FIXED)
# =========================
def analyze(df):

    if df is None or df.empty:
        return None

    l = df.iloc[-1]

    # SAFE EXTRACTION
    price = float(l["Close"])
    ema20 = float(l["EMA20"])
    ema50 = float(l["EMA50"])
    atr = float(l["ATR"])

    reg = regime(df)

    long_score = 50
    short_score = 50

    # =========================
    # BREAKOUT
    # =========================
    high20 = df["Close"].rolling(20).max().iloc[-1]
    low20 = df["Close"].rolling(20).min().iloc[-1]

    if price > high20 * 0.999:
        long_score += 30

    if price < low20 * 1.001:
        short_score += 30

    # =========================
    # TREND / PULLBACK
    # =========================
    if abs(price - ema20) < atr * 0.6:
        long_score += 10
        short_score += 10

    if price > ema50:
        long_score += 10
    else:
        short_score += 10

    # =========================
    # REGIME BIAS
    # =========================
    if reg == "UP":
        long_score += 10
    elif reg == "DOWN":
        short_score += 10

    # =========================
    # PROBABILITY
    # =========================
    total = long_score + short_score
    long_p = long_score / total
    short_p = short_score / total

    # =========================
    # DIRECTION
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

    # =========================
    # RISK ENGINE
    # =========================
    if direction == "LONG":
        sl = price - atr * 1.5
        tp = price + atr * 2.5
    else:
        sl = price + atr * 1.5
        tp = price - atr * 2.5

    rr = abs(tp - price) / abs(price - sl) if price != sl else 0

    size = position_size(price, sl)

    return {
        "price": price,
        "direction": direction,
        "confidence": conf,
        "long_p": long_p,
        "short_p": short_p,
        "regime": reg,
        "sl": sl,
        "tp": tp,
        "rr": rr,
        "size": size,
        "df": df
    }


# =========================
# CHART
# =========================
def plot(df):

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="Price"
    ))

    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["EMA20"],
        name="EMA20"
    ))

    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["EMA50"],
        name="EMA50"
    ))

    fig.update_layout(height=500)

    return fig


# =========================
# UI
# =========================
st.title("🏦 Hedge Fund Quant System v11 (FULL FIXED)")

custom = st.text_input("Tickers (comma separated)")

watchlist = [x.strip().upper() for x in custom.split(",")] if custom else WATCHLIST

if st.button("Scan starten"):

    results = []

    for ticker in watchlist:

        df = load_data(ticker)
        if df is None:
            continue

        df = indicators(df)
        res = analyze(df)

        if res is None:
            continue

        emoji = "🟢" if res["direction"] == "LONG" else "🔴" if res["direction"] == "SHORT" else "⚪"

        results.append({
            "Ticker": f"{emoji} {ticker}",
            "Direction": res["direction"],
            "Confidence %": round(res["confidence"] * 100, 1),
            "Long %": round(res["long_p"] * 100, 1),
            "Short %": round(res["short_p"] * 100, 1),
            "Regime": res["regime"],
            "Price": round(res["price"],2),
            "SL": round(res["sl"],2),
            "TP": round(res["tp"],2),
            "RR": round(res["rr"],2),
            "Size": round(res["size"],2)
        })

    df_out = pd.DataFrame(results).sort_values("Confidence %", ascending=False)

    st.dataframe(df_out, use_container_width=True)

    # =========================
    # TOP CHART
    # =========================
    if len(results) > 0:
        top = results[0]["Ticker"].replace("🟢 ","").replace("🔴 ","").replace("⚪ ","")

        df = load_data(top)
        df = indicators(df)

        st.subheader("📊 Top Setup Chart")
        st.plotly_chart(plot(df), use_container_width=True)
