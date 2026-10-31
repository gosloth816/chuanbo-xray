from streamlit.testing.v1 import AppTest


def make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("XRAY_DATA_DIR", str(tmp_path / "runtime"))
    return AppTest.from_file("xray_app.py", default_timeout=30).run()


def test_app_initial_render_has_tabs_and_no_exception(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["① 新建诊断", "② 证据审查台", "③ 导出报告", "④ 关于与验证"]
    assert any(button.label == "加载合成演示案例" for button in app.button)


def test_demo_case_runs_and_human_review_is_saved(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    demo_button = [button for button in app.button if button.label == "加载合成演示案例"][0]
    demo_button.click()
    app.run()
    assert not app.exception
    review = app.session_state["review"]
    assert len(review.claims) == 6
    assert review.is_synthetic is True

    app.selectbox(key="action_CLM-001").set_value("确认系统判断")
    app.text_input(key="reviewer_CLM-001").set_value("测试审核员")
    save_button = [button for button in app.button if button.key and "human_review_CLM-001" in button.key][0]
    save_button.click()
    app.run()
    assert not app.exception
    review = app.session_state["review"]
    assert review.claims[0].human_review.status == "accepted"
    assert review.claims[0].human_review.reviewer == "测试审核员"
    assert len(app.get("download_button")) == 3

def test_public_mode_discloses_cloud_processing_and_hides_local_model(tmp_path, monkeypatch):
    monkeypatch.setenv("XRAY_DEPLOYMENT_MODE", "public")
    app = make_app(tmp_path, monkeypatch)
    assert not app.exception
    assert any("公开演示网页" in warning.value for warning in app.warning)
    assert not any(button.label == "测试本地模型连接" for button in app.button)


def test_public_sources_case_runs_without_upload(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    next(button for button in app.button if button.label == "运行公开资料案例").click()
    app.run()
    assert not app.exception
    review = app.session_state["review"]
    assert len(review.claims) == 1
    assert review.is_synthetic is False
    assert review.documents[1].metadata["scope"] == "general_guidance"
    assert any("真实公开技术资料" in item.value for item in app.caption)
