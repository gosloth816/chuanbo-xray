"""侧边栏、模型配置与审核会话辅助函数。"""

from __future__ import annotations

import os

import streamlit as st

from .constants import ANALYSIS_MODE_LABELS, APP_NAME, APP_SUBTITLE
from .local_llm import LocalLLMClient, LocalLLMError
from .models import ReviewSession
from .pipeline import AnalysisError
from .storage import ReviewStore


def model_signature(base_url: str, model: str) -> str:
    return f"{base_url.strip()}::{model.strip()}"


def build_llm(enable_llm: bool, llm_base: str, llm_model: str) -> LocalLLMClient | None:
    if not enable_llm:
        return None
    signature = model_signature(llm_base, llm_model)
    if not st.session_state.get("llm_ok") or st.session_state.get("llm_signature") != signature:
        raise AnalysisError("本地大模型尚未通过连接测试，不能启用增强分析。")
    return LocalLLMClient(llm_base, llm_model)


def render_sidebar(store: ReviewStore) -> tuple[bool, str, str]:
    with st.sidebar:
        st.markdown(
            f"""
            <div class="xray-brand">
              <div class="xray-brand-mark">XR</div>
              <div class="xray-brand-copy">
                <strong>{APP_NAME}</strong>
                <span>{APP_SUBTITLE}</span>
              </div>
            </div>
            <div class="xray-side-status">本地私有运行 · 材料不离开本机</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown("**隐私与运行边界**")
        st.caption("材料只在当前电脑处理；不包含付费接口；不会上传到远程仓库或第三方服务。")

        st.markdown("---")
        st.markdown("**可选：本地大模型增强**")
        st.caption("仅允许连接 localhost / 127.0.0.1 / ::1。未配置时使用明确标识的本地规则模式。")
        default_base = os.environ.get("XRAY_LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
        default_model = os.environ.get("XRAY_LOCAL_LLM_MODEL", "qwen2.5:3b")
        enable_llm = st.checkbox("启用本地大模型配置", value=False)
        llm_base = st.text_input("本地服务地址", value=default_base, disabled=not enable_llm)
        llm_model = st.text_input("本地模型名称", value=default_model, disabled=not enable_llm)
        signature = model_signature(llm_base, llm_model)
        if st.session_state.get("llm_signature") and st.session_state["llm_signature"] != signature:
            st.session_state["llm_ok"] = False
            st.session_state["llm_message"] = "地址或模型已变化，请重新测试连接。"
        if st.button("测试本地模型连接", disabled=not enable_llm, width="stretch"):
            try:
                client = LocalLLMClient(llm_base, llm_model)
                ok, message = client.check_available()
                st.session_state["llm_ok"] = ok
                st.session_state["llm_message"] = message
                st.session_state["llm_signature"] = signature
            except LocalLLMError as exc:
                st.session_state["llm_ok"] = False
                st.session_state["llm_message"] = str(exc)
                st.session_state["llm_signature"] = signature
        if enable_llm and st.session_state.get("llm_message"):
            if st.session_state.get("llm_ok"):
                st.success(st.session_state["llm_message"])
            else:
                st.warning(st.session_state["llm_message"])

        st.markdown("---")
        st.markdown("**当前任务**")
        review: ReviewSession | None = st.session_state.get("review")
        if review:
            st.caption(f"审核编号：{review.run_id}")
            st.caption(f"宣传主张：{len(review.claims)} 条")
            st.caption(f"模式：{ANALYSIS_MODE_LABELS.get(review.mode, review.mode)}")
        else:
            st.caption("尚未创建审核任务。")

        recent = store.list_reviews(limit=5)
        if recent:
            st.markdown("---")
            st.markdown("**最近本地记录**")
            for item in recent:
                tag = "合成" if item["is_synthetic"] else "材料"
                st.caption(f"{item['created_at'][:16].replace('T', ' ')}｜{item['title'][:18]}｜{tag}")

        st.markdown("---")
        st.caption("使用本工具不代表取得法律、监管或事实认定意见。")
    return enable_llm, llm_base, llm_model

