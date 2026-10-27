"""证据检索、引用校验与离线规则判断。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re
from typing import Iterable

from .models import DocumentChunk, EvidenceItem

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_ALNUM_RUN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?%?")
_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;])|\n+")
_CLAIM_SPLIT = re.compile(r"(?<=[。！？!?；;])\s*|\n+")
_QUANTITY = re.compile(r"(?<!\d)(\d+(?:\.\d+)?)\s*(%|％|倍|天|次|公斤|千克|克|毫升|亩|株|年|小时)")
_STOP_TOKENS = {
    "本产品", "产品", "使用", "可达", "达到", "能够", "可以", "进行", "通过", "以及",
    "相关", "资料", "结果", "具有", "适用", "作用", "显示", "表明", "主要", "其中",
}

CLAIM_CUES = (
    "防效", "防治", "防控", "抑制", "增产", "产量", "减少", "减量", "提升", "提高",
    "降低", "有效", "显著", "达到", "可达", "适用", "安全", "无残留", "零风险",
    "所有", "全部", "任何", "彻底", "保证", "唯一", "第一", "领先", "改善", "增强",
    "研发", "登记", "推荐", "可减少",
)

BROAD_CUES = (
    "所有", "全部", "任何", "完全", "彻底", "绝对", "保证", "零风险", "无残留",
    "安全无害", "100%", "永久", "无副作用", "不受", "均适用",
)

CONDITION_CUES = (
    "试验", "试验中", "条件下", "供试品种", "推荐剂量", "小区试验", "处理组", "对照组",
    "山东泰安", "设施番茄", "单一品种", "仅完成", "仅验证", "本试验",
)

NEGATIVE_EVIDENCE_CUES = (
    "未设置", "未开展", "未检测", "未验证", "不能据此", "尚不能", "不适用于",
    "没有提供", "无相关数据", "仅完成", "未覆盖", "无法判断", "尚无",
)

METRIC_GROUPS = {
    "防效": ("防效", "防治效果", "防病效果", "抑制"),
    "产量": ("产量", "增产", "提高产量"),
    "农药减量": ("农药", "减量", "减少", "施药"),
    "残留": ("残留", "安全"),
    "范围": ("适用", "所有", "品种", "作物"),
}


def tokenize(text: str) -> list[str]:
    normalized = text.lower().replace("％", "%")
    tokens: list[str] = []
    for run in _CJK_RUN.findall(normalized):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    tokens.extend(_ALNUM_RUN.findall(normalized))
    return [token for token in tokens if token not in _STOP_TOKENS]


@dataclass
class ScoredChunk:
    chunk: DocumentChunk
    score: float


class EvidenceIndex:
    def __init__(self, chunks: Iterable[DocumentChunk]):
        self.chunks = [chunk for chunk in chunks if chunk.text.strip()]
        self.doc_tokens = [tokenize(chunk.text) for chunk in self.chunks]
        self.doc_freq: Counter[str] = Counter()
        for tokens in self.doc_tokens:
            self.doc_freq.update(set(tokens))
        self.avg_length = sum(len(tokens) for tokens in self.doc_tokens) / max(len(self.doc_tokens), 1)
        self.lengths = [len(tokens) for tokens in self.doc_tokens]
        self.counts = [Counter(tokens) for tokens in self.doc_tokens]
        self.total_docs = len(self.chunks)

    def _idf(self, token: str) -> float:
        df = self.doc_freq.get(token, 0)
        return math.log(1 + (self.total_docs - df + 0.5) / (df + 0.5))

    def search(self, query: str, *, top_k: int = 4, min_score: float = 0.18) -> list[ScoredChunk]:
        if not self.chunks:
            return []
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        query_counts = Counter(query_tokens)
        scored: list[ScoredChunk] = []
        k1, b = 1.5, 0.75
        for chunk, counts, length in zip(self.chunks, self.counts, self.lengths):
            score = 0.0
            for token, query_tf in query_counts.items():
                term_frequency = counts.get(token, 0)
                if not term_frequency:
                    continue
                denominator = term_frequency + k1 * (1 - b + b * length / max(self.avg_length, 1e-9))
                score += self._idf(token) * (term_frequency * (k1 + 1) / denominator) * min(query_tf, 2)
            if score >= min_score:
                scored.append(ScoredChunk(chunk=chunk, score=round(score, 4)))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def quote_exists_in_chunk(quote: str, chunk_text: str) -> bool:
    normalized_quote = _normalize_for_match(quote)
    normalized_chunk = _normalize_for_match(chunk_text)
    return bool(normalized_quote) and normalized_quote in normalized_chunk


def select_quote(chunk_text: str, claim_text: str, *, max_chars: int = 260) -> str:
    sentences = [part.strip() for part in _SENTENCE_SPLIT.split(chunk_text) if part and part.strip()]
    if not sentences:
        return chunk_text[:max_chars].strip()
    claim_tokens = set(tokenize(claim_text))
    best_index = 0
    best_score = -1
    for index, sentence in enumerate(sentences):
        overlap = len(claim_tokens & set(tokenize(sentence)))
        length_penalty = max(len(sentence), 1) ** 0.15
        score = overlap / length_penalty
        if score > best_score:
            best_score = score
            best_index = index
    quote = sentences[best_index]
    if len(quote) > max_chars:
        quote = quote[:max_chars].rstrip("，,。；; ") + "…"
        if not quote_exists_in_chunk(quote, chunk_text):
            quote = sentences[best_index][:max_chars].strip()
    return quote


def retrieve_evidence(claim_text: str, reference_chunks: list[DocumentChunk], *, top_k: int = 4) -> list[EvidenceItem]:
    index = EvidenceIndex(reference_chunks)
    results = index.search(claim_text, top_k=top_k)
    evidence: list[EvidenceItem] = []
    for result in results:
        quote = select_quote(result.chunk.text, claim_text)
        valid = quote_exists_in_chunk(quote, result.chunk.text)
        evidence.append(
            EvidenceItem(
                chunk_id=result.chunk.chunk_id,
                source_name=result.chunk.source_name,
                location=result.chunk.location,
                quote=quote,
                retrieval_score=result.score,
                quote_valid=valid,
                validation_note="原文逐字校验通过" if valid else "引用未在原文中逐字找到",
            )
        )
    return evidence


def extract_claim_sentences(text: str) -> list[str]:
    claims: list[str] = []
    seen: set[str] = set()
    for raw in _CLAIM_SPLIT.split(text.replace("\r\n", "\n")):
        stripped = raw.strip()
        if not stripped or stripped.startswith(("#", ">")):
            continue
        candidate = re.sub(r"^[*\-\s\d.、（）()]+", "", stripped)
        candidate = candidate.strip()
        if not (6 <= len(candidate) <= 220):
            continue
        if candidate.startswith("本文件为") or "合成测试材料" in candidate:
            continue
        if not any(cue in candidate for cue in CLAIM_CUES):
            continue
        key = re.sub(r"\s+", "", candidate)
        if key in seen:
            continue
        seen.add(key)
        claims.append(candidate)
    return claims


def _extract_quantities(text: str) -> list[tuple[float, str]]:
    normalized = text.replace("％", "%")
    values: list[tuple[float, str]] = []
    for value, unit in _QUANTITY.findall(normalized):
        values.append((float(value), unit.replace("%", "%")))
    return values


def _metric_groups(text: str) -> set[str]:
    groups = set()
    for group, terms in METRIC_GROUPS.items():
        if any(term in text for term in terms):
            groups.add(group)
    return groups


def _has_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def _relevant_overlap(claim_text: str, evidence_text: str) -> set[str]:
    claim_tokens = set(tokenize(claim_text)) - _STOP_TOKENS
    evidence_tokens = set(tokenize(evidence_text)) - _STOP_TOKENS
    return claim_tokens & evidence_tokens


def classify_claim_offline(claim_text: str, evidence: list[EvidenceItem], evidence_chunks: list[DocumentChunk]) -> tuple[str, str, str]:
    """返回 verdict、判断依据、建议修改。"""
    valid_evidence = [item for item in evidence if item.quote_valid]
    if not valid_evidence:
        return (
            "insufficient",
            "在上传的产品/技术资料中没有检索到可定位且通过原文校验的相关证据。没有找到证据不等于证明宣传虚假。",
            "补充可定位的试验资料、登记信息或技术报告；无法补充时，建议删除或弱化该宣传主张。",
        )

    chunk_by_id = {chunk.chunk_id: chunk for chunk in evidence_chunks}
    evidence_text = " ".join(chunk_by_id[item.chunk_id].text for item in valid_evidence if item.chunk_id in chunk_by_id)
    claim_numbers = _extract_quantities(claim_text)
    evidence_numbers = _extract_quantities(evidence_text)
    claim_metrics = _metric_groups(claim_text)
    evidence_metrics = _metric_groups(evidence_text)
    shared_metrics = claim_metrics & evidence_metrics
    overlap = _relevant_overlap(claim_text, evidence_text)
    broad = _has_any(claim_text, BROAD_CUES)
    negative = _has_any(evidence_text, NEGATIVE_EVIDENCE_CUES)
    evidence_conditioned = _has_any(evidence_text, CONDITION_CUES)
    claim_conditioned = _has_any(claim_text, CONDITION_CUES)
    positive_claim = _has_any(claim_text, ("安全", "无残留", "适用", "有效", "防效", "提升", "减少", "增产"))


    values_conflict = False
    if claim_numbers and evidence_numbers and shared_metrics:
        claim_values = {round(value, 2) for value, _ in claim_numbers}
        evidence_values = {round(value, 2) for value, _ in evidence_numbers}
        values_conflict = bool(claim_values and evidence_values and not (claim_values & evidence_values))
    if values_conflict:
        return (
            "conflicting",
            "宣传主张中的数值与检索到的资料数值不一致，需要人工核对目标指标、试验批次、统计口径和计算方式。",
            "先核对原始数据与统计口径；在确认前不要保留该数值，或改为与资料完全一致的表述并注明来源。",
        )

    common_number = False
    if claim_numbers and evidence_numbers:
        common_number = bool({round(value, 2) for value, _ in claim_numbers} & {round(value, 2) for value, _ in evidence_numbers})
    if common_number and evidence_conditioned and not claim_conditioned:
        return (
            "conditionally_supported",
            "资料中有相应数值，但该结果来自特定试验条件、供试品种、地区或剂量；当前宣传没有说明这些适用边界。",
            "补充地区、作物品种、试验条件、处理剂量和结果来源；避免把特定试验结果扩展为普遍效果。",
        )

    if positive_claim and negative:
        return (
            "insufficient",
            "检索到的资料明确显示相关项目未开展、未验证或不能据此判断，尚不足以支持该宣传表述。",
            "删除超出资料范围的结论；如确有依据，请补充完整试验、检测或登记资料，并注明适用条件。",
        )
    if broad and evidence_conditioned:
        return (
            "conditionally_supported",
            "资料仅覆盖有限条件，而宣传使用了绝对化或全覆盖表达，现有证据不足以支撑其范围。",
            "将绝对化表述改为有条件的客观表述，并注明已验证的作物、地区、剂量和试验范围。",
        )

    if broad:
        return (
            "insufficient",
            "宣传使用了绝对化或全覆盖表达，但检索到的资料没有提供覆盖该范围的直接证据。",
            "删除绝对化表述，补充覆盖该范围的资料；无法补充时改为限定性表述。",
        )

    if len(overlap) >= 2:
        return (
            "supported",
            "上传资料中存在与该主张直接相关的可定位内容，未发现明显的数值或范围冲突。该判断只表示资料支持，不构成独立事实认定。",
            "可以保留，但建议在发布材料中注明主要证据来源；若用于正式宣传，仍需由审核人员核对完整资料。",
        )

    return (
        "insufficient",
        "资料中虽有部分词语相关，但没有形成足以支持该主张的直接证据。",
        "补充与该主张直接对应的原文、试验数据或登记信息；无法补充时建议删除或改写。",
    )



