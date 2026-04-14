"""
Trading Scanner v3 – Entry Precision (KO proposals removed)
- KO-Vorschläge entfernt aus Sidebar und Detailansicht
- Light gray UI, trading rules enforced and reported
Start: streamlit run scanner.py
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from urllib.parse import quote

# ─────────────────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────────────────
st.set_page_config(page_title="Trading Scanner", page_icon="📡", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

  html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #f2f4f6; color: #111827;
    font-size: 13px;
  }
  .main, [data-testid="stAppViewContainer"] { background-color: #f2f4f6; }
  [data-testid="stSidebar"] { background-color: #e5e7eb; border-right: 1px solid #d1d5db; }

  h1,h2,h3 { font-family: 'IBM Plex Mono', monospace; color: #0b5fff; font-size:1.05rem; }
  .topbar { display:flex; align-items:baseline; gap:12px; border-bottom: 1px solid #d1d5db; padding-bottom:10px; margin-bottom:16px; }
  .topbar-title { font-family:'IBM Plex Mono',monospace; font-size:1.15rem; font-weight:600; color:#0b5fff; }
  .topbar-sub   { font-size:0.72rem; color:#6b7280; }

  .metric-row { display:flex; gap:8px; margin-bottom:12px; flex-wrap:wrap; }
  .metric { background:#ffffff; border:1px solid #d1d5db; border-radius:8px; padding:8px 12px; flex:1; min-width:80px; }
  .mlabel { font-size:0.62rem; text-transform:uppercase; letter-spacing:1px; color:#6b7280; }
  .mvalue { font-family:'IBM Plex Mono',monospace; font-size:1rem; font-weight:600; color:#111827; margin-top:2px; }

  .card { background:#ffffff; border:1px solid #d1d5db; border-radius:8px; padding:10px 12px; margin-bottom:12px; }
  .card-title { font-size:0.66rem; text-transform:uppercase; letter-spacing:1px; color:#6b7280; margin-bottom:6px; }

  .ko-setup { background:#ffffff; border:1px solid #d1d5db; border-radius:8px; padding:8px; margin-bottom:8px; font-size:0.9rem; }
  .ko-setup h4 { margin:0 0 6px 0; font-family:'IBM Plex Mono',monospace; color:#111827; font-size:0.95rem; }
  .ko-setup p { margin:0; color:#374151; font-size:0.85rem; }

  .ko-grid { display:grid; grid-template-columns:1fr 1fr; gap:6px 10px; margin-top:8px; }
  .ko-key { color:#6b7280; font-size:0.82rem; } .ko-val { font-family:'IBM Plex Mono',monospace; color:#111827; text-align:right; }

  .pill { display:inline-block; padding:1px 8px; border-radius:10px; font-size:0.67rem; margin:2px 2px 2px 0; }
  .pill-green  { background:#ecfdf5; color:#059669; }
  .pill-red    { background:#fef2f2; color:#ef4444; }
  .pill-orange { background:#fffbeb; color:#f59e0b; }

  .link-btn { display:inline-block; padding:6px 12px; border-radius:6px; background:#e5e7eb; border:1px solid #d1d5db; color:#0b5fff; font-size:0.78rem; text-decoration:none; margin-right:6px; margin-top:4px; }

  div.stButton > button {
    background:#ffffff; border:1px solid #d1d5db; color:#111827;
    border-radius:6px; font-size:0.82rem; transition:all 0.12s;
  }
  div.stButton > button:hover { border-color:#0b5fff; color:#0b5fff; }

  #MainMenu, footer, header { visibility:hidden; }
  .block-container { padding-top:1rem; padding-left:1rem; padding-right:1rem; }
  [data-testid="stDataFrame"] { border:1px solid #d1d5db; border-radius:8px; overflow:hidden; font-size:0.9rem; }
  table { font-size:0.9rem; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
#  WATCHLIST
# ─────────────────────────────────────────────────────────
WATCHLIST = {
    "Tech":     ["AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","NFLX"],
    "Semis":    ["AMD","AVGO","QCOM","INTC","MU","AMAT","LRCX","TXN"],
    "Software": ["CRM","ADBE","ORCL","CSCO","NOW","SNOW"],
    "Finance":  ["JPM","BAC","GS","MS","V","MA"],
    "Health":   ["UNH","JNJ","PFE","LLY","MRK"],
    "Energy":   ["XOM","CVX","COP"],
    "Consumer": ["WMT","COST","HD","LOW","NKE","SBUX","DIS"],
}
ALL_TICKERS = [t for g in WATCHLIST.values() for t in g]
TICKER_TO_SECTOR = {t: s for s, ts in WATCHLIST.items() for t in ts}
EUR_USD_FALLBACK = 1.09

# ─────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────
def sf(x):
    try:
        if isinstance(x, pd.Series):
            x = x.iloc[0]
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None

def flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df.loc[:, ~df.columns.duplicated()]

def to_series(df, col):
    s = df[col]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return pd.to_numeric(s, errors="coerce")

# ─────────────────────────────────────────────────────────
#  DATA
# ─────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load(ticker: str):
    try:
        df = yf.download(ticker, period="120d", interval="1h", progress=False)
        if df is None or df.empty:
            return None
        df = df.reset_index()
        df = flatten(df)
        for col in ["Open","High","Low","Close","Volume"]:
            if col in df.columns:
                df[col] = to_series(df, col)
        df = df[["Datetime","Open","High","Low","Close","Volume"]].dropna()
        return df
    except Exception:
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def get_eur_usd():
    try:
        df = yf.download("EURUSD=X", period="2d", interval="1h", progress=False)
        df = flatten(df)
        return sf(df["Close"].iloc[-1]) or EUR_USD_FALLBACK
    except Exception:
        return EUR_USD_FALLBACK

# ─────────────────────────────────────────────────────────
#  MARKET METRICS (für Regeln)
# ─────────────────────────────────────────────────────────
def market_metrics():
    try:
        spy = yf.download("SPY", period="3d", interval="1d", progress=False)
        qqq = yf.download("QQQ", period="3d", interval="1d", progress=False)
        vix = yf.download("^VIX", period="3d", interval="1d", progress=False)
        spy = flatten(spy); qqq = flatten(qqq); vix = flatten(vix)

        def last_change(df):
            if df is None or df.empty or len(df) < 2:
                return None
            c0 = sf(df["Close"].iloc[-2])
            c1 = sf(df["Close"].iloc[-1])
            if not c0 or not c1:
                return None
            return (c1 - c0) / c0 * 100

        return {
            "SPY_chg": last_change(spy),
            "QQQ_chg": last_change(qqq),
            "VIX":     sf(vix["Close"].iloc[-1]) if not vix.empty else None,
        }
    except Exception:
        return {"SPY_chg": None, "QQQ_chg": None, "VIX": None}

# ─────────────────────────────────────────────────────────
#  INDICATORS
# ─────────────────────────────────────────────────────────
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c = df["Close"]

    df["EMA20"]  = c.ewm(span=20,  adjust=False).mean()
    df["EMA50"]  = c.ewm(span=50,  adjust=False).mean()
    df["EMA200"] = c.ewm(span=200, adjust=False).mean()

    prev = c.shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev).abs(),
            (df["Low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["ATR"]  = tr.rolling(14).mean()
    df["ATR5"] = tr.rolling(5).mean()

    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["MACD"]        = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"]   = df["MACD"] - df["MACD_signal"]

    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    df["BB_upper"] = sma20 + 2 * std20
    df["BB_lower"] = sma20 - 2 * std20
    df["BB_pct"]   = (c - df["BB_lower"]) / (df["BB_upper"] - df["BB_lower"])

    df["Vol_avg"] = df["Volume"].rolling(20).mean()

    return df.dropna()

# ─────────────────────────────────────────────────────────
#  ENTRY QUALITY SCORE
# ─────────────────────────────────────────────────────────
def entry_quality(df: pd.DataFrame, direction: str):
    r     = df.iloc[-1]
    prev  = df.iloc[-2]
    price = sf(r["Close"]); ema20=sf(r["EMA20"]); atr=sf(r["ATR"])
    atr5  = sf(r["ATR5"]);  rsi=sf(r["RSI"])
    macdh = sf(r["MACD_hist"]); pmacdh=sf(prev["MACD_hist"])
    bbpct = sf(r["BB_pct"]); vol=sf(r["Volume"]); volavg=sf(r["Vol_avg"])

    if None in [price, ema20, atr, rsi]:
        return 0, []

    score = 0
    sigs  = []

    dist = abs(price - ema20) / atr
    if dist < 0.4:
        score += 25; sigs.append(("Nahe EMA20 – idealer Pullback", "good"))
    elif dist < 0.8:
        score += 12; sigs.append(("Moderat von EMA20 entfernt", "neutral"))
    else:
        sigs.append(("Weit von EMA20 – Extended Move", "bad"))

    if direction == "LONG":
        if 40 <= rsi <= 55:
            score += 20; sigs.append((f"RSI {rsi:.0f} – optimale Long-Zone", "good"))
        elif 35 <= rsi < 40:
            score += 12; sigs.append((f"RSI {rsi:.0f} – leicht überverkauft", "neutral"))
        elif rsi > 65:
            sigs.append((f"RSI {rsi:.0f} – überkauft", "bad"))
        else:
            score += 6; sigs.append((f"RSI {rsi:.0f}", "neutral"))
    else:
        if 45 <= rsi <= 60:
            score += 20; sigs.append((f"RSI {rsi:.0f} – optimale Short-Zone", "good"))
        elif rsi > 65:
            score += 12; sigs.append((f"RSI {rsi:.0f} – überkauft, Short-Chance", "neutral"))
        elif rsi < 35:
            sigs.append((f"RSI {rsi:.0f} – überverkauft, Short riskant", "bad"))
        else:
            score += 6; sigs.append((f"RSI {rsi:.0f}", "neutral"))

    if macdh is not None and pmacdh is not None:
        if direction == "LONG" and macdh > pmacdh:
            score += 20; sigs.append(("MACD Hist dreht bullisch", "good"))
        elif direction == "SHORT" and macdh < pmacdh:
            score += 20; sigs.append(("MACD Hist dreht bärisch", "good"))
        else:
            sigs.append(("MACD läuft gegen Richtung", "bad"))

    if atr5 and atr:
        rv = atr5 / atr
        if rv < 0.8:
            score += 15; sigs.append(("Volatilität komprimiert", "good"))
        elif rv < 1.2:
            score += 7; sigs.append(("Volatilität normal", "neutral"))
        else:
            sigs.append(("Hohe kurzfristige Volatilität", "bad"))

    if vol and volavg and volavg > 0:
        vr = vol / volavg
        if vr > 1.3:
            score += 10; sigs.append((f"Volumen +{(vr-1)*100:.0f}% – Bestätigung", "good"))
        elif vr < 0.6:
            sigs.append(("Volumen dünn – schwache Bestätigung", "bad"))
        else:
            score += 5; sigs.append(("Volumen normal", "neutral"))

    if bbpct is not None:
        if direction == "LONG" and bbpct < 0.45:
            score += 10; sigs.append(("Im unteren Bollinger-Band", "good"))
        elif direction == "SHORT" and bbpct > 0.55:
            score += 10; sigs.append(("Im oberen Bollinger-Band", "good"))

    return min(int(score), 100), sigs

# ─────────────────────────────────────────────────────────
#  TREND SCORE
# ─────────────────────────────────────────────────────────
def trend_score(df: pd.DataFrame):
    r     = df.iloc[-1]; prev = df.iloc[-2]
    price = sf(r["Close"]); ema20=sf(r["EMA20"]); ema50=sf(r["EMA50"])
    ema200=sf(r["EMA200"]); rsi=sf(r["RSI"]); macd=sf(r["MACD"])
    msig  = sf(r["MACD_signal"]); macdh=sf(r["MACD_hist"])
    pmacdh=sf(prev["MACD_hist"]); atr=sf(r["ATR"]); bbpct=sf(r["BB_pct"])

    if None in [price, ema20, ema50, ema200, rsi, macd, msig, atr]:
        return None, 0

    direction = "LONG" if price > ema50 else "SHORT"
    s = 0

    if direction == "LONG":
        if price > ema200: s += 15
        if price > ema50:  s += 12
        if ema20 > ema50:  s += 8
        if price > ema20:  s += 5
    else:
        if price < ema200: s += 15
        if price < ema50:  s += 12
        if ema20 < ema50:  s += 8
        if price < ema20:  s += 5

    if direction == "LONG":
        if 45 < rsi < 70:    s += 20
        elif 35 < rsi <= 45: s += 10
    else:
        if 30 < rsi < 55:    s += 20
        elif 55 <= rsi < 65: s += 10

    if direction == "LONG":
        if macd > msig:  s += 12
        if macdh and pmacdh and macdh > pmacdh: s += 8
    else:
        if macd < msig:  s += 12
        if macdh and pmacdh and macdh < pmacdh: s += 8

    if bbpct is not None and 0.3 < bbpct < 0.7:
        s += 10

    atr_pct = atr / price * 100
    if 0.5 < atr_pct < 3.0:
        s += 10

    return direction, min(s, 100)

# ─────────────────────────────────────────────────────────
#  TRADE LEVELS
# ─────────────────────────────────────────────────────────
def build_levels(price, atr, direction: str):
    if direction == "LONG":
        sl  = price - 1.5 * atr
        tp1 = price + 1.5 * atr
        tp2 = price + 3.0 * atr
        ko  = price - 2.0 * atr
    else:
        sl  = price + 1.5 * atr
        tp1 = price - 1.5 * atr
        tp2 = price - 3.0 * atr
        ko  = price + 2.0 * atr
    rr = abs(tp2 - price) / abs(price - sl)
    return dict(entry=price, sl=sl, tp1=tp1, tp2=tp2, ko=ko, rr=rr)

# ─────────────────────────────────────────────────────────
#  REGEL-ENGINE (Trading-Regeln)
# ─────────────────────────────────────────────────────────
def evaluate_rules(df: pd.DataFrame, direction: str, price: float, atr: float, market: dict):
    reasons = []
    ok = True

    ema20 = sf(df["EMA20"].iloc[-1])
    ema50 = sf(df["EMA50"].iloc[-1])
    ema200 = sf(df["EMA200"].iloc[-1])
    rsi = sf(df["RSI"].iloc[-1])
    macd = sf(df["MACD"].iloc[-1])
    msig = sf(df["MACD_signal"].iloc[-1])
    atr_pct = (atr / price * 100) if price and atr else None

    spy_chg = market.get("SPY_chg")
    qqq_chg = market.get("QQQ_chg")
    vix = market.get("VIX")

    if direction == "LONG":
        if not (price and ema20 and ema50 and ema200 and price > ema20 > ema50 > ema200):
            ok = False
            reasons.append("Trend nicht klar: Kurs/EMAs nicht in sauberer Long-Struktur.")
    else:
        if not (price and ema20 and ema50 and ema200 and price < ema20 < ema50 < ema200):
            ok = False
            reasons.append("Trend nicht klar: Kurs/EMAs nicht in sauberer Short-Struktur.")

    if atr_pct is None or not (0.5 <= atr_pct <= 3.0):
        ok = False
        reasons.append(f"ATR% nicht moderat ({'n/a' if atr_pct is None else f'{atr_pct:.2f}'}).")

    if rsi is None or macd is None or msig is None or not (45 <= rsi <= 60 and macd > msig):
        ok = False
        reasons.append(f"Momentum nicht ideal (RSI {rsi}, MACD vs Signal).")

    if direction == "LONG" and price and ema20 and price < ema20:
        ok = False
        reasons.append("Trendbruch: Kurs unter EMA20.")
    if direction == "SHORT" and price and ema20 and price > ema20:
        ok = False
        reasons.append("Trendbruch: Kurs über EMA20.")

    if vix is not None and vix > 20:
        ok = False
        reasons.append(f"VIX hoch ({vix:.1f}).")

    if rsi is not None and (rsi < 40 or rsi > 70):
        ok = False
        reasons.append(f"Momentum kritisch (RSI {rsi:.1f}).")

    good_market = (
        spy_chg is not None and qqq_chg is not None and vix is not None and
        spy_chg > 0 and qqq_chg > 0 and vix < 20
    )
    if not good_market:
        ok = False
        reasons.append("Marktumfeld nicht ideal (SPY/QQQ nicht grün oder VIX nicht niedrig).")

    return ok, reasons

# ─────────────────────────────────────────────────────────
#  SCAN
# ─────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def run_scan(min_score):
    results = []
    market = market_metrics()
    for ticker in ALL_TICKERS:
        df = load(ticker)
        if df is None or len(df) < 220:
            continue
        df = add_indicators(df)
        direction, ts = trend_score(df)
        if direction is None or ts < min_score:
            continue
        r = df.iloc[-1]
        price = sf(r["Close"]); atr = sf(r["ATR"]); rsi = sf(r["RSI"])
        if not price or not atr:
            continue
        eq, _ = entry_quality(df, direction)
        levels = build_levels(price, atr, direction)
        prev = df[df["Datetime"] < (df["Datetime"].iloc[-1] - pd.Timedelta("23h"))]
        chg = None
        if len(prev):
            p0 = sf(prev.iloc[-1]["Close"])
            if p0:
                chg = (price - p0) / p0 * 100

        rules_ok, reasons = evaluate_rules(df, direction, price, atr, market)

        results.append({
            "Ticker":  ticker,
            "Sektor":  TICKER_TO_SECTOR.get(ticker, "–"),
            "Dir":     direction,
            "Trend":   ts,
            "Entry-Q": eq,
            "Price":   round(price, 2),
            "RSI":     round(rsi, 1) if rsi else None,
            "ATR%":    round(atr / price * 100, 2),
            "RR":      round(levels["rr"], 1),
            "Chg%":    round(chg, 2) if chg else None,
            "Rules_OK": rules_ok,
            "Fail_Reasons": "; ".join(reasons) if reasons else "",
        })
    df_out = pd.DataFrame(results)
    if not df_out.empty:
        df_out = df_out.sort_values(
            ["Rules_OK", "Trend", "Entry-Q"], ascending=[False, False, False]
        ).reset_index(drop=True)
    return df_out

# ─────────────────────────────────────────────────────────
#  CHART
# ─────────────────────────────────────────────────────────
def build_chart(df, levels, direction):
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.60, 0.20, 0.20], vertical_spacing=0.03
    )

    fig.add_trace(go.Candlestick(
        x=df["Datetime"], open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="Preis",
        increasing_fillcolor="#059669", increasing_line_color="#059669",
        decreasing_fillcolor="#ef4444", decreasing_line_color="#ef4444",
    ), row=1, col=1)

    for col, color, w in [("EMA20","#0b5fff",1.2),("EMA50","#6366f1",1.2),("EMA200","#f59e0b",1.0)]:
        fig.add_trace(go.Scatter(
            x=df["Datetime"], y=df[col],
            line=dict(color=color, width=w), name=col, opacity=0.85
        ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df["Datetime"], y=df["BB_upper"],
        line=dict(color="#9ca3af", width=1, dash="dot"), showlegend=False
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df["Datetime"], y=df["BB_lower"],
        line=dict(color="#9ca3af", width=1, dash="dot"),
        fill="tonexty", fillcolor="rgba(156,163,175,0.10)", showlegend=False
    ), row=1, col=1)

    level_cfg = [
        ("entry","ENTRY","#111827","solid"),
        ("sl",   "SL",   "#ef4444","dash"),
        ("tp1",  "TP1",  "#059669","dash"),
        ("tp2",  "TP2",  "#059669","dot"),
        ("ko",   "KO",   "#f59e0b","dash"),
    ]
    for key, label, color, dash in level_cfg:
        v = levels.get(key)
        if v:
            fig.add_hline(
                y=v, line_color=color, line_width=1, line_dash=dash,
                annotation_text=f" {label} {v:.2f}",
                annotation_font_color=color, annotation_font_size=10,
                row=1, col=1
            )

    fig.add_trace(go.Scatter(
        x=df["Datetime"], y=df["RSI"],
        line=dict(color="#0b5fff", width=1.5), name="RSI"
    ), row=2, col=1)
    for lvl, col in [(70,"#ef4444"),(50,"#9ca3af"),(30,"#059669")]:
        fig.add_hline(y=lvl, line_color=col, line_dash="dot", line_width=1, row=2, col=1)

    hist_c = ["#059669" if v >= 0 else "#ef4444" for v in df["MACD_hist"]]
    fig.add_trace(go.Bar(
        x=df["Datetime"], y=df["MACD_hist"],
        marker_color=hist_c, name="Hist", opacity=0.7
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df["Datetime"], y=df["MACD"],
        line=dict(color="#0b5fff", width=1.2), name="MACD"
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df["Datetime"], y=df["MACD_signal"],
        line=dict(color="#f59e0b", width=1.2), name="Signal"
    ), row=3, col=1)

    bg = "#f2f4f6"
    fig.update_layout(
        height=640, paper_bgcolor=bg, plot_bgcolor="#ffffff",
        font=dict(family="IBM Plex Mono", color="#111827", size=10),
        legend=dict(bgcolor="rgba(255,255,255,0.8)", font_size=10, x=0.01, y=0.99),
        margin=dict(l=5, r=5, t=10, b=5),
        xaxis_rangeslider_visible=False, hovermode="x unified",
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor="#e5e7eb", showgrid=True, zeroline=False, row=i, col=1)
        fig.update_yaxes(gridcolor="#e5e7eb", showgrid=True, zeroline=False, row=i, col=1)
    return fig

# ─────────────────────────────────────────────────────────
#  SIDEBAR (KO-Setups static descriptions where position sizer was)
# ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Scanner")
    min_score  = st.slider("Mindest-Trend-Score", 40, 90, 60, 5)
    dir_filter = st.radio("Richtung", ["Alle","LONG","SHORT"], horizontal=True)

    st.markdown("---")
    st.markdown("### 🔰 KO-Setups (Konservativ / Moderat / Aggressiv)")
    st.markdown('<div class="ko-setup"><h4>Konservativ 🛡️</h4><p>Barrier ≈ Preis − 2.5 × ATR · Weit, niedriger Hebel, geringes KO-Risiko.</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="ko-setup"><h4>Moderat ⚖️</h4><p>Barrier ≈ Preis − 1.5 × ATR · Ausgewogenes Verhältnis Risiko/Ertrag.</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="ko-setup"><h4>Aggressiv ⚡</h4><p>Barrier ≈ Preis − 0.7 × ATR · Eng, hoher Hebel, hohes KO-Risiko.</p></div>', unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🔄 Neu laden"):
        st.cache_data.clear()
        st.rerun()

    st.markdown('<p style="font-size:0.72rem;color:#6b7280;">Daten alle 5 min gecacht · EUR/USD auto</p>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────────────────
eur_usd = get_eur_usd()
st.markdown(f"""
<div class="topbar">
  <span class="topbar-title">📡 TRADING SCANNER</span>
  <span class="topbar-sub">{datetime.now().strftime('%H:%M:%S')} &nbsp;|&nbsp;
  {len(ALL_TICKERS)} Ticker &nbsp;|&nbsp; EUR/USD {eur_usd:.4f}</span>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
