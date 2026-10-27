"""运行合成验证集并生成真实评估记录。"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_data import list_demo_cases, load_case_meta, load_demo_documents  # noqa: E402
from src.pipeline import analyze_documents  # noqa: E402


def main() -> int:
    started = time.perf_counter()
    case_results: list[dict] = []
    claim_results: list[dict] = []
    label_stats: dict[str, dict[str, int]] = {}
    quotes_checked = 0
    quotes_valid = 0
    expected_risk_count = 0
    false_support_count = 0

    for case in list_demo_cases():
        case_started = time.perf_counter()
        metadata = load_case_meta(case["case_id"])
        session = analyze_documents(
            title=metadata["case_name"],
            documents=load_demo_documents(case["case_id"]),
            mode="offline_rules",
        )
        elapsed = time.perf_counter() - case_started
        expected = metadata["expected_verdicts"]
        actual = {claim.text: claim.verdict for claim in session.claims}
        case_correct = 0
        case_quotes_checked = 0
        case_quotes_valid = 0
        for claim in session.claims:
            expected_verdict = expected.get(claim.text)
            correct = expected_verdict == claim.verdict
            case_correct += int(correct)
            valid_quotes = sum(1 for evidence in claim.evidence if evidence.quote_valid)
            quotes_checked += len(claim.evidence)
            quotes_valid += valid_quotes
            case_quotes_checked += len(claim.evidence)
            case_quotes_valid += valid_quotes
            if expected_verdict in {"insufficient", "conflicting", "manual_review"}:
                expected_risk_count += 1
                if claim.verdict in {"supported", "conditionally_supported"}:
                    false_support_count += 1
            stats = label_stats.setdefault(claim.verdict, {"expected": 0, "correct": 0})
            if expected_verdict is not None:
                expected_stats = label_stats.setdefault(expected_verdict, {"expected": 0, "correct": 0})
                expected_stats["expected"] += 1
                expected_stats["correct"] += int(correct)
            claim_results.append(
                {
                    "case_id": case["case_id"],
                    "claim_id": claim.claim_id,
                    "claim_text": claim.text,
                    "expected_verdict": expected_verdict,
                    "actual_verdict": claim.verdict,
                    "correct": correct,
                    "evidence_count": len(claim.evidence),
                    "valid_quote_count": valid_quotes,
                    "all_quotes_valid": valid_quotes == len(claim.evidence),
                }
            )
        case_results.append(
            {
                "case_id": case["case_id"],
                "case_name": metadata["case_name"],
                "claim_count": len(session.claims),
                "expected_claim_count": len(expected),
                "correct_claim_count": case_correct,
                "all_claims_correct": case_correct == len(expected) and len(session.claims) == len(expected),
                "quotes_checked": case_quotes_checked,
                "quotes_valid": case_quotes_valid,
                "elapsed_seconds": round(elapsed, 4),
            }
        )

    total_claims = len(claim_results)
    correct_claims = sum(1 for item in claim_results if item["correct"])
    result = {
        "ran_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "command": ".venv\\Scripts\\python.exe scripts\\run_evaluation.py",
        "mode": "offline_rules",
        "dataset": "三个明确标注的合成测试案例",
        "data_notice": "合成测试数据，不对应任何真实产品、企业、试验或论文；结果不能外推为真实业务准确率。",
        "python": sys.version,
        "platform": platform.platform(),
        "passed": correct_claims == total_claims and quotes_checked == quotes_valid,
        "total_cases": len(case_results),
        "total_claims": total_claims,
        "correct_claims": correct_claims,
        "label_accuracy": round(correct_claims / total_claims, 4) if total_claims else 0.0,
        "quotes_checked": quotes_checked,
        "quotes_valid": quotes_valid,
        "quote_validation_rate": round(quotes_valid / quotes_checked, 4) if quotes_checked else 0.0,
        "expected_risk_count": expected_risk_count,
        "false_support_count": false_support_count,
        "false_support_rate": round(false_support_count / expected_risk_count, 4) if expected_risk_count else 0.0,
        "by_label": label_stats,
        "cases": case_results,
        "claims": claim_results,
        "elapsed_seconds": round(time.perf_counter() - started, 4),
    }

    docs = ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "evaluation_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# 合成验证集运行结果",
        "",
        f"- 运行时间：{result['ran_at']}",
        f"- 运行模式：{result['mode']}",
        f"- 案例数：{result['total_cases']}",
        f"- 宣传主张数：{result['total_claims']}",
        f"- 判断类别与人工参考答案一致：{result['correct_claims']} / {result['total_claims']}（{result['label_accuracy'] * 100:.2f}%）",
        f"- 引用逐字校验通过：{result['quotes_valid']} / {result['quotes_checked']}（{result['quote_validation_rate'] * 100:.2f}%）",
        f"- 应判为风险但被错误放行：{result['false_support_count']} / {result['expected_risk_count']}（{result['false_support_rate'] * 100:.2f}%）",
        f"- 总耗时：{result['elapsed_seconds']} 秒",
        "",
        "> 数据说明：三个案例均为明确标注的合成测试数据，不对应任何真实产品、企业、试验或论文。以上结果只用于验证软件流程和当前规则，不可外推为真实业务准确率。",
        "",
        "## 分类结果",
        "",
        "| 案例 | 主张数 | 正确数 | 引用校验 | 耗时（秒） |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for case_result in case_results:
        lines.append(
            f"| {case_result['case_name']} | {case_result['claim_count']} | {case_result['correct_claim_count']} | "
            f"{case_result['quotes_valid']}/{case_result['quotes_checked']} | {case_result['elapsed_seconds']} |"
        )
    lines.extend(
        [
            "",
            "## 运行命令",
            "",
            "```powershell",
            ".venv\\Scripts\\python.exe scripts\\run_evaluation.py",
            "```",
            "",
        ]
    )
    (docs / "evaluation_results.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "passed", "total_cases", "total_claims", "correct_claims", "label_accuracy",
        "quotes_checked", "quotes_valid", "quote_validation_rate", "false_support_count",
        "expected_risk_count", "elapsed_seconds",
    )}, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
