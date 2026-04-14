"""
Trading Scanner v8 – Analystenratings integriert
- Datenquelle: yfinance (Yahoo Finance)
- Analystenratings werden gecached und in Scan + Detailansicht angezeigt
- Im Chart wird der aktuelle Kurs mit einem schwarzen Punkt und Rating-Label markiert
- Pools: S&P 500 / Nasdaq-100 / EuroStoxx50 (sample lists)
- Prefilter, optionaler Markt-Check, RSI/ATR-Parameter, hourly->daily fallback
Start: streamlit run scanner.py
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------- Page config & Theme ----------------
st.set_page_config(page_title="Trading Scanner", page_icon="📡", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
  html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; background-color: #f2f4f6; color: #111827; font-size:13px; }
  .topbar { display:flex; align-items:baseline; gap:12px; border-bottom:1px solid #d1d5db; padding-bottom:10px; margin-bottom:14px; }
  .topbar-title { font-family:'IBM Plex Mono',monospace; font-size:1.15rem; color:#0b5fff; font-weight:600; }
  .topbar-sub { font-size:0.72rem; color:#6b7280; }
  .metric-row { display:flex; gap:8px; margin-bottom:12px; flex-wrap:wrap; }
  .metric { background:#fff; border:1px solid #d1d5db; border-radius:8px; padding:8px 12px; flex:1; min-width:80px; }
  .mlabel { font-size:0.62rem; color:#6b7280; text-transform:uppercase; letter-spacing:1px; }
  .mvalue { font-family:'IBM Plex Mono',monospace; font-size:1rem; font-weight:600; color:#111827; }
  .ko-setup { background:#fff; border:1px solid #d1d5db; border-radius:8px; padding:8px; margin-bottom:8px; font-size:0.9rem; }
  .ko-grid { display:grid; grid-template-columns:1fr 1fr; gap:6px 10px; margin-top:6px; }
  [data-testid="stDataFrame"] { border:1px solid #d1d5db; border-radius:8px; overflow:hidden; }
  table { font-size:0.9rem; }
  #MainMenu, footer, header { visibility:hidden; }
  .block-container { padding-top:1rem; padding-left:1rem; padding-right:1rem; }
</style>
""", unsafe_allow_html=True)

# ---------------- Pools (sample lists) ----------------
SP500_TICKERS = [
    "AAPL","MSFT","AMZN","NVDA","GOOGL","META","TSLA","BRK-B","JPM","JNJ","V","PG","UNH","HD","MA",
    "DIS","PYPL","ADBE","CMCSA","NFLX","INTC","PFE","KO","PEP","CSCO","XOM","CVX","ABBV","T","NKE",
    "ORCL","ABT","CRM","AVGO","TXN","QCOM","COST","WMT","MCD","DHR","LLY","BMY","MDT","NEE","HON",
    "AMGN","SBUX","LOW","INTU","MS","AXP","GILD","RTX","LIN","AMT","PLD","SCHW","SPGI","BLK","BKNG",
    "ISRG","NOW","ZTS","LMT","GE","CAT","DE","MMM","SYK","ADI","BDX","CI","CB","TMO","EL","ADP","FIS"
]

NASDAQ100_TICKERS = [
    "AAPL","MSFT","AMZN","NVDA","GOOGL","META","TSLA","PYPL","ADBE","CMCSA","INTC","CSCO","PEP","QCOM",
    "AMGN","AVGO","TXN","NFLX","INTU","SBUX","GILD","ISRG","AMD","REGN","BIIB","LRCX","ADP","ILMN",
    "DOCU","ZM","SNPS","MELI","EA","ROST","EXC","MNST","CTSH","WDAY"
]

EUROSTOXX50_TICKERS = [
    "ASML.AS","SAP.DE","SAN.PA","SIE.DE","OR.PA","BNP.PA","AIR.PA","RNO.PA","ENEL.MI","ENI.MI",
    "IBE.MC","TOTF.PA","VOW3.DE","BAS.DE","DTE.DE","MC.PA","PHIA.AS","CRH.I","AD.AS","ABI.BR",
    "LVMH.PA","SHEL.L","ULVR.L","NESN.SW","NOVN.SW","ROG.SW","CS.PA","BN.PA","BAYN.DE","MC.PA"
]

