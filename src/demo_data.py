"""内置合成演示案例加载器。"""

from __future__ import annotations

import json
from pathlib import Path

from .models import ParsedDocument
from .parsing import parse_document_bytes


DEMO_ROOT = Path(__file__).resolve().parent.parent / "data" / "demo"

CASE_SPECS = {
    "case_01": {
        "directory": "case_01",
        "files": (
            ("promotional_copy.txt", "promotion"),
            ("product_manual.txt", "reference"),
            ("trial_summary.txt", "reference"),
        ),
    },
    "case_02": {
        "directory": "case_02",
        "files": (
            ("promotional_copy.txt", "promotion"),
            ("product_manual.txt", "reference"),
            ("trial_summary.txt", "reference"),
        ),
    },
    "case_03": {
        "directory": "case_03",
        "files": (
            ("promotional_copy.txt", "promotion"),
            ("product_manual.txt", "reference"),
            ("trial_summary.txt", "reference"),
        ),
    },
}


def _case_dir(case_id: str) -> Path:
    spec = CASE_SPECS.get(case_id)
    if spec is None:
        raise KeyError(f"未知演示案例：{case_id}")
    return DEMO_ROOT / spec["directory"]


def list_demo_cases() -> list[dict]:
    cases: list[dict] = []
    for case_id in CASE_SPECS:
        metadata = load_case_meta(case_id)
        cases.append({"case_id": case_id, **metadata})
    return cases


def load_case_meta(case_id: str = "case_01") -> dict:
    return json.loads((_case_dir(case_id) / "case_meta.json").read_text(encoding="utf-8"))


def load_demo_documents(case_id: str = "case_01") -> list[ParsedDocument]:
    case_dir = _case_dir(case_id)
    documents: list[ParsedDocument] = []
    for filename, role in CASE_SPECS[case_id]["files"]:
        data = (case_dir / filename).read_bytes()
        documents.append(
            parse_document_bytes(
                name=filename,
                role=role,
                data=data,
                is_synthetic=True,
            )
        )
    return documents
