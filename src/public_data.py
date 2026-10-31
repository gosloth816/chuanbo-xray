"""公开技术资料 + 明确标注的自编传播演练，不冒充企业原始文案。"""

import hashlib
import json
from pathlib import Path

from .parsing import parse_document_bytes

ROOT = Path(__file__).resolve().parent.parent / "data" / "public_sources"

CASES = {
    "evidence_scope": {
        "title": "山东小麦：技术依据能否证明产品效果？",
        "description": "用公开技术指导核对通用技术描述、单品效果和绝对化宣传。",
        "claims": [
            "小麦中后期“一喷三防”技术能防病虫、防干热风、防早衰，增粒重，对保障小麦稳产丰收具有重要作用。",
            "本产品能够提高小麦防效，保证增产30%。",
            "本产品对所有作物均适用，安全无残留。",
            "本产品能够减少农药用量50%。",
        ],
        "origin": ["公开原文摘录", "自编压力测试", "自编压力测试", "自编压力测试"],
        "expected": ["supported", "insufficient", "insufficient", "insufficient"],
    },
    "source_difference": {
        "title": "山东小麦：两份指导意见为何不能混用？",
        "description": "保留年份与地区条件，核对雨后补治和作业参数的资料差异。",
        "claims": [
            "所有地区小麦施药后4小时遇雨都不需要补治。",
            "本产品可减少小麦病虫害危害损失率至5%以内。",
            "所有植保无人机每亩施药液量都可以减少到0.5升。",
            "本产品防治小麦赤霉病的防效可达99%。",
        ],
        "origin": ["自编压力测试"] * 4,
        "expected": ["manual_review", "insufficient", "manual_review", "insufficient"],
    },
}


MARKET_ROOT = ROOT.parent / "market_sources"
_market_meta = json.loads((MARKET_ROOT / "bayer_claim.json").read_text(encoding="utf-8"))
_market_quote = (MARKET_ROOT / "bayer_claim.txt").read_text(encoding="utf-8")
CASES["real_announcement"] = {
    "title": "企业公开宣传：减药数据有何直接依据？",
    "description": "一条真实官网表述，对照两份通用技术资料；核对现有依据能否支持具体数值。",
    "claims": [_market_quote],
    "origin": ["企业官网原文节选，非自编"],
    "expected": ["insufficient"],
    "real_promotion": True,
    "promotion_source": _market_meta,
}


def sources():
    return json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))


def load_public_case(case_id="evidence_scope"):
    case = CASES[case_id]
    promotion = parse_document_bytes(
        name=("企业官网原文节选.txt" if case.get("real_promotion") else "传播演练文案（含自编压力测试，非真实企业宣传）.txt"), role="promotion",
        data="\n".join(case["claims"]).encode("utf-8"), is_synthetic=not case.get("real_promotion", False),
    )
    promotion.metadata.update(data_origin="公开原文摘录与自编测试混合", claim_origins=case["origin"])
    if case.get("real_promotion"):
        data = (MARKET_ROOT / "bayer_claim.txt").read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if hashlib.sha256(data).hexdigest() != _market_meta["excerpt_sha256"]:
            raise ValueError("企业公开表述快照校验失败")
        promotion.metadata.update(_market_meta)
        promotion.metadata["data_origin"] = "企业官网真实原文短节选"
        promotion.warnings.append("仅核对所提供资料是否足以支持该表述，不判定企业声明真假；原文涉及组合方案，完整上下文见来源链接。")
    documents = [promotion]
    for source in sources():
        # 文本快照按LF换行校验，原始HTML指纹仍单独保留。
        # Git归档或Windows检出可能仅改变换行，不能误报为资料篡改。
        data = (ROOT / source["file"]).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if hashlib.sha256(data).hexdigest() != source["text_sha256"]:
            raise ValueError(f"公开资料快照校验失败：{source['title']}")
        document = parse_document_bytes(name=source["title"] + ".txt", role="reference", data=data)
        document.metadata.update(source)
        document.warnings.append("公开技术资料仅作历史传播核对演练，不是当前施药建议、产品效果证明或机构背书。")
        documents.append(document)
    return documents
