import json

from src.demo_data import load_demo_documents
from src.models import HumanReview
from src.pipeline import analyze_documents
from src.readiness import review_readiness
from src.report import build_html_report, build_json_report, build_markdown_report


def session():
    return analyze_documents(title="完整性检查", documents=load_demo_documents())


def test_draft_status_survives_all_exports():
    review = session()
    assert review_readiness(review)["status"] == "复核草稿"
    assert "报告状态：复核草稿" in build_html_report(review)
    assert "报告状态：复核草稿" in build_markdown_report(review)
    assert json.loads(build_json_report(review))["review_readiness"]["issues"]


def test_accepting_everything_does_not_hide_unresolved_risk():
    review = session()
    for claim in review.claims:
        claim.human_review = HumanReview(status="accepted", reviewer="甲", reviewed_at="2026-10-31")
    result = review_readiness(review)
    assert result["status"] == "待处理"
    assert any("人工结论仍需补证或处理" in item["reasons"] for item in result["issues"])


def test_rejected_claims_require_reason_and_are_not_release_approval():
    review = session()
    for claim in review.claims:
        claim.human_review = HumanReview(status="rejected", reviewer="甲", note="从发布稿删除", reviewed_at="2026-10-31")
    assert review_readiness(review)["status"] == "复核记录完整"
    assert "须从发布稿删除" in review_readiness(review)["notice"]
    review.claims[0].human_review.note = ""
    assert review_readiness(review)["status"] == "待处理"


def test_modified_supported_claim_needs_text_and_valid_evidence():
    review = session()
    review.claims = review.claims[:1]
    claim = review.claims[0]
    claim.human_review = HumanReview(status="modified", reviewer="甲", note="补充条件", final_verdict="conditionally_supported", reviewed_at="2026-10-31")
    assert review_readiness(review)["issues"]
    claim.human_review.final_text = "仅限所述试验条件"
    assert review_readiness(review)["status"] == "复核记录完整"
    claim.evidence[0].quote_valid = False
    assert review_readiness(review)["status"] == "待处理"


def test_empty_claim_set_cannot_be_complete():
    review = session()
    review.claims = []
    assert review_readiness(review)["status"] == "复核草稿"