#  SCAN + FILTER
# ─────────────────────────────────────────────────────────
with st.spinner("Scanner läuft …"):
    results = run_scan(min_score)

if dir_filter == "LONG":
    results = results[results["Dir"] == "LONG"].reset_index(drop=True)
elif dir_filter == "SHORT":
    results = results[results["Dir"] == "SHORT"].reset_index(drop=True)

# ─────────────────────────────────────────────────────────
#  SUMMARY
# ─────────────────────────────────────────────────────────
if results.empty:
    lc = sc = aq = 0
    tp = "–"
else:
    lc = len(results[results["Dir"] == "LONG"])
    sc = len(results[results["Dir"] == "SHORT"])
    aq = int(results["Entry-Q"].mean())
    tp = results.iloc[0]["Ticker"]

st.markdown(f"""
<div class="metric-row">
  <div class="metric"><div class="mlabel">Signale</div><div class="mvalue blue">{len(results)}</div></div>
  <div class="metric"><div class="mlabel">LONG</div><div class="mvalue green">{lc}</div></div>
  <div class="metric"><div class="mlabel">SHORT</div><div class="mvalue red">{sc}</div></div>
  <div class="metric"><div class="mlabel">Ø Entry-Q</div><div class="mvalue">{aq}</div></div>
  <div class="metric"><div class="mlabel">Top Signal</div><div class="mvalue blue">{tp}</div></div>
</div>
""", unsafe_allow_html=True)

