"""JSON、Markdown 与 HTML 审核报告导出。"""

from __future__ import annotations

from datetime import datetime
import html
import re
from typing import Any

from .constants import (
    AI_DISCLOSURE,
    ANALYSIS_MODE_LABELS,
    APP_NAME,
    APP_SUBTITLE,
    APP_VERSION,
    REVIEW_STATUS_LABELS,
    VERDICT_COLORS,
    VERDICT_LABELS,
)
from .models import ReviewSession, dumps_json


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def safe_filename(title: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n]+', "-", title).strip(" .-")
    return cleaned[:60] or "未命名审核任务"


def report_payload(session: ReviewSession, audit_events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "report_standard": "传播X光审核报告-v2",
        "generated_at": _now(),
        "application": {"name": APP_NAME, "subtitle": APP_SUBTITLE, "version": APP_VERSION},
        "session": session.to_dict(),
        "audit_events": audit_events or [],
        "ai_disclosure": AI_DISCLOSURE,
        "disclaimer": "本报告为宣传材料发布前辅助审核记录，不构成真实性、合法性或合规性结论。",
    }


def build_json_report(session: ReviewSession, audit_events: list[dict[str, Any]] | None = None) -> str:
    return dumps_json(report_payload(session, audit_events), indent=2)


def _claim_markdown(claim, index: int) -> str:
    label = VERDICT_LABELS.get(claim.verdict, claim.verdict)
    review_label = REVIEW_STATUS_LABELS.get(claim.human_review.status, claim.human_review.status)
    lines = [
        f"### {index}. {claim.text}",
        "",
        f"- 来源：{claim.source_name}",
        f"- 系统判断：{label}",
        f"- 判断依据：{claim.rationale}",
        f"- 修改建议：{claim.suggested_revision}",
        f"- 人工复核：{review_label}",
    ]
    if claim.human_review.reviewer:
        lines.append(f"- 复核人：{claim.human_review.reviewer}")
    if claim.human_review.final_verdict:
        lines.append(f"- 人工结论：{VERDICT_LABELS.get(claim.human_review.final_verdict, claim.human_review.final_verdict)}")
    if claim.human_review.note:
        lines.append(f"- 人工意见：{claim.human_review.note}")
    if claim.human_review.final_text:
        lines.append(f"- 最终表述建议：{claim.human_review.final_text}")
    lines.append("\n证据：")
    if not claim.evidence:
        lines.append("- 未检索到可定位证据。")
    for evidence in claim.evidence:
        valid = "通过" if evidence.quote_valid else "未通过"
        lines.append(
            f"- {evidence.source_name} · {evidence.location}（原文校验：{valid}）\n"
            f"  > {evidence.quote}"
        )
    return "\n".join(lines)


def build_markdown_report(session: ReviewSession, audit_events: list[dict[str, Any]] | None = None) -> str:
    counts = session.verdict_counts
    lines = [
        f"# {session.title}",
        "",
        f"**{APP_NAME}｜{APP_SUBTITLE}**",
        "",
        f"- 审核编号：{session.run_id}",
        f"- 创建时间：{session.created_at}",
        f"- 分析模式：{ANALYSIS_MODE_LABELS.get(session.mode, session.mode)}",
        f"- 模型：{session.model_name or '未调用模型'}",
        f"- 提示词版本：{session.prompt_version}",
        f"- 合成测试材料：{'是' if session.is_synthetic else '否'}",
        "",
        "## 结果摘要",
        "",
        "| 有资料支持 | 有条件支持 | 证据不足 | 资料冲突 | 待人工核验 |",
        "| --- | --- | --- | --- | --- |",
        f"| {counts['supported']} | {counts['conditionally_supported']} | {counts['insufficient']} | {counts['conflicting']} | {counts['manual_review']} |",
        "",
        "## 宣传主张与证据",
        "",
    ]
    lines.extend(_claim_markdown(claim, index) for index, claim in enumerate(session.claims, start=1))
    lines.extend(["", "## 使用边界", ""])
    lines.extend(f"- {item}" for item in session.limitations)
    lines.extend(["", "## AI 使用披露", ""])
    lines.extend(f"- {value}" for value in AI_DISCLOSURE.values())
    if audit_events:
        lines.extend(["", "## 操作留痕", ""])
        for event in audit_events:
            lines.append(f"- {event['timestamp']}｜{event['actor']}｜{event['action']}")
    lines.extend(["", "---", "", "本报告为发布前辅助审核记录，不构成真实性、合法性或合规性结论。"])
    return "\n".join(lines)


