"""界面主题与公共组件。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import streamlit as st

from .constants import APP_NAME, APP_SUBTITLE, VERDICT_COLORS, VERDICT_LABELS


@lru_cache(maxsize=1)
def _theme_css() -> str:
    return Path(__file__).with_name("theme.css").read_text(encoding="utf-8")


def inject_css() -> None:
    st.markdown(f"<style>{_theme_css()}</style>", unsafe_allow_html=True)


def badge(verdict: str) -> str:
    label = VERDICT_LABELS.get(verdict, verdict)
    color = VERDICT_COLORS.get(verdict, "#475467")
    return f'<span class="xray-badge" style="background:{color}">{label}</span>'


def render_hero() -> None:
    st.markdown(
        f"""
        <section class="xray-hero">
          <div class="hero-copy">
            <div class="hero-kicker">Track 03 · AI 传播工具创新</div>
            <h1>{APP_NAME}<br><span>让每条宣传都有证据。</span></h1>
            <p class="hero-subtitle">
              {APP_SUBTITLE}。把宣传主张拆开，把原始证据找出来，
              把必须由人做的判断留给人。
            </p>
            <div class="hero-tags">
              <span class="hero-tag">LOCAL-FIRST</span>
              <span class="hero-tag">原文可定位</span>
              <span class="hero-tag">人工可修改</span>
              <span class="hero-tag">报告可追溯</span>
            </div>
          </div>
          <aside class="hero-console" aria-label="证据核验流程示意">
            <div class="console-head">
              <span class="console-title">Evidence Rail / 核验轨</span>
              <span class="console-live">LOCAL MODE</span>
            </div>
            <div class="evidence-rail">
              <div class="rail-step">
                <div class="rail-node">01</div>
                <div><strong>宣传主张</strong><small>从材料中拆出可核验句子</small></div>
                <span class="rail-status">Extract</span>
              </div>
              <div class="rail-step">
                <div class="rail-node">02</div>
                <div><strong>原始证据</strong><small>文件 · 页码 · 段落 · 引文</small></div>
                <span class="rail-status">Locate</span>
              </div>
              <div class="rail-step">
                <div class="rail-node">03</div>
                <div><strong>风险判断</strong><small>支持 · 条件 · 不足 · 冲突</small></div>
                <span class="rail-status">Assess</span>
              </div>
              <div class="rail-step">
                <div class="rail-node">04</div>
                <div><strong>人工复核</strong><small>确认 · 修改 · 驳回 · 留痕</small></div>
                <span class="rail-status">Review</span>
              </div>
            </div>
            <div class="console-foot">
              <span>Claim → Evidence → Human</span>
              <span>No Paid API</span>
            </div>
          </aside>
        </section>
        """,
        unsafe_allow_html=True,
    )
