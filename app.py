import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")

# =========================
# WATCHLIST (erweitert)
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
    "DIS","NKE","SBUX"
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
    "GOOGL": ("Comm","Internet"),
    "NFLX": ("Comm","Streaming"),
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
# LOAD
# =========================
@st.cache_data(ttl=300)
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
# 🔥 SCORE (ECHT DIFFERENZIERT)
# =========================
def score(df, i):

    r = df.iloc[i]

    p = safe(r["Close"])
    ema20 = safe(r["EMA20"])
    ema50 = safe(r["EMA50"])
    atr = safe(r["ATR"])

    if None in [p, ema20, ema50, atr]:
        return "NO", 0

    score = 50  # BASE

    # TREND (+/- 20)
    if p > ema50:
        score += 20
        direction = "LONG"
    else:
        score += 20
        direction = "SHORT"

    # MOMENTUM (+25)
    high = df["Close"].iloc[i-20:i].max()
    low = df["Close"].iloc[i-20:i].min()

    if p > high:
        score += 25
    elif p < low:
        score += 25
    else:
        score -= 10

    # PULLBACK (+15)
    dist = abs(p - ema20)

    if dist < atr * 0.5:
        score += 15
    elif dist < atr:
        score += 5
    else:
        score -= 10

    # TREND ALIGNMENT (+15)
    if ema20 > ema50 and p > ema20:
        score += 15
    elif ema20 < ema50 and p < ema20:
        score += 15
    else:
        score -= 10

    # VOLATILITY PENALTY (-20)
    score -= (atr / p) * 20

    return direction, round(max(0, min(100, score)),1)

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
# SCAN (MIT FILTER)
# =========================
def scan(sec, indus):

    res = []

    for t in WATCHLIST:

        s,i = SECTOR_MAP.get(t,("Other","Other"))

        if sec!="All" and s!=sec:
            continue
        if indus!="All" and i!=indus:
            continue

        df = load(t)
        if df is None:
            continue

        df = ind(df)

        d,sc = score(df,len(df)-1)

        if sc < 75:
            continue

        p,sl,tp,rr = trade(df,len(df)-1,d)

        res.append({
            "Ticker":t,
            "Sektor":s,
            "Industrie":i,
            "Signal":d,
            "Score":sc,
            "Entry":round(p,2),
            "SL":round(sl,2),
            "TP":round(tp,2),
            "RR":round(rr,2)
        })

    return pd.DataFrame(res).sort_values("Score",ascending=False)

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
st.title("🚀 Version 25.1 – PRO Derivate Scanner")

sec = st.selectbox("Sektor", ["All"] + sorted(set(v[0] for v in SECTOR_MAP.values())))
indus = st.selectbox("Industrie", ["All"] + sorted(set(v[1] for v in SECTOR_MAP.values())))

df = scan(sec, indus)

if df.empty:
    st.warning("Keine starken Setups")
else:

    ev = st.dataframe(df,selection_mode="single-row",on_select="rerun")

    if ev and len(ev.selection["rows"])>0:

        row = df.iloc[ev.selection["rows"][0]]
        t = row["Ticker"]

        dff = ind(load(t))

        st.subheader(t)

        st.plotly_chart(chart(dff,row),use_container_width=True)
