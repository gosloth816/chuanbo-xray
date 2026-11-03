"""Render the approved review workspace against a real review session."""
import base64
import json
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import declare_component

from .parsing import DocumentParseError, parse_document_bytes
from .storage import ReviewStore

VERDICTS = {
    "supported": "有依据",
    "conditionally_supported": "有条件支持",
    "insufficient": "依据不足",
    "conflicting": "与资料冲突",
    "manual_review": "待人工判断",
}


def _return_to_studio():
    st.session_state["show_xray"] = False
    st.session_state.pop("xray_advanced", None)
    st.rerun()


def _rows(review, store):
    checked = {}
    for event in store.get_events(review.run_id):
        if event["action"] == "checklist_review":
            details = json.loads(event["details_json"])
            checked[details["claim"]] = details["checked"]
    rows = []
    for claim in review.claims:
        documents = [
            document for document in review.documents
            if document.metadata.get("review_claim") == claim.claim_id
        ]
        evidence = [
            f"{item.source_name} · {item.location}：{item.quote}"
            for item in claim.evidence if item.quote_valid
        ]
        rows.append({
            "id": claim.claim_id, "claim": claim.text,
            "tag": VERDICTS.get(claim.verdict, "待人工判断"),
            "reason": claim.rationale, "rewrite": claim.suggested_revision,
            "source": "\n".join(evidence) or "当前没有可展示的有效引用。",
            "need": "核对材料的商品、批次及适用范围，再确认它是否支持这句话。",
            "checked": checked.get(claim.claim_id, claim.human_review.status != "unreviewed"),
            "materials": [{"name": doc.name, "note": doc.metadata.get("review_note", ""),
                           "excerpt": "\n".join(chunk.text for chunk in doc.chunks[:2])[:600]}
                          for doc in documents],
        })
    return rows


def _upload(event, review, claim_id, store):
    encoded = event["data"].split(",", 1)[1]
    if len(encoded) > 14 * 1024 * 1024:
        raise ValueError("请选择 10 MB 以内的文件。")
    data = base64.b64decode(encoded, validate=True)
    if not data or len(data) > 10 * 1024 * 1024:
        raise ValueError("文件为空或超过 10 MB。")
    name = str(event["fileName"]).replace("\\", "/").split("/")[-1][:180]
    document = parse_document_bytes(name=name, role="reference", data=data)
    if not document.chunks:
        raise ValueError("没有读到可核对的文字，请上传带文字层的 PDF、DOCX 或 TXT。")
    document.metadata.update(review_claim=claim_id, review_note=str(event.get("note", ""))[:300])
    review.documents.append(document)
    try:
        store.save_review(review, action="evidence_linked", details={"claim": claim_id, "name": name})
    except Exception:
        review.documents.pop()
        raise


def render_review_desk():
    store = ReviewStore()
    review = st.session_state.get("review")
    rows = _rows(review, store) if review else []
    response = st.session_state.get("review_desk_response", {})
    component = declare_component("approved_xray", path=Path(__file__).with_name("xray_frontend"))
    event = component(state={
        **response, "revision": f"{review.run_id if review else 'none'}:{response.get('revision', '')}",
        "title": (review.title + (" · 合成案例" if review.is_synthetic else "")) if review else "",
        "rows": rows,
    }, key="approved-xray", default=None)
    if not isinstance(event, dict) or not event.get("id"):
        return
    if event["id"] == st.session_state.get("review_desk_last"):
        return
    st.session_state["review_desk_last"] = event["id"]
    name = event.get("name")
    if name == "return":
        _return_to_studio()
    if name == "advanced":
        st.session_state["xray_advanced"] = True
        st.rerun()
    claim_id = event.get("claim")
    row = next((item for item in rows if item["id"] == claim_id), None)
    result = {"revision": event["id"]}
    if row:
        try:
            if name == "toggle":
                store.add_event(review.run_id, "checklist_review", "当前复核人",
                                {"claim": claim_id, "checked": not row["checked"]})
                result["message"] = "复核清单已更新。"
            elif name == "upload":
                _upload(event, review, claim_id, store)
                result.update(uploaded=True, message="材料已关联，请核对材料摘录和原件。")
        except DocumentParseError as error:
            result["message"] = str(error)
        except (ValueError, KeyError, IndexError, TypeError):
            result["message"] = "无法读取材料，请选择 10 MB 以内的 PDF、DOCX 或 TXT。"
    st.session_state["review_desk_response"] = result
    st.rerun()
