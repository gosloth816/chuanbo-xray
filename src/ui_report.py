"""报告导出与关于页面。"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from .constants import (
    AI_DISCLOSURE,
    APP_NAME,
    APP_SUBTITLE,
    APP_VERSION,
    PROMPT_VERSION,
    REVIEW_STATUS_LABELS,
    VERDICT_DESCRIPTIONS,
    VERDICT_LABELS,
)
from .models import ReviewSession
from .report import build_html_report, build_json_report, build_markdown_report, safe_filename
from .storage import ReviewStore


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def render_report(store: ReviewStore) -> None:
    review: ReviewSession | None = st.session_state.get("review")
    if not review:
        st.info("尚未创建审核任务，暂无可导出的报告。")
        return
    audit_events = store.get_events(review.run_id)
    counts = review.verdict_counts
    review_counts = review.review_counts
    st.markdown(
        f"""
        <div class="section-head">
          <div>
            <span class="section-eyebrow">Output / Audit Report</span>
            <h2>导出审核报告</h2>
            <p>{html.escape(review.title)} · 系统判断、原文证据、人工复核、使用边界和操作留痕。</p>
          </div>
          <span class="section-chip">HTML · Markdown · JSON</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if review_counts["unreviewed"]:
        st.warning(f"仍有 {review_counts['unreviewed']} 条主张未完成人工复核。当前导出的报告会如实显示未复核状态。")

    summary_rows = [
        {"判断类别": VERDICT_LABELS[key], "数量": counts[key], "说明": VERDICT_DESCRIPTIONS[key]}
        for key in VERDICT_LABELS
    ]
    st.dataframe(summary_rows, width="stretch", hide_index=True)

    html_report = build_html_report(review, audit_events)
    markdown_report = build_markdown_report(review, audit_events)
    json_report = build_json_report(review, audit_events)
    base_name = safe_filename(review.title)
    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            "下载 HTML 报告",
            data=html_report,
            file_name=f"{base_name}-审核报告.html",
            mime="text/html",
            width="stretch",
        )
    with d2:
        st.download_button(
            "下载 Markdown 报告",
            data=markdown_report,
            file_name=f"{base_name}-审核报告.md",
            mime="text/markdown",
            width="stretch",
        )
    with d3:
        st.download_button(
            "下载结构化 JSON",
            data=json_report,
            file_name=f"{base_name}-审核记录.json",
            mime="application/json",
            width="stretch",
        )

    st.markdown("### 报告预览")
    components.html(html_report, height=760, scrolling=True)
    with st.expander("查看操作留痕"):
        if audit_events:
            for event in audit_events:
                st.caption(f"{event['timestamp']}｜{event['actor']}｜{event['action']}｜{event['details_json'][:180]}")
        else:
            st.caption("尚无操作留痕记录。")


def _load_verification() -> dict[str, Any] | None:
    path = PROJECT_ROOT / "docs" / "verification.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def render_about() -> None:
    st.markdown(
        """
        <div class="section-head">
          <div>
            <span class="section-eyebrow">System / Transparency</span>
            <h2>产品说明与 AI 使用披露</h2>
            <p>运行边界、提示词版本、测试记录和本地隐私策略。</p>
          </div>
          <span class="section-chip">Verified Locally</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        "<strong>传播 X 光</strong>不是文案生成器，也不是违法或造假判定系统。"
        "它帮助山东农业科技企业、植保产品企业的宣传审核人员，在材料发布前核查每条宣传主张是否有上传资料支持、"
        "是否遗漏试验条件、是否存在数值冲突，以及哪些内容必须人工确认。",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<strong>关键原则：</strong>没有检索到证据，不等于证明宣传虚假；系统判断不是事实认定，必须由人复核。",
        unsafe_allow_html=True,
    )

    st.markdown("### 工作流")
    st.code(
        "上传宣传材料与产品资料 → 文档解析 → 主张提取 → 证据检索 → 原文引用校验\n"
        "→ 风险分类 → 人工复核与修改 → 留痕 → HTML / Markdown / JSON 导出",
        language=None,
    )

    st.markdown("### AI 使用披露")
    for value in AI_DISCLOSURE.values():
        st.markdown(f"- {value}")

    st.markdown("### 当前可验证状态")
    verification = _load_verification()
    if verification:
        status = "通过" if verification.get("passed") else "未通过"
        st.success(
            f"最近一次自动测试：{status}｜{verification.get('passed_tests', 0)} passed｜"
            f"运行时间：{verification.get('ran_at', '未记录')}"
        )
        st.caption(f"测试命令：{verification.get('command', '未记录')}")
        if verification.get("scope"):
            st.caption(f"覆盖范围：{verification['scope']}")
    else:
        st.info("尚未生成自动测试验证记录。请运行项目测试后再查看。")

    st.markdown("### 本地大模型配置")
    st.markdown(
        "- 默认模式不调用模型，所有解析、检索和规则判断在本机完成。\n"
        "- 如自行启动本机兼容服务，可以在侧边栏填写地址和模型名并测试连接。\n"
        "- 应用会拒绝 `localhost`、`127.0.0.1`、`::1` 之外的地址，避免材料离开本机。\n"
        "- 模型调用失败时，系统直接提示失败，不会用固定文案冒充分析结果。"
    )

    st.markdown("### 版本信息")
    st.code(
        f"应用版本：{APP_VERSION}\n提示词版本：{PROMPT_VERSION}\n报告标准：传播X光审核报告-v2",
        language=None,
    )

    st.markdown("### 使用边界")
    for item in [
        "本工具只核验上传资料与宣传主张之间的关系，不判断资料本身是否真实、完整或具有法律效力。",
        "未检索到证据不等于宣传虚假。",
        "本地规则模式依赖关键词、数值和限制语提示，适合流程验证，不等同于完整语义判断。",
        "扫描版 PDF 和图片若没有可提取文字或人工转写，系统不会猜测其内容。",
        "正式发布前仍需企业审核、专业判断和必要的法律审查。",
    ]:
        st.markdown(f"- {item}")

