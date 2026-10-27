"""证据审查台与人工复核交互。"""

from __future__ import annotations

import html

import streamlit as st

from .constants import (
    ANALYSIS_MODE_LABELS,
    REVIEW_STATUS_LABELS,
    VERDICT_DESCRIPTIONS,
    VERDICT_LABELS,
)
from .local_llm import LocalLLMError
from .models import Claim, HumanReview, ReviewSession, now_iso
from .pipeline import AnalysisError, add_manual_claim
from .storage import ReviewStore
from .ui_sidebar import build_llm
from .ui_theme import badge


REVIEW_ACTIONS = ["未复核", "确认系统判断", "修改判断", "驳回主张"]


def _status_text(claim: Claim) -> str:
    review = claim.human_review
    status = REVIEW_STATUS_LABELS.get(review.status, review.status)
    pieces = [f"复核状态：{status}"]
    if review.reviewer:
        pieces.append(f"复核人：{review.reviewer}")
    if review.reviewed_at:
        pieces.append(f"时间：{review.reviewed_at}")
    return "｜".join(pieces)


def _verdict_option_index(verdict: str) -> int:
    values = list(VERDICT_LABELS.keys())
    return values.index(verdict) if verdict in values else 0


def render_claim_review(store: ReviewStore, review: ReviewSession, claim: Claim) -> None:
    with st.container(border=True):
        head, state = st.columns([4, 1])
        with head:
            st.markdown(f"#### {claim.claim_id} · {claim.text}")
            st.markdown(
                f"{badge(claim.verdict)} <span class='xray-status'>来源：{html.escape(claim.source_name)} · 提取方式：{html.escape(claim.extraction_method)}</span>",
                unsafe_allow_html=True,
            )
        with state:
            st.markdown(
                f"<div class='xray-status' style='text-align:right'>{html.escape(_status_text(claim))}</div>",
                unsafe_allow_html=True,
            )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**系统判断依据**")
            st.write(claim.rationale)
        with c2:
            st.markdown("**建议修改方向**")
            st.write(claim.suggested_revision)

        with st.expander(f"查看原始证据（{len(claim.evidence)} 条）"):
            st.caption(VERDICT_DESCRIPTIONS.get(claim.verdict, ""))
            if not claim.evidence:
                st.warning("未检索到可定位证据。没有找到证据不等于证明宣传虚假。")
            for evidence in claim.evidence:
                validation = "✅ 原文逐字校验通过" if evidence.quote_valid else "❌ 原文逐字校验未通过"
                st.markdown(
                    "<div class='xray-evidence'>"
                    f"<div class='xray-evidence-meta'><strong>{html.escape(evidence.source_name)}</strong> · "
                    f"{html.escape(evidence.location)} · {validation} · 检索分 {evidence.retrieval_score:.2f}</div>"
                    f"{html.escape(evidence.quote)}</div>",
                    unsafe_allow_html=True,
                )

        current_status = claim.human_review.status
        action_default = {
            "accepted": "确认系统判断",
            "modified": "修改判断",
            "rejected": "驳回主张",
        }.get(current_status, "未复核")
        current_final_verdict = claim.human_review.final_verdict or claim.verdict
        with st.form(f"human_review_{claim.claim_id}"):
            st.markdown("**人工复核留痕**")
            f1, f2, f3 = st.columns(3)
            with f1:
                action = st.selectbox(
                    "处理方式",
                    REVIEW_ACTIONS,
                    index=REVIEW_ACTIONS.index(action_default),
                    key=f"action_{claim.claim_id}",
                )
            with f2:
                final_label = st.selectbox(
                    "人工结论",
                    list(VERDICT_LABELS.values()),
                    index=_verdict_option_index(current_final_verdict),
                    key=f"final_verdict_{claim.claim_id}",
                )
            with f3:
                reviewer = st.text_input(
                    "复核人",
                    value=claim.human_review.reviewer,
                    key=f"reviewer_{claim.claim_id}",
                    placeholder="姓名或岗位",
                )
            note = st.text_area(
                "人工意见 / 核实说明",
                value=claim.human_review.note,
                height=86,
                key=f"note_{claim.claim_id}",
                placeholder="说明为什么修改、驳回或维持系统判断。修改或驳回时必填。",
            )
            final_text = st.text_area(
                "最终表述建议（可编辑）",
                value=claim.human_review.final_text,
                height=76,
                key=f"final_text_{claim.claim_id}",
                placeholder="填写可进入报告和发布材料的修改表述。",
            )
            submitted = st.form_submit_button("保存该条人工复核", type="primary")
        if submitted:
            if action != "未复核" and not reviewer.strip():
                st.error("请填写复核人。")
                return
            if action in {"修改判断", "驳回主张"} and not note.strip():
                st.error("修改或驳回系统判断时，请填写人工意见。")
                return
            verdict_values = list(VERDICT_LABELS.keys())
            selected_final = verdict_values[list(VERDICT_LABELS.values()).index(final_label)]
            if action == "未复核":
                status = "unreviewed"
                selected_final = ""
            elif action == "确认系统判断":
                status = "accepted"
                selected_final = claim.verdict
            elif action == "修改判断":
                status = "modified"
            else:
                status = "rejected"
            claim.human_review = HumanReview(
                status=status,
                reviewer=reviewer.strip(),
                note=note.strip(),
                final_text=final_text.strip(),
                final_verdict=selected_final,
                reviewed_at=now_iso() if action != "未复核" else "",
            )
            store.save_review(
                review,
                action="human_review_saved",
                actor=reviewer.strip() or "未填写",
                details={
                    "claim_id": claim.claim_id,
                    "system_verdict": claim.verdict,
                    "human_status": status,
                    "final_verdict": selected_final,
                    "note": note.strip(),
                },
            )
            st.session_state["flash"] = f"{claim.claim_id} 的人工复核记录已保存。"
            st.rerun()


