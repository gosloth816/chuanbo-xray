from src.demo_data import list_demo_cases, load_case_meta, load_demo_documents
from src.pipeline import add_manual_claim, analyze_documents


def test_demo_case_end_to_end_offline():
    session = analyze_documents(
        title="绿盾一号合成演示案例",
        documents=load_demo_documents(),
        mode="offline_rules",
    )
    assert session.is_synthetic is True
    assert len(session.documents) == 3
    assert len(session.claims) == 6
    actual = {claim.text: claim.verdict for claim in session.claims}
    expected = load_case_meta()["expected_verdicts"]
    assert actual == expected
    assert all(item.quote_valid for claim in session.claims for item in claim.evidence)
    assert session.verdict_counts["conflicting"] == 1
    assert session.verdict_counts["conditionally_supported"] == 1


def test_all_synthetic_cases_match_reference_labels():
    total = 0
    correct = 0
    for case in list_demo_cases():
        session = analyze_documents(
            title=case["case_name"],
            documents=load_demo_documents(case["case_id"]),
            mode="offline_rules",
        )
        actual = {claim.text: claim.verdict for claim in session.claims}
        expected = load_case_meta(case["case_id"])["expected_verdicts"]
        assert actual == expected, case["case_id"]
        assert all(item.quote_valid for claim in session.claims for item in claim.evidence)
        total += len(expected)
        correct += sum(actual[claim_text] == verdict for claim_text, verdict in expected.items())
    assert total == 14
    assert correct == 14


def test_manual_claim_is_added_and_evidence_checked():
    session = analyze_documents(
        title="测试",
        documents=load_demo_documents(),
        mode="offline_rules",
    )
    before = len(session.claims)
    claim = add_manual_claim(
        session=session,
        claim_text="本产品在山东泰安设施番茄试验中对灰霉病防效为82.4%。",
        reviewer="测试审核员",
    )
    assert len(session.claims) == before + 1
    assert claim.claim_id == f"CLM-{before + 1:03d}"
    assert claim.evidence
