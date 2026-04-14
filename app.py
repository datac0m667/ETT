"""
Trading Scanner v3 – Entry Precision + KO-Zertifikat Panel (refactored)
Starten: streamlit run scanner.py
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
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

  html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0d0f14; color: #c9d1d9;
  }
  .main, [data-testid="stAppViewContainer"] { background-color: #0d0f14; }
  [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #21262d; }

  h1,h2,h3 { font-family: 'IBM Plex Mono', monospace; color: #58a6ff; }

  .topbar {
    display:flex; align-items:baseline; gap:14px;
    border-bottom: 1px solid #21262d; padding-bottom:12px; margin-bottom:20px;
  }
  .topbar-title { font-family:'IBM Plex Mono',monospace; font-size:1.35rem; font-weight:600; color:#58a6ff; }
  .topbar-sub   { font-size:0.75rem; color:#484f58; }

  .metric-row { display:flex; gap:10px; margin-bottom:16px; flex-wrap:wrap; }
  .metric { background:#161b22; border:1px solid #21262d; border-radius:8px; padding:10px 16px; flex:1; min-width:90px; }
  .mlabel { font-size:0.65rem; text-transform:uppercase; letter-spacing:1px; color:#484f58; }
  .mvalue { font-family:'IBM Plex Mono',monospace; font-size:1.2rem; font-weight:600; color:#c9d1d9; margin-top:2px; }
  .green  { color:#3fb950 !important; } .red { color:#f85149 !important; }
  .blue   { color:#58a6ff !important; } .orange { color:#ffa657 !important; }

  .card {
    background:#161b22; border:1px solid #21262d;
    border-radius:8px; padding:14px 18px; margin-bottom:14px;
  }
  .card-title { font-size:0.68rem; text-transform:uppercase; letter-spacing:1px; color:#484f58; margin-bottom:8px; }

  .level-row {
    display:flex; justify-content:space-between; align-items:center;
    padding:6px 0; border-bottom:1px solid #21262d;
    font-family:'IBM Plex Mono',monospace; font-size:0.82rem;
  }
  .level-row:last-child { border-bottom:none; }
  .llabel { color:#484f58; font-size:0.72rem; }

  .badge {
    display:inline-block; padding:2px 10px; border-radius:12px;
    font-family:'IBM Plex Mono',monospace; font-size:0.72rem; font-weight:600;
  }
  .long-b  { background:#1a3d26; color:#3fb950; border:1px solid #2ea043; }
  .short-b { background:#3d1a1a; color:#f85149; border:1px solid #da3633; }

  .ko-card {
    background:#161b22; border:1px solid #21262d; border-radius:8px;
    padding:12px 16px; margin-bottom:10px;
  }
  .ko-tag { font-size:0.65rem; text-transform:uppercase; letter-spacing:1px; margin-bottom:6px; }
  .ko-grid { display:grid; grid-template-columns:1fr 1fr; gap:4px 16px; font-size:0.78rem; }
  .ko-key  { color:#484f58; } .ko-val { font-family:'IBM Plex Mono',monospace; color:#c9d1d9; text-align:right; }

  .entry-quality {
    display:flex; align-items:flex-start; gap:10px;
    background:#161b22; border:1px solid #21262d; border-radius:8px; padding:12px 16px; margin-bottom:14px;
  }
  .eq-score { font-family:'IBM Plex Mono',monospace; font-size:2rem; font-weight:600; }
  .eq-label { font-size:0.65rem; color:#484f58; text-transform:uppercase; letter-spacing:1px; }

  .pill {
    display:inline-block; padding:1px 8px; border-radius:10px;
    font-size:0.67rem; margin:2px 2px 2px 0;
  }
  .pill-green  { background:#1a3d26; color:#3fb950; }
  .pill-red    { background:#3d1a1a; color:#f85149; }
  .pill-orange { background:#3d2e1a; color:#ffa657; }

  .link-btn {
    display:inline-block; padding:6px 14px; border-radius:6px;
    background:#1f2937; border:1px solid #30363d; color:#58a6ff;
    font-size:0.78rem; text-decoration:none; margin-right:6px; margin-top:4px;
  }

  div.stButton > button {
    background:#161b22; border:1px solid #30363d; color:#c9d1d9;
    border-radius:6px; font-size:0.82rem; transition:all 0.15s;
  }
  div.stButton > button:hover { border-color:#58a6ff; color:#58a6ff; }

  #MainMenu, footer, header { visibility:hidden; }
  .block-container { padding-top:1.5rem; }
  [data-testid="stDataFrame"] { border:1px solid #21262d; border-radius:8px; overflow:hidden; }
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

    # 1) Pullback zur EMA20
    dist = abs(price - ema20) / atr
    if dist < 0.4:
        score += 25; sigs.append(("Nahe EMA20 – idealer Pullback", "good"))
    elif dist < 0.8:
        score += 12; sigs.append(("Moderat von EMA20 entfernt", "neutral"))
    else:
        sigs.append(("Weit von EMA20 – Extended Move", "bad"))

    # 2) RSI-Zone
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

    # 3) MACD dreht in Trade-Richtung
    if macdh is not None and pmacdh is not None:
        if direction == "LONG" and macdh > pmacdh:
            score += 20; sigs.append(("MACD Hist dreht bullisch", "good"))
        elif direction == "SHORT" and macdh < pmacdh:
            score += 20; sigs.append(("MACD Hist dreht bärisch", "good"))
        else:
            sigs.append(("MACD läuft gegen Richtung", "bad"))

    # 4) Volatilität komprimiert
    if atr5 and atr:
        rv = atr5 / atr
        if rv < 0.8:
            score += 15; sigs.append(("Volatilität komprimiert", "good"))
        elif rv < 1.2:
            score += 7; sigs.append(("Volatilität normal", "neutral"))
        else:
            sigs.append(("Hohe kurzfristige Volatilität", "bad"))

    # 5) Volumen
    if vol and volavg and volavg > 0:
        vr = vol / volavg
        if vr > 1.3:
            score += 10; sigs.append((f"Volumen +{(vr-1)*100:.0f}% – Bestätigung", "good"))
        elif vr < 0.6:
            sigs.append(("Volumen dünn – schwache Bestätigung", "bad"))
        else:
            score += 5; sigs.append(("Volumen normal", "neutral"))

    # 6) Bollinger-Position
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

    if bbpct is not None:
        if 0.3 < bbpct < 0.7:
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
#  KO-ZERTIFIKAT VORSCHLÄGE
# ─────────────────────────────────────────────────────────
def ko_proposals(price, atr, direction, eur_usd):
    """
    3 Vorschläge: konservativ / moderat / aggressiv.
    Standard-Bezugsverhältnis US-Aktien: 0.10 (10 Zertifikate = 1 Aktie in USD).
    Zertifikatskurs ≈ (Kurs - Strike) × Ratio / EUR_USD
    """
    ratio = 0.10
    configs = [
        ("Konservativ 🛡️", 2.5, "#3fb950", "Weite Barrier – niedriger Hebel, geringe KO-Gefahr"),
        ("Moderat ⚖️",      1.5, "#58a6ff", "Ausgewogen – empfohlener Standardansatz"),
        ("Aggressiv ⚡",     0.7, "#ffa657", "Enge Barrier – hoher Hebel, erhöhtes KO-Risiko"),
    ]
    proposals = []
    for name, mult, color, desc in configs:
        if direction == "LONG":
            barrier = price - mult * atr
            strike  = barrier * 0.99
        else:
            barrier = price + mult * atr
            strike  = barrier * 1.01

        abstand_pct = abs(price - barrier) / price * 100
        hebel       = price / abs(price - strike)
        cert_price  = abs(price - strike) * ratio / eur_usd

        proposals.append({
            "name": name, "color": color, "desc": desc,
            "barrier": round(barrier, 2), "strike": round(strike, 2),
            "abstand": round(abstand_pct, 1),
            "hebel":   round(hebel, 1),
            "cert_price": round(cert_price, 2),
            "ratio": ratio, "direction": direction,
        })
    return proposals

def search_links(ticker, direction):
    typ = "call" if direction == "LONG" else "put"
    TYP = "CALL" if direction == "LONG" else "PUT"
    return {
        "Boerse Stuttgart": f"https://www.boerse-stuttgart.de/de-de/produkte/hebelprodukte/knockouts/?underlying={ticker}&producttype=knock-out-{typ}",
        "OnVista":          f"https://www.onvista.de/derivate/knock-out?type={TYP}&underlying={quote(ticker)}",
        "Comdirect":        f"https://www.comdirect.de/inf/derivate/knockouts.html?SEARCH_VALUE={ticker}&KNOCK_OUT_TYPE={typ.upper()}",
        "DZ Bank":          f"https://www.dzbank-derivate.de/Aktuell/Suche?underlying={ticker}&type={typ}",
    }

# ─────────────────────────────────────────────────────────
#  POSITION SIZER
# ─────────────────────────────────────────────────────────
def position_size(capital_eur, risk_pct, price, sl, cert_price, ratio, eur_usd):
    risk_eur      = capital_eur * risk_pct / 100
    sl_dist_usd   = abs(price - sl)
    sl_dist_cert  = sl_dist_usd * ratio / eur_usd
    if sl_dist_cert <= 0:
        return {}
    anzahl        = int(risk_eur / sl_dist_cert)
    invest_eur    = anzahl * cert_price
    return {
        "risk_eur":   round(risk_eur, 2),
        "anzahl":     anzahl,
        "invest_eur": round(invest_eur, 2),
        "max_loss":   round(anzahl * cert_price, 2),
    }

# ─────────────────────────────────────────────────────────
#  SCAN
# ─────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def run_scan(min_score):
    results = []
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
        })
    df_out = pd.DataFrame(results)
    if not df_out.empty:
        df_out = df_out.sort_values(["Trend", "Entry-Q"], ascending=False).reset_index(drop=True)
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
        increasing_fillcolor="#3fb950", increasing_line_color="#3fb950",
        decreasing_fillcolor="#f85149", decreasing_line_color="#f85149",
    ), row=1, col=1)

    for col, color, w in [("EMA20","#58a6ff",1.2),("EMA50","#d2a8ff",1.2),("EMA200","#ffa657",1.0)]:
        fig.add_trace(go.Scatter(
            x=df["Datetime"], y=df[col],
            line=dict(color=color, width=w), name=col, opacity=0.85
        ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df["Datetime"], y=df["BB_upper"],
        line=dict(color="#484f58", width=1, dash="dot"), showlegend=False
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df["Datetime"], y=df["BB_lower"],
        line=dict(color="#484f58", width=1, dash="dot"),
        fill="tonexty", fillcolor="rgba(72,79,88,0.07)", showlegend=False
    ), row=1, col=1)

    level_cfg = [
        ("entry","ENTRY","#c9d1d9","solid"),
        ("sl",   "SL",   "#f85149","dash"),
        ("tp1",  "TP1",  "#3fb950","dash"),
        ("tp2",  "TP2",  "#3fb950","dot"),
        ("ko",   "KO",   "#ffa657","dash"),
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
        line=dict(color="#58a6ff", width=1.5), name="RSI"
    ), row=2, col=1)
    for lvl, col in [(70,"#f85149"),(50,"#484f58"),(30,"#3fb950")]:
        fig.add_hline(y=lvl, line_color=col, line_dash="dot", line_width=1, row=2, col=1)

    hist_c = ["#3fb950" if v >= 0 else "#f85149" for v in df["MACD_hist"]]
    fig.add_trace(go.Bar(
        x=df["Datetime"], y=df["MACD_hist"],
        marker_color=hist_c, name="Hist", opacity=0.7
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df["Datetime"], y=df["MACD"],
        line=dict(color="#58a6ff", width=1.2), name="MACD"
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df["Datetime"], y=df["MACD_signal"],
        line=dict(color="#ffa657", width=1.2), name="Signal"
    ), row=3, col=1)

    bg = "#0d0f14"
    fig.update_layout(
        height=680, paper_bgcolor=bg, plot_bgcolor=bg,
        font=dict(family="IBM Plex Mono", color="#c9d1d9", size=10),
        legend=dict(bgcolor="rgba(0,0,0,0)", font_size=10, x=0.01, y=0.99),
        margin=dict(l=5, r=5, t=10, b=5),
        xaxis_rangeslider_visible=False, hovermode="x unified",
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor="#21262d", showgrid=True, zeroline=False, row=i, col=1)
        fig.update_yaxes(gridcolor="#21262d", showgrid=True, zeroline=False, row=i, col=1)
    return fig

# ─────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Scanner")
    min_score  = st.slider("Mindest-Trend-Score", 40, 90, 60, 5)
    dir_filter = st.radio("Richtung", ["Alle","LONG","SHORT"], horizontal=True)

    st.markdown("---")
    st.markdown("### 💰 Positionsrechner")
    capital  = st.number_input("Kapital (€)", value=10000, step=500)
    risk_pct = st.slider("Risiko pro Trade (%)", 0.5, 5.0, 1.0, 0.5)
    st.markdown(f"**Max. Risiko: {capital*risk_pct/100:.0f} €**")

    st.markdown("---")
    if st.button("🔄 Neu laden"):
        st.cache_data.clear()
        st.rerun()

    st.markdown(
        '<p style="font-size:0.72rem;color:#484f58;">Daten alle 5 min gecacht · EUR/USD auto</p>',
        unsafe_allow_html=True
    )

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
#  TABLE (Styler mit .map statt .applymap)
# ─────────────────────────────────────────────────────────
disp = results[["Ticker","Sektor","Dir","Trend","Entry-Q","Price","RSI","ATR%","RR","Chg%"]].copy()

def sd(v):
    if v == "LONG":
        return "color:#3fb950;font-weight:600"
    if v == "SHORT":
        return "color:#f85149;font-weight:600"
    return ""

def ss(v):
    if v >= 80:
        return "color:#3fb950;font-weight:600"
    if v >= 65:
        return "color:#58a6ff"
    return ""

def se(v):
    if v >= 70:
        return "color:#3fb950;font-weight:600"
    if v >= 50:
        return "color:#ffa657"
    return "color:#f85149"

def sc2(v):
    if v is None:
        return ""
    return "color:#3fb950" if v > 0 else "color:#f85149"

styled = (
    disp.style
    .map(sd,  subset=["Dir"])
    .map(ss,  subset=["Trend"])
    .map(se,  subset=["Entry-Q"])
    .map(sc2, subset=["Chg%"])
    .format({
        "Price": "{:.2f}",
        "RSI":   "{:.1f}",
        "ATR%":  "{:.2f}%",
        "RR":    "{:.1f}",
        "Chg%":  lambda x: f"{x:+.2f}%" if x is not None else "–",
    })
    .set_properties(**{"background-color": "#161b22", "color": "#c9d1d9"})
)

event = st.dataframe(
    styled,
    use_container_width=True,
    selection_mode="single-row",
    on_select="rerun",
    height=min(420, 42 + len(disp) * 38),
)

# ─────────────────────────────────────────────────────────
#  DETAIL VIEW
# ─────────────────────────────────────────────────────────
selection = event.selection
if selection and "rows" in selection and len(selection["rows"]) > 0:
    idx = selection["rows"][0]
    row = results.iloc[idx]
    ticker = row["Ticker"]
else:
    ticker = results.iloc[0]["Ticker"]

df_detail = load(ticker)
if df_detail is None or len(df_detail) < 220:
    st.warning(f"Keine Detaildaten für {ticker}.")
    st.stop()

df_detail = add_indicators(df_detail)
direction, ts = trend_score(df_detail)
eq_score, eq_sigs = entry_quality(df_detail, direction)
last = df_detail.iloc[-1]
price = sf(last["Close"])
atr   = sf(last["ATR"])
levels = build_levels(price, atr, direction)
proposals = ko_proposals(price, atr, direction, eur_usd)
links = search_links(ticker, direction)

col_left, col_right = st.columns([2, 1])

with col_left:
    st.markdown(f"### {ticker} – Detailansicht")
    fig = build_chart(df_detail, levels, direction)
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.markdown("### Setup & Levels")

    badge_cls = "long-b" if direction == "LONG" else "short-b"
    st.markdown(f"""
    <div class="card">
      <div class="card-title">Trend</div>
      <span class="badge {badge_cls}">{direction}</span>
      <div style="margin-top:8px;font-size:0.8rem;">
        Trend-Score: <b>{ts}</b><br/>
        Entry-Quality: <b>{eq_score}</b>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="card"><div class="card-title">Trade Levels</div>', unsafe_allow_html=True)
    for label, key in [("Entry", "entry"), ("Stop-Loss", "sl"), ("TP1", "tp1"), ("TP2", "tp2"), ("KO-Referenz", "ko")]:
        v = levels.get(key)
        st.markdown(
            f"""
            <div class="level-row">
              <span class="llabel">{label}</span>
              <span>{v:.2f}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="entry-quality">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="eq-score">{eq_score}</div>
        <div>
          <div class="eq-label">Entry-Qualität</div>
          <div style="margin-top:4px;font-size:0.78rem;">
        """,
        unsafe_allow_html=True,
    )
    for txt, t in eq_sigs:
        cls = "pill-green" if t == "good" else ("pill-orange" if t == "neutral" else "pill-red")
        st.markdown(f'<span class="pill {cls}">{txt}</span>', unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

    st.markdown("### KO-Zertifikate")
    for p in proposals:
        st.markdown(
            f"""
            <div class="ko-card">
              <div class="ko-tag" style="color:{p['color']};">{p['name']}</div>
              <div style="font-size:0.75rem;margin-bottom:6px;">{p['desc']}</div>
              <div class="ko-grid">
                <span class="ko-key">Barrier</span><span class="ko-val">{p['barrier']}</span>
                <span class="ko-key">Strike</span><span class="ko-val">{p['strike']}</span>
                <span class="ko-key">Abstand</span><span class="ko-val">{p['abstand']}%</span>
                <span class="ko-key">Hebel</span><span class="ko-val">{p['hebel']}x</span>
                <span class="ko-key">Preis (ca.)</span><span class="ko-val">{p['cert_price']} €</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Positionsgröße (Beispiel)")
    if proposals:
        p0 = proposals[1] if len(proposals) > 1 else proposals[0]
        ps = position_size(
            capital_eur=capital,
            risk_pct=risk_pct,
            price=price,
            sl=levels["sl"],
            cert_price=p0["cert_price"],
            ratio=p0["ratio"],
            eur_usd=eur_usd,
        )
        if ps:
            st.markdown(
                f"""
                <div class="card">
                  <div class="card-title">Positionsrechner</div>
                  <div style="font-size:0.8rem;">
                    Risiko: <b>{ps['risk_eur']} €</b><br/>
                    Stückzahl: <b>{ps['anzahl']}</b><br/>
                    Investition: <b>{ps['invest_eur']} €</b><br/>
                    Max. Verlust (KO): <b>{ps['max_loss']} €</b>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("### Links zu KO-Suche")
    for name, url in links.items():
        st.markdown(f'<a class="link-btn" href="{url}" target="_blank">{name}</a>', unsafe_allow_html=True)
