"""运行完整测试并写入实际验证记录。"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    started = time.perf_counter()
    command = [sys.executable, "-m", "pytest"]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = (completed.stdout or "") + (completed.stderr or "")
    passed_match = re.search(r"(\d+) passed", output)
    failed_match = re.search(r"(\d+) failed", output)
    passed_tests = int(passed_match.group(1)) if passed_match else 0
    failed_tests = int(failed_match.group(1)) if failed_match else 0
    result = {
        "ran_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "command": ".venv\\Scripts\\python.exe -m pytest",
        "passed": completed.returncode == 0,
        "return_code": completed.returncode,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "scope": "核心业务、文档解析、检索与引用校验、规则分类、本地模型地址限制、SQLite 留痕、报告导出和 Streamlit 交互测试",
        "output_tail": output[-4000:],
    }
    docs = ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    print(json.dumps({key: result[key] for key in ("passed", "passed_tests", "failed_tests", "elapsed_seconds")}, ensure_ascii=False))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
