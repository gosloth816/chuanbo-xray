"""领域数据模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
import json
from typing import Any
from uuid import uuid4


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Verdict(str, Enum):
    SUPPORTED = "supported"
    CONDITIONALLY_SUPPORTED = "conditionally_supported"
    INSUFFICIENT = "insufficient"
    CONFLICTING = "conflicting"
    MANUAL_REVIEW = "manual_review"


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    MODIFIED = "modified"
    REJECTED = "rejected"


def jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


@dataclass
class DocumentChunk:
    chunk_id: str
    source_name: str
    role: str
    location: str
    text: str
    page: int | None = None
    paragraph: int | None = None
    is_synthetic: bool = False

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass
class ParsedDocument:
    name: str
    role: str
    content_type: str
    chunks: list[DocumentChunk] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    is_synthetic: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n".join(chunk.text for chunk in self.chunks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass
class EvidenceItem:
    chunk_id: str
    source_name: str
    location: str
    quote: str
    retrieval_score: float
    quote_valid: bool
    validation_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass
class HumanReview:
    status: str = ReviewStatus.UNREVIEWED.value
    reviewer: str = ""
    note: str = ""
    final_text: str = ""
    final_verdict: str = ""
    reviewed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass
class Claim:
    claim_id: str
    text: str
    source_name: str
    verdict: str
    rationale: str
    suggested_revision: str
    evidence: list[EvidenceItem] = field(default_factory=list)
    requires_human: bool = True
    extraction_method: str = "offline_rules"
    human_review: HumanReview = field(default_factory=HumanReview)

    @property
    def display_text(self) -> str:
        return self.human_review.final_text.strip() or self.text

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass
class ReviewSession:
    run_id: str
    title: str
    created_at: str
    mode: str
    model_name: str
    prompt_version: str
    documents: list[ParsedDocument]
    claims: list[Claim]
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    is_synthetic: bool = False
    notes: str = ""
    analysis_seconds: float | None = None

    @classmethod
    def create(
        cls,
        *,
        title: str,
        mode: str,
        model_name: str,
        documents: list[ParsedDocument],
        claims: list[Claim],
        prompt_version: str,
        warnings: list[str] | None = None,
        limitations: list[str] | None = None,
        is_synthetic: bool = False,
    ) -> "ReviewSession":
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return cls(
            run_id=f"XRAY-{stamp}-{uuid4().hex[:6].upper()}",
            title=title,
            created_at=now_iso(),
            mode=mode,
            model_name=model_name,
            prompt_version=prompt_version,
            documents=documents,
            claims=claims,
            warnings=warnings or [],
            limitations=limitations or [],
            is_synthetic=is_synthetic,
        )

    @property
    def verdict_counts(self) -> dict[str, int]:
        counts = {key: 0 for key in ("supported", "conditionally_supported", "insufficient", "conflicting", "manual_review")}
        for claim in self.claims:
            counts[claim.verdict] = counts.get(claim.verdict, 0) + 1
        return counts

    @property
    def review_counts(self) -> dict[str, int]:
        counts = {key: 0 for key in ("unreviewed", "accepted", "modified", "rejected")}
        for claim in self.claims:
            status = claim.human_review.status
            counts[status] = counts.get(status, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass
class AuditEvent:
    event_id: int | None
    run_id: str
    timestamp: str
    action: str
    actor: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


def dumps_json(value: Any, *, indent: int = 2) -> str:
    return json.dumps(jsonable(value), ensure_ascii=False, indent=indent)