POOLS = {
    "S&P 500": SP500_TICKERS,
    "Nasdaq-100": NASDAQ100_TICKERS,
    "EuroStoxx50": EUROSTOXX50_TICKERS,
}

# ---------------- Helpers ----------------
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

# ---------------- Data loader with hourly -> daily fallback ----------------
@st.cache_data(ttl=300, show_spinner=False)
def load(ticker: str):
    try:
        df = yf.download(ticker, period="120d", interval="1h", progress=False)
    except Exception:
        df = None

    if df is None or df.empty or len(df) < 220:
        try:
            df = yf.download(ticker, period="720d", interval="1d", progress=False)
        except Exception:
            df = None

    if df is None or df.empty:
        return None

    df = df.reset_index()
    df = flatten(df)
    for col in ["Open","High","Low","Close","Volume"]:
        if col in df.columns:
            df[col] = to_series(df, col)
    if "Datetime" not in df.columns and "Date" in df.columns:
        df = df.rename(columns={"Date": "Datetime"})
    if "Datetime" not in df.columns and "index" in df.columns:
        df = df.rename(columns={"index": "Datetime"})
    cols = [c for c in ["Datetime","Open","High","Low","Close","Volume"] if c in df.columns]
    df = df.loc[:, cols].dropna()
    if df.empty:
        return None
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def get_eur_usd():
    try:
        df = yf.download("EURUSD=X", period="2d", interval="1h", progress=False)
        df = flatten(df)
        return sf(df["Close"].iloc[-1]) or 1.09
    except Exception:
        return 1.09

# ---------------- Indicators ----------------
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c = df["Close"]
    df["EMA20"]  = c.ewm(span=20, adjust=False).mean()
    df["EMA50"]  = c.ewm(span=50, adjust=False).mean()
    df["EMA200"] = c.ewm(span=200, adjust=False).mean()
    prev = c.shift(1)
    tr = pd.concat([df["High"]-df["Low"], (df["High"]-prev).abs(), (df["Low"]-prev).abs()], axis=1).max(axis=1)
    df["ATR"]  = tr.rolling(14).mean()
    df["ATR5"] = tr.rolling(5).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100/(1+rs))
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]
    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    df["BB_upper"] = sma20 + 2*std20
    df["BB_lower"] = sma20 - 2*std20
    df["BB_pct"] = (c - df["BB_lower"]) / (df["BB_upper"] - df["BB_lower"])
    df["Vol_avg"] = df["Volume"].rolling(20).mean()
    return df.dropna()

# ---------------- Market metrics ----------------
@st.cache_data(ttl=300, show_spinner=False)
def market_metrics():
    try:
        spy = yf.download("SPY", period="3d", interval="1d", progress=False)
        qqq = yf.download("QQQ", period="3d", interval="1d", progress=False)
        vix = yf.download("^VIX", period="3d", interval="1d", progress=False)
        spy = flatten(spy); qqq = flatten(qqq); vix = flatten(vix)
        def last_change(df):
            if df is None or df.empty or len(df) < 2:
                return None
            c0 = sf(df["Close"].iloc[-2]); c1 = sf(df["Close"].iloc[-1])
            if not c0 or not c1:
                return None
            return (c1 - c0) / c0 * 100
        return {"SPY_chg": last_change(spy), "QQQ_chg": last_change(qqq), "VIX": sf(vix["Close"].iloc[-1]) if not vix.empty else None}
    except Exception:
        return {"SPY_chg": None, "QQQ_chg": None, "VIX": None}

