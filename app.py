import streamlit as st
import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD

st.set_page_config(layout="wide")

WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA",
    "SAP.DE","ADS.DE","ALV.DE",
    "MC.PA","OR.PA","HSBA.L"
]

def load_data(ticker):
    return yf.download(ticker, period="3mo", interval="1h")

def indicators(df):
    df = df.copy()

    # wichtig: nur echte Close Series erzwingen
    close = df["Close"]

    # falls MultiIndex → fixen
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    close = close.squeeze()

    # EMAs
    df["EMA9"] = close.ewm(span=9).mean()
    df["EMA21"] = close.ewm(span=21).mean()
    df["EMA50"] = close.ewm(span=50).mean()
    df["EMA200"] = close.ewm(span=200).mean()

    # RSI FIX
    df["RSI"] = RSIIndicator(close).rsi()

    # MACD FIX
    macd = MACD(close)
    df["MACD"] = macd.macd()
    df["MACD_SIGNAL"] = macd.macd_signal()

    return df

def analyze(df):
    df = df.dropna().copy()

    l = df.iloc[-1]

   def safe(x):
    try:
        return float(x)
    except:
        return None

    ema50 = safe(l["EMA50"])
    ema200 = safe(l["EMA200"])
    ema9 = safe(l["EMA9"])
    ema21 = safe(l["EMA21"])
    rsi = safe(l["RSI"])
    macd = safe(l["MACD"])
    macd_sig = safe(l["MACD_SIGNAL"])
    price = safe(l["Close"])

    # wenn Daten kaputt → skip
    values = [ema50, ema200, ema9, ema21, rsi, macd, macd_sig, price]

if any(v is None for v in values):
    return None

    score = 0

    # Trend
    if ema50 > ema200:
        score += 30
    elif ema50 < ema200:
        score -= 30

    # EMA Struktur
    if ema9 > ema21:
        score += 20

    # RSI
    if rsi < 35:
        score += 20
    elif rsi > 70:
        score -= 20

    # MACD
    if macd > macd_sig:
        score += 20
    else:
        score -= 20

    entry = ema9
    sl = ema21
    tp = price + (price - sl) * 2

    rr = abs((tp - price) / (price - sl)) if price != sl else 0

    ko = sl * 0.995
    lev = price / (price - ko)

    return price, score, entry, sl, tp, rr, ko, lev

st.title("🚀 Elite KO Trading Tool")

custom = st.text_input("Eigene Ticker (z.B. AAPL,TSLA,NVDA)")

if custom:
    watchlist = [x.strip().upper() for x in custom.split(",")]
else:
    watchlist = WATCHLIST

if st.button("Scanner starten"):

    results = []

    for ticker in watchlist:
        df = load_data(ticker)

        if df.empty:
            continue

        df = indicators(df)
        price, score, entry, sl, tp, rr, ko, lev = analyze(df)

        if score >= 50 and rr >= 2:
            results.append({
                "Ticker": ticker,
                "Score": score,
                "Preis": round(price,2),
                "Entry": round(entry,2),
                "SL": round(sl,2),
                "TP": round(tp,2),
                "RR": round(rr,2),
                "KO": round(ko,2),
                "Hebel": round(lev,1)
            })

    df_out = pd.DataFrame(results).sort_values(by="Score", ascending=False)

    st.dataframe(df_out, use_container_width=True)

    if not df_out.empty:
        st.success("🔥 Nur starke Setups angezeigt")
    else:
        st.warning("Keine guten Trades aktuell")
