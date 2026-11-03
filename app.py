"""齐鲁卖点与传播 X 光入口。"""
import streamlit as st

from src.studio_exact import render_exact_studio
from src.ui_theme import inject_css
from src.xray_workspace import render_xray_workspace

st.set_page_config(page_title="齐鲁卖点｜创作与发布前审核", layout="wide")
if st.session_state.pop("workspace_next", None) == "传播 X 光审核":
    st.session_state["show_xray"] = True

if st.session_state.get("show_xray"):
    inject_css()
    if st.button("返回创作室"):
        st.session_state["show_xray"] = False
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
    render_exact_studio()
