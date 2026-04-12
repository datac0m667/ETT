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
RISIKO = 0.01

# =========================
# SAFE DATA LOADER
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

        df = df.dropna()

        if len(df) < 100:
            return None

        return df

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

    df = df.dropna()

    return df

# =========================
# V11 SIGNAL ENGINE (STABLE CORE)
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
# POSITION SIZING
# =========================
def position_size(account, price, sl):
    risk = abs(price - sl)
    if risk == 0:
        return 0
    return (account * RISIKO) / risk

# =========================
# PORTFOLIO BACKTEST (SAFE)
# =========================
def portfolio_backtest(data):

    capital = STARTKAPITAL
    equity = []

    trades = 0
    wins = 0

    if len(data) == 0:
        return [STARTKAPITAL], STARTKAPITAL, 0, 0

    max_len = min([len(df) for df in data.values()])

    for i in range(50, max_len - 1):

        step_pnl = 0

        for ticker, df in data.items():

            if i >= len(df):
                continue

            direction, price, sl, tp, lp, sp, conf = signal(df, i)

            if direction == "NO TRADE":
                continue

            next_price = df["Close"].iloc[i + 1]

            size = position_size(capital, price, sl)

            if direction == "LONG":
                pnl = (next_price - price) * size
            else:
                pnl = (price - next_price) * size

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
st.title("🧠🏦 Hedgefonds KI System v15 – FIXED STABLE")

input_t = st.text_input("Tickers (kommagetrennt)")

watch = [x.strip().upper() for x in input_t.split(",")] if input_t else WATCHLIST

if st.button("Analyse starten"):

    data = {}
    results = []

    # =========================
    # LOAD DATA SAFE
    # =========================
    for t in watch:

        df = load_data(t)

        if df is None:
            continue

        df = indicators(df)

        if df is None or len(df) < 100:
            continue

        data[t] = df

    # =========================
    # BACKTEST SAFE
    # =========================
    equity, capital, trades, winrate = portfolio_backtest(data)

    # =========================
    # OUTPUT SAFE TABLE
    # =========================
    for t, df in data.items():

        direction, price, sl, tp, lp, sp, conf = signal(df, len(df) - 1)

        emoji = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚪"

        results.append({
            "Ticker": t,
            "Signal": direction,
            "Konfidenz %": round(conf * 100, 1),
            "Preis": round(price, 2),
            "SL": round(sl, 2),
            "TP": round(tp, 2)
        })

        st.subheader(f"{emoji} {t} → {direction}")
        st.plotly_chart(chart(df), use_container_width=True)

    # =========================
    # SAFE TABLE OUTPUT (NO KEYERROR EVER)
    # =========================
    if len(results) > 0:

        df_res = pd.DataFrame(results)

        st.subheader("📊 Signaltabelle")

        st.dataframe(df_res, use_container_width=True)

    else:
        st.warning("Keine gültigen Signale gefunden.")

    # =========================
    # EQUITY
    # =========================
    st.subheader("📈 Portfolio Equity")

    st.write({
        "Endkapital": round(capital, 2),
        "Trades": trades,
        "Gewinnrate %": round(winrate, 2)
    })

    st.line_chart(equity)
