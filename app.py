import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")

# =========================
# CONFIG (HEDGE FUND STYLE)
# =========================
WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA",
    "SAP.DE","ADS.DE","ALV.DE",
    "MC.PA","OR.PA","HSBA.L","BP.L",
    "^GSPC","^NDX"
]

ACCOUNT_SIZE = 10000  # simuliertes Kapital
RISK_PER_TRADE = 0.01  # 1%

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
# INDICATORS (INSTITUTIONAL MINIMALISM)
# =========================
def indicators(df):
    df = df.copy()
    close = df["Close"].astype(float)

    df["EMA20"] = close.ewm(span=20).mean()
    df["EMA50"] = close.ewm(span=50).mean()
    df["EMA200"] = close.ewm(span=200).mean()

    # ATR (real volatility engine)
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
        return "UPTREND"
    elif ema50 < ema200 and strength > 0.02:
        return "DOWNTREND"
    else:
        return "RANGE"

# =========================
# POSITION SIZE (HEDGE FUND CORE)
# =========================
def position_size(account, risk_pct, entry, sl):
    risk_amount = account * risk_pct
    risk_per_share = abs(entry - sl)

    if risk_per_share == 0:
        return 0

    size = risk_amount / risk_per_share
    return max(size, 0)

# =========================
# SIGNAL ENGINE (VERSION 9)
# =========================
def signal_engine(df):

    l = df.iloc[-1]

    price = float(l["Close"])
    ema20 = float(l["EMA20"])
    ema50 = float(l["EMA50"])
    atr = float(l["ATR"])

    reg = regime(df)

    score = 50
    setup = "NO_TRADE"

    # =========================
    # STRUCTURE LOGIC
    # =========================
    high20 = df["Close"].rolling(20).max().iloc[-1]
    low20 = df["Close"].rolling(20).min().iloc[-1]

    breakout_up = price > high20 * 0.999
    breakout_down = price < low20 * 1.001

    pullback_long = abs(price - ema20) < atr * 0.6 and price > ema50
    pullback_short = abs(price - ema20) < atr * 0.6 and price < ema50

    mean_long = reg == "RANGE" and price < ema20
    mean_short = reg == "RANGE" and price > ema20

    # =========================
    # CLASSIFICATION
    # =========================
    if breakout_up:
        setup = "BREAKOUT_LONG"
        score += 30

    elif breakout_down:
        setup = "BREAKOUT_SHORT"
        score += 30

    elif pullback_long:
        setup = "TREND_PULLBACK_LONG"
        score += 25

    elif pullback_short:
        setup = "TREND_PULLBACK_SHORT"
        score += 25

    elif mean_long:
        setup = "MEAN_REVERSION_LONG"
        score += 20

    elif mean_short:
        setup = "MEAN_REVERSION_SHORT"
        score += 20

    else:
        setup = "NO_SETUP"
        score -= 10

    # =========================
    # RISK ENGINE (ATR BASED)
    # =========================
    if "LONG" in setup:
        sl = price - atr * 1.5
        tp = price + atr * 2.5
    else:
        sl = price + atr * 1.5
        tp = price - atr * 2.5

    risk = abs(price - sl)
    reward = abs(tp - price)

    rr = reward / risk if risk != 0 else 0

    # =========================
    # QUALITY FILTER
    # =========================
    volatility_ok = atr / price > 0.001  # Mindestbewegung

    if not volatility_ok:
        score -= 10

    if rr > 2:
        score += 10
    else:
        score -= 5

    # =========================
    # FINAL GRADE
    # =========================
    if score >= 80:
        grade = "A+ INSTITUTIONAL"
    elif score >= 70:
        grade = "A SETUP"
    elif score >= 60:
        grade = "B SETUP"
    else:
        grade = "NO TRADE"

    # position sizing
    size = position_size(ACCOUNT_SIZE, RISK_PER_TRADE, price, sl)

    return {
        "price": price,
        "regime": reg,
        "setup": setup,
        "grade": grade,
        "score": round(score,1),
        "entry": price,
        "sl": sl,
        "tp": tp,
        "rr": rr,
        "position_size": round(size,2)
    }

# =========================
# UI
# =========================
st.title("🏦 Hedge Fund Trading Engine v9")

custom = st.text_input("Tickers (comma separated)")

watchlist = [x.strip().upper() for x in custom.split(",")] if custom else WATCHLIST

if st.button("Scan starten"):

    results = []

    for ticker in watchlist:

        df = load_data(ticker)
        if df is None:
            continue

        df = indicators(df)

        res = signal_engine(df)

        results.append({
            "Ticker": ticker,
            "Regime": res["regime"],
            "Setup": res["setup"],
            "Grade": res["grade"],
            "Score": res["score"],
            "Price": round(res["price"],2),
            "SL": round(res["sl"],2),
            "TP": round(res["tp"],2),
            "RR": round(res["rr"],2),
            "Size": round(res["position_size"],2)
        })

    df_out = pd.DataFrame(results).sort_values("Score", ascending=False)

    st.dataframe(df_out, use_container_width=True)

    st.success("Hedge Fund Scan abgeschlossen")
