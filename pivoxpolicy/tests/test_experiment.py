"""실험 — 에이전트 유형 × 규제 기준. 구조 · 단조성 · 결정성 · 쓰기 · 페이지."""

from __future__ import annotations

import pytest

from pivoxpolicy import experiment as X


@pytest.fixture(scope="module")
def R():
    return X.run()


def test_shape_and_determinism(R):
    assert [a["id"] for a in R["agents"]] == ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]
    assert R["readings"] == list(X.READINGS)
    for a in R["agents"]:
        for rd, m in a["readings"].items():
            assert sum(m[k] for k in X.ATTACK_KEYS) == m["attacks"] > 0
    again = X.run()
    assert [a["readings"] for a in again["agents"]] == [a["readings"] for a in R["agents"]]       # 난수 없음


def test_monotone_in_regulatory_strength(R):
    """기준이 강할수록 미차단은 늘지 않는다(유형마다)."""
    order = ["none", "binding_explicit", "binding_interpretive", "guideline", "all"]
    for a in R["agents"]:
        d = [a["readings"][rd]["defect"] for rd in order]
        assert d == sorted(d, reverse=True), (a["id"], d)
        assert a["readings"]["none"]["defect"] == a["readings"]["none"]["attacks"]
        assert a["readings"]["all"]["defect"] == 0 and a["readings"]["all"]["held"] == 0


def test_current_findings_are_pinned(R):
    """논문에 옮기는 발견 — 의무 라이브러리가 바뀌어 이 값이 움직이면 일부러 확인하고 고친다."""
    none_ai = {a["id"] for a in R["agents"] if not a["explicit_ai_controls"]}
    assert none_ai == {"A2", "A3", "A6", "A7"}
    a5 = next(a for a in R["agents"] if a["id"] == "A5")
    assert a5["high_impact"] and "human_approval" in a5["explicit_ai_controls"]
    assert a5["readings"]["binding_explicit"]["held"] >= 1                      # 고영향 유형: 명문 기준에서 승인 의존이 생긴다
    dep = sum(len(a["interpretation_dependent"]) for a in R["agents"])
    assert dep > R["aggregate"]["binding_explicit"]["attacks"] / 2              # 절반 넘게 해석에 달려 있다


def test_outputs(R, tmp_path):
    paths = X.write_all(tmp_path, R)
    assert {p.name for p in paths} == {"results.csv", "summary.md", "manifest.json", "results.json"}
    assert (tmp_path / "results.csv").read_text(encoding="utf-8").startswith("﻿agent,label,reading,metric,value")
    md = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "## 결과 요약" in md and "표 4." in md
    page = X.page(R)
    assert "<script" not in page and "그림 1" in page and "그림 2" in page and "표 1" in page and "명문 기준" in page
    assert "gen-" not in page                                                   # 페이지는 식별자 대신 공격 유형 이름을 쓴다
    assert "least_privilege" not in " ".join(X.findings(R))                     # 요약 문장은 통제 이름을 한국어로


def test_by_scenario_adds_up(R):
    sc = X.by_scenario(R)
    assert sum(v["n"] for v in sc.values()) == R["aggregate"]["binding_explicit"]["attacks"]
    assert sum(v["dep"] for v in sc.values()) == sum(len(a["interpretation_dependent"]) for a in R["agents"])
    for v in sc.values():
        for rd in R["readings"]:
            assert sum(v[rd].values()) == v["n"]
    assert all(k in X.terms.SCENARIO for k in sc)