def _badge(text: str, color: str) -> str:
    return f'<span class="badge" style="--badge:{html.escape(color)}">{html.escape(text)}</span>'


def build_html_report(session: ReviewSession, audit_events: list[dict[str, Any]] | None = None) -> str:
    counts = session.verdict_counts
    summary_cards = "".join(
        f'<div class="metric"><span>{html.escape(VERDICT_LABELS[key])}</span><strong>{counts[key]}</strong></div>'
        for key in ("supported", "conditionally_supported", "insufficient", "conflicting", "manual_review")
    )
    claim_sections: list[str] = []
    for index, claim in enumerate(session.claims, start=1):
        color = VERDICT_COLORS.get(claim.verdict, "#475467")
        evidence_html: list[str] = []
        for evidence in claim.evidence:
            valid_label = "逐字校验通过" if evidence.quote_valid else "逐字校验未通过"
            valid_class = "valid" if evidence.quote_valid else "invalid"
            evidence_html.append(
                f"""
                <div class="evidence">
                  <div class="evidence-meta">
                    <strong>{html.escape(evidence.source_name)}</strong>
                    <span>{html.escape(evidence.location)}</span>
                    <span class="{valid_class}">{valid_label}</span>
                  </div>
                  <blockquote>{html.escape(evidence.quote)}</blockquote>
                </div>
                """
            )
        if not evidence_html:
            evidence_html.append('<p class="muted">未检索到可定位证据。</p>')
        review = claim.human_review
        human_bits = []
        if review.reviewer:
            human_bits.append(f"复核人：{html.escape(review.reviewer)}")
        human_bits.append(f"状态：{html.escape(REVIEW_STATUS_LABELS.get(review.status, review.status))}")
        if review.final_verdict:
            human_bits.append(
                f"人工结论：{html.escape(VERDICT_LABELS.get(review.final_verdict, review.final_verdict))}"
            )
        if review.note:
            human_bits.append(f"人工意见：{html.escape(review.note)}")
        if review.final_text:
            human_bits.append(f"最终表述：{html.escape(review.final_text)}")
        claim_sections.append(
            f"""
            <section class="claim">
              <div class="claim-head">
                <div><span class="index">{index:02d}</span><h3>{html.escape(claim.text)}</h3></div>
                {_badge(VERDICT_LABELS.get(claim.verdict, claim.verdict), color)}
              </div>
              <p class="source">来源：{html.escape(claim.source_name)}</p>
              <div class="grid">
                <div><h4>系统判断依据</h4><p>{html.escape(claim.rationale).replace(chr(10), '<br>')}</p></div>
                <div><h4>修改建议</h4><p>{html.escape(claim.suggested_revision)}</p></div>
              </div>
              <h4>原始证据</h4>
              {''.join(evidence_html)}
              <div class="human"><strong>人工复核留痕</strong><p>{'<br>'.join(human_bits)}</p></div>
            </section>
            """
        )
    audit_html = ""
    if audit_events:
        rows = "".join(
            f"<tr><td>{html.escape(event['timestamp'])}</td><td>{html.escape(event['actor'])}</td><td>{html.escape(event['action'])}</td></tr>"
            for event in audit_events
        )
        audit_html = f"""
        <section class="panel"><h2>操作留痕</h2><table><thead><tr><th>时间</th><th>操作人</th><th>动作</th></tr></thead><tbody>{rows}</tbody></table></section>
        """
    disclosure = "".join(f"<li>{html.escape(value)}</li>" for value in AI_DISCLOSURE.values())
    limitations = "".join(f"<li>{html.escape(item)}</li>" for item in session.limitations)
    warnings = "".join(f"<li>{html.escape(item)}</li>" for item in session.warnings)
    warning_block = f'<section class="panel warning"><h2>运行提示</h2><ul>{warnings}</ul></section>' if warnings else ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(session.title)}｜{APP_NAME}审核报告</title>
