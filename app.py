"""齐鲁卖点与传播X光一体化入口。"""
import streamlit as st
from src.ui_theme import inject_css
from src.ui_studio import render_studio
from src.xray_workspace import render_xray_workspace

st.set_page_config(page_title="齐鲁卖点｜创作与发布前审核", page_icon="✦", layout="wide", initial_sidebar_state="collapsed")
inject_css()
if "workspace_next" in st.session_state:
    st.session_state["workspace"] = st.session_state.pop("workspace_next")
with st.sidebar:
    st.markdown("### 齐鲁卖点")
    workspace = st.radio("工作区", ["文案创作", "传播 X 光审核"], key="workspace")
    st.caption("创作版 1.1.1 · 场景、卖点与分渠道成稿")
if workspace == "传播 X 光审核":
    render_xray_workspace()
else:
    st.markdown("<div class='workspace-top'><span>齐鲁卖点 <span class='workspace-slash'>/</span> 创作与审核</span><span class='workspace-mode'>商家确认 · AI创作 · 人工发布</span></div>", unsafe_allow_html=True)
    render_studio()
