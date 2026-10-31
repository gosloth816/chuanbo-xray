"""模拟模型输出只测试程序边界，不是真实模型效果验证。"""

from src.models import DocumentChunk
from src.pipeline import _evidence_from_llm
from src.demo_data import load_demo_documents
from src.pipeline import analyze_documents
from src.metrics import workflow_metrics


def test_model_cannot_cite_chunk_outside_supplied_candidates():
    chunk = DocumentChunk("hidden", "资料", "reference", "第1段", "防效80%")
    result, warnings = _evidence_from_llm(
        {"evidence": [{"chunk_id": "hidden", "quote": "防效80%"}]},
        [], {"hidden": chunk}, {},
    )
    assert not result
    assert warnings


def test_metrics_record_timing_and_do_not_invent_quality_rate():
    session = analyze_documents(title="指标测试", documents=load_demo_documents())
    result = workflow_metrics(session)
    assert result["analysis_seconds"] is not None
    assert result["analysis_seconds"] >= 0
    assert result["reviewed_claim_count"] == 0
    assert result["review_completion_rate"] == 0
    session.claims = []
    result = workflow_metrics(session)
    assert result["quote_validation_rate"] is None
    assert result["review_completion_rate"] is None
