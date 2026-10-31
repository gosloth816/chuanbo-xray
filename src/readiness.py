"""汇总复核记录完整性；不据此批准宣传材料发布。"""

from .models import ReviewSession


def review_readiness(session: ReviewSession) -> dict:
    issues = []
    for claim in session.claims:
        review = claim.human_review
        reasons = []
        if review.status not in {"accepted", "modified", "rejected"}:
            reasons.append("尚未完成人工复核")
        else:
            if not review.reviewer.strip() or not review.reviewed_at.strip():
                reasons.append("缺少复核人或复核时间")
            if review.status in {"modified", "rejected"} and not review.note.strip():
                reasons.append("修改或驳回缺少理由")
            if review.status != "rejected":
                final = claim.verdict if review.status == "accepted" else review.final_verdict
                if final not in {"supported", "conditionally_supported"}:
                    reasons.append("人工结论仍需补证或处理")
                if review.status == "modified" and not review.final_text.strip():
                    reasons.append("修改后尚未填写最终表述")
                if final == "conditionally_supported" and not review.final_text.strip():
                    reasons.append("条件支持尚未填写包含适用条件的最终表述")
                if not claim.evidence or any(not e.quote_valid for e in claim.evidence):
                    reasons.append("原始证据缺失或引用校验未通过")
                if review.status == "accepted" and review.final_verdict and review.final_verdict != claim.verdict:
                    reasons.append("确认记录与系统结论不一致")
        if reasons:
            issues.append({"claim_id": claim.claim_id, "reasons": reasons})
    if not session.claims:
        issues.append({"claim_id": "任务", "reasons": ["未提取到主张，需人工检查材料覆盖范围"]})
    if any(c.human_review.status == "unreviewed" for c in session.claims) or not session.claims:
        status = "复核草稿"
    else:
        status = "待处理" if issues else "复核记录完整"
    return {
        "status": status,
        "total_claims": len(session.claims),
        "issues": issues,
        "notice": "仅检查复核记录完整性，不代表材料可发布；驳回内容须从发布稿删除，资料真实性与适用条件仍需专业审核。",
    }