# ---------------- Analysteninfo (gecached) ----------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ticker_info(ticker: str):
    """
    Liefert recommendationMean, recommendationKey, recommendationCount und ggf. letzte Empfehlung.
    Caching reduziert wiederholte yfinance.info Aufrufe.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        rec_mean = info.get("recommendationMean")
        rec_key = info.get("recommendationKey")
        rec_count = info.get("recommendationCount")
        # historische Empfehlungen (optional, kann leer sein)
        last_rec = None
        try:
            rec_hist = t.recommendations
            if rec_hist is not None and not rec_hist.empty:
                last_row = rec_hist.iloc[-1]
                last_rec = {
                    "date": str(last_row.name) if last_row.name is not None else None,
                    "firm": last_row.get("firm") if "firm" in last_row.index else None,
                    "action": last_row.get("action") if "action" in last_row.index else None,
                }
        except Exception:
            last_rec = None
        return {
            "rec_mean": rec_mean,
            "rec_key": rec_key,
            "rec_count": rec_count,
            "last_rec": last_rec,
        }
    except Exception:
        return {"rec_mean": None, "rec_key": None, "rec_count": None, "last_rec": None}

# ---------------- Entry quality / trend / levels ----------------
def entry_quality(df: pd.DataFrame, direction: str):
    r = df.iloc[-1]; prev = df.iloc[-2]
    price = sf(r["Close"]); ema20 = sf(r["EMA20"]); atr = sf(r["ATR"])
    atr5 = sf(r["ATR5"]); rsi = sf(r["RSI"])
    macdh = sf(r["MACD_hist"]); pmacdh = sf(prev["MACD_hist"])
    bbpct = sf(r["BB_pct"]); vol = sf(r["Volume"]); volavg = sf(r["Vol_avg"])
    if None in [price, ema20, atr, rsi]:
        return 0, []
    score = 0; sigs = []
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

def trend_score(df: pd.DataFrame):
    r = df.iloc[-1]; prev = df.iloc[-2]
    price = sf(r["Close"]); ema20 = sf(r["EMA20"]); ema50 = sf(r["EMA50"])
    ema200 = sf(r["EMA200"]); rsi = sf(r["RSI"]); macd = sf(r["MACD"])
    msig = sf(r["MACD_signal"]); macdh = sf(df["MACD_hist"].iloc[-1]) if "MACD_hist" in df.columns else None
    pmacdh = sf(prev["MACD_hist"]) if "MACD_hist" in df.columns else None
    atr = sf(r["ATR"]); bbpct = sf(r["BB_pct"])
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
        if macdh is not None and pmacdh is not None and macdh > pmacdh: s += 8
    else:
        if macd < msig: s += 12
        if macdh is not None and pmacdh is not None and macdh < pmacdh: s += 8
    if bbpct is not None and 0.3 < bbpct < 0.7:
        s += 10
    atr_pct = atr / price * 100
    if 0.5 < atr_pct < 3.0:
        s += 10
    return direction, min(s, 100)

def build_levels(price, atr, direction: str):
    if direction == "LONG":
        sl = price - 1.5 * atr; tp1 = price + 1.5 * atr; tp2 = price + 3.0 * atr; ko = price - 2.0 * atr
    else:
        sl = price + 1.5 * atr; tp1 = price - 1.5 * atr; tp2 = price - 3.0 * atr; ko = price + 2.0 * atr
    rr = abs(tp2 - price) / abs(price - sl) if abs(price - sl) > 1e-9 else None
    return dict(entry=price, sl=sl, tp1=tp1, tp2=tp2, ko=ko, rr=rr)

# ---------------- Prefilter ----------------
@st.cache_data(ttl=3600, show_spinner=False)
def prefilter_tickers(tickers, min_mcap=5e9, min_avgvol=300000, max_checks=500):
    keep = []
    removed = []
    checked = 0
    for t in tickers:
        if checked >= max_checks:
            break
        checked += 1
        try:
            info = yf.Ticker(t).info
        except Exception:
            # silent skip on info fetch failure
            continue
        mcap = info.get("marketCap") or info.get("market_cap")
        avgvol = info.get("averageVolume") or info.get("averageVolume10days") or info.get("volume")
        if mcap is None or avgvol is None:
            removed.append((t, "missing_info"))
            continue
        try:
            if mcap >= min_mcap and avgvol >= min_avgvol:
                keep.append(t)
            else:
                removed.append((t, "below_threshold"))
        except Exception:
            removed.append((t, "error"))
    return keep, removed, checked

# ---------------- Rule engine ----------------
def evaluate_rules(df: pd.DataFrame, direction: str, price: float, atr: float, market: dict,
                   require_market=True, rsi_min=45, rsi_max=60, atr_min=0.5, atr_max=3.0):
    reasons = []; ok = True
    ema20 = sf(df["EMA20"].iloc[-1]); ema50 = sf(df["EMA50"].iloc[-1]); ema200 = sf(df["EMA200"].iloc[-1])
    rsi = sf(df["RSI"].iloc[-1]); macd = sf(df["MACD"].iloc[-1]); msig = sf(df["MACD_signal"].iloc[-1])
    atr_pct = (atr / price * 100) if price and atr else None
    spy_chg = market.get("SPY_chg"); qqq_chg = market.get("QQQ_chg"); vix = market.get("VIX")

    if direction == "LONG":
        if not (price and ema20 and ema50 and ema200 and price > ema20 > ema50 > ema200):
            ok = False; reasons.append("Trend nicht klar: Long-Struktur fehlt.")
    else:
        if not (price and ema20 and ema50 and ema200 and price < ema20 < ema50 < ema200):
            ok = False; reasons.append("Trend nicht klar: Short-Struktur fehlt.")

    if atr_pct is None or not (atr_min <= atr_pct <= atr_max):
        ok = False; reasons.append(f"ATR% nicht moderat ({'n/a' if atr_pct is None else f'{atr_pct:.2f}'}).")

    if rsi is None or macd is None or msig is None or not (rsi_min <= rsi <= rsi_max and macd > msig):
        ok = False; reasons.append(f"Momentum nicht ideal (RSI {rsi}, MACD vs Signal).")

    if direction == "LONG" and price and ema20 and price < ema20:
        ok = False; reasons.append("Trendbruch: Kurs unter EMA20.")
    if direction == "SHORT" and price and ema20 and price > ema20:
        ok = False; reasons.append("Trendbruch: Kurs über EMA20.")

    if vix is not None and vix > 20:
        ok = False; reasons.append(f"VIX hoch ({vix:.1f}).")

    if rsi is not None and (rsi < 40 or rsi > 70):
        ok = False; reasons.append(f"Momentum kritisch (RSI {rsi:.1f}).")

    if require_market:
        good_market = (spy_chg is not None and qqq_chg is not None and vix is not None and spy_chg > 0 and qqq_chg > 0 and vix < 20)
        if not good_market:
            ok = False; reasons.append("Marktumfeld nicht ideal (SPY/QQQ/VIX).")

    return ok, reasons

# ---------------- Scan (mit Analysteninfo) ----------------
@st.cache_data(ttl=300, show_spinner=False)
def run_scan(min_score, pool_tickers, require_market, rsi_min, rsi_max, atr_min, atr_max):
    results = []
    market = market_metrics()
    for ticker in pool_tickers:
        df = load(ticker)
        if df is None or len(df) < 220:
            continue
        try:
            df = add_indicators(df)
        except Exception:
            continue
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

        # Analysteninfo nur hier abfragen (gecached)
        info = fetch_ticker_info(ticker)
        rec_mean = info.get("rec_mean")
        rec_key = info.get("rec_key")
        rec_count = info.get("rec_count")

        rules_ok, reasons = evaluate_rules(df, direction, price, atr, market,
                                           require_market=require_market,
                                           rsi_min=rsi_min, rsi_max=rsi_max,
                                           atr_min=atr_min, atr_max=atr_max)
        results.append({
            "Ticker": ticker,
            "Sektor": "–",
            "Dir": direction,
            "Trend": ts,
            "Entry-Q": eq,
            "Price": round(price, 2),
            "RSI": round(rsi, 1) if rsi else None,
            "ATR%": round(atr / price * 100, 2),
            "RR": round(levels["rr"], 1) if levels["rr"] is not None else None,
            "Chg%": round(chg, 2) if chg else None,
            "Analyst_Mean": round(rec_mean, 2) if rec_mean is not None else None,
            "Analyst_Key": rec_key,
            "Analyst_Count": rec_count,
            "Rules_OK": rules_ok,
            "Fail_Reasons": "; ".join(reasons) if reasons else "",
        })
    df_out = pd.DataFrame(results)
    if not df_out.empty:
        df_out = df_out.sort_values(["Rules_OK", "Trend", "Entry-Q"], ascending=[False, False, False]).reset_index(drop=True)
    return df_out

# ---------------- Sidebar controls ----------------
with st.sidebar:
    st.markdown("### ⚙️ Scanner")
    min_score = st.slider("Mindest-Trend-Score", 30, 90, 60, 5)
    pool_choice = st.selectbox("Pool wählen", list(POOLS.keys()))
    st.markdown("---")
    st.markdown("### 🔎 Prefilter (MarketCap / AvgVolume)")
    min_mcap = st.number_input("Min MarketCap (USD)", value=5_000_000_000, step=1_000_000_000, format="%d")
    min_avgvol = st.number_input("Min Avg Volume", value=200_000, step=50_000, format="%d")
    max_info_checks = st.number_input("Max info checks (prefilter)", value=300, step=50, format="%d")
    st.markdown("---")
    st.markdown("### ⚖️ Rule parameters")
    require_market = st.checkbox("Markt-Check erzwingen (SPY/QQQ/VIX)", value=True)
    rsi_min, rsi_max = st.slider("RSI Range", 30, 80, (45, 60))
    atr_min, atr_max = st.slider("ATR% Range", 0.1, 6.0, (0.5, 3.0), step=0.1)
    st.markdown("---")
    st.markdown("### 🔰 KO-Setups (Info)")
    st.markdown('<div class="ko-setup"><strong>Konservativ</strong>: Barrier ≈ Preis − 2.5 × ATR · Weit, niedriger Hebel.</div>', unsafe_allow_html=True)
    st.markdown('<div class="ko-setup"><strong>Moderat</strong>: Barrier ≈ Preis − 1.5 × ATR · Ausgewogen.</div>', unsafe_allow_html=True)
    st.markdown('<div class="ko-setup"><strong>Aggressiv</strong>: Barrier ≈ Preis − 0.7 × ATR · Eng, hoher Hebel.</div>', unsafe_allow_html=True)
    st.markdown("---")
    if st.button("🔄 Neu laden"):
        st.cache_data.clear()
        st.rerun()
    st.markdown(f'<p style="font-size:0.72rem;color:#6b7280;">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} · EUR/USD auto</p>', unsafe_allow_html=True)

# ---------------- Determine pool and prefilter ----------------
base_pool = POOLS.get(pool_choice, [])
st.info(f"Pool: {pool_choice} · Kandidaten (sample): {len(base_pool)}")

with st.spinner("Prefilter läuft (MarketCap / AvgVolume)…"):
    pool_prefiltered, removed_list, checked = prefilter_tickers(base_pool, min_mcap=min_mcap, min_avgvol=min_avgvol, max_checks=int(max_info_checks))
    removed_count = len(removed_list)
    st.write(f"Prefilter geprüft: {checked} tickers · entfernt: {removed_count}")
    if removed_count:
        reasons = [r for (_, r) in removed_list]
        rc = {}
        for r in reasons:
            rc[r] = rc.get(r, 0) + 1
        if rc:
            st.write("Entfernungsgründe (Top):")
            for k, v in sorted(rc.items(), key=lambda x: -x[1])[:5]:
                st.write(f"- {k}: {v}")
    if not pool_prefiltered:
        st.warning("Prefilter hat keine Ticker zurückgegeben. Pool wird ungefiltert verwendet.")
        pool_prefiltered = base_pool

# ---------------- Run scan ----------------
with st.spinner("Scanner läuft …"):
    results = run_scan(min_score, pool_prefiltered, require_market, rsi_min, rsi_max, atr_min, atr_max)

# ---------------- If no results, guidance and stop ----------------
if results.empty:
    st.warning("Keine Signale gefunden. Mögliche Ursachen: Regeln zu strikt, Prefilter entfernt viele Kandidaten oder Datenqualität.")
    st.stop()

# ---------------- Summary metrics ----------------
lc = len(results[results["Dir"] == "LONG"])
sc = len(results[results["Dir"] == "SHORT"])
aq = int(results["Entry-Q"].mean()) if not results.empty else 0
tp = results.iloc[0]["Ticker"] if not results.empty else "–"

st.markdown(f"""
<div class="topbar">
  <span class="topbar-title">📡 TRADING SCANNER</span>
  <span class="topbar-sub">{datetime.now().strftime('%H:%M:%S')} &nbsp;|&nbsp; Pool: {pool_choice} &nbsp;|&nbsp; EUR/USD {get_eur_usd():.4f}</span>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="metric-row">
  <div class="metric"><div class="mlabel">Signale</div><div class="mvalue">{len(results)}</div></div>
  <div class="metric"><div class="mlabel">LONG</div><div class="mvalue" style="color:#059669">{lc}</div></div>
  <div class="metric"><div class="mlabel">SHORT</div><div class="mvalue" style="color:#ef4444">{sc}</div></div>
  <div class="metric"><div class="mlabel">Ø Entry-Q</div><div class="mvalue">{aq}</div></div>
  <div class="metric"><div class="mlabel">Top Signal</div><div class="mvalue">{tp}</div></div>
