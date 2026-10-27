import pytest

from src.local_llm import LocalLLMError, LocalLLMClient, _extract_json_object, validate_local_base_url


def test_local_url_validation_accepts_loopback():
    assert validate_local_base_url("http://127.0.0.1:11434/v1") == "http://127.0.0.1:11434/v1"
    assert validate_local_base_url("http://localhost:1234/v1") == "http://localhost:1234/v1"


def test_local_url_validation_rejects_remote_host():
    with pytest.raises(LocalLLMError):
        validate_local_base_url("https://api.example.com/v1")


def test_local_client_rejects_remote_host():
    with pytest.raises(LocalLLMError):
        LocalLLMClient("https://example.com/v1", "demo")


def test_extract_json_from_markdown_fence():
    assert _extract_json_object('```json\n{"ok": true}\n```') == {"ok": True}
