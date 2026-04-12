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
    df["EMA9"] = df["Close"].ewm(span=9).mean()
    df["EMA21"] = df["Close"].ewm(span=21).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["EMA200"] = df["Close"].ewm(span=200).mean()

    df["RSI"] = RSIIndicator(df["Close"]).rsi()

    macd = MACD(df["Close"])
    df["MACD"] = macd.macd()
    df["MACD_SIGNAL"] = macd.macd_signal()

    return df

def analyze(df):
    l = df.iloc[-1]
    price = l["Close"]

    score = 0

    if l["EMA50"] > l["EMA200"]:
        score += 30
    if l["EMA9"] > l["EMA21"]:
        score += 20
    if l["RSI"] < 35:
        score += 20
    if l["MACD"] > l["MACD_SIGNAL"]:
        score += 20

    entry = l["EMA9"]
    sl = l["EMA21"]
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
