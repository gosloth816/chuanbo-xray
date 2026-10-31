"""真实服务验证：使用合成事实调用生成接口；不以演示样例回退。"""
from pathlib import Path
import sys
import json

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.studio_model import StudioModel, PROMPT_VERSION
from src.models import now_iso


def main():
    result = {"checked_at": now_iso(), "prompt_version": PROMPT_VERSION, "real_generation": False,
              "vision_verified": False, "notice": "仅用合成事实检查真实文本生成调用；图片识别须另行验证。"}
    try:
        model = StudioModel()
        result["model"] = model.name
        sample = json.loads((ROOT / "data/studio/demo.json").read_text(encoding="utf-8"))
        result["items"] = model.generate(sample["facts"], "家庭日常购买", ["朋友圈"], "自然清楚")
        result["real_generation"] = True
    except Exception as exc:
        result["error"] = str(exc)
    (ROOT / "docs/studio_model_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("真实模型生成已验证。" if result["real_generation"] else "真实模型调用未完成，失败原因已记录；未使用固定文案回退。")
    return 0 if result["real_generation"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
