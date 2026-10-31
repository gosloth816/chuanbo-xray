"""模拟模型只用于校验程序；不作为真实模型运行证据。"""
import json

import pytest
from streamlit.testing.v1 import AppTest

from src.studio import audit_copy, new_bundle, save_edit, send_to_xray
from src.studio_model import StudioModel, StudioError, prepare_image


FACTS = {"F1": {"field": "产品名称", "value": "演示苹果"}, "F2": {"field": "规格", "value": "5斤/箱"}}
ITEMS = [{"channel": "朋友圈", "title": "演示苹果", "body": "演示苹果5斤装。", "fact_ids": ["F1", "F2"]}]


def test_unconfirmed_number_and_claim_are_flagged():
    assert len(audit_copy("有机苹果，99元包邮，保证增产。", FACTS)) >= 4


def test_human_edits_and_handoff_keep_source_snapshot():
    bundle = new_bundle(FACTS, ITEMS, model="测试桩", audience="家庭", tone="自然", synthetic=True)
    save_edit(bundle, 0, "演示苹果5斤装", "5斤一箱，先了解规格再选购。")
    assert bundle["events"][-1]["before"]["body"] != bundle["items"][0]["body"]
    session = send_to_xray(bundle)
    assert session.is_synthetic
    assert session.claims
    assert session.documents[1].text == "产品名称：演示苹果\n规格：5斤/箱"
    assert bundle["id"] in session.notes


def test_model_failure_cannot_return_fixed_copy(monkeypatch):
    import requests
    def fail(*args, **kwargs):
        raise requests.ConnectionError("unavailable")
    monkeypatch.setattr(requests, "post", fail)
    with pytest.raises(StudioError, match="没有生成AI结果"):
        StudioModel().generate(FACTS, "家庭", ["朋友圈"], "自然")


def test_unknown_fact_ids_are_rejected(monkeypatch):
    model = StudioModel()
    monkeypatch.setattr(model, "call", lambda *args, **kwargs: {"items": [{**ITEMS[0], "fact_ids": ["F999"]}]})
    with pytest.raises(StudioError, match="未确认"):
        model.generate(FACTS, "家庭", ["朋友圈"], "自然")


def test_broken_image_fails_before_network():
    with pytest.raises(StudioError):
        prepare_image(b"not an image")


def test_studio_demo_edit_and_xray_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("XRAY_DATA_DIR", str(tmp_path))
    app = AppTest.from_file("app.py", default_timeout=30).run()
    assert not app.exception
    next(b for b in app.button if b.label == "加载合成演示").click().run()
    assert not app.exception
    assert app.session_state["studio_bundle"]["synthetic"]
    next(b for b in app.button if b.label == "一键送至传播 X 光").click().run()
    assert not app.exception
    assert app.session_state["workspace"] == "传播 X 光审核"
    assert app.session_state["review"].claims


def test_changing_facts_disables_generation_and_handoff(tmp_path, monkeypatch):
    monkeypatch.setenv("XRAY_DATA_DIR", str(tmp_path))
    app = AppTest.from_file("app.py", default_timeout=30).run()
    next(b for b in app.button if b.label == "加载合成演示").click().run()
    app.text_input(key="product_规格").set_value("10斤/箱").run()
    assert next(b for b in app.button if b.label == "一键送至传播 X 光").disabled
    assert next(b for b in app.button if b.label == "生成多渠道文案").disabled


def test_cloud_without_model_config_cannot_call_localhost(monkeypatch):
    for key in ("STUDIO_MODEL_BASE_URL", "STUDIO_MODEL_NAME", "STUDIO_MODEL_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    model = StudioModel(public=True)
    assert model.remote and not model.ready
    with pytest.raises(StudioError, match="尚未配置"):
        model.generate(FACTS, "家庭", ["朋友圈"], "自然")


def test_cloud_requires_confirmed_free_quota_before_call():
    config = {"STUDIO_MODEL_BASE_URL": "https://api.example.com/v1", "STUDIO_MODEL_NAME": "vision", "STUDIO_MODEL_API_KEY": "test-only"}
    model = StudioModel(settings=config, public=True)
    with pytest.raises(StudioError, match="免费额度保护"):
        model.generate(FACTS, "家庭", ["朋友圈"], "自然")
    config["STUDIO_FREE_QUOTA_CONFIRMED"] = True
    assert not StudioModel(settings=config, public=True).block_reason


def test_cloud_refuses_local_address():
    with pytest.raises(StudioError, match="不能使用"):
        StudioModel(settings={"STUDIO_MODEL_BASE_URL": "http://127.0.0.1:11434/v1"}, public=True)


def test_public_app_without_model_still_runs_demo(tmp_path, monkeypatch):
    monkeypatch.setenv("XRAY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("XRAY_DEPLOYMENT_MODE", "public")
    for key in ("STUDIO_MODEL_BASE_URL", "STUDIO_MODEL_NAME", "STUDIO_MODEL_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    app = AppTest.from_file("app.py", default_timeout=30).run()
    assert not app.exception
    assert any("云端模型尚未配置" in item.value for item in app.info)
    next(b for b in app.button if b.label == "加载合成演示").click().run()
    assert not app.exception
    assert next(b for b in app.button if b.label == "生成多渠道文案").disabled
    assert not next(b for b in app.button if b.label == "一键送至传播 X 光").disabled


def test_flash_uses_direct_answer_and_bounded_output(monkeypatch):
    captured = {}
    class Response:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": '{"ok":true}'}}]}
    def post(*args, **kwargs):
        captured.update(kwargs["json"])
        return Response()
    monkeypatch.setattr("requests.post", post)
    model = StudioModel(settings={"STUDIO_MODEL_NAME": "qwen3.8-flash"})
    assert model.call("测试", {})["ok"]
    assert captured["enable_thinking"] is False
    assert captured["max_tokens"] == 2048
