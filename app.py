# scanner.py
"""
Trading Scanner – modernized, rules enforced, light UI
Start: streamlit run scanner.py
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from urllib.parse import quote
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Trading Scanner", page_icon="📡", layout="wide")

# ---------- LIGHT THEME (helles Grau) ----------
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
  html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; background-color: #f2f4f6; color: #0f1720; }
  .topbar-title { font-family:'IBM Plex Mono',monospace; color:#0b5fff; font-size:1.3rem; margin-bottom:0.5rem; }
  .card { background:#ffffff; border:1px solid #d1d5db; border-radius:8px; padding:12px; margin-bottom:10px; }
  .metric { background:#ffffff; border:1px solid #e5e7eb; border-radius:8px; padding:10px 14px; }
  .block-container { padding-top:1.2rem; }
  table { border-collapse:collapse; width:100%; font-size:0.9rem; }
  th, td { border:1px solid #e5e7eb; padding:6px 8px; text-align:right; }
  th { background:#f9fafb; text-align:center; }
  td:first-child, th:first-child { text-align:left; }
</style>
""", unsafe_allow_html=True)

# ---------- WATCHLIST ----------
WATCHLIST = {
    "Tech": ["AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","NFLX"],
    "Semis": ["AMD","AVGO","QCOM","INTC","MU","AMAT","LRCX","TXN"],
    "Finance": ["JPM","BAC","GS","MS","V","MA"],
}
ALL_TICKERS = [t for g in WATCHLIST.values() for t in g]
TICKER_TO_SECTOR = {t: s for s, ts in WATCHLIST.items() for t in ts}
EUR_USD_FALLBACK = 1.09

# ---------- HELPERS ----------
def sf(x):
    try:
        if isinstance(x, pd.Series):
            x = x.iloc[0]
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None

def flatten(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df.loc[:, ~df.columns.duplicated()]

def to_series(df, col):
    s = df[col]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return pd.to_numeric(s, errors="coerce")

# ---------- DATA ----------
@st.cache_data(ttl=300, show_spinner=False)
def load(ticker):
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

# ---------- INDICATORS ----------
def add_indicators(df):
    df = df.copy()
    c = df["Close"]

    df["EMA20"]  = c.ewm(span=20,  adjust=False).mean()
    df["EMA50"]  = c.ewm(span=50,  adjust=False).mean()
    df["EMA200"] = c.ewm(span=200, adjust=False).mean()

    prev = c.shift(1)
    tr = pd.concat([df["High"]-df["Low"],
                    (df["High"]-prev).abs(),
                    (df["Low"]-prev).abs()], axis=1).max(axis=1)
    df["ATR"]  = tr.rolling(14).mean()
    df["ATR5"] = tr.rolling(5).mean()

    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100/(1+rs))

    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["MACD"]        = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"]   = df["MACD"] - df["MACD_signal"]

    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    df["BB_upper"] = sma20 + 2*std20
    df["BB_lower"] = sma20 - 2*std20
    df["BB_pct"]   = (c - df["BB_lower"]) / (df["BB_upper"] - df["BB_lower"])

    df["Vol_avg"] = df["Volume"].rolling(20).mean()

    return df.dropna()

# ---------- RULE CHECKS ----------
def market_metrics():
    try:
        spy = yf.download("SPY", period="10d", interval="1d", progress=False)
        qqq = yf.download("QQQ", period="10d", interval="1d", progress=False)
        vix = yf.download("^VIX", period="10d", interval="1d", progress=False)
        spy = flatten(spy); qqq = flatten(qqq); vix = flatten(vix)
        return {
            "SPY_close": sf(spy["Close"].iloc[-1]) if not spy.empty else None,
            "QQQ_close": sf(qqq["Close"].iloc[-1]) if not qqq.empty else None,
            "VIX":       sf(vix["Close"].iloc[-1]) if not vix.empty else None,
        }
    except Exception:
        return {"SPY_close":None,"QQQ_close":None,"VIX":None}

