"""只计算运行事实，不把程序耗时当作人工效率提升。"""

from .models import ReviewSession


def workflow_metrics(session: ReviewSession) -> dict:
    evidence = [e for c in session.claims for e in c.evidence]
    total = len(session.claims)
    reviewed = sum(c.human_review.status in {"accepted", "modified", "rejected"} for c in session.claims)
    return {
        "analysis_seconds": session.analysis_seconds,
        "claim_count": total,
        "reviewed_claim_count": reviewed,
        "review_completion_rate": reviewed / total if total else None,
        "quote_count": len(evidence),
        "valid_quote_count": sum(e.quote_valid for e in evidence),
        "quote_validation_rate": sum(e.quote_valid for e in evidence) / len(evidence) if evidence else None,
        "claims_without_evidence": sum(not c.evidence for c in session.claims),
        "modified_claim_count": sum(c.human_review.status == "modified" for c in session.claims),
        "notice": "程序分析耗时不含人工审核时间；引用校验率不等于判断准确率。未采集对照人工耗时，不能据此宣称效率提升。",
    }