<style>
:root{{--ink:#17251f;--muted:#66756d;--line:#dfe8e2;--brand:#13795b;--bg:#f4f7f4;}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif;line-height:1.7}}
main{{max-width:1080px;margin:0 auto;padding:40px 24px 64px}} .hero{{background:linear-gradient(135deg,#0b4f3b,#13795b 58%,#69a67b);color:white;border-radius:24px;padding:36px 40px;margin-bottom:24px}}
.hero h1{{font-size:34px;margin:8px 0}} .hero p{{margin:6px 0;opacity:.9}} .panel,.claim{{background:white;border:1px solid var(--line);border-radius:18px;padding:24px;margin:18px 0;box-shadow:0 8px 24px rgba(20,60,45,.05)}}
.meta{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px 24px}} .meta div{{border-bottom:1px dashed var(--line);padding:8px 0}} .meta span{{display:block;color:var(--muted);font-size:12px}}
.metrics{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:18px 0}} .metric{{background:white;border:1px solid var(--line);border-radius:14px;padding:16px}} .metric span{{font-size:12px;color:var(--muted)}} .metric strong{{display:block;font-size:28px}}
.claim-head{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}} .claim-head>div{{display:flex;gap:14px;align-items:flex-start}} .index{{display:inline-flex;min-width:38px;height:38px;align-items:center;justify-content:center;background:#edf5f0;color:var(--brand);border-radius:12px;font-weight:700}}
h2{{margin-top:0}} h3{{margin:0;font-size:20px}} h4{{margin:18px 0 8px;color:#34483f}} .badge{{background:var(--badge);color:white;border-radius:999px;padding:6px 12px;white-space:nowrap;font-size:13px;font-weight:700}}
.source,.muted{{color:var(--muted);font-size:13px}} .grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}} .evidence{{border-left:4px solid #9cc6b3;background:#f7faf8;padding:14px 18px;border-radius:0 12px 12px 0;margin:10px 0}} .evidence-meta{{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--muted)}} blockquote{{margin:10px 0 0;font-size:15px;color:#243b30}}
.valid{{color:var(--brand);font-weight:700}} .invalid{{color:#b42318;font-weight:700}} .human{{margin-top:18px;padding:14px 16px;background:#f8f5ee;border-radius:12px}} .warning{{background:#fff9e8;border-color:#efdcae}} ul{{padding-left:22px}}
table{{width:100%;border-collapse:collapse}} th,td{{text-align:left;padding:10px;border-bottom:1px solid var(--line)}} .foot{{color:var(--muted);font-size:12px;margin-top:24px}}
@media(max-width:760px){{.meta,.metrics,.grid{{grid-template-columns:1fr}} .hero{{padding:28px 24px}} .claim-head{{flex-direction:column}}}}
@media print{{body{{background:white}} main{{max-width:none;padding:0}} .panel,.claim{{box-shadow:none;break-inside:avoid}} .hero{{border-radius:0}}}}
</style>
</head>
<body><main>
<section class="hero">
  <div>{html.escape(APP_NAME)} · 审核报告</div>
  <h1>{html.escape(session.title)}</h1>
  <p>{html.escape(APP_SUBTITLE)}</p>
  <p>审核编号 {html.escape(session.run_id)} · {html.escape(session.created_at)}</p>
</section>
<section class="panel">
  <h2>任务概况</h2>
  <div class="meta">
    <div><span>分析模式</span>{html.escape(ANALYSIS_MODE_LABELS.get(session.mode, session.mode))}</div>
    <div><span>模型</span>{html.escape(session.model_name or '未调用模型')}</div>
    <div><span>提示词版本</span>{html.escape(session.prompt_version)}</div>
    <div><span>材料数量</span>{len(session.documents)} 份</div>
    <div><span>宣传主张</span>{len(session.claims)} 条</div>
    <div><span>合成测试材料</span>{'是' if session.is_synthetic else '否'}</div>
  </div>
  <div class="metrics">{summary_cards}</div>
</section>
{warning_block}
{''.join(claim_sections)}
{audit_html}
<section class="panel"><h2>使用边界</h2><ul>{limitations}</ul></section>
<section class="panel"><h2>AI 使用与隐私披露</h2><ul>{disclosure}</ul></section>
<p class="foot">本报告为宣传材料发布前辅助审核记录，不构成真实性、合法性或合规性结论。生成时间：{html.escape(_now())}</p>
</main></body></html>"""
