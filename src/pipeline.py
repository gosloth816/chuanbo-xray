"""从材料到证据审核结果的完整流水线。"""

from __future__ import annotations

import re
import time
from typing import Any

from .constants import LIMITATIONS, PROMPT_VERSION
from .evidence import (
    classify_claim_offline,
    extract_claim_sentences,
    quote_exists_in_chunk,
    retrieve_evidence,
)
from .local_llm import LocalLLMClient, LocalLLMError
from .models import Claim, DocumentChunk, EvidenceItem, ParsedDocument, ReviewSession


class AnalysisError(RuntimeError):
    """分析流程无法可靠完成时抛出。"""


def _apply_evidence_scope(claim: Claim, documents: list[ParsedDocument]) -> None:
    references = [doc for doc in documents if doc.role == "reference"]
    if references and all(doc.metadata.get("scope") == "general_guidance" for doc in references):
        if any(term in claim.text for term in ("本产品", "这款产品", "该产品")) or re.search(r"(?:增产|提高|减少|降低).{0,12}\d+(?:\.\d+)?%", claim.text):
            claim.verdict = "insufficient"
            claim.rationale = "当前参考资料全部为通用技术指导，不能证明某个具体产品或方案的效果、登记范围或安全性。即使词语或数值吻合，也需要对应产品的直接证据。"
            claim.suggested_revision = "删除没有单品证据的效果承诺；补充该产品的可核对资料及适用条件后再复核。"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).strip()


def _find_source_name(claim_text: str, promotion_documents: list[ParsedDocument]) -> str:
    normalized_claim = _normalize_text(claim_text)
    for document in promotion_documents:
        if normalized_claim in _normalize_text(document.text):
            return document.name
    return promotion_documents[0].name if promotion_documents else "宣传材料"


def _candidate_payload(evidence: list[EvidenceItem], chunks: list[DocumentChunk]) -> list[dict[str, str]]:
    chunk_map = {chunk.chunk_id: chunk for chunk in chunks}
    payload: list[dict[str, str]] = []
    for item in evidence:
        chunk = chunk_map.get(item.chunk_id)
        if not chunk:
            continue
        payload.append(
            {
                "chunk_id": chunk.chunk_id,
                "source_name": chunk.source_name,
                "location": chunk.location,
                "text": chunk.text,
            }
        )
    return payload


def _evidence_from_llm(
    raw_result: dict[str, Any],
    candidates: list[dict[str, str]],
    chunk_map: dict[str, DocumentChunk],
    score_map: dict[str, float],
) -> tuple[list[EvidenceItem], list[str]]:
    raw_evidence = raw_result.get("evidence", [])
    items: list[EvidenceItem] = []
    warnings: list[str] = []
    seen: set[str] = set()
    candidate_ids = {item["chunk_id"] for item in candidates}
    for raw in raw_evidence:
        if not isinstance(raw, dict):
            warnings.append("模型返回了无法识别的证据条目，已忽略。")
            continue
        chunk_id = str(raw.get("chunk_id", "")).strip()
        quote = str(raw.get("quote", "")).strip()
        if chunk_id not in candidate_ids or chunk_id not in chunk_map:
            warnings.append(f"模型引用了不存在的候选证据 {chunk_id or '（空）'}，已忽略。")
            continue
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        chunk = chunk_map[chunk_id]
        valid = quote_exists_in_chunk(quote, chunk.text)
        items.append(
            EvidenceItem(
                chunk_id=chunk_id,
                source_name=chunk.source_name,
                location=chunk.location,
                quote=quote,
                retrieval_score=score_map.get(chunk_id, 0.0),
                quote_valid=valid,
                validation_note="原文逐字校验通过" if valid else "模型引用未在原文中逐字找到",
            )
        )
    return items, warnings


def _analyze_claim(
    *,
    claim_text: str,
    source_name: str,
    reference_chunks: list[DocumentChunk],
    mode: str,
    llm: LocalLLMClient | None,
    claim_id: str,
) -> Claim:
    evidence = retrieve_evidence(claim_text, reference_chunks)
    if mode == "offline_rules":
        verdict, rationale, suggestion = classify_claim_offline(claim_text, evidence, reference_chunks)
        return Claim(
            claim_id=claim_id,
            text=claim_text,
            source_name=source_name,
            verdict=verdict,
            rationale=rationale,
            suggested_revision=suggestion,
            evidence=evidence,
            extraction_method="offline_rules",
        )

    if llm is None:
        raise AnalysisError("启用了本地大模型模式，但没有可用的模型客户端。")
    chunk_map = {chunk.chunk_id: chunk for chunk in reference_chunks}
    score_map = {item.chunk_id: item.retrieval_score for item in evidence}
    candidates = _candidate_payload(evidence, reference_chunks)
    try:
        raw_result = llm.analyze_claim(claim_text, candidates)
    except LocalLLMError as exc:
        raise AnalysisError(str(exc)) from exc
    llm_evidence, evidence_warnings = _evidence_from_llm(raw_result, candidates, chunk_map, score_map)
    verdict = raw_result["verdict"]
    valid_evidence = [item for item in llm_evidence if item.quote_valid]
    rationale = raw_result["rationale"]
    if evidence_warnings:
        rationale += "\n\n引用校验提示：" + " ".join(evidence_warnings)
    if evidence_warnings or (verdict != "insufficient" and not valid_evidence):
        verdict = "manual_review"
        rationale += "\n\n模型引用存在异常或判断缺少有效证据，因此转为待人工核验。"
    if any(not item.quote_valid for item in llm_evidence):
        verdict = "manual_review"
    return Claim(
        claim_id=claim_id,
        text=claim_text,
        source_name=source_name,
        verdict=verdict,
        rationale=rationale,
        suggested_revision=raw_result["suggested_revision"],
        evidence=llm_evidence,
        extraction_method="local_llm",
    )