def render_reviewer(store: ReviewStore, enable_llm: bool, llm_base: str, llm_model: str) -> None:
    review: ReviewSession | None = st.session_state.get("review")
    if not review:
        st.info("尚未创建审核任务。请先在“新建诊断”中上传材料，或加载内置合成案例。")
        return

    if st.session_state.get("flash"):
        st.success(st.session_state.pop("flash"))

    counts = review.verdict_counts
    review_counts = review.review_counts
    st.subheader(review.title)
    st.caption(
        f"审核编号 {review.run_id}｜{ANALYSIS_MODE_LABELS.get(review.mode, review.mode)}｜"
        f"模型 {review.model_name or '未调用'}｜提示词 {review.prompt_version}"
    )
    if review.is_synthetic:
        st.warning("当前任务包含明确标注的合成测试材料，只用于功能演示，不能作为真实产品结论。")
    for warning in review.warnings:
        st.info(warning)

    cols = st.columns(5)
    for col, key in zip(cols, ("supported", "conditionally_supported", "insufficient", "conflicting", "manual_review")):
        with col:
            st.markdown(
                f'<div class="xray-metric"><span>{VERDICT_LABELS[key]}</span><strong>{counts[key]}</strong>'
                f'<small>{VERDICT_DESCRIPTIONS[key][:22]}…</small></div>',
                unsafe_allow_html=True,
            )

    st.write("")
    reviewed_count = review_counts["accepted"] + review_counts["modified"] + review_counts["rejected"]
    st.markdown(
        f"<div class='xray-boundary'>已有 <strong>{reviewed_count}</strong> / {len(review.claims)} 条完成人工复核；"
        f"仍有 <strong>{review_counts['unreviewed']}</strong> 条未复核。系统判断必须经过人工确认后才能进入最终发布建议。</div>",
        unsafe_allow_html=True,
    )

    filter_labels = ["全部"] + [VERDICT_LABELS[key] for key in VERDICT_LABELS]
    selected_filter = st.selectbox("按系统判断筛选", filter_labels, index=0)
    selected_verdict = (
        None
        if selected_filter == "全部"
        else list(VERDICT_LABELS.keys())[list(VERDICT_LABELS.values()).index(selected_filter)]
    )
    claims = review.claims if selected_verdict is None else [claim for claim in review.claims if claim.verdict == selected_verdict]

    if not claims:
        st.info("当前筛选条件下没有宣传主张。")
    for claim in claims:
        render_claim_review(store, review, claim)

    with st.expander("补充一条人工发现的主张"):
        with st.form("manual_claim_form"):
            manual_text = st.text_area("待核验主张", height=80, placeholder="填写宣传材料中需要核查的具体表述。")
            manual_reviewer = st.text_input("补充人", placeholder="姓名或岗位")
            manual_submit = st.form_submit_button("检索证据并加入审核清单")
        if manual_submit:
            if len(manual_text.strip()) < 4:
                st.error("主张过短，无法检索证据。")
            elif not manual_reviewer.strip():
                st.error("请填写补充人。")
            else:
                try:
                    llm = None
                    if review.mode == "local_llm":
                        llm = build_llm(enable_llm, llm_base, llm_model)
                    claim = add_manual_claim(
                        session=review,
                        claim_text=manual_text,
                        reviewer=manual_reviewer.strip(),
                        mode=review.mode,
                        llm=llm,
                    )
                    store.save_review(
                        review,
                        action="manual_claim_added",
                        actor=manual_reviewer.strip(),
                        details={"claim_id": claim.claim_id, "claim_text": claim.text, "verdict": claim.verdict},
                    )
                    st.session_state["flash"] = f"{claim.claim_id} 已加入审核清单。"
                    st.rerun()
                except (AnalysisError, LocalLLMError) as exc:
                    st.error(f"补充主张失败：{exc}")

