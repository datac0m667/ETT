import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")

WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA",
    "GOOGL","NFLX","AMD","AVGO",
    "BRK-B","JPM","V","MA","UNH","XOM","LLY"
]

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
}

COMPANY = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "META": "Meta Platforms, Inc.",
    "TSLA": "Tesla, Inc."
}

# =========================
# HELPERS
# =========================
def safe(x):
    try:
        if isinstance(x, pd.Series):
            x = x.iloc[0]
        return float(x)
    except:
        return None

def clean(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df.loc[:, ~df.columns.duplicated()]

def load(t):
    try:
        df = yf.download(t, period="120d", interval="1h", progress=False)
        if df.empty:
            return None
        df = df.reset_index()
        df = clean(df)
        return df.dropna()
    except:
        return None

# =========================
# INDICATORS
# =========================
def ind(df):
    df = df.copy()

    close = df["Close"]

    df["EMA20"] = close.ewm(span=20).mean()
    df["EMA50"] = close.ewm(span=50).mean()

    prev = close.shift()

    tr = pd.concat([
        df["High"]-df["Low"],
        (df["High"]-prev).abs(),
        (df["Low"]-prev).abs()
    ], axis=1).max(axis=1)

    df["ATR"] = tr.rolling(14).mean()

    return df.dropna()

# =========================
# SCORE ENGINE 🔥
# =========================
def score(df, i):

    r = df.iloc[i]

    price = safe(r["Close"])
    ema20 = safe(r["EMA20"])
    ema50 = safe(r["EMA50"])
    atr = safe(r["ATR"])

    if None in [price, ema20, ema50, atr]:
        return "NO", 0

    score = 0

    # 1️⃣ TREND (0–30)
    if price > ema50:
        score += 30
        direction = "LONG"
    else:
        score += 30
        direction = "SHORT"

    # 2️⃣ MOMENTUM (0–25)
    high20 = df["Close"].iloc[i-20:i].max()
    low20 = df["Close"].iloc[i-20:i].min()

    if price > high20:
        score += 25
        direction = "LONG"
    elif price < low20:
        score += 25
        direction = "SHORT"

    # 3️⃣ PULLBACK ENTRY (0–20)
    dist = abs(price - ema20)

    if dist < atr * 0.5:
        score += 20
    elif dist < atr:
        score += 10

    # 4️⃣ VOLATILITY PENALTY (-15)
    vol = atr / price
    score -= vol * 15

    # 5️⃣ TREND ALIGNMENT (0–25)
    if ema20 > ema50 and price > ema20:
        score += 25
    elif ema20 < ema50 and price < ema20:
        score += 25

    return direction, round(max(0, min(100, score)),1)

# =========================
# TRADE
# =========================
def trade(df, i, direction):

    p = safe(df.iloc[i]["Close"])
    atr = safe(df.iloc[i]["ATR"])

    if not p or not atr:
        return None,None,None,None,None,0

    if direction=="LONG":
        sl = p - atr
        tp1 = p + atr
        tp2 = p + 2*atr
        ko = sl - 0.5*atr
    else:
        sl = p + atr
        tp1 = p - atr
        tp2 = p - 2*atr
        ko = sl + 0.5*atr

    rr = abs(tp2-p)/abs(p-sl)

    return p,sl,tp1,tp2,ko,rr

# =========================
# SCAN
# =========================
def scan(sec, indus):

    out = []

    for t in WATCHLIST:

        s,i = SECTOR_MAP.get(t,("Unknown","Unknown"))

        if sec!="All" and s!=sec: continue
        if indus!="All" and i!=indus: continue

        df = load(t)
        if df is None: continue

        df = ind(df)

        d,sc = score(df,len(df)-1)

        if sc < 70:
            continue

        p,sl,tp1,tp2,ko,rr = trade(df,len(df)-1,d)

        out.append({
            "Ticker":t,
            "Unternehmen": COMPANY.get(t,t),
            "Sektor":s,
            "Industrie":i,
            "Signal":d,
            "Score":sc,
            "Entry":round(p,2),
            "SL":round(sl,2),
            "TP1":round(tp1,2),
            "TP2":round(tp2,2),
            "RR":round(rr,2)
        })

    return pd.DataFrame(out).sort_values("Score",ascending=False)

# =========================
# CHART
# =========================
def chart(df,tr):

    fig = go.Figure()

    fig.add_trace(go.Scatter(x=df["Datetime"],y=df["Close"],name="Preis"))
    fig.add_trace(go.Scatter(x=df["Datetime"],y=df["EMA20"],name="EMA20"))
    fig.add_trace(go.Scatter(x=df["Datetime"],y=df["EMA50"],name="EMA50"))

    fig.add_hline(y=tr["Entry"],line_dash="dash")
    fig.add_hline(y=tr["SL"],line_color="red")
    fig.add_hline(y=tr["TP1"],line_color="green")

    fig.update_yaxes(autorange=True)

    return fig

# =========================
# UI
# =========================
st.title("🚀 Version 24 – Echtgeld Trading Engine")

sec = st.selectbox("Sektor", ["All"] + sorted(set(v[0] for v in SECTOR_MAP.values())))
indus = st.selectbox("Industrie", ["All"] + sorted(set(v[1] for v in SECTOR_MAP.values())))

df = scan(sec, indus)

if df.empty:
    st.warning("Keine starken Trades aktuell")
else:

    ev = st.dataframe(df,selection_mode="single-row",on_select="rerun")

    if ev and len(ev.selection["rows"])>0:

        row = df.iloc[ev.selection["rows"][0]]
        t = row["Ticker"]

        dff = ind(load(t))
        d,sc = score(dff,len(dff)-1)
        p,sl,tp1,tp2,ko,rr = trade(dff,len(dff)-1,d)

        st.subheader(f"{t} – {row['Unternehmen']}")

        st.plotly_chart(chart(dff,{
            "Entry":p,"SL":sl,"TP1":tp1
        }),use_container_width=True)
