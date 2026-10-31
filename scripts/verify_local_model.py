"""以真实本机模型运行合成案例；失败如实记录，不回退规则冒充成功。"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.demo_data import load_demo_documents
from src.local_llm import LocalLLMClient
from src.models import now_iso
from src.pipeline import analyze_documents
from src.report import report_payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    parser.add_argument("--model", default="qwen2.5:3b")
    args = parser.parse_args()
    result = {"checked_at": now_iso(), "model": args.model, "real_model_run": False,
              "data_notice": "仅发送内置合成材料；不包含真实企业资料。"}
    try:
        client = LocalLLMClient(args.base_url, args.model)
        available, message = client.check_available()
        if not available:
            raise RuntimeError(message)
        session = analyze_documents(title="本机大模型实际运行验证（合成案例）",
                                    documents=load_demo_documents(), mode="local_llm", llm=client)
        result.update(real_model_run=True, report=report_payload(session))
    except Exception as exc:
        result["error"] = str(exc)
    output = ROOT / "docs" / "local_model_verification.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("真实模型运行已完成。" if result["real_model_run"] else "真实模型验证未完成，原因已记录。")
    return 0 if result["real_model_run"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
