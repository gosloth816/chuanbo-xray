"""新建诊断页面。"""

from __future__ import annotations

from typing import Any

import streamlit as st

from .constants import is_public_deployment
from .demo_data import list_demo_cases, load_case_meta, load_demo_documents
from .local_llm import LocalLLMError
from .models import ParsedDocument, ReviewSession
from .parsing import DocumentParseError, parse_document_bytes, parse_text_document
from .pipeline import AnalysisError, analyze_documents
from .storage import ReviewStore
from .ui_sidebar import build_llm
from .ui_public import render_public_cases


DOC_ACCEPT = ["txt", "md", "pdf", "docx"]
IMAGE_ACCEPT = ["png", "jpg", "jpeg"]
MAX_FILE_BYTES = 20 * 1024 * 1024


def _parse_uploaded(files: list[Any], role: str) -> list[ParsedDocument]:
    documents: list[ParsedDocument] = []
    for uploaded in files:
        data = uploaded.getvalue()
        if len(data) > MAX_FILE_BYTES:
            raise DocumentParseError(f"{uploaded.name} 超过 20 MB 限制。")
        documents.append(parse_document_bytes(name=uploaded.name, role=role, data=data))
    return documents


def _save_new_session(review: ReviewSession, store: ReviewStore) -> None:
    st.session_state["review"] = review
    store.save_review(
        review,
        action="analysis_completed",
        actor="system",
        details={"mode": review.mode, "claim_count": len(review.claims), "is_synthetic": review.is_synthetic},
    )
    st.session_state["flash"] = f"审核任务 {review.run_id} 已生成，并保存到本地记录。"


def render_new_review(store: ReviewStore, enable_llm: bool, llm_base: str, llm_model: str) -> None:
    st.markdown("<div class='page-heading'><h1>传播 X 光</h1><p>农业科技宣传材料发布前审核。</p></div>", unsafe_allow_html=True)
    if is_public_deployment():
        st.warning("公开演示：上传材料会发送到托管服务器，请勿上传敏感或未获授权的材料。")
    render_public_cases(store, enable_llm, llm_base, llm_model)
    with st.expander("上传材料，新建审核任务", expanded=False):
        _render_upload_form(store, enable_llm, llm_base, llm_model)


def _render_upload_form(store: ReviewStore, enable_llm: bool, llm_base: str, llm_model: str) -> None:
    title = st.text_input("审核任务名称", value="农业科技产品宣传材料发布前审核", key="task_title")

    left, right = st.columns(2)
    with left:
        promotion_files = st.file_uploader(
            "宣传文案（可多选）",
            type=DOC_ACCEPT,
            accept_multiple_files=True,
            key="promotion_files",
            help="支持 TXT、MD、PDF、DOCX。扫描版 PDF 需要可提取文字或人工转写。",
        )
    with right:
        reference_files = st.file_uploader(
            "产品说明、技术报告或论文（可多选）",
            type=DOC_ACCEPT,
            accept_multiple_files=True,
            key="reference_files",
            help="至少上传一份可检索的产品或技术资料。",
        )

    poster = st.file_uploader("宣传海报（可选）", type=IMAGE_ACCEPT, accept_multiple_files=False, key="poster_file")
    poster_text = ""
    if poster:
        image_col, note_col = st.columns([1, 2])
        with image_col:
            st.image(poster.getvalue(), caption=poster.name, width="stretch")
        with note_col:
            st.info("当前版本不进行离线 OCR，也不会猜测海报文字。可人工转写海报中的文字，转写内容会作为宣传主张来源并保留为独立材料。")
            poster_text = st.text_area(
                "海报人工转写（可选）",
                height=170,
                key="poster_transcription",
                placeholder="按海报实际文字抄录，不要补充图片中没有的内容。",
            )

    mode_options = ["本地规则核验（无需模型，可离线运行）"]
    if enable_llm:
        mode_options.append("本地大模型增强（需本机服务）")
    selected_mode = st.radio("分析方式", mode_options, horizontal=True)
    mode = "local_llm" if selected_mode.startswith("本地大模型") else "offline_rules"

    demo_cases = list_demo_cases()
    demo_names = [case["case_name"] for case in demo_cases]
    selected_demo_name = st.selectbox("内置合成演示案例", demo_names, index=0)
    selected_demo_id = demo_cases[demo_names.index(selected_demo_name)]["case_id"]
    st.caption("演示案例均为明确标注的合成测试数据，不对应任何真实产品、企业、试验或论文。")

    action_col, demo_col = st.columns([2, 1])
    with action_col:
        analyze_clicked = st.button("开始诊断", type="primary", width="stretch")
    with demo_col:
        demo_clicked = st.button("加载合成演示案例", width="stretch")

    if demo_clicked:
        try:
            metadata = load_case_meta(selected_demo_id)
            with st.spinner("正在解析合成案例并检索证据..."):
                review = analyze_documents(
                    title=metadata["case_name"],
                    documents=load_demo_documents(selected_demo_id),
                    mode="offline_rules",
                )
                _save_new_session(review, store)
            st.success("合成演示案例已完成。请切换到“证据审查台”查看主张和原文证据。")
            st.rerun()
        except (AnalysisError, DocumentParseError) as exc:
            st.error(f"演示案例运行失败：{exc}")
        except Exception as exc:
            st.error(f"演示案例运行失败：{exc}")

    if analyze_clicked:
        if not promotion_files and not poster_text.strip():
            st.error("请至少上传一份宣传文案，或填写海报人工转写。")
            return
        if not reference_files:
            st.error("请至少上传一份产品/技术资料用于证据检索。")
            return
        try:
            with st.spinner("正在解析材料、提取主张并核对原始证据..."):
                documents: list[ParsedDocument] = []
                documents.extend(_parse_uploaded(promotion_files or [], "promotion"))
                documents.extend(_parse_uploaded(reference_files or [], "reference"))
                if poster:
                    if poster_text.strip():
                        documents.append(
                            parse_text_document(
                                name=f"{poster.name}（人工转写）",
                                role="poster",
                                text=poster_text,
                            )
                        )
                    else:
                        documents.append(
                            ParsedDocument(
                                name=poster.name,
                                role="poster",
                                content_type=poster.type or "image",
                                warnings=["海报图片未进行离线文字识别，也未参与主张提取；如需审核海报文字，请填写人工转写。"],
                                metadata={"file_size": len(poster.getvalue())},
                            )
                        )
                llm = build_llm(enable_llm, llm_base, llm_model) if mode == "local_llm" else None
                review = analyze_documents(title=title, documents=documents, mode=mode, llm=llm)
                _save_new_session(review, store)
            st.success(f"诊断完成：共识别 {len(review.claims)} 条宣传主张。请切换到“证据审查台”继续人工复核。")
            st.rerun()
        except (AnalysisError, DocumentParseError, LocalLLMError) as exc:
            st.error(f"分析未完成：{exc}")
        except Exception as exc:
            st.error(f"分析未完成：{exc}")
