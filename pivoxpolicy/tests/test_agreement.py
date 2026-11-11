"""2차 코딩 합치기 · 사건 코딩 κ."""

import yaml

from pivoxpolicy.agreement import coding_yaml, incident_vectors, render_incident_agreement


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