def evaluate_rules(df, direction, price, atr, proposals, eur_usd, market):
    reasons = []
    ok = True

    ema20 = sf(df["EMA20"].iloc[-1]); ema50 = sf(df["EMA50"].iloc[-1]); ema200 = sf(df["EMA200"].iloc[-1])
    if direction == "LONG":
        if not (ema20 and ema50 and ema200 and ema20 > ema50 > ema200):
            ok = False; reasons.append("Trend nicht sauber (EMA20>EMA50>EMA200 fehlt)")
    else:
        if not (ema20 and ema50 and ema200 and ema20 < ema50 < ema200):
            ok = False; reasons.append("Trend nicht sauber (EMA20<EMA50<EMA200 fehlt)")

    atr_pct = (atr/price*100) if price and atr else None
    if atr_pct is None or not (0.5 < atr_pct < 3.0):
        ok = False; reasons.append(f"ATR% außerhalb Bereich (aktuell {atr_pct})")

    if market.get("VIX") and market["VIX"] > 20:
        ok = False; reasons.append(f"VIX hoch ({market['VIX']:.1f})")

    rsi = sf(df["RSI"].iloc[-1]); macd = sf(df["MACD"].iloc[-1]); msig = sf(df["MACD_signal"].iloc[-1])
    if rsi is None or macd is None or msig is None or not (45 <= rsi <= 60 and macd > msig):
        ok = False; reasons.append(f"Momentum nicht ideal (RSI {rsi}, MACD>Signal?)")

    if proposals:
        p = proposals[1] if len(proposals) > 1 else proposals[0]
        barrier = p["barrier"]; dist = abs(price - barrier)
        if dist < 1.2 * atr:
            ok = False; reasons.append(f"KO zu nah (Abstand {dist:.2f} < 1.2*ATR)")
        if not (4.5 <= p["hebel"] <= 9):
            reasons.append(f"Hebel ausserhalb 4.5-9 (hebel {p['hebel']})")
    else:
        ok = False; reasons.append("Keine KO‑Vorschläge verfügbar")

    return ok, reasons

# ---------- KO proposals & position sizing ----------
def ko_proposals(price, atr, direction, eur_usd):
    ratio = 0.10
    configs = [
        ("Konservativ", 2.5, "#3fb950", "weit"),
        ("Moderat", 1.5, "#58a6ff", "ausgewogen"),
        ("Aggressiv", 0.7, "#ffa657", "eng"),
    ]
    proposals = []
    for name, mult, color, desc in configs:
        if direction == "LONG":
            barrier = price - mult * atr
            strike = barrier * 0.99
        else:
            barrier = price + mult * atr
            strike = barrier * 1.01

        abstand_pct = abs(price - barrier) / price * 100
        hebel = price / max(abs(price - strike), 1e-9)
        cert_price = abs(price - strike) * ratio / eur_usd

        proposals.append({
            "name": name, "color": color, "desc": desc,
            "barrier": round(barrier, 2), "strike": round(strike, 2),
            "abstand": round(abstand_pct, 1),
            "hebel": round(hebel, 1),
            "cert_price": round(cert_price, 2),
            "ratio": ratio
        })
    return proposals

def position_size(capital_eur, risk_pct, price, sl, cert_price, ratio, eur_usd):
    risk_eur = capital_eur * risk_pct / 100
    sl_dist_usd = abs(price - sl)
    sl_dist_cert = sl_dist_usd * ratio / eur_usd
    if sl_dist_cert <= 0:
        return {}
    anzahl = int(risk_eur / sl_dist_cert)
    invest_eur = anzahl * cert_price
    return {
        "risk_eur": round(risk_eur, 2),
        "anzahl": anzahl,
        "invest_eur": round(invest_eur, 2),
        "max_loss": round(anzahl * cert_price, 2),
    }