def analyze_documents(
    *,
    title: str,
    documents: list[ParsedDocument],
    mode: str = "offline_rules",
    llm: LocalLLMClient | None = None,
) -> ReviewSession:
    started = time.perf_counter()
    if mode not in {"offline_rules", "local_llm"}:
        raise AnalysisError("未知分析模式。")
    promotion_documents = [doc for doc in documents if doc.role in {"promotion", "poster"}]
    reference_documents = [doc for doc in documents if doc.role == "reference"]
    reference_chunks = [chunk for doc in reference_documents for chunk in doc.chunks]
    promotion_text = "\n".join(doc.text for doc in promotion_documents if doc.text.strip()).strip()
    if not promotion_text:
        raise AnalysisError("没有可分析的宣传文本。请上传含可提取文字的文案，或填写海报人工转写。")
    if not reference_chunks:
        raise AnalysisError("没有可检索的产品/技术资料。请至少上传一份含可提取文字的资料。")

    warnings = [warning for doc in documents for warning in doc.warnings]
    is_synthetic = any(doc.is_synthetic for doc in documents)
    if is_synthetic:
        warnings.append("本次审核包含明确标注的合成测试材料，不能作为真实产品结论使用。")
    if mode == "offline_rules":
        warnings.append("当前使用本地规则核验模式，未调用大模型；判断依据来自关键词检索、数值核对和限制语提示。")

    if mode == "local_llm":
        if llm is None:
            raise AnalysisError("本地大模型模式不可用，请先测试本地模型连接。")
        try:
            claim_texts = llm.extract_claims(promotion_text)
        except LocalLLMError as exc:
            raise AnalysisError(str(exc)) from exc
        normalized_promotion = _normalize_text(promotion_text)
        for claim_text in claim_texts:
            if _normalize_text(claim_text) not in normalized_promotion:
                raise AnalysisError(f"模型提取的主张未能在宣传原文中逐字定位：{claim_text}")
    else:
        claim_texts = extract_claim_sentences(promotion_text)

    if not claim_texts:
        raise AnalysisError("未提取到可核验的宣传主张。请检查宣传文本，或在审核阶段手动补充主张。")

    claims: list[Claim] = []
    for index, claim_text in enumerate(claim_texts, start=1):
        source_name = _find_source_name(claim_text, promotion_documents)
        claims.append(
            _analyze_claim(
                claim_text=claim_text,
                source_name=source_name,
                reference_chunks=reference_chunks,
                mode=mode,
                llm=llm,
                claim_id=f"CLM-{index:03d}",
            )
        )

    # 通用技术指导与具体产品试验属于不同证据层级，避免把背景知识当成单品证明。
    for claim in claims:
        _apply_evidence_scope(claim, documents)

    session = ReviewSession.create(
        title=title.strip() or "未命名审核任务",
        mode=mode,
        model_name=llm.model if llm else "",
        documents=documents,
        claims=claims,
        prompt_version=PROMPT_VERSION,
        warnings=warnings,
        limitations=list(LIMITATIONS),
        is_synthetic=is_synthetic,
    )
    session.analysis_seconds = round(time.perf_counter() - started, 4)
    return session


def add_manual_claim(
    *,
    session: ReviewSession,
    claim_text: str,
    reviewer: str,
    mode: str | None = None,
    llm: LocalLLMClient | None = None,
) -> Claim:
    clean_text = claim_text.strip()
    if len(clean_text) < 4:
        raise AnalysisError("人工补充的主张过短，无法检索证据。")
    if any(claim.text.strip() == clean_text for claim in session.claims):
        raise AnalysisError("该主张已存在，无需重复添加。")
    reference_chunks = [chunk for doc in session.documents if doc.role == "reference" for chunk in doc.chunks]
    promotion_documents = [doc for doc in session.documents if doc.role in {"promotion", "poster"}]
    source_name = _find_source_name(clean_text, promotion_documents) if promotion_documents else "人工补充"
    claim_id = f"CLM-{len(session.claims) + 1:03d}"
    claim = _analyze_claim(
        claim_text=clean_text,
        source_name=source_name,
        reference_chunks=reference_chunks,
        mode=mode or session.mode,
        llm=llm,
        claim_id=claim_id,
    )
    claim.extraction_method = "manual"
    _apply_evidence_scope(claim, session.documents)
    session.claims.append(claim)
    return claim
