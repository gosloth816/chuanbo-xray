"""内置合成演示案例加载器。"""

from __future__ import annotations

import json
from pathlib import Path

from .models import ParsedDocument
from .parsing import parse_document_bytes


CASE_ROOT = Path(__file__).resolve().parent.parent / "data" / "demo" / "case_01"

DEMO_FILE_SPECS = (
    ("promotional_copy.txt", "promotion"),
    ("product_manual.txt", "reference"),
    ("trial_summary.txt", "reference"),
)


def load_case_meta() -> dict:
    return json.loads((CASE_ROOT / "case_meta.json").read_text(encoding="utf-8"))


def load_demo_documents() -> list[ParsedDocument]:
    documents: list[ParsedDocument] = []
    for filename, role in DEMO_FILE_SPECS:
        data = (CASE_ROOT / filename).read_bytes()
        documents.append(
            parse_document_bytes(
                name=filename,
                role=role,
                data=data,
                is_synthetic=True,
            )
        )
    return documents
