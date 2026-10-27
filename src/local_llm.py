"""可选的本地大模型客户端。禁止连接非本机地址。"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import requests


class LocalLLMError(RuntimeError):
    """本地模型不可用或返回结果不符合要求。"""


def validate_local_base_url(base_url: str) -> str:
    parsed = urlparse(base_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise LocalLLMError("本地模型地址必须以 http:// 或 https:// 开头。")
    if parsed.username or parsed.password:
        raise LocalLLMError("本地模型地址不能包含用户名或密码。")
    hostname = (parsed.hostname or "").lower()
    if hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise LocalLLMError("为保护材料隐私，只允许连接 localhost、127.0.0.1 或 ::1。")
    return base_url.rstrip("/")


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise LocalLLMError("本地模型没有返回可解析的 JSON。")
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LocalLLMError("本地模型返回的 JSON 格式无效。") from exc
    if not isinstance(value, dict):
        raise LocalLLMError("本地模型返回结果不是 JSON 对象。")
    return value


class LocalLLMClient:
    def __init__(self, base_url: str, model: str, timeout: int = 120):
        self.base_url = validate_local_base_url(base_url)
        self.model = model.strip()
        self.timeout = timeout
        if not self.model:
            raise LocalLLMError("请填写本地模型名称。")

    def check_available(self) -> tuple[bool, str]:
        try:
            response = requests.get(f"{self.base_url}/models", timeout=5)
            response.raise_for_status()
            payload = response.json()
            model_ids = [item.get("id", "") for item in payload.get("data", []) if isinstance(item, dict)]
            if self.model in model_ids:
                return True, f"已连接本地模型服务，找到模型 {self.model}。"
            if model_ids:
                return False, f"本地服务可连接，但未找到模型 {self.model}。可用模型：{', '.join(model_ids[:8])}。"
            return False, "本地服务可连接，但没有返回可用模型列表。"
        except Exception as exc:
            return False, f"无法连接本地模型服务：{exc}"

    def _chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except requests.RequestException as exc:
            raise LocalLLMError(f"本地模型调用失败：{exc}") from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LocalLLMError("本地模型响应结构不符合预期。") from exc
        return _extract_json_object(content)

    def extract_claims(self, promotion_text: str) -> list[str]:
        if len(promotion_text) > 30000:
            raise LocalLLMError("宣传文本超过 30000 字符。请拆分材料后分别审核，避免静默截断。")
        system_prompt = (
            "你是农业科技宣传材料的宣传主张提取器。只提取可由产品资料或技术资料核验的明确主张。"
            "不要补充原文没有的信息，不要生成新文案。只返回 JSON 对象，格式为 "
            '{"claims":[{"text":"宣传原文中的完整句子"}]}。逐条保留原文，不合并不同句子。'
        )
        user_prompt = f"请从以下宣传材料中提取宣传主张：\n\n{promotion_text}"
        payload = self._chat_json(system_prompt, user_prompt)
        raw_claims = payload.get("claims")
        if not isinstance(raw_claims, list):
            raise LocalLLMError("本地模型没有返回 claims 列表。")
        claims: list[str] = []
        for item in raw_claims:
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
            else:
                text = str(item).strip()
            if 4 <= len(text) <= 300 and text not in claims:
                claims.append(text)
        if not claims:
            raise LocalLLMError("本地模型未提取到可核验的宣传主张。")
        return claims

    def analyze_claim(self, claim_text: str, candidates: list[dict[str, str]]) -> dict[str, Any]:
        if not candidates:
            return {
                "verdict": "insufficient",
                "rationale": "在上传资料中没有检索到与该主张相关的候选证据。没有找到证据不等于证明宣传虚假。",
                "suggested_revision": "补充可定位的产品资料或技术依据；无法补充时删除或弱化该主张。",
                "evidence": [],
            }
        evidence_text = "\n\n".join(
            f"[{item['chunk_id']}]\n来源：{item['source_name']} · {item['location']}\n原文：{item['text']}"
            for item in candidates
        )
        system_prompt = (
            "你是严谨的农业科技宣传证据核对助手。你只能依据用户给出的候选原文判断，不能使用外部知识，"
            "不能编造来源、页码、数据或结论。verdict 只能是 supported、conditionally_supported、"
            "insufficient、conflicting、manual_review。没有证据时必须用 insufficient；引用必须逐字摘录候选原文。"
            "只返回 JSON 对象，格式为 "
            '{"verdict":"...","rationale":"...","suggested_revision":"...","evidence":[{"chunk_id":"...","quote":"..."}]}。'
        )
        user_prompt = f"宣传主张：{claim_text}\n\n候选证据：\n{evidence_text}"
        payload = self._chat_json(system_prompt, user_prompt)
        verdict = str(payload.get("verdict", "")).strip()
        if verdict not in {"supported", "conditionally_supported", "insufficient", "conflicting", "manual_review"}:
            raise LocalLLMError("本地模型返回了不允许的判断类别。")
        rationale = str(payload.get("rationale", "")).strip()
        suggestion = str(payload.get("suggested_revision", "")).strip()
        if not rationale:
            raise LocalLLMError("本地模型没有返回判断依据。")
        evidence = payload.get("evidence", [])
        if not isinstance(evidence, list):
            raise LocalLLMError("本地模型返回的 evidence 不是列表。")
        return {
            "verdict": verdict,
            "rationale": rationale,
            "suggested_revision": suggestion or "请由审核人员补充修改建议。",
            "evidence": evidence,
        }