# ---------- TREND SCORE & ENTRY QUALITY ----------
def trend_score(df):
    r = df.iloc[-1]; prev = df.iloc[-2]
    price = sf(r["Close"]); ema20 = sf(r["EMA20"]); ema50 = sf(r["EMA50"]); ema200 = sf(r["EMA200"])
    rsi = sf(r["RSI"]); macd = sf(r["MACD"]); msig = sf(r["MACD_signal"]); atr = sf(r["ATR"]); bbpct = sf(r["BB_pct"])

    if None in [price, ema20, ema50, ema200, rsi, macd, msig, atr]:
        return None, 0

    direction = "LONG" if price > ema50 else "SHORT"
    s = 0

    if direction == "LONG":
        if price > ema200: s += 15
        if price > ema50: s += 12
        if ema20 > ema50: s += 8
        if price > ema20: s += 5
    else:
        if price < ema200: s += 15
        if price < ema50: s += 12
        if ema20 < ema50: s += 8
        if price < ema20: s += 5

    if direction == "LONG":
        if 45 < rsi < 70: s += 20
        elif 35 < rsi <= 45: s += 10
    else:
        if 30 < rsi < 55: s += 20
        elif 55 <= rsi < 65: s += 10

    if direction == "LONG":
        if macd > msig: s += 12
    else:
        if macd < msig: s += 12

    if bbpct is not None and 0.3 < bbpct < 0.7: s += 10

    atr_pct = atr / price * 100
    if 0.5 < atr_pct < 3.0: s += 10

    return direction, min(s, 100)

def entry_quality(df, direction):
    r = df.iloc[-1]; prev = df.iloc[-2]
    price = sf(r["Close"]); ema20 = sf(r["EMA20"]); atr = sf(r["ATR"])
    atr5 = sf(r["ATR5"]); rsi = sf(r["RSI"])
    macdh = sf(r["MACD_hist"]); pmacdh = sf(prev["MACD_hist"])
    bbpct = sf(r["BB_pct"]); vol = sf(r["Volume"]); volavg = sf(r["Vol_avg"])

    if None in [price, ema20, atr, rsi]:
        return 0, []

    score = 0
    sigs = []

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

# ---------- SCAN ----------
@st.cache_data(ttl=300, show_spinner=False)
def run_scan(min_score, eur_usd):
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
        proposals = ko_proposals(price, atr, direction, eur_usd)
        ok, reasons = evaluate_rules(df, direction, price, atr, proposals, eur_usd, market)
        prev = df[df["Datetime"] < (df["Datetime"].iloc[-1] - pd.Timedelta("23h"))]
        chg = None
        if len(prev):
            p0 = sf(prev.iloc[-1]["Close"])
            if p0:
                chg = (price - p0) / p0 * 100
        results.append({
            "Ticker": ticker,
            "Sektor": TICKER_TO_SECTOR.get(ticker, "–"),
            "Dir": direction,
            "Trend": ts,
            "Entry-Q": eq,
            "Price": round(price, 2),
            "RSI": round(rsi, 1) if rsi else None,
            "ATR%": round(atr/price*100, 2),
            "RR": 3.0,
            "Chg%": round(chg, 2) if chg else None,
            "Rules_OK": ok,
            "Fail_Reasons": "; ".join(reasons) if reasons else ""
        })
    df_out = pd.DataFrame(results)
    if not df_out.empty:
        df_out = df_out.sort_values(["Rules_OK", "Trend", "Entry-Q"], ascending=[False, False, False]).reset_index(drop=True)
    return df_out

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("### ⚙️ Scanner")
    min_score = st.slider("Mindest-Trend-Score", 40, 90, 60, 5)
    dir_filter = st.radio("Richtung", ["Alle","LONG","SHORT"], horizontal=True)
    st.markdown("---")
    capital = st.number_input("Kapital (€)", value=10000, step=500)
    risk_pct = st.slider("Risiko pro Trade (%)", 0.5, 5.0, 1.0, 0.5)
    st.markdown(f"**Max. Risiko: {capital*risk_pct/100:.0f} €**")
    if st.button("🔄 Neu laden"):
        st.cache_data.clear()
        st.rerun()

# ---------- RUN SCAN ----------
eur_usd = get_eur_usd()
st.markdown(
    f"<div class='topbar-title'>📡 TRADING SCANNER — {datetime.now().strftime('%H:%M:%S')} | EUR/USD {eur_usd:.4f}</div>",
    unsafe_allow_html=True
)
with st.spinner("Scanner läuft …"):
    results = run_scan(min_score, eur_usd)

if dir_filter == "LONG":
    results = results[results["Dir"] == "LONG"].reset_index(drop=True)
elif dir_filter == "SHORT":
    results = results[results["Dir"] == "SHORT"].reset_index(drop=True)

# ---------- SUMMARY ----------
if results.empty:
    st.info("Keine Signale gefunden.")
    st.stop()

st.markdown(
    f"<div class='card'><b>Signale:</b> {len(results)} — <b>Regeln erfüllt:</b> {results['Rules_OK'].sum()}</div>",
    unsafe_allow_html=True
)

