"""界面主题与公共组件。"""

from __future__ import annotations

import streamlit as st

from .constants import APP_NAME, APP_SUBTITLE, VERDICT_COLORS, VERDICT_LABELS


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root { --ink:#18271f; --muted:#66756d; --line:#dfe8e2; --brand:#13795b; --surface:#fff; }
        .stApp { background: radial-gradient(circle at 8% 0%, #e4f1e8 0, #f5f7f4 34%, #f5f7f4 100%); }
        [data-testid="stHeader"] { background: transparent; }
        .block-container { max-width: 1280px; padding-top: 2rem; padding-bottom: 4rem; }
        .xray-hero { position:relative; overflow:hidden; border-radius:26px; padding:34px 38px; color:#fff;
            background:linear-gradient(128deg,#083d2e 0%,#13795b 55%,#73a982 100%);
            box-shadow:0 20px 60px rgba(11,79,59,.18); margin-bottom:22px; }
        .xray-hero::after { content:""; position:absolute; width:260px; height:260px; right:-60px; top:-100px;
            border-radius:50%; border:40px solid rgba(255,255,255,.08); }
        .xray-kicker { letter-spacing:.16em; text-transform:uppercase; font-size:12px; opacity:.78; }
        .xray-hero h1 { margin:8px 0 6px; font-size:clamp(34px,4vw,54px); line-height:1.05; }
        .xray-hero p { margin:8px 0 0; max-width:790px; color:rgba(255,255,255,.88); font-size:16px; }
        .xray-pill { display:inline-flex; align-items:center; gap:7px; padding:6px 11px; border-radius:999px;
            background:rgba(255,255,255,.13); border:1px solid rgba(255,255,255,.18); font-size:12px; margin-top:18px; }
        .xray-card { background:rgba(255,255,255,.92); border:1px solid var(--line); border-radius:18px;
            padding:18px 20px; min-height:100px; box-shadow:0 8px 28px rgba(20,60,45,.045); }
        .xray-metric { background:#fff; border:1px solid var(--line); border-radius:16px; padding:15px 16px;
            min-height:92px; box-shadow:0 5px 18px rgba(20,60,45,.04); }
        .xray-metric span { color:var(--muted); font-size:12px; display:block; }
        .xray-metric strong { color:var(--ink); font-size:29px; line-height:1.25; }
        .xray-metric small { color:var(--muted); font-size:11px; }
        .xray-badge { display:inline-block; color:#fff; font-weight:700; border-radius:999px;
            padding:5px 11px; font-size:12px; letter-spacing:.02em; }
        .xray-status { color:var(--muted); font-size:13px; }
        .xray-evidence { background:#f7faf8; border-left:4px solid #9cc6b3; border-radius:0 12px 12px 0;
            padding:12px 15px; margin:8px 0; white-space:pre-wrap; color:#274337; }
        .xray-evidence-meta { font-size:12px; color:var(--muted); margin-bottom:6px; }
        .xray-boundary { background:#edf5f0; border:1px solid #cfe2d7; color:#2d4a3d;
            border-radius:14px; padding:12px 15px; margin:8px 0; }
        .xray-footer { color:var(--muted); font-size:12px; text-align:center; padding-top:24px; }
        div[data-testid="stForm"] { border:1px solid var(--line); border-radius:16px; padding:16px 18px; background:#fbfcfb; }
        div[data-testid="stExpander"] { border-color:var(--line); }
        .stButton > button, .stDownloadButton > button { border-radius:10px; font-weight:650; }
        .stButton > button[kind="primary"] { background:var(--brand); border-color:var(--brand); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def badge(verdict: str) -> str:
    label = VERDICT_LABELS.get(verdict, verdict)
    color = VERDICT_COLORS.get(verdict, "#475467")
    return f'<span class="xray-badge" style="background:{color}">{label}</span>'


def render_hero() -> None:
    st.markdown(
        f"""
        <section class="xray-hero">
          <div class="xray-kicker">Track 03 · AI 传播工具创新</div>
          <h1>{APP_NAME}</h1>
          <p>{APP_SUBTITLE}。把宣传主张拆开，把原始证据找出来，把必须由人做的判断留给人。</p>
          <div class="xray-pill">本地处理 · 原文可定位 · 人工可修改 · 报告可导出</div>
        </section>
        """,
        unsafe_allow_html=True,
    )
