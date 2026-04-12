import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")

# =========================
# WATCHLIST
# =========================
WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA",
    "GOOGL","NFLX","AMD","AVGO",
    "BRK-B","JPM","V","MA","UNH","XOM","LLY",
    "CRM","ADBE","ORCL","CSCO","QCOM"
]

# =========================
# SEKTOR / INDUSTRIE
# =========================
SECTOR_MAP = {
    "AAPL": ("Technology", "Consumer Electronics"),
    "MSFT": ("Technology", "Software"),
    "NVDA": ("Technology", "Semiconductors"),
    "AMZN": ("Consumer Discretionary", "E-Commerce"),
    "META": ("Communication", "Social Media"),
    "TSLA": ("Consumer Discretionary", "Automotive"),
    "GOOGL": ("Communication", "Internet"),
    "NFLX": ("Communication", "Streaming"),
    "AMD": ("Technology", "Semiconductors"),
    "AVGO": ("Technology", "Semiconductors"),
    "BRK-B": ("Financial", "Insurance"),
    "JPM": ("Financial", "Banking"),
    "V": ("Financial", "Payments"),
    "MA": ("Financial", "Payments"),
    "UNH": ("Healthcare", "Insurance"),
    "XOM": ("Energy", "Oil & Gas"),
    "LLY": ("Healthcare", "Pharma"),
    "CRM": ("Technology", "Software"),
    "ADBE": ("Technology", "Software"),
    "ORCL": ("Technology", "Software"),
    "CSCO": ("Technology", "Networking"),
    "QCOM": ("Technology", "Semiconductors")
}

# =========================
# COMPANY NAMES
# =========================
COMPANY_OVERRIDES = {
    "MSFT": "Microsoft Corporation",
    "AAPL": "Apple Inc.",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "META": "Meta Platforms, Inc.",
    "TSLA": "Tesla, Inc."
}

def get_name(ticker):
    if ticker in COMPANY_OVERRIDES:
        return COMPANY_OVERRIDES[ticker]
    try:
        info = yf.Ticker(ticker).get_info()
        return info.get("longName") or ticker
    except:
        return ticker

# =========================
# SAFE FLOAT (🔥 CRITICAL FIX)
# =========================
def safe_float(x):
    try:
        if isinstance(x, pd.Series):
            x = x.iloc[0]
        if pd.isna(x):
            return None
        return float(x)
    except:
        return None

# =========================
# DATA
# =========================
def load(ticker):
    try:
        df = yf.download(ticker, period="180d", interval="1h", progress=False)

        if df is None or df.empty:
            return None

        df = df.reset_index()
        df = df[["Datetime","Open","High","Low","Close"]]

        df = df.dropna().copy()

        return df

    except:
        return None

