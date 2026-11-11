"""2차 코딩 합치기 · 사건 코딩 κ."""

import yaml

import pytest

from pivoxpolicy.agreement import (
    IncidentCodingError,
    coding_yaml,
    incident_vectors,
    render_incident_agreement,
    second_controls,
)


def test_coding_yaml_roundtrips_and_keeps_null():
    res = {"items": {"d1": {"inventory": {"covered": True, "evidence": "§3 \"inventory\": yes", "note": "a:b"},
                            "vendors": {"covered": False}, "unique_id": {"covered": None, "note": "paywalled"}}}}
    y = yaml.safe_load(coding_yaml(res, "ai_x", "원문", "2026-11-11"))
    assert y["coder"] == "ai_x" and y["provisional"] is True
    d1 = y["items"]["d1"]
    assert d1["inventory"]["covered"] is True and d1["inventory"]["evidence"] == '§3 "inventory": yes'
    assert d1["vendors"]["covered"] is False and d1["unique_id"]["covered"] is None
    assert d1["kill_switch"]["covered"] is None  # 빠진 통제 = null(미코딩)


def test_incident_vectors_and_disagreements():
    first = {"i1": ["least_privilege", "audit_trail"], "i2": [], "only_first": ["vendors"]}
    second = {"i1": {"least_privilege": True, "kill_switch": True}, "i2": {}, "only_second": {"vendors": True}}
    a, b, diff, per = incident_vectors(first, second)
    assert len(a) == len(b) == 2 * 7          # 공통 사건 2건 × 7
    assert sorted(diff) == [("i1", "audit_trail"), ("i1", "kill_switch")]
    assert per["least_privilege"] == ([True, False], [True, False])
    md = render_incident_agreement(first, second, "ai_x")
    assert "공통 사건 2건" in md and "1차만 참" in md and "2차만 참" in md


def test_second_controls_rejects_unknown_ids():
    raw = {"incidents": {"i1": {"controls": ["least_privilege"]}, "i2": {"controls": []}}}
    got = second_controls(raw, {"i1", "i2"})
    assert got["i1"]["least_privilege"] is True and not any(got["i2"].values())
    with pytest.raises(IncidentCodingError):
        second_controls({"incidents": {"i1": {"controls": ["least_priv"]}}})
    with pytest.raises(IncidentCodingError):
        second_controls({"incidents": {"typo": {"controls": []}}}, {"i1"})


def test_render_reports_both_true_and_thin_basis():
    first = {"i1": ["least_privilege"], "i2": ["least_privilege"], "i3": []}
    second = {"i1": {"least_privilege": True}, "i2": {}, "i3": {}}
    md = render_incident_agreement(first, second, "ai_x", basis={"i2": "summary_only"})
    row = next(line for line in md.splitlines() if line.startswith("| least_privilege"))
    assert row.split("|")[2:5] == [" 2 ", " 1 ", " 1 "]  # 1차 2 · 2차 1 · 둘 다 1
    assert "요약으로만 판단한 사건 1건" in md and "`i2`" in md