if results.empty:
    st.info(f"Keine Signale bei Score ≥ {min_score}. Filter lockern?")
    st.stop()

# ─────────────────────────────────────────────────────────
#  TABLE (kompatibel, without Styler applymap issues)
# ─────────────────────────────────────────────────────────
disp = results[["Ticker","Sektor","Dir","Trend","Entry-Q","Price","RSI","ATR%","RR","Chg%","Rules_OK"]].copy()

def color_dir_html(v):
    if v == "LONG":
        return '<span style="color:#0b5fff;font-weight:600">LONG</span>'
    if v == "SHORT":
        return '<span style="color:#ef4444;font-weight:600">SHORT</span>'
    return str(v)

def color_trend_html(v):
    try:
        vv = float(v)
    except Exception:
        return str(v)
    if vv >= 80:
        return f'<span style="color:#059669;font-weight:600">{int(vv)}</span>'
    if vv >= 65:
        return f'<span style="color:#0b5fff">{int(vv)}</span>'
    return f"{int(vv)}"

def color_entry_html(v):
    try:
        vv = float(v)
    except Exception:
        return str(v)
    if vv >= 70:
        return f'<span style="color:#059669;font-weight:600">{int(vv)}</span>'
    if vv >= 50:
        return f'<span style="color:#f59e0b">{int(vv)}</span>'
    return f'<span style="color:#ef4444">{int(vv)}</span>'

