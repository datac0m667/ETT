import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")

WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA",
    "SAP.DE","ADS.DE","ALV.DE",
    "MC.PA","OR.PA","HSBA.L","BP.L",
    "^GSPC","^NDX"
]

# =========================
# FIXED DATA LOADER (IMPORTANT)
# =========================
def load_data(ticker):
    try:
        df = yf.download(
            ticker,
            period="90d",
            interval="1h",
            auto_adjust=False,
            progress=False
        )

        if df is None or df.empty:
            return None

        # 🔥 FIX 1: MultiIndex flatten
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()

        return df

    except:
        return None

# =========================
# INDICATORS
# =========================
def indicators(df):
    df = df.copy()

    close = df["Close"].astype(float)

    df["EMA9"] = close.ewm(span=9).mean()
    df["EMA21"] = close.ewm(span=21).mean()
    df["EMA50"] = close.ewm(span=50).mean()
    df["EMA200"] = close.ewm(span=200).mean()

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9).mean()

    return df.dropna()

# =========================
# SAFE FLOAT
# =========================
def f(x):
    try:
        return float(x)
    except:
        return None

# =========================
# ANALYSE
# =========================
def analyze(df):
    if df is None or df.empty:
        return None, {"error": "no data"}

    l = df.iloc[-1]

    price = f(l["Close"])
    ema9 = f(l["EMA9"])
    ema21 = f(l["EMA21"])
    ema50 = f(l["EMA50"])
    ema200 = f(l["EMA200"])
    rsi = f(l["RSI"])
    macd = f(l["MACD"])
    macd_sig = f(l["MACD_SIGNAL"])

    values = [price, ema9, ema21, ema50, ema200, rsi, macd, macd_sig]

    # 🔥 FIX: echte Diagnose statt NULL blackbox
    if any(v is None or np.isnan(v) for v in values):
        return None, {
            "error": "indicator NaN",
            "raw_close": l["Close"]
        }

    score = 50

    if ema9 > ema21:
        score += 15
    else:
        score -= 10

    if price > ema50:
        score += 10

    if rsi < 40:
        score += 10
    elif rsi > 70:
        score -= 10

    if macd > macd_sig:
        score += 10
    else:
        score -= 5

    entry = ema21
    sl = ema50
    tp = price + (price - sl) * 1.5 if price > sl else price - (sl - price) * 1.5

    rr = abs((tp - price) / (price - sl)) if price != sl else 0

    ko = sl * 0.995
    lev = price / (price - ko) if price > ko else 0

    return (price, score, entry, sl, tp, rr, ko, lev), None

# =========================
# UI
# =========================
st.title("🚀 KO Scanner v6 – FIXED DATA ENGINE")

custom = st.text_input("Tickers (comma separated)")

watchlist = [x.strip().upper() for x in custom.split(",")] if custom else WATCHLIST

if st.button("Scanner starten"):

    results = []
    debug = []

    for ticker in watchlist:

        df = load_data(ticker)

        if df is None:
            debug.append((ticker, "NO DATA"))
            continue

        df = indicators(df)

        result, err = analyze(df)

        if err:
            debug.append((ticker, err))
            continue

        price, score, entry, sl, tp, rr, ko, lev = result

        if score < 35:
            continue

        if rr < 1.2:
            continue

        results.append({
            "Ticker": ticker,
            "Score": round(score,1),
            "Price": round(price,2),
            "Entry": round(entry,2),
            "SL": round(sl,2),
            "TP": round(tp,2),
            "RR": round(rr,2),
            "KO": round(ko,2),
            "Lev": round(lev,1)
        })

    if results:
        st.dataframe(pd.DataFrame(results).sort_values("Score", ascending=False))
    else:
        st.warning("Keine starken Setups aktuell")

        st.subheader("🧠 DEBUG (warum keine Trades?)")
        st.write(debug)
