"""
NIFTY Positioning Dashboard - dark trading-terminal style, full layout
Run locally with: streamlit run dashboard.py
Deploy free at: https://share.streamlit.io
"""

import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go

st.set_page_config(page_title="NIFTY Positioning Dashboard", layout="wide", page_icon="📊")

DB_PATH = "data/nifty.db"

BG, PANEL, GRID = "#0B0F17", "#131A26", "#1F2A3A"
TEXT, MUTED = "#E6EDF3", "#8B98A9"
TEAL, RED, GREEN, ORANGE = "#5EEAD4", "#F85149", "#3FB950", "#F0B429"

st.markdown(f"""
<style>
.stApp {{ background-color: {BG}; }}
[data-testid="stMetric"] {{
    background-color: {PANEL}; border: 1px solid {GRID};
    border-radius: 10px; padding: 12px 14px;
}}
[data-testid="stMetricLabel"] {{ color: {MUTED} !important; }}
h1, h2, h3, h4 {{ color: {TEXT}; }}
.panel-note {{
    background-color: {PANEL}; border-left: 3px solid {TEAL};
    border-radius: 6px; padding: 12px 16px; color: {MUTED};
    font-size: 0.92rem; margin-bottom: 1rem;
}}
.signal-row {{
    display: flex; justify-content: space-between; align-items: center;
    background-color: {PANEL}; border: 1px solid {GRID};
    border-radius: 8px; padding: 8px 14px; margin-bottom: 6px;
}}
.signal-label {{ color: {TEXT}; font-size: 0.88rem; }}
.signal-sub {{ color: {MUTED}; font-size: 0.75rem; }}
.signal-score {{
    background-color: {GRID}; color: {TEXT}; border-radius: 6px;
    padding: 2px 10px; font-weight: 600; font-size: 0.85rem;
}}
.anomaly-card {{
    background-color: {PANEL}; border-left: 3px solid {ORANGE};
    border-radius: 6px; padding: 10px 14px; margin-bottom: 8px;
}}
.anomaly-title {{ color: {ORANGE}; font-weight: 600; font-size: 0.88rem; }}
.anomaly-sub {{ color: {MUTED}; font-size: 0.78rem; }}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_table(name):
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql(f"SELECT * FROM {name}", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def dark_layout(fig, title=None, height=340):
    fig.update_layout(
        title=title, template="plotly_dark",
        paper_bgcolor=PANEL, plot_bgcolor=PANEL,
        font=dict(color=TEXT, size=12), height=height,
        margin=dict(l=10, r=10, t=40 if title else 10, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def col_lookup(df, *keywords):
    """Find a column whose name contains all given keywords (case-insensitive)."""
    for c in df.columns:
        cl = c.lower()
        if all(k.lower() in cl for k in keywords):
            return c
    return None


st.title("📊 NIFTY Positioning Dashboard")
st.caption("Derived from free NSE option chain + participant-wise open interest data · refreshed daily via GitHub Actions")

oc = load_table("option_chain")
poi = load_table("participant_oi")

# ================= TOP METRIC STRIP =================
if oc.empty:
    st.markdown(
        '<div class="panel-note">⚠️ No option chain data yet. NSE occasionally blocks the free/cloud fetch — '
        'check back after the next scheduled run, or trigger the workflow manually from the Actions tab.</div>',
        unsafe_allow_html=True,
    )
    spot = pcr = resistance = support = None
else:
    latest_date = oc["date"].max()
    latest = oc[oc["date"] == latest_date].sort_values("strike")
    spot = latest["spot"].iloc[0]
    total_call_oi, total_put_oi = latest["call_oi"].sum(), latest["put_oi"].sum()
    pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi else 0
    resistance = latest.loc[latest["call_oi"].idxmax(), "strike"]
    support = latest.loc[latest["put_oi"].idxmax(), "strike"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("NIFTY Spot", f"{spot:,.0f}")
    m2.metric("Put / Call Ratio", pcr, "put-heavy" if pcr > 1 else "call-heavy")
    m3.metric("Resistance (max call OI)", f"{resistance:,.0f}")
    m4.metric("Support (max put OI)", f"{support:,.0f}")

# Participant-derived metrics (used across panels below)
fii_net = dii_net = client_net = pro_net = None
if not poi.empty:
    poi.columns = [c.strip() for c in poi.columns]
    latest_poi_date = poi["report_date"].max()
    p = poi[poi["report_date"] == latest_poi_date].copy()
    type_col = col_lookup(p, "client", "type") or p.columns[0]
    fut_long = col_lookup(p, "future", "index", "long")
    fut_short = col_lookup(p, "future", "index", "short")

    def net_for(label):
        row = p[p[type_col].astype(str).str.upper().str.contains(label, na=False)]
        if row.empty or not fut_long or not fut_short:
            return None
        return int(row[fut_long].iloc[0]) - int(row[fut_short].iloc[0])

    fii_net = net_for("FII")
    dii_net = net_for("DII")
    client_net = net_for("CLIENT")
    pro_net = net_for("PRO")

# ================= ROW 1: PREDICTION BIAS / SIGNAL BREAKDOWN / SPOT+PCR =================
r1a, r1b, r1c = st.columns([1, 1.3, 1.3])

with r1a:
    st.markdown("#### Prediction Bias")
    if pcr is not None:
        bias_score = max(-100, min(100, round((1 - pcr) * 100)))
        gauge = go.Figure(go.Indicator(
            mode="gauge+number", value=bias_score,
            number={"font": {"color": TEXT, "size": 30}},
            gauge={
                "axis": {"range": [-100, 100], "tickcolor": MUTED, "tickfont": {"color": MUTED, "size": 9}},
                "bar": {"color": TEAL, "thickness": 0.25},
                "bgcolor": PANEL, "borderwidth": 0,
                "steps": [
                    {"range": [-100, -20], "color": "#3A1F22"},
                    {"range": [-20, 20], "color": "#2B2F1F"},
                    {"range": [20, 100], "color": "#1F3A2A"},
                ],
            },
        ))
        dark_layout(gauge, height=220)
        st.plotly_chart(gauge, use_container_width=True)
        label = "Bearish" if bias_score < -15 else "Bullish" if bias_score > 15 else "Neutral"
        st.caption(f"**{label}** · derived from PCR ({pcr})")
    else:
        st.markdown('<div class="panel-note">No data</div>', unsafe_allow_html=True)

with r1b:
    st.markdown("#### Signal Breakdown")
    signals = []
    if fii_net is not None:
        signals.append(("FII net position in futures", f"Net {fii_net:+,}", min(30, abs(fii_net) // 200) if fii_net < 0 else 10, fii_net < 0))
    if pcr is not None:
        signals.append(("Put-Call Ratio", f"PCR {pcr}", 16 if pcr > 1.2 else 8, pcr > 1))
    if pcr is not None:
        signals.append(("Call vs Put OI writing", f"{'Put-heavy' if pcr>1 else 'Call-heavy'}", 10, pcr > 1))
    if client_net is not None:
        signals.append(("Client (retail) positioning", f"Net {client_net:+,}", min(12, abs(client_net) // 300), client_net > 0))
    if not signals:
        st.markdown('<div class="panel-note">No signals available yet</div>', unsafe_allow_html=True)
    for label, sub, score, bearish in signals:
        arrow = "🔻" if bearish else "🔺"
        st.markdown(f"""
        <div class="signal-row">
            <div><div class="signal-label">{arrow} {label}</div><div class="signal-sub">{sub}</div></div>
            <div class="signal-score">{score}</div>
        </div>""", unsafe_allow_html=True)

with r1c:
    st.markdown("#### Spot — Session History")
    if not oc.empty:
        hist = oc.groupby("date").agg(spot=("spot", "first")).reset_index().sort_values("date")
        fig = go.Figure()
        fig.add_scatter(x=hist["date"], y=hist["spot"], mode="lines+markers",
                         line=dict(color=TEAL, width=2), marker=dict(size=5), name="Spot")
        dark_layout(fig, height=300)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"PCR **{pcr}** · Spot **{spot:,.0f}**" if pcr is not None else "")
    else:
        st.markdown('<div class="panel-note">No data</div>', unsafe_allow_html=True)

# ================= ROW 2: ANOMALY RADAR + NET POSITION =================
r2a, r2b = st.columns([1, 1.5])

with r2a:
    st.markdown("#### Anomaly Radar")
    anomalies = []
    if fii_net is not None and dii_net is not None and (fii_net < 0) != (dii_net < 0):
        anomalies.append(("FII-DII divergence", f"FII net {fii_net:+,} while DII net {dii_net:+,}"))
    if pcr is not None and pcr > 1.5:
        anomalies.append(("Extreme put writing", f"PCR at {pcr} — unusually put-heavy"))
    if client_net is not None and abs(client_net) > 100000:
        anomalies.append(("Large retail positioning", f"Client net {client_net:+,} contracts"))
    if not anomalies:
        st.markdown('<div class="panel-note">No anomalies flagged from current data.</div>', unsafe_allow_html=True)
    for title, sub in anomalies:
        st.markdown(f'<div class="anomaly-card"><div class="anomaly-title">⚠ {title}</div>'
                     f'<div class="anomaly-sub">{sub}</div></div>', unsafe_allow_html=True)

with r2b:
    st.markdown("#### Net Position — FII / DII / Pro / Client")
    parts = [("Client", client_net), ("DII", dii_net), ("FII", fii_net), ("Pro", pro_net)]
    parts = [(k, v) for k, v in parts if v is not None]
    if parts:
        fig = go.Figure()
        fig.add_bar(x=[k for k, v in parts], y=[v for k, v in parts],
                    marker_color=[GREEN if v > 0 else RED for k, v in parts])
        dark_layout(fig, height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown('<div class="panel-note">No participant data yet.</div>', unsafe_allow_html=True)

# ================= ROW 3: OI BY STRIKE + OI CHANGE =================
if not oc.empty:
    r3a, r3b = st.columns(2)
    with r3a:
        st.markdown("#### Open Interest by Strike")
        fig = go.Figure()
        fig.add_bar(x=latest["strike"], y=latest["call_oi"], name="Call OI", marker_color=RED)
        fig.add_bar(x=latest["strike"], y=latest["put_oi"], name="Put OI", marker_color=GREEN)
        fig.add_vline(x=spot, line_dash="dash", line_color=TEAL)
        fig.update_layout(barmode="group")
        dark_layout(fig, height=320)
        st.plotly_chart(fig, use_container_width=True)
    with r3b:
        st.markdown("#### OI Change by Strike")
        fig2 = go.Figure()
        fig2.add_bar(x=latest["strike"], y=latest["call_oi_chg"], name="Call OI Δ", marker_color=ORANGE)
        fig2.add_bar(x=latest["strike"], y=latest["put_oi_chg"], name="Put OI Δ", marker_color=TEAL)
        fig2.update_layout(barmode="group")
        dark_layout(fig2, height=320)
        st.plotly_chart(fig2, use_container_width=True)

# ================= ROW 4: FUTURES / OPTIONS TABLES BY PARTICIPANT =================
st.markdown("#### Futures — Index Long / Short by Participant")
if not poi.empty:
    show_cols = [type_col] + [c for c in [fut_long, fut_short] if c]
    table = p[show_cols].copy()
    if fut_long and fut_short:
        table["Net"] = table[fut_long] - table[fut_short]
        table["Stance"] = table["Net"].apply(lambda x: "Long" if x > 0 else "Short")
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.caption(f"EOD data for {latest_poi_date} — ~1 trading day lag, a structural limit of free NSE data.")
else:
    st.markdown('<div class="panel-note">No participant OI data yet — NSE publishes this the morning after each trading day.</div>', unsafe_allow_html=True)

st.divider()
st.caption("Data source: NSE India public APIs & daily reports · Educational use — not investment advice.")
