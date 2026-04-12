import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")

# =========================
# KONFIG
# =========================
WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA",
    "SAP.DE","ADS.DE","ALV.DE",
    "MC.PA","OR.PA","HSBA.L","BP.L",
    "^GSPC","^NDX"
]

KONTO_START = 10000
RISIKO = 0.01

# =========================
# DATEN
# =========================
def lade_daten(ticker):
    try:
        df = yf.download(ticker, period="180d", interval="1h", progress=False)

        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        df = df.copy()

        for c in ["Open","High","Low","Close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        return df.dropna()

    except:
        return None

# =========================
# INDICATORS
# =========================
def indikatoren(df):
    df = df.copy()

    close = df["Close"]

    df["EMA20"] = close.ewm(span=20).mean()
    df["EMA50"] = close.ewm(span=50).mean()

    high = df["High"]
    low = df["Low"]

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
# SIGNAL ENGINE (VERSION 11)
# =========================
def analyse(df):

    l = df.iloc[-1]

    preis = float(l["Close"])
    ema20 = float(l["EMA20"])
    ema50 = float(l["EMA50"])
    atr = float(l["ATR"])

    long_score = 50
    short_score = 50

    # Trend
    if preis > ema50:
        long_score += 10
    else:
        short_score += 10

    # Pullback
    if abs(preis - ema20) < atr * 0.6:
        long_score += 10
        short_score += 10

    # Breakout
    high20 = df["Close"].rolling(20).max().iloc[-1]
    low20 = df["Close"].rolling(20).min().iloc[-1]

    if preis > high20:
        long_score += 25

    if preis < low20:
        short_score += 25

    total = long_score + short_score
    long_p = long_score / total
    short_p = short_score / total

    if long_p > 0.60:
        richtung = "LONG"
        conf = long_p
    elif short_p > 0.60:
        richtung = "SHORT"
        conf = short_p
    else:
        richtung = "NO TRADE"
        conf = 0.5

    if richtung == "LONG":
        sl = preis - atr * 1.5
        tp = preis + atr * 2.5
    elif richtung == "SHORT":
        sl = preis + atr * 1.5
        tp = preis - atr * 2.5
    else:
        sl = tp = preis

    rr = abs(tp - preis) / abs(preis - sl) if preis != sl else 0

    return {
        "preis": preis,
        "richtung": richtung,
        "confidence": conf,
        "long_p": long_p,
        "short_p": short_p,
        "sl": sl,
        "tp": tp,
        "rr": rr,
        "df": df
    }

# =========================
# POSITION SIZE
# =========================
def position_size(entry, sl):
    risiko = abs(entry - sl)
    if risiko == 0:
        return 0
    return (KONTO_START * RISIKO) / risiko

# =========================
# BACKTEST ENGINE
# =========================
def backtest(df):

    konto = KONTO_START
    equity = []

    trades = 0
    wins = 0

    for i in range(50, len(df)-1):

        l = df.iloc[i]

        preis = float(l["Close"])
        ema20 = float(l["EMA20"])
        ema50 = float(l["EMA50"])
        atr = float(l["ATR"])

        long_score = 50
        short_score = 50

        if preis > ema50:
            long_score += 10
        else:
            short_score += 10

        if abs(preis - ema20) < atr * 0.6:
            long_score += 10
            short_score += 10

        high20 = df["Close"].iloc[i-20:i].max()
        low20 = df["Close"].iloc[i-20:i].min()

        if preis > high20:
            long_score += 25
        if preis < low20:
            short_score += 25

        total = long_score + short_score
        long_p = long_score / total
        short_p = short_score / total

        if long_p > 0.60:
            direction = "LONG"
        elif short_p > 0.60:
            direction = "SHORT"
        else:
            equity.append(konto)
            continue

        if direction == "LONG":
            sl = preis - atr * 1.5
            next_price = df["Close"].iloc[i+1]
            pnl = (next_price - preis)
        else:
            sl = preis + atr * 1.5
            next_price = df["Close"].iloc[i+1]
            pnl = (preis - next_price)

        size = position_size(preis, sl)

        pnl = pnl * size

        konto += pnl

        if pnl > 0:
            wins += 1

        trades += 1
        equity.append(konto)

    winrate = (wins / trades * 100) if trades > 0 else 0

    return equity, konto, trades, winrate

# =========================
# CHART
# =========================
def chart(df):

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="Preis"
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
st.title("🏦 Quant Hedgefonds System v11 + Backtest")

eingabe = st.text_input("Tickers (kommagetrennt)")

watchlist = [x.strip().upper() for x in eingabe.split(",")] if eingabe else WATCHLIST

if st.button("Analyse starten"):

    ergebnisse = []

    for ticker in watchlist:

        df = lade_daten(ticker)
        if df is None:
            continue

        df = indikatoren(df)
        res = analyse(df)

        emoji = "🟢" if res["richtung"] == "LONG" else "🔴" if res["richtung"] == "SHORT" else "⚪"

        ergebnisse.append({
            "Ticker": f"{emoji} {ticker}",
            "Richtung": res["richtung"],
            "Konfidenz %": round(res["confidence"] * 100, 1),
            "Long %": round(res["long_p"] * 100, 1),
            "Short %": round(res["short_p"] * 100, 1),
            "Preis": round(res["preis"],2),
            "SL": round(res["sl"],2),
            "TP": round(res["tp"],2),
            "RR": round(res["rr"],2)
        })

    df_out = pd.DataFrame(ergebnisse).sort_values("Konfidenz %", ascending=False)

    st.subheader("📊 Hauptanalyse (Quant Signal Engine)")
    st.dataframe(df_out, use_container_width=True)

    # =========================
    # TOP CHART + BACKTEST
    # =========================
    if len(ergebnisse) > 0:

        top_ticker = ergebnisse[0]["Ticker"].replace("🟢 ","").replace("🔴 ","").replace("⚪ ","")

        df = lade_daten(top_ticker)
        df = indikatoren(df)

        st.subheader("📈 Chart (Top Setup)")
        st.plotly_chart(chart(df), use_container_width=True)

        st.subheader("📉 Backtest (Historische Simulation)")

        equity, endkapital, trades, winrate = backtest(df)

        st.write({
            "Endkapital": round(endkapital,2),
            "Anzahl Trades": trades,
            "Gewinnrate %": round(winrate,2)
        })

        st.line_chart(equity)
