"""평가 루브릭 — 신호에서 레벨 도출, 프로필, 평가자 간 κ."""

import pytest

from pivoxpolicy.assess import build_profile, compare_assessors, render_comparison, render_profile
from pivoxpolicy.rubric import (
    Dimension, RubricError, derive_level, load_assessments, load_rubric,
    render_codebook, validate_assessment,
)


def test_rubric_loads_groups_and_signal_invariants():
    rub = load_rubric()
    assert len(rub.dimensions) >= 14 and rub.provisional is True
    assert sum(len(v) for v in rub.groups().values()) == len(rub.dimensions)
    ac = {d.id for d in rub.groups()["agent_control"]}
    assert {"inventory", "vendors", "unique_id", "least_privilege", "human_approval", "audit_trail", "kill_switch"} <= ac
    for d in rub.dimensions:
        assert [l.level for l in d.levels] == [0, 1, 2, 3]
        levels = {s.level for s in d.signals}
        assert 1 in levels and 3 in levels
        for s in d.signals:
            if s.level == 3:
                assert s.min_evidence == "primary"   # 보도만으로 L3 불가


def test_derive_level_rules():
    rub = load_rubric()
    dim = rub.by_id("inventory")
    # 전부 null → 미평가
    assert derive_level(dim, {}).level is None
    assert derive_level(dim, {"mentions_ai_governance": {"observed": None}}).level is None
    # false 만 → 0
    d = derive_level(dim, {"mentions_ai_governance": {"observed": False}})
    assert d.level == 0 and d.checked_any is True
    # L1 primary 발화 → 1
    d = derive_level(dim, {"mentions_ai_governance": {"observed": True, "evidence_level": "primary"}})
    assert d.level == 1 and d.fired == ["mentions_ai_governance"]
    # L2 가 press 면 발화 못 함(↓), L1 만 → 1
    d = derive_level(dim, {
        "mentions_ai_governance": {"observed": True, "evidence_level": "primary"},
        "discloses_ai_usecases": {"observed": True, "evidence_level": "press"},
    })
    assert d.level == 1 and "discloses_ai_usecases" in d.downgraded
    # L2 primary → 최고값 2
    d = derive_level(dim, {
        "mentions_ai_governance": {"observed": True, "evidence_level": "primary"},
        "discloses_ai_usecases": {"observed": True, "evidence_level": "primary"},
    })
    assert d.level == 2
    # L3 는 press 면 못 감
    d = derive_level(dim, {"verified_inventory": {"observed": True, "evidence_level": "press"}})
    assert d.level == 0 and d.downgraded == ["verified_inventory"]
    d = derive_level(dim, {"verified_inventory": {"observed": True, "evidence_level": "primary"}})
    assert d.level == 3


def test_seed_assessments_validate_and_derive_expected():
    rub = load_rubric()
    asmts = load_assessments()
    assert "example-worked_2026" in asmts
    for name, a in asmts.items():
        assert validate_assessment(a, rub) == [], name
    prof = build_profile(asmts["example-worked_2026"], rub)
    assert prof.level("inventory") == 1
    assert prof.level("human_approval") == 2
    assert prof.level("test_scope") == 1          # L2 가 press 라 ↓
    assert prof.level("detection_time") == 3
    assert prof.level("escalation") is None       # 전부 null
    assert prof.level("vendors") == 0             # 전부 false


def test_validate_rejects_unknown_signal_and_missing_evidence():
    rub = load_rubric()
    bad = {"subject": "x", "period": "2026", "assessor": "t", "scores": {
        "inventory": {
            "mentions_ai_governance": {"observed": True, "evidence": "", "evidence_level": "primary"},  # evidence 없음
            "nope_signal": {"observed": True, "evidence": "e", "evidence_level": "primary"},             # 모르는 신호
        },
        "nope_dim": {"x": {"observed": True}},
    }}
    probs = validate_assessment(bad, rub)
    assert any("evidence" in p and "mentions_ai_governance" in p for p in probs)
    assert any("nope_signal" in p for p in probs)
    assert any("nope_dim" in p for p in probs)


def test_profile_counts_keep_unknown_separate():
    rub = load_rubric()
    prof = build_profile(load_assessments()["example-worked_2026"], rub)
    v, z, coded = prof.verified_count(rub)
    assert v == 1                                  # detection_time
    assert coded == len(rub.dimensions) - 1        # escalation 만 미평가
    dist = prof.group_distribution(rub)
    assert dist["connection"].get("unknown") == 1  # escalation


def test_render_profile_and_codebook_say_evidence_not_control():
    rub = load_rubric()
    prof = build_profile(load_assessments()["example-worked_2026"], rub)
    out = render_profile(prof, rub)
    assert "공개 증거 수준" in out and "통제 유무" in out and "예시은행" in out
    cb = render_codebook(rub)
    assert "직접 고르지 않는다" in cb and "primary 필요" in cb


def test_kappa_signal_and_level():
    rub = load_rubric()
    base = load_assessments()["example-worked_2026"]
    a = dict(base); a["assessor"] = "A"
    # B: 한 신호만 다르게 (inventory L2 신호를 봤다고)
    import copy
    b = copy.deepcopy(base); b["assessor"] = "B"
    b["scores"]["inventory"]["discloses_ai_usecases"] = {"observed": True, "evidence": "e", "evidence_level": "primary"}
    res = compare_assessors(a, b, rub)
    assert res["n_signals"] > 0 and res["n_dims"] > 0
    assert ("inventory", 1, 2) in res["disagreements"]
    assert res["signal_kappa"].kappa is not None
    assert render_comparison([build_profile(a, rub)], rub).find("단일 등급 없음") >= 0


def test_dimension_rejects_missing_or_bad_signals():
    base = {"id": "x", "num": 1, "group": "testing", "name_ko": "a", "name_en": "a", "question": "q",
            "levels": [{"level": i, "label_ko": "", "criterion": ""} for i in range(4)]}
    with pytest.raises(RubricError):   # 신호 없음
        Dimension.from_dict(base)
    with pytest.raises(RubricError):   # L3 신호가 press
        Dimension.from_dict({**base, "signals": [
            {"id": "s1", "level": 1, "min_evidence": "press", "question": "q"},
            {"id": "s3", "level": 3, "min_evidence": "press", "question": "q"},
        ]})
