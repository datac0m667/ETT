import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")

# =========================
# UNIVERSE
# =========================
WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA",
    "GOOGL","NFLX","AMD","AVGO",
    "BRK-B","JPM","V","MA","UNH","XOM","LLY",
    "CRM","ADBE","ORCL","CSCO","QCOM"
]

# =========================
# COMPANY NAME (FIXED + ROBUST)
# =========================
name_cache = {}

def get_name(ticker):

    if ticker in name_cache:
        return name_cache[ticker]

    try:
        t = yf.Ticker(ticker)
        info = t.get_info()

        name = (
            info.get("longName")
            or info.get("shortName")
            or info.get("displayName")
            or ticker
        )

        # CLEAN FALLBACK FIX
        if name.upper() == ticker.upper():
            name = f"{ticker} (unverified name)"

    except:
        name = f"{ticker} (no data)"

    name_cache[ticker] = name
    return name

# =========================
# DATA
# =========================
def load(ticker):
    try:
        df = yf.download(ticker, period="180d", interval="1h", progress=False)

        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        return df[["Open","High","Low","Close"]].dropna()

    except:
        return None

# =========================
# INDICATORS
# =========================
def indicators(df):
    df = df.copy()

    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()

    tr = np.maximum(
        df["High"] - df["Low"],
        np.maximum(
            abs(df["High"] - df["Close"].shift()),
            abs(df["Low"] - df["Close"].shift())
        )
    )

    df["ATR"] = pd.Series(tr).rolling(14).mean()

    return df.dropna()

# =========================
# SCORING ENGINE
# =========================
def score(df, i):

    l = df.iloc[i]

    price = l["Close"]
    ema20 = l["EMA20"]
    ema50 = l["EMA50"]
    atr = l["ATR"]

    score = 50
    direction = "NO TRADE"

    if price > ema50:
        score += 20
        direction = "LONG"
    else:
        score += 20
        direction = "SHORT"

    high20 = df["Close"].iloc[max(0,i-20):i].max()
    low20 = df["Close"].iloc[max(0,i-20):i].min()

    if price > high20:
        score += 25
        direction = "LONG"

    if price < low20:
        score += 25
        direction = "SHORT"

    if abs(price - ema20) < atr * 0.6:
        score += 10

    vol = atr / price
    score -= vol * 10

    return direction, max(0, min(100, score))

# =========================
# TRADE BUILDER
# =========================
def build_trade(df, i, direction):

    price = df.iloc[i]["Close"]
    atr = df.iloc[i]["ATR"]

    entry = price

    if direction == "LONG":
        sl = price - atr * 1.5
        tp1 = price + atr * 1.5
        tp2 = price + atr * 3.0
        ko = sl - atr * 0.5
    else:
        sl = price + atr * 1.5
        tp1 = price - atr * 1.5
        tp2 = price - atr * 3.0
        ko = sl + atr * 0.5

    rr = abs(tp2 - entry) / abs(entry - sl)

    return entry, sl, tp1, tp2, ko, rr

# =========================
# DATA STATE (CLICK SYSTEM)
# =========================
if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = None

# =========================
# SCANNER
# =========================
def scan():

    results = []

    for t in WATCHLIST:

        df = load(t)

        if df is None or len(df) < 120:
            continue

        df = indicators(df)

        direction, sc = score(df, len(df)-1)

        if sc < 65:
            continue

        entry, sl, tp1, tp2, ko, rr = build_trade(df, len(df)-1, direction)

        results.append({
            "Ticker": t,
            "Unternehmen": get_name(t),
            "Direction": direction,
            "Score": round(sc,1),
            "Entry": round(entry,2),
            "SL": round(sl,2),
            "TP1": round(tp1,2),
            "TP2": round(tp2,2),
            "KO": round(ko,2),
            "RR": round(rr,2)
        })

    return pd.DataFrame(results)

# =========================
# CHART
# =========================
def chart(df, trade):

    import plotly.graph_objects as go

    fig = go.Figure()

    fig.add_trace(go.Scatter(y=df["Close"], name="Preis"))
    fig.add_trace(go.Scatter(y=df["EMA20"], name="EMA20"))
    fig.add_trace(go.Scatter(y=df["EMA50"], name="EMA50"))

    # ENTRY / SL / TP VISUAL
    fig.add_hline(y=trade["Entry"], line_width=1, line_dash="dash")
    fig.add_hline(y=trade["SL"], line_width=1, line_color="red")
    fig.add_hline(y=trade["TP1"], line_width=1, line_color="green")
    fig.add_hline(y=trade["TP2"], line_width=1, line_color="green")

    fig.update_layout(height=450)

    return fig

# =========================
# UI
# =========================
st.title("📊🧠 Version 22 – Live Derivate Terminal (Click-to-Chart)")

df = scan()

if df.empty:
    st.warning("Keine starken Setups gefunden.")
else:

    st.subheader("🏆 Top Setups")

    event = st.dataframe(
        df,
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun"
    )

    # =========================
    # CLICK LOGIC
    # =========================
    if len(event.selection["rows"]) > 0:

        idx = event.selection["rows"][0]
        row = df.iloc[idx]

        ticker = row["Ticker"]
        st.session_state.selected_ticker = ticker

    # =========================
    # CHART SECTION
    # =========================
    if st.session_state.selected_ticker:

        t = st.session_state.selected_ticker

        df_chart = indicators(load(t))
        _, _, _, _, _, _ = build_trade(df_chart, len(df_chart)-1, "LONG")

        trade = df_chart.iloc[-1]

        direction, sc = score(df_chart, len(df_chart)-1)
        entry, sl, tp1, tp2, ko, rr = build_trade(df_chart, len(df_chart)-1, direction)

        st.subheader(f"📈 Chart: {t} – {get_name(t)}")

        st.plotly_chart(
            chart(df_chart, {
                "Entry": entry,
                "SL": sl,
                "TP1": tp1,
                "TP2": tp2
            }),
            use_container_width=True
        )

        st.write({
            "Direction": direction,
            "Score": sc,
            "Entry": entry,
            "SL": sl,
            "TP1": tp1,
            "TP2": tp2,
            "KO": ko,
            "RR": rr
        })