# =========================
# INDICATORS
# =========================
def indicators(df):

    df = df.copy()

    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()

    prev_close = df["Close"].shift(1)

    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - prev_close).abs()
    tr3 = (df["Low"] - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    df["ATR"] = tr.rolling(14, min_periods=14).mean()

    return df.dropna()

# =========================
# SCORE ENGINE (SAFE)
# =========================
def score(df, i):

    row = df.iloc[i]

    price = safe_float(row["Close"])
    ema20 = safe_float(row["EMA20"])
    ema50 = safe_float(row["EMA50"])
    atr = safe_float(row["ATR"])

    if None in [price, ema20, ema50, atr]:
        return "NO TRADE", 0

    score = 50
    direction = "NO TRADE"

    if price > ema50:
        score += 20
        direction = "LONG"
    else:
        score += 20
        direction = "SHORT"

    high20 = safe_float(df["Close"].iloc[max(0, i-20):i].max())
    low20 = safe_float(df["Close"].iloc[max(0, i-20):i].min())

    if high20 and price > high20:
        score += 25
        direction = "LONG"

    if low20 and price < low20:
        score += 25
        direction = "SHORT"

    if abs(price - ema20) < atr * 0.6:
        score += 10

    score -= (atr / price) * 10

    return direction, max(0, min(100, score))

# =========================
# TRADE BUILDER
# =========================
def build_trade(df, i, direction):

    price = safe_float(df.iloc[i]["Close"])
    atr = safe_float(df.iloc[i]["ATR"])

    if price is None or atr is None:
        return None, None, None, None, None, 0

    if direction == "LONG":
        sl = price - atr * 1.5
        tp1 = price + atr * 1.5
        tp2 = price + atr * 3
        ko = sl - atr * 0.5
    else:
        sl = price + atr * 1.5
        tp1 = price - atr * 1.5
        tp2 = price - atr * 3
        ko = sl + atr * 0.5

    rr = abs(tp2 - price) / abs(price - sl) if sl != price else 0

    return price, sl, tp1, tp2, ko, rr

# =========================
# SCAN
# =========================
def scan(sector_filter, industry_filter):

    results = []

    for t in WATCHLIST:

        sector, industry = SECTOR_MAP.get(t, ("Unknown","Unknown"))

        if sector_filter != "All" and sector != sector_filter:
            continue
        if industry_filter != "All" and industry != industry_filter:
            continue

        df = load(t)
        if df is None or len(df) < 120:
            continue

        df = indicators(df)
        if df.empty:
            continue

        direction, sc = score(df, len(df)-1)

        if sc < 65:
            continue

        entry, sl, tp1, tp2, ko, rr = build_trade(df, len(df)-1, direction)

        results.append({
            "Ticker": t,
            "Unternehmen": get_name(t),
            "Sektor": sector,
            "Industrie": industry,
            "Direction": direction,
            "Score": round(sc,1),
            "Entry": round(entry,2) if entry else None,
            "SL": round(sl,2) if sl else None,
            "TP1": round(tp1,2) if tp1 else None,
            "TP2": round(tp2,2) if tp2 else None,
            "KO": round(ko,2) if ko else None,
            "RR": round(rr,2)
        })

    return pd.DataFrame(results)

# =========================
# CHART
# =========================
def chart(df, trade):

    fig = go.Figure()

    fig.add_trace(go.Scatter(x=df["Datetime"], y=df["Close"], name="Preis"))
    fig.add_trace(go.Scatter(x=df["Datetime"], y=df["EMA20"], name="EMA20"))
    fig.add_trace(go.Scatter(x=df["Datetime"], y=df["EMA50"], name="EMA50"))

    if trade["Entry"]:
        fig.add_hline(y=trade["Entry"], line_dash="dash")
        fig.add_hline(y=trade["SL"], line_color="red")
        fig.add_hline(y=trade["TP1"], line_color="green")
        fig.add_hline(y=trade["TP2"], line_color="green")

    fig.update_layout(height=450)

    return fig

# =========================
# UI
# =========================
st.title("📊 Version 23.2 – FINAL Stable Derivate Scanner")

sector = st.selectbox("Sektor", ["All"] + sorted(set(v[0] for v in SECTOR_MAP.values())))
industry = st.selectbox("Industrie", ["All"] + sorted(set(v[1] for v in SECTOR_MAP.values())))

df = scan(sector, industry)

if df.empty:
    st.warning("Keine Setups gefunden")
else:

    event = st.dataframe(df, use_container_width=True, selection_mode="single-row", on_select="rerun")

    if event and len(event.selection["rows"]) > 0:

        row = df.iloc[event.selection["rows"][0]]
        t = row["Ticker"]

        df_chart = indicators(load(t))

        direction, sc = score(df_chart, len(df_chart)-1)
        entry, sl, tp1, tp2, ko, rr = build_trade(df_chart, len(df_chart)-1, direction)

        st.subheader(f"{t} – {get_name(t)}")

        st.plotly_chart(chart(df_chart, {
            "Entry": entry,
            "SL": sl,
            "TP1": tp1,
            "TP2": tp2
        }), use_container_width=True)
