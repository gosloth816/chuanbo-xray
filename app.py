"""齐鲁卖点与传播 X 光入口。"""
import streamlit as st

from src.review_desk import render_review_desk
from importlib import reload
from src import studio_exact

if getattr(studio_exact, "EXACT_RELEASE", None) != 5:
    reload(studio_exact)
from src.ui_theme import inject_css
from src.xray_workspace import render_xray_workspace

st.set_page_config(page_title="齐鲁卖点｜创作与发布前审核", layout="wide")
if st.session_state.pop("workspace_next", None) == "传播 X 光审核":
    st.session_state["show_xray"] = True

if st.session_state.get("show_xray") and st.session_state.get("xray_advanced"):
    inject_css()
    if st.button("返回逐句审核"):
        st.session_state["xray_advanced"] = False
        st.rerun()
    render_xray_workspace()
else:
    st.markdown(
        """<style>
        [data-testid="stHeader"],[data-testid="stSidebar"],[data-testid="stToolbar"]{display:none}
        [data-testid="stMainBlockContainer"]{padding:0;max-width:none}
        iframe[title$="approved_studio"]{display:block}
        </style>""", unsafe_allow_html=True,
    )
    if st.session_state.get("show_xray"):
        render_review_desk()
    else:
        studio_exact.render_exact_studio()
