import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")

# =========================
# KONFIGURATION
# =========================
WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA",
    "SAP.DE","ADS.DE","ALV.DE",
    "MC.PA","OR.PA","HSBA.L","BP.L",
    "^GSPC","^NDX"
]

KONTOSTAND_START = 10000
RISIKO_PRO_TRADE = 0.01

# =========================
# DATENLADUNG
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
# SIGNAL ENGINE
# =========================
def signal(df, i):

    l = df.iloc[i]

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
    high20 = df["Close"].iloc[max(0, i-20):i].max()
    low20 = df["Close"].iloc[max(0, i-20):i].min()

    if preis > high20:
        long_score += 20

    if preis < low20:
        short_score += 20

    total = long_score + short_score
    long_p = long_score / total
    short_p = short_score / total

    if long_p > 0.60:
        richtung = "LONG"
    elif short_p > 0.60:
        richtung = "SHORT"
    else:
        richtung = "NO TRADE"

    if richtung == "LONG":
        sl = preis - atr * 1.5
        tp = preis + atr * 2.5
    elif richtung == "SHORT":
        sl = preis + atr * 1.5
        tp = preis - atr * 2.5
    else:
        sl, tp = preis, preis

    return richtung, preis, sl, tp

# =========================
# POSITIONSSIZE
# =========================
def positionsgröße(konto, preis, sl):
    risiko = abs(preis - sl)
    if risiko == 0:
        return 0
    return (konto * RISIKO_PRO_TRADE) / risiko

# =========================
# BACKTEST
# =========================
def backtest(df):

    konto = KONTOSTAND_START
    equity = []

    trades = 0
    wins = 0

    for i in range(50, len(df)-1):

        richtung, preis, sl, tp = signal(df, i)

        if richtung == "NO TRADE":
            equity.append(konto)
            continue

        size = positionsgröße(konto, preis, sl)

        next_price = df["Close"].iloc[i+1]

        trades += 1

        if richtung == "LONG":
            if next_price > preis:
                pnl = (next_price - preis) * size
            else:
                pnl = (next_price - preis) * size

        elif richtung == "SHORT":
            if next_price < preis:
                pnl = (preis - next_price) * size
            else:
                pnl = (preis - next_price) * size

        else:
            pnl = 0

        konto += pnl

        if pnl > 0:
            wins += 1

        equity.append(konto)

    return equity, konto, trades, wins

# =========================
# EQUITY CHART
# =========================
def equity_chart(equity):

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        y=equity,
        mode="lines",
        name="Kontoverlauf"
    ))

    fig.update_layout(height=400, title="📈 Equity Kurve")

    return fig

# =========================
# UI
# =========================
st.title("🏦 Quant Hedgefonds System v12 – Backtest & Equity")

eingabe = st.text_input("Tickers (kommagetrennt)")

watchlist = [x.strip().upper() for x in eingabe.split(",")] if eingabe else WATCHLIST

if st.button("Backtest starten"):

    ergebnisse = []

    for ticker in watchlist:

        df = lade_daten(ticker)
        if df is None:
            continue

        df = indikatoren(df)

        equity, endkapital, trades, wins = backtest(df)

        winrate = wins / trades * 100 if trades > 0 else 0

        ergebnisse.append({
            "Aktie": ticker,
            "Endkapital": round(endkapital,2),
            "Trades": trades,
            "Gewinnrate %": round(winrate,2)
        })

        st.subheader(f"📊 Equity Kurve: {ticker}")
        st.plotly_chart(equity_chart(equity), use_container_width=True)

    st.subheader("📋 Ergebnis Übersicht")
    st.dataframe(pd.DataFrame(ergebnisse).sort_values("Endkapital", ascending=False), use_container_width=True)
