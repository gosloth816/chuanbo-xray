"""公开依据传播演练：报告漏提取、类别差异及风险漏提示，不隐藏失败。"""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.public_data import CASES, load_public_case, sources
from src.pipeline import analyze_documents
from src.models import now_iso
from src.report import build_html_report


def main():
    rows = []
    for key, case in CASES.items():
        session = analyze_documents(title=case["title"], documents=load_public_case(key))
        actual = {claim.text: claim.verdict for claim in session.claims}
        (ROOT / "docs" / f"public_case_{key}.html").write_text(build_html_report(session), encoding="utf-8")
        for text, expected, origin in zip(case["claims"], case["expected"], case["origin"]):
            verdict = actual.get(text)
            rows.append(dict(case_id=key, text=text, origin=origin, expected=expected,
                             actual=verdict, extracted=verdict is not None, exact_match=verdict == expected,
                             risk=expected != "supported",
                             risk_flagged=verdict in {"insufficient", "conflicting", "manual_review"}))
    risks = [row for row in rows if row["risk"]]
    result = dict(ran_at=now_iso(), mode="offline_rules", sources=sources(),
                  notice="2份通用技术依据 + 9条输入（1条技术原文、7条自编压力测试、1条真实企业宣传节选）。参考类别由本次开发拟定，未经独立专家标注，不是外部独立测试集或真实用户反馈。",
                  expected_claims=len(rows), extracted_claims=sum(row["extracted"] for row in rows),
                  exact_matches=sum(row["exact_match"] for row in rows),
                  expected_risks=len(risks), flagged_risks=sum(row["risk_flagged"] for row in risks), rows=rows)
    (ROOT / "docs" / "public_evaluation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 公开依据传播演练运行记录", "", result["notice"], "",
             f"- 提取覆盖：{result['extracted_claims']}/{len(rows)}",
             f"- 具体类别与开发参考一致：{result['exact_matches']}/{len(rows)}",
             f"- 风险提示覆盖：{result['flagged_risks']}/{len(risks)}（仅统计证据不足、冲突或待核验，不能解释为正确诊断率）", "",
             "| 输入 | 来源性质 | 开发参考 | 实际类别 |", "| --- | --- | --- | --- |"]
    lines += [f"| {r['text']} | {r['origin']} | {r['expected']} | {r['actual'] or '漏提取'} |" for r in rows]
    lines += ["", "两个差异案例中的资料差异和否定语义需要人工判断。规则引擎能够提示风险，但不能稳定解释跨文件条件，也不能替代真实模型和人工测试。未为提高本次分数而修改参考类别。"]
    (ROOT / "docs" / "public_evaluation.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("expected_claims", "extracted_claims", "exact_matches", "expected_risks", "flagged_risks")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
