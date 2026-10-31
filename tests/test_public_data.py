import json
import pytest

from src.public_data import CASES, load_public_case, sources
from src.pipeline import analyze_documents, add_manual_claim
from src.report import build_html_report, build_json_report, build_markdown_report


def test_public_evidence_is_real_but_authored_promotion_is_labelled():
    docs = load_public_case()
    assert docs[0].is_synthetic
    assert all(not doc.is_synthetic for doc in docs[1:])
    assert len(sources()) == 2
    assert all(doc.metadata["url"].startswith("https://jnny.jinan.gov.cn/") for doc in docs[1:])


def test_public_guidance_cannot_prove_specific_product_effect():
    session = analyze_documents(title="公开依据", documents=load_public_case())
    assert len(session.claims) == len(CASES["evidence_scope"]["claims"])
    assert all(c.verdict == "insufficient" for c in session.claims if "本产品" in c.text)
    claim = add_manual_claim(session=session, claim_text="该产品可以减少农药用量。", reviewer="甲")
    assert claim.verdict == "insufficient"
    payload = json.loads(build_json_report(session))
    assert len(payload["source_provenance"]) == 2
    for report in [build_html_report(session), build_markdown_report(session)]:
        assert sources()[0]["url"] in report
        assert sources()[0]["sha256"] in report


def test_real_company_excerpt_is_not_labelled_as_synthetic():
    session = analyze_documents(title="真实表述", documents=load_public_case("real_announcement"))
    assert not session.is_synthetic
    assert len(session.claims) == 1
    assert session.claims[0].verdict == "insufficient"
    assert session.documents[0].metadata["publisher"] == "拜耳中国官网"
    payload = json.loads(build_json_report(session))
    assert len(payload["source_provenance"]) == 3
    assert "组合方案" in payload["session"]["documents"][0]["metadata"]["context"]


def test_snapshot_line_endings_survive_packaging_but_content_changes_fail(tmp_path, monkeypatch):
    import src.public_data as module
    for source in sources():
        data = (module.ROOT / source["file"]).read_bytes().replace(b"\r\n", b"\n")
        (tmp_path / source["file"]).write_bytes(data.replace(b"\n", b"\r\n"))
    (tmp_path / "manifest.json").write_bytes((module.ROOT / "manifest.json").read_bytes())
    monkeypatch.setattr(module, "ROOT", tmp_path)
    assert len(load_public_case()) == 3
    changed = tmp_path / sources()[0]["file"]
    changed.write_bytes(changed.read_bytes().replace("小麦".encode(), "大豆".encode()))
    with pytest.raises(ValueError, match="快照校验失败"):
        load_public_case()
