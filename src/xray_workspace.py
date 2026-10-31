"""传播 X 光 Streamlit 入口。"""

from __future__ import annotations

import streamlit as st

from src.constants import APP_NAME, APP_SUBTITLE, is_public_deployment
from src.storage import ReviewStore
from src.ui_new import render_new_review
from src.ui_report import render_about, render_report
from src.ui_review import render_reviewer
from src.ui_sidebar import render_sidebar
from src.ui_theme import inject_css, render_hero




def init_state() -> None:
    defaults = {
        "review": None,
        "flash": None,
        "llm_ok": False,
        "llm_message": "",
        "llm_signature": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value



def render_xray_workspace():
    init_state()
    inject_css()
    store = ReviewStore()
    render_hero()
    enable_llm, llm_base, llm_model = render_sidebar(store)

    tabs = st.tabs(["① 新建诊断", "② 证据审查台", "③ 导出报告", "④ 关于与验证"])
    with tabs[0]:
        render_new_review(store, enable_llm, llm_base, llm_model)
    with tabs[1]:
        render_reviewer(store, enable_llm, llm_base, llm_model)
    with tabs[2]:
        render_report(store)
    with tabs[3]:
        render_about()

    runtime_label = "公开演示" if is_public_deployment() else "本地原型"
    st.markdown(
        f"<div class='xray-footer'>{APP_NAME} · {APP_SUBTITLE} · {runtime_label} · 系统判断需人工复核</div>",
        unsafe_allow_html=True,
    )
