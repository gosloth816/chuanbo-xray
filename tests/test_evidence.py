from src.evidence import (
    EvidenceIndex,
    classify_claim_offline,
    extract_claim_sentences,
    quote_exists_in_chunk,
    retrieve_evidence,
    tokenize,
)
from src.models import DocumentChunk, EvidenceItem


def make_chunk(chunk_id: str, text: str) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        source_name="试验摘要.txt",
        role="reference",
        location="第 1 页 · 段落 1",
        text=text,
    )


def evidence_for(chunk: DocumentChunk, quote: str) -> EvidenceItem:
    return EvidenceItem(
        chunk_id=chunk.chunk_id,
        source_name=chunk.source_name,
        location=chunk.location,
        quote=quote,
        retrieval_score=1.2,
        quote_valid=True,
        validation_note="原文逐字校验通过",
    )


def test_tokenize_chinese_and_numbers():
    tokens = tokenize("番茄灰霉病防效82.4%")
    assert "番茄" in tokens
    assert "82.4%" in tokens


def test_retrieval_finds_quantitative_evidence():
    chunks = [
        make_chunk("a", "试验结果：灰霉病防效达到82.4%。"),
        make_chunk("b", "产品包装规格为每瓶100毫升。"),
    ]
    index = EvidenceIndex(chunks)
    results = index.search("番茄灰霉病防效可达82.4%")
    assert results
    assert results[0].chunk.chunk_id == "a"


def test_quote_validation_is_exact_after_whitespace_normalization():
    assert quote_exists_in_chunk("防效达到 82.4%", "试验结果：\n防效达到 82.4%。")
    assert not quote_exists_in_chunk("防效达到 92%", "试验结果：防效达到 82.4%。")


def test_claim_extraction_keeps_numeric_and_capability_claims():
    claims = extract_claim_sentences("本产品防效可达82.4%。包装规格为100毫升。产品安全无残留。")
    assert "本产品防效可达82.4%。" in claims
    assert "产品安全无残留。" in claims


def test_offline_conflict_detection():
    chunk = make_chunk("a", "在山东泰安设施番茄试验中，推荐剂量处理组灰霉病防效为82.4%。")
    verdict, rationale, _ = classify_claim_offline(
        "使用绿盾一号后，番茄灰霉病防效可达92%。",
        [evidence_for(chunk, "在山东泰安设施番茄试验中，推荐剂量处理组灰霉病防效为82.4%。")],
        [chunk],
    )
    assert verdict == "conflicting"
    assert "数值" in rationale


def test_offline_conditional_detection():
    chunk = make_chunk("a", "在山东泰安设施番茄试验中，推荐剂量处理组灰霉病防效为82.4%。")
    verdict, _, _ = classify_claim_offline(
        "本产品对番茄灰霉病防效可达82.4%。",
        [evidence_for(chunk, "在山东泰安设施番茄试验中，推荐剂量处理组灰霉病防效为82.4%。")],
        [chunk],
    )
    assert verdict == "conditionally_supported"


def test_offline_missing_evidence():
    verdict, rationale, _ = classify_claim_offline("本产品可减少化学农药使用量50%。", [], [])
    assert verdict == "insufficient"
    assert "没有找到证据不等于证明宣传虚假" in rationale


def test_retrieve_evidence_discards_unrelated_chunks():
    chunks = [make_chunk("a", "包装规格为每瓶100毫升。")]
    evidence = retrieve_evidence("本产品可减少化学农药使用量50%", chunks)
    assert evidence == []
