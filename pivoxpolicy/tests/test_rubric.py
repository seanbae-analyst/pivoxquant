"""평가 루브릭·채점 — 실데이터 검증 + 단위."""

import pytest

from pivoxpolicy.assess import build_profile, compare_assessors, render_comparison, render_profile
from pivoxpolicy.rubric import (
    RubricError, load_assessments, load_rubric, validate_assessment,
)


def test_rubric_loads_and_groups_cover_all_dimensions():
    rub = load_rubric()
    assert len(rub.dimensions) >= 14
    assert rub.provisional is True
    grouped = sum(len(v) for v in rub.groups().values())
    assert grouped == len(rub.dimensions)
    # 7개 통제가 agent_control 에 그대로
    ac = {d.id for d in rub.groups()["agent_control"]}
    assert {"inventory", "vendors", "unique_id", "least_privilege", "human_approval", "audit_trail", "kill_switch"} <= ac
    for d in rub.dimensions:
        assert [l.level for l in d.levels] == [0, 1, 2, 3]


def test_seed_assessments_validate():
    rub = load_rubric()
    asmts = load_assessments()
    assert "example-worked_2026" in asmts
    for name, a in asmts.items():
        assert validate_assessment(a, rub) == [], name


def test_validate_rejects_press_level3_and_missing_evidence():
    rub = load_rubric()
    bad = {"subject": "x", "period": "2026", "assessor": "t", "scores": {
        "inventory": {"level": 3, "evidence": "보도만", "evidence_level": "press"},
        "vendors": {"level": 2, "evidence": "", "evidence_level": "primary"},
        "nope": {"level": 1, "evidence": "e", "evidence_level": "primary"},
    }}
    probs = validate_assessment(bad, rub)
    assert any("press" in p for p in probs)
    assert any("vendors" in p and "evidence" in p for p in probs)
    assert any("nope" in p for p in probs)


def test_profile_counts_and_distribution_keep_unknown_separate():
    rub = load_rubric()
    a = load_assessments()["example-worked_2026"]
    prof = build_profile(a)
    v, z, coded = prof.verified_count(rub)
    # 예시: detection_time=3 하나, 0 은 vendors·unique_id·kill_switch·test_coverage=4, escalation=null 은 미평가
    assert v == 1
    assert z == 4
    assert coded == len(rub.dimensions) - 1   # escalation 만 null
    dist = prof.group_distribution(rub)
    assert dist["agent_control"].get("unknown", 0) == 0
    assert dist["connection"].get("unknown") == 1   # escalation


def test_render_profile_says_evidence_not_control():
    rub = load_rubric()
    prof = build_profile(load_assessments()["example-worked_2026"])
    out = render_profile(prof, rub)
    assert "공개 증거 수준" in out and "통제 유무" in out
    assert "예시은행" in out


def test_compare_assessors_kappa_on_levels():
    rub = load_rubric()
    a = {"subject": "같은은행", "period": "2026", "assessor": "A", "scores": {
        "inventory": {"level": 2, "evidence": "e", "evidence_level": "primary"},
        "vendors": {"level": 1, "evidence": "e", "evidence_level": "primary"},
        "unique_id": {"level": 0},
        "kill_switch": {"level": 3, "evidence": "e", "evidence_level": "primary"},
    }}
    b = {"subject": "같은은행", "period": "2026", "assessor": "B", "scores": {
        "inventory": {"level": 2, "evidence": "e", "evidence_level": "primary"},
        "vendors": {"level": 2, "evidence": "e", "evidence_level": "primary"},  # 불일치
        "unique_id": {"level": 0},
        "kill_switch": {"level": 3, "evidence": "e", "evidence_level": "primary"},
    }}
    res = compare_assessors(a, b, rub)
    assert res["n"] == 4
    assert res["disagreements"] == [("vendors", 1, 2)]
    assert 0.0 < res["kappa"].kappa < 1.0
    assert res["kappa"].weighted_kappa is not None


def test_comparison_grid_has_no_single_grade():
    rub = load_rubric()
    profiles = [build_profile(load_assessments()["example-worked_2026"])]
    out = render_comparison(profiles, rub)
    assert "단일 등급 없음" in out
    # 합계/평균/종합 같은 단어로 뭉친 행이 없어야 한다
    assert "종합점수" not in out and "총점" not in out


def test_dimension_rejects_bad_levels():
    with pytest.raises(RubricError):
        from pivoxpolicy.rubric import Dimension
        Dimension.from_dict({"id": "x", "num": 1, "group": "testing", "name_ko": "a", "name_en": "a",
                             "question": "q", "levels": [{"level": 0, "label_ko": "", "criterion": ""}]})
