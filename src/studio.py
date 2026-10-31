"""创作数据、人工修改记录与传播X光交接。"""
from copy import deepcopy
import hashlib
import json
import re
import sqlite3
from uuid import uuid4

from .models import ReviewSession, now_iso
from .parsing import parse_document_bytes
from .pipeline import add_manual_claim
from .storage import default_database_path
from .studio_model import PROMPT_VERSION


def fingerprint(description, image=None):
    return hashlib.sha256(description.encode() + (image or b"")).hexdigest()


def audit_copy(text, facts):
    context = "\n".join(row["value"] for row in facts.values())
    warnings = []
    for number in set(re.findall(r"\d+(?:\.\d+)?", text)):
        if number not in re.findall(r"\d+(?:\.\d+)?", context):
            warnings.append(f"数字 {number} 未出现在确认信息中，请核实。")
    for phrase in ("保证", "零风险", "治愈", "降血糖", "最好", "全网第一", "无残留"):
        if phrase in text:
            warnings.append(f"“{phrase}”需要人工审查，当前检查不构成合规结论。")
    for phrase in ("有机", "绿色认证", "包邮", "糖度", "保质期"):
        if phrase in text and phrase not in context:
            warnings.append(f"“{phrase}”缺少对应确认信息。")
    return warnings


def new_bundle(facts, items, *, model, audience, tone, synthetic=False, synthetic_input=False, creative_brief=None):
    return {"id": "QL-" + uuid4().hex[:10], "created_at": now_iso(), "facts": deepcopy(facts),
            "items": deepcopy(items), "model": model, "prompt_version": PROMPT_VERSION,
            "audience": audience, "tone": tone, "synthetic": synthetic,
            "synthetic_input": bool(synthetic or synthetic_input),
            "creative_brief": deepcopy(creative_brief or {}),
            "origin": "预先编写的合成演示，未调用模型" if synthetic else "实际模型调用",
            "events": [{"at": now_iso(), "action": "created", "origin": "sample" if synthetic else "model"}]}


def save_edit(bundle, index, title, body):
    before = deepcopy(bundle["items"][index])
    bundle["items"][index].update(title=title.strip(), body=body.strip())
    bundle["events"].append({"at": now_iso(), "action": "human_edit", "index": index,
                             "before": before, "after": deepcopy(bundle["items"][index])})


def persist(bundle):
    with sqlite3.connect(default_database_path()) as db:
        db.execute("CREATE TABLE IF NOT EXISTS studio_drafts (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        db.execute("INSERT OR REPLACE INTO studio_drafts VALUES (?, ?)",
                   (bundle["id"], json.dumps(bundle, ensure_ascii=False)))


def export_markdown(bundle):
    lines = ["# 齐鲁卖点 · 创作文案", "", f"- 记录：{bundle['id']}", f"- 来源：{bundle['origin']}",
             f"- 输入材料：{'合成测试商品' if bundle.get('synthetic_input', bundle['synthetic']) else '用户提供，未独立验证'}",
             f"- 模型：{bundle['model']}", f"- 提示词：{bundle['prompt_version']}",
             f"- 受众：{bundle['audience']}", f"- 表达风格：{bundle['tone']}"]
    brief = bundle.get("creative_brief", {})
    if brief:
        lines += [f"- 创作目标：{brief.get('goal', '')}", f"- 篇幅：{brief.get('length', '')}",
                  "- 主推事实：" + ", ".join(brief.get("focus_fact_ids", [])),
                  f"- 创作方向（非事实依据）：{brief.get('creative_direction', '')}"]
    lines += ["", "## 商家确认信息", ""]
    for fid, row in bundle["facts"].items():
        lines.append(f"- {fid} · {row['field']}：{row['value']}")
    for item in bundle["items"]:
        lines += ["", f"## {item['channel']}", "", item["title"], "", item["body"], "",
                  "模型标注的事实编号（不代表已验证内容）：" + ", ".join(item["fact_ids"])]
        lines += ["- 待核对：" + warning for warning in audit_copy(item["title"] + item["body"], bundle["facts"])]
    lines += ["", "## 操作记录", ""]
    lines += [f"- {event['at']} · {event['action']}" for event in bundle["events"]]
    lines += ["", "本文件为创作草稿；商家确认信息未经过独立验证，发布前仍需人工审核。"]
    return "\n".join(lines)


def send_to_xray(bundle):
    synthetic_input = bundle.get("synthetic_input", bundle["synthetic"])
    promotion = "\n".join(item["title"] + "。\n" + item["body"] for item in bundle["items"])
    reference = "\n".join(row["field"] + "：" + row["value"] for row in bundle["facts"].values())
    docs = [parse_document_bytes(name="待发布文案.txt", role="promotion", data=promotion.encode(), is_synthetic=synthetic_input),
            parse_document_bytes(name="商家确认信息（未经独立验证）.txt", role="reference", data=reference.encode(), is_synthetic=synthetic_input)]
    warnings = [warning for item in bundle["items"] for warning in audit_copy(item["title"] + item["body"], bundle["facts"])]
    session = ReviewSession.create(title="齐鲁卖点发布前审核", mode="offline_rules", model_name="", documents=docs,
        claims=[], prompt_version=PROMPT_VERSION, is_synthetic=synthetic_input,
        warnings=["本次传播X光使用规则核对，未调用审核模型。依据仅为商家确认信息，不验证其真实性。"] + warnings,
        limitations=["来自齐鲁卖点的创作草稿，未经过发布批准。", "事实编号为模型自报，不代表完整语义支持。"])
    for text in re.split(r"[\n。！？；]+", promotion):
        text = text.strip()
        if len(text) >= 4 and not any(c.text == text for c in session.claims):
            add_manual_claim(session=session, claim_text=text, reviewer="齐鲁卖点交接")
    session.notes = json.dumps({"studio_id": bundle["id"], "origin": bundle["origin"],
                                 "generation_model": bundle["model"], "creative_brief": bundle.get("creative_brief", {}),
                                 "events": bundle["events"]}, ensure_ascii=False)
    return session
