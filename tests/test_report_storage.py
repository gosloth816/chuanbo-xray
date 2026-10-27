import json

from src.demo_data import load_demo_documents
from src.pipeline import analyze_documents
from src.report import build_html_report, build_json_report, build_markdown_report, safe_filename
from src.storage import ReviewStore


def test_storage_round_trip_and_audit(tmp_path):
    session = analyze_documents(title="报告测试", documents=load_demo_documents())
    store = ReviewStore(tmp_path / "test.sqlite3")
    store.save_review(session, action="analysis_saved", actor="system")
    store.add_event(session.run_id, "human_review_saved", "审核员", {"claims": 1})
    reviews = store.list_reviews()
    events = store.get_events(session.run_id)
    assert reviews[0]["run_id"] == session.run_id
    assert [event["action"] for event in events] == ["analysis_saved", "human_review_saved"]


def test_reports_include_evidence_and_disclosure():
    session = analyze_documents(title="报告测试", documents=load_demo_documents())
    markdown = build_markdown_report(session)
    html = build_html_report(session)
    payload = json.loads(build_json_report(session))
    assert "防效可达92%" in markdown
    assert "AI 使用与隐私披露" in html
    assert payload["session"]["run_id"] == session.run_id
    assert "不构成真实性、合法性或合规性结论" in markdown


def test_html_report_escapes_untrusted_title_and_claim():
    session = analyze_documents(title="报告测试", documents=load_demo_documents())
    session.title = '<script>alert(1)</script>'
    session.claims[0].text = '<img src=x onerror=alert(1)>'
    html = build_html_report(session)
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
    assert '<img src=x' not in html


def test_safe_filename():
    assert "/" not in safe_filename("赛道三/传播X光")
    assert safe_filename("   ") == "未命名审核任务"
