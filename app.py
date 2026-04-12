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
    "AMZN": ("Consumer", "E-Commerce"),
    "META": ("Communication", "Social Media"),
    "TSLA": ("Consumer", "Automotive"),
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
# SAFE FLOAT
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
# CLEAN DATA
# =========================
def clean_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    return df

def safe_col(df, col):
    c = df[col]
    if isinstance(c, pd.DataFrame):
        c = c.iloc[:, 0]
    return pd.Series(c).astype(float)

# =========================
# LOAD
# =========================
def load(ticker):
    try:
        df = yf.download(ticker, period="180d", interval="1h", progress=False)

        if df is None or df.empty:
            return None

        df = df.reset_index()
        df = clean_columns(df)

        df["Close"] = safe_col(df, "Close")
        df["High"] = safe_col(df, "High")
        df["Low"] = safe_col(df, "Low")

        df = df[["Datetime","Open","High","Low","Close"]].dropna()

        return df

    except:
        return None

# =========================
# INDICATORS
# =========================
def indicators(df):

    df = df.copy()
    close = safe_col(df, "Close")

    df["EMA20"] = close.ewm(span=20, adjust=False).mean()
    df["EMA50"] = close.ewm(span=50, adjust=False).mean()

    prev_close = close.shift(1)

    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs()
    ], axis=1).max(axis=1)

    df["ATR"] = tr.rolling(14).mean()

    return df.dropna()

# =========================
# SCORE
# =========================
def score(df, i):

    row = df.iloc[i]

    price = safe_float(row["Close"])
    ema50 = safe_float(row["EMA50"])
    atr = safe_float(row["ATR"])

    if None in [price, ema50, atr]:
        return "NO TRADE", 0

    direction = "LONG" if price > ema50 else "SHORT"
    score = 60

    return direction, score

# =========================
# TRADE
# =========================
def build_trade(df, i, direction):

    price = safe_float(df.iloc[i]["Close"])
    atr = safe_float(df.iloc[i]["ATR"])

    if not price or not atr:
        return None, None, None, None, None, 0

    if direction == "LONG":
        sl = price - atr
        tp1 = price + atr
        tp2 = price + atr * 2
        ko = sl - atr * 0.5
    else:
        sl = price + atr
        tp1 = price - atr
        tp2 = price - atr * 2
        ko = sl + atr * 0.5

    rr = abs(tp2 - price) / abs(price - sl)

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
        if df is None or len(df) < 100:
            continue

        df = indicators(df)

        direction, sc = score(df, len(df)-1)

        if sc < 60:
            continue

        entry, sl, tp1, tp2, ko, rr = build_trade(df, len(df)-1, direction)

        results.append({
            "Ticker": t,
            "Unternehmen": get_name(t),
            "Sektor": sector,
            "Industrie": industry,
            "Direction": direction,
            "Score": sc,
            "Entry": entry,
            "SL": sl,
            "TP1": tp1,
            "TP2": tp2,
            "RR": rr
        })

    return pd.DataFrame(results)

# =========================
# CHART (AUTO Y SCALE FIX)
# =========================
def chart(df, trade):

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["Datetime"],
        y=df["Close"],
        name="Preis"
    ))

    fig.add_trace(go.Scatter(
        x=df["Datetime"],
        y=df["EMA20"],
        name="EMA20"
    ))

    fig.add_trace(go.Scatter(
        x=df["Datetime"],
        y=df["EMA50"],
        name="EMA50"
    ))

    if trade["Entry"]:
        fig.add_hline(y=trade["Entry"], line_dash="dash")
        fig.add_hline(y=trade["SL"], line_color="red")
        fig.add_hline(y=trade["TP1"], line_color="green")

    # 🔥 AUTO SCALE FIX
    fig.update_yaxes(autorange=True, fixedrange=False)

    fig.update_layout(
        height=500,
        xaxis=dict(rangeslider=dict(visible=True))
    )

    return fig

# =========================
# UI
# =========================
st.title("📊 Version 23.4 – Final Trading Terminal")

sector = st.selectbox("Sektor", ["All"] + sorted(set(v[0] for v in SECTOR_MAP.values())))
industry = st.selectbox("Industrie", ["All"] + sorted(set(v[1] for v in SECTOR_MAP.values())))

df = scan(sector, industry)

if df.empty:
    st.warning("Keine Setups gefunden")
else:

    event = st.dataframe(df, use_container_width=True, selection_mode="single-row", on_select="rerun")

    if event and len(event.selection["rows"]) > 0:

        t = df.iloc[event.selection["rows"][0]]["Ticker"]

        df_chart = indicators(load(t))

        direction, sc = score(df_chart, len(df_chart)-1)
        entry, sl, tp1, tp2, ko, rr = build_trade(df_chart, len(df_chart)-1, direction)

        st.subheader(f"{t} – {get_name(t)}")

        st.plotly_chart(chart(df_chart, {
            "Entry": entry,
            "SL": sl,
            "TP1": tp1
        }), use_container_width=True)