def color_chg_html(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    try:
        vv = float(v)
    except Exception:
        return str(v)
    if vv > 0:
        return f'<span style="color:#059669">+{vv:.2f}%</span>'
    return f'<span style="color:#ef4444">{vv:.2f}%</span>'

def color_rules_html(v):
    if v:
        return '<span style="background:#ecfdf5;color:#065f46;padding:3px 6px;border-radius:4px;">OK</span>'
    return '<span style="background:#fef2f2;color:#7f1d1d;padding:3px 6px;border-radius:4px;">FAIL</span>'

table = pd.DataFrame({
    "Ticker": disp["Ticker"],
    "Sektor": disp["Sektor"],
    "Dir": disp["Dir"].apply(color_dir_html),
    "Trend": disp["Trend"].apply(color_trend_html),
    "Entry-Q": disp["Entry-Q"].apply(color_entry_html),
    "Price": disp["Price"].apply(lambda x: f"{x:.2f}"),
    "RSI": disp["RSI"].apply(lambda x: f"{x:.1f}" if x is not None else "–"),
    "ATR%": disp["ATR%"].apply(lambda x: f"{x:.2f}%"),
    "RR": disp["RR"].apply(lambda x: f"{x:.1f}"),
    "Chg%": disp["Chg%"].apply(color_chg_html),
    "Rules": disp["Rules_OK"].apply(color_rules_html),
})

st.markdown(table.to_html(escape=False, index=False), unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
#  DETAIL VIEW (KO proposals removed)
# ─────────────────────────────────────────────────────────
selected = st.selectbox("Detailansicht Ticker", options=list(results["Ticker"]), index=0)
df_detail = load(selected)
if df_detail is None:
    st.warning("Keine Detaildaten für diesen Ticker.")
else:
    df_detail = add_indicators(df_detail)
    direction, ts = trend_score(df_detail)
    eq_score, eq_sigs = entry_quality(df_detail, direction)
    last = df_detail.iloc[-1]
    price = sf(last["Close"]); atr = sf(last["ATR"])
    levels = build_levels(price, atr, direction)

    st.markdown(f"### {selected} – {direction} – TrendScore {ts} – EntryQ {eq_score}")
    fig = build_chart(df_detail, levels, direction)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Entry-Qualität")
    pills = []
    for txt, kind in eq_sigs:
        cls = "pill-green" if kind == "good" else ("pill-orange" if kind == "neutral" else "pill-red")
        pills.append(f'<span class="pill {cls}">{txt}</span>')
    st.markdown(" ".join(pills), unsafe_allow_html=True)

    st.markdown("#### Regel-Check (Scan)")
    row = results[results["Ticker"] == selected].iloc[0]
    if row["Rules_OK"]:
        st.success("Alle definierten Trading-Regeln sind erfüllt – Setup statistisch robust.")
    else:
        st.error("Nicht alle Trading-Regeln erfüllt – kein sauberes KO-Setup.")
        if row["Fail_Reasons"]:
            st.write(row["Fail_Reasons"])
