import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")

# =========================
# LARGE WATCHLIST (SP500 + NASDAQ TOP)
# =========================
WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA",
    "GOOGL","NFLX","AMD","AVGO",
    "INTC","CSCO","ADBE","CRM","ORCL",
    "QCOM","TXN","AMAT","MU","LRCX",
    "JPM","BAC","GS","MS","V","MA",
    "UNH","JNJ","PFE","LLY",
    "XOM","CVX","COP",
    "WMT","COST","HD","LOW",
    "DIS","NKE","SBUX",
    "BA","CAT","GE",
    "PYPL","SQ","SHOP"
]

# =========================
# SEKTOR MAP
# =========================
SECTOR_MAP = {
    "AAPL": ("Tech","Hardware"),
    "MSFT": ("Tech","Software"),
    "NVDA": ("Tech","Semis"),
    "AMZN": ("Consumer","Ecom"),
    "META": ("Comm","Social"),
    "TSLA": ("Auto","EV"),
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

# =========================
# DATA
# =========================
@st.cache_data(ttl=300)
def load(t):
    try:
        df = yf.download(t, period="90d", interval="1h", progress=False)
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
    c = df["Close"]

    df["EMA20"] = c.ewm(span=20).mean()
    df["EMA50"] = c.ewm(span=50).mean()

    prev = c.shift()

    tr = pd.concat([
        df["High"]-df["Low"],
        (df["High"]-prev).abs(),
        (df["Low"]-prev).abs()
    ], axis=1).max(axis=1)

    df["ATR"] = tr.rolling(14).mean()

    return df.dropna()

# =========================
# SCORE (REALISTIC)
# =========================
def score(df, i):

    r = df.iloc[i]

    p = safe(r["Close"])
    ema20 = safe(r["EMA20"])
    ema50 = safe(r["EMA50"])
    atr = safe(r["ATR"])

    if None in [p, ema20, ema50, atr]:
        return "NO", 0

    score = 0

    # TREND (0–25)
    if p > ema50:
        score += 25
        direction = "LONG"
    else:
        score += 25
        direction = "SHORT"

    # MOMENTUM (0–20)
    high = df["Close"].iloc[i-20:i].max()
    low = df["Close"].iloc[i-20:i].min()

    if p > high:
        score += 20
    elif p < low:
        score += 20

    # PULLBACK (0–20)
    dist = abs(p-ema20)
    if dist < atr*0.5:
        score += 20
    elif dist < atr:
        score += 10

    # TREND ALIGN (0–20)
    if ema20 > ema50 and p > ema20:
        score += 20
    elif ema20 < ema50 and p < ema20:
        score += 20

    # VOL (penalty)
    score -= (atr/p)*10

    return direction, round(score,1)

# =========================
# TRADE
# =========================
def trade(df, i, d):

    p = safe(df.iloc[i]["Close"])
    atr = safe(df.iloc[i]["ATR"])

    if not p or not atr:
        return None,None,None,None,0

    if d=="LONG":
        sl = p-atr
        tp = p+2*atr
    else:
        sl = p+atr
        tp = p-2*atr

    rr = abs(tp-p)/abs(p-sl)

    return p,sl,tp,rr

# =========================
# SCAN
# =========================
def scan():

    res = []

    for t in WATCHLIST:

        df = load(t)
        if df is None: continue

        df = ind(df)

        d,sc = score(df,len(df)-1)

        p,sl,tp,rr = trade(df,len(df)-1,d)

        res.append({
            "Ticker":t,
            "Signal":d,
            "Score":sc,
            "Entry":p,
            "SL":sl,
            "TP":tp,
            "RR":rr
        })

    df = pd.DataFrame(res)

    return df.sort_values("Score",ascending=False).head(10)

# =========================
# CHART
# =========================
def chart(df,tr):

    fig = go.Figure()

    fig.add_trace(go.Scatter(x=df["Datetime"],y=df["Close"],name="Preis"))
    fig.add_trace(go.Scatter(x=df["Datetime"],y=df["EMA20"],name="EMA20"))
    fig.add_trace(go.Scatter(x=df["Datetime"],y=df["EMA50"],name="EMA50"))

    fig.add_hline(y=tr["Entry"])
    fig.add_hline(y=tr["SL"],line_color="red")

    fig.update_yaxes(autorange=True)

    return fig

# =========================
# UI
# =========================
st.title("🚀 Version 25 – Echtgeld Scanner")

df = scan()

st.subheader("🏆 Top 10 Trades")

ev = st.dataframe(df,selection_mode="single-row",on_select="rerun")

if ev and len(ev.selection["rows"])>0:

    row = df.iloc[ev.selection["rows"][0]]
    t = row["Ticker"]

    dff = ind(load(t))

    st.subheader(t)

    st.plotly_chart(chart(dff,row),use_container_width=True)