# ---------- TABLE (ohne Styler, mit HTML-Farben) ----------
def color_dir(v):
    if v == "LONG":
        return '<span style="color:#0b5fff;font-weight:600">LONG</span>'
    if v == "SHORT":
        return '<span style="color:#ef4444;font-weight:600">SHORT</span>'
    return str(v)

def color_trend(v):
    try:
        v = float(v)
    except Exception:
        return str(v)
    if v >= 80:
        return f'<span style="color:#059669;font-weight:600">{v:.0f}</span>'
    if v >= 65:
        return f'<span style="color:#0b5fff">{v:.0f}</span>'
    return f"{v:.0f}"

def color_entry(v):
    try:
        v = float(v)
    except Exception:
        return str(v)
    if v >= 70:
        return f'<span style="color:#059669;font-weight:600">{v:.0f}</span>'
    if v >= 50:
        return f'<span style="color:#f59e0b">{v:.0f}</span>'
    return f'<span style="color:#ef4444">{v:.0f}</span>'

def color_chg(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    try:
        v = float(v)
    except Exception:
        return str(v)
    if v > 0:
        return f'<span style="color:#059669">+{v:.2f}%</span>'
    return f'<span style="color:#ef4444">{v:.2f}%</span>'

def color_rules(v):
    if v:
        return '<span style="background:#ecfdf5;color:#065f46;padding:3px 6px;border-radius:4px;">OK</span>'
    return '<span style="background:#fff1f2;color:#7f1d1d;padding:3px 6px;border-radius:4px;">FAIL</span>'

table = pd.DataFrame({
    "Ticker": results["Ticker"],
    "Sektor": results["Sektor"],
    "Dir": results["Dir"].apply(color_dir),
    "Trend": results["Trend"].apply(color_trend),
    "Entry-Q": results["Entry-Q"].apply(color_entry),
    "Price": results["Price"].apply(lambda x: f"{x:.2f}"),
    "RSI": results["RSI"].apply(lambda x: f"{x:.1f}" if x is not None else "–"),
    "ATR%": results["ATR%"].apply(lambda x: f"{x:.2f}%"),
    "RR": results["RR"].apply(lambda x: f"{x:.1f}"),
    "Chg%": results["Chg%"].apply(color_chg),
    "Rules": results["Rules_OK"].apply(color_rules),
    "Fail_Reasons": results["Fail_Reasons"],
})

st.markdown(table.to_html(escape=False, index=False), unsafe_allow_html=True)

# ---------- DETAIL via selectbox ----------
selected = st.selectbox("Detailansicht wählen", options=list(results["Ticker"]), index=0)
df_detail = load(selected)
if df_detail is None:
    st.warning("Keine Detaildaten.")
else:
    df_detail = add_indicators(df_detail)
    direction, ts = trend_score(df_detail)
    eq_score, eq_sigs = entry_quality(df_detail, direction)
    last = df_detail.iloc[-1]; price = sf(last["Close"]); atr = sf(last["ATR"])
    levels = {
        "entry": price,
        "sl": price - 1.5*atr if direction == "LONG" else price + 1.5*atr,
        "tp1": price + 1.5*atr if direction == "LONG" else price - 1.5*atr,
        "tp2": price + 3*atr if direction == "LONG" else price - 3*atr,
        "ko": price - 2*atr if direction == "LONG" else price + 2*atr
    }
    proposals = ko_proposals(price, atr, direction, eur_usd)
    st.markdown(f"### {selected} — {direction} — TrendScore {ts} — EntryQ {eq_score}")
    fig = make_subplots(rows=1, cols=1, shared_xaxes=True)
    fig.add_trace(go.Scatter(x=df_detail["Datetime"], y=df_detail["Close"], name="Close"))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("**KO Vorschläge**")
    for p in proposals:
        st.markdown(
            f"- {p['name']}: Barrier {p['barrier']} | Strike {p['strike']} | Hebel {p['hebel']} | Preis {p['cert_price']} €"
        )
    st.markdown("**Fail Reasons (Scan)**")
    row = results[results["Ticker"] == selected].iloc[0]
    st.write(row["Fail_Reasons"] or "Alle Regeln erfüllt.")
