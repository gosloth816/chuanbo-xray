"""界面主题与公共组件。"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from .constants import APP_NAME, APP_SUBTITLE, VERDICT_COLORS, VERDICT_LABELS, is_public_deployment


def _theme_css() -> str:
    return Path(__file__).with_name("theme.css").read_text(encoding="utf-8")


def inject_css() -> None:
    st.markdown(f"<style>{_theme_css()}</style>", unsafe_allow_html=True)


def badge(verdict: str) -> str:
    label = VERDICT_LABELS.get(verdict, verdict)
    color = VERDICT_COLORS.get(verdict, "#475467")
    return f'<span class="xray-badge" style="background:{color}">{label}</span>'


def render_hero() -> None:
    mode = "公开演示" if is_public_deployment() else "本地工作区"
    st.markdown(
        f"<div class='workspace-top'><span>传播 X 光 <span class='workspace-slash'>/</span> 宣传审核</span>"
        f"<span class='workspace-mode'>{mode}</span></div>",
        unsafe_allow_html=True,
    )