</div>
""", unsafe_allow_html=True)

# ---------------- Table (inkl. Analysteninfo) ----------------
disp = results[["Ticker","Sektor","Dir","Trend","Entry-Q","Price","RSI","ATR%","RR","Chg%","Analyst_Mean","Analyst_Key","Analyst_Count","Rules_OK"]].copy()

def color_dir_html(v):
    if v == "LONG": return '<span style="color:#0b5fff;font-weight:600">LONG</span>'
    if v == "SHORT": return '<span style="color:#ef4444;font-weight:600">SHORT</span>'
    return str(v)

def color_trend_html(v):
    try: vv = float(v)
    except Exception: return str(v)
    if vv >= 80: return f'<span style="color:#059669;font-weight:600">{int(vv)}</span>'
    if vv >= 65: return f'<span style="color:#0b5fff">{int(vv)}</span>'
    return f"{int(vv)}"

def color_entry_html(v):
    try: vv = float(v)
    except Exception: return str(v)
    if vv >= 70: return f'<span style="color:#059669;font-weight:600">{int(vv)}</span>'
    if vv >= 50: return f'<span style="color:#f59e0b">{int(vv)}</span>'
    return f'<span style="color:#ef4444">{int(vv)}</span>'

def color_chg_html(v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "–"
    try: vv = float(v)
    except Exception: return str(v)
    if vv > 0: return f'<span style="color:#059669">+{vv:.2f}%</span>'
    return f'<span style="color:#ef4444">{vv:.2f}%</span>'

def color_rules_html(v):
    if v: return '<span style="background:#ecfdf5;color:#065f46;padding:3px 6px;border-radius:4px;">OK</span>'
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
    "RR": disp["RR"].apply(lambda x: f"{x:.1f}" if x is not None else "–"),
    "Chg%": disp["Chg%"].apply(color_chg_html),
    "Analyst Mean": results["Analyst_Mean"].apply(lambda x: f"{x:.2f}" if x is not None else "–"),
    "Analyst Key": results["Analyst_Key"].fillna("–"),
    "Analyst Count": results["Analyst_Count"].apply(lambda x: str(x) if x is not None else "–"),
    "Rules": disp["Rules_OK"].apply(color_rules_html),
})
st.markdown(table.to_html(escape=False, index=False), unsafe_allow_html=True)

# ---------------- Detail view (mit schwarzem Punkt für Analystenrating) ----------------
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

    # fetch analyst info for selected ticker (cached)
    ainfo = fetch_ticker_info(selected)
    rec_mean = ainfo.get("rec_mean")
    rec_key = ainfo.get("rec_key")
    rec_count = ainfo.get("rec_count")

    st.markdown(f"### {selected} – {direction} – TrendScore {ts} – EntryQ {eq_score}")
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6,0.2,0.2], vertical_spacing=0.03)

    # Candles + EMAs + Bollinger
    fig.add_trace(go.Candlestick(
        x=df_detail["Datetime"], open=df_detail["Open"], high=df_detail["High"],
        low=df_detail["Low"], close=df_detail["Close"], name="Preis",
        increasing_line_color="#059669", decreasing_line_color="#ef4444"
    ), row=1, col=1)
    for col, color in [("EMA20","#0b5fff"),("EMA50","#6366f1"),("EMA200","#f59e0b")]:
        fig.add_trace(go.Scatter(x=df_detail["Datetime"], y=df_detail[col], line=dict(color=color, width=1.2), name=col), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_detail["Datetime"], y=df_detail["BB_upper"], line=dict(color="#9ca3af", width=1, dash="dot"), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_detail["Datetime"], y=df_detail["BB_lower"], line=dict(color="#9ca3af", width=1, dash="dot"), fill="tonexty", fillcolor="rgba(156,163,175,0.10)", showlegend=False), row=1, col=1)

    # Markiere aktuellen Kurs mit schwarzem Punkt und Rating-Label (falls vorhanden)
    try:
        last_dt = df_detail["Datetime"].iloc[-1]
        marker_text = f"Rating: {rec_mean:.2f} ({rec_key})" if rec_mean is not None else (f"{rec_key}" if rec_key else "n/a")
        marker_size = 10 if rec_count is None else min(max(6, int(4 + np.log1p(rec_count)*2)), 18)
        fig.add_trace(go.Scatter(
            x=[last_dt], y=[price],
            mode="markers+text",
            marker=dict(color="black", size=marker_size),
            text=[marker_text],
            textposition="top center",
            name="Analyst Rating"
        ), row=1, col=1)
    except Exception:
        pass

    # RSI
    fig.add_trace(go.Scatter(x=df_detail["Datetime"], y=df_detail["RSI"], line=dict(color="#0b5fff", width=1.2), name="RSI"), row=2, col=1)
    for lvl, col in [(70,"#ef4444"),(50,"#9ca3af"),(30,"#059669")]:
        fig.add_hline(y=lvl, line_color=col, line_dash="dot", line_width=1, row=2, col=1)

    # MACD hist + MACD lines
    hist_c = ["#059669" if v >= 0 else "#ef4444" for v in df_detail["MACD_hist"]]
    fig.add_trace(go.Bar(x=df_detail["Datetime"], y=df_detail["MACD_hist"], marker_color=hist_c, name="MACD_hist"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_detail["Datetime"], y=df_detail["MACD"], line=dict(color="#0b5fff", width=1.2), name="MACD"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_detail["Datetime"], y=df_detail["MACD_signal"], line=dict(color="#f59e0b", width=1.2), name="Signal"), row=3, col=1)

    fig.update_layout(height=700, paper_bgcolor="#f2f4f6", plot_bgcolor="#ffffff", margin=dict(l=5,r=5,t=10,b=5), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # Entry quality pills
    st.markdown("#### Entry-Qualität")
    pills = []
    for txt, kind in eq_sigs:
        cls = "background:#ecfdf5;color:#059669;padding:4px 8px;border-radius:8px;" if kind=="good" else ("background:#fffbeb;color:#f59e0b;padding:4px 8px;border-radius:8px;" if kind=="neutral" else "background:#fef2f2;color:#ef4444;padding:4px 8px;border-radius:8px;")
        pills.append(f'<span style="{cls} margin-right:6px;">{txt}</span>')
    st.markdown(" ".join(pills), unsafe_allow_html=True)

    # Analysteninfo anzeigen
    st.markdown("#### Analystenrating")
    st.write(f"- **Mean**: {rec_mean if rec_mean is not None else 'n/a'}")
    st.write(f"- **Key**: {rec_key if rec_key else 'n/a'}")
    st.write(f"- **Count**: {rec_count if rec_count is not None else 'n/a'}")
    if ainfo.get("last_rec"):
        st.write(f"- **Letzte Empfehlung**: {ainfo['last_rec']}")

    # Regel-Check
    st.markdown("#### Regel-Check (Scan)")
    row = results[results["Ticker"] == selected].iloc[0]
    if row["Rules_OK"]:
        st.success("Alle definierten Trading-Regeln sind erfüllt – Setup statistisch robust.")
    else:
        st.error("Nicht alle Trading-Regeln erfüllt – kein sauberes KO-Setup.")
        if row["Fail_Reasons"]:
            st.write(row["Fail_Reasons"])
