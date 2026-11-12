"""진단 보고서 — 데이터(우선 조치 · RCM · 책무별) · Markdown · HTML(이스케이프) · CSV(엑셀 · 수식 막기) · CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from pivoxpolicy import cli, diagnosis, intake

SPEC = Path(__file__).resolve().parents[1] / "examples" / "agent_spec_order.yaml"


@pytest.fixture(scope="module")
def D():
    r = intake.build(SPEC.read_text(encoding="utf-8"))
    agent = {"id": "agt_test00", "status": "active", "expires_at": None, **r["agent"], "compliance": r["compliance"], "cases": r["cases"],
             "intake": {"tools": r["tools"], "warnings": r["warnings"], "skipped": r["skipped"]}}
    return diagnosis.diagnose(agent, r["components"], company="가상 증권사 B")


def test_actions_conflict_first_then_binding(D):
    acts = D["actions"]
    assert acts[0]["kind"] == "conflict" and "제15조" in acts[0]["title"]
    lp = next(a for a in acts if a["title"].startswith("최소 권한을"))
    assert lp["kind"] == "violation" and "제70조" in lp["basis"][0]               # 가장 센 근거(문언대로)가 앞
    audit = next(a for a in acts if a["title"].startswith("감사 기록을"))
    assert "강제 · 문언대로" in audit["basis"][0]


def test_rcm_rows(D):
    rows = {r["control"]: r for r in D["rcm"]}
    assert len(rows) == 7 and rows["least_privilege"]["judgment"].startswith("미흡")
    assert rows["human_approval"]["mode"] == "자동" and "승인자에만" in rows["human_approval"]["judgment"]
    assert rows["audit_trail"]["type"] == "탐지" and rows["least_privilege"]["owner"]


def test_renderers(D):
    md = diagnosis.to_markdown(D)
    assert md.startswith("# AI 에이전트 내부통제 진단 보고서") and "## 3. 통제 매트릭스 (RCM)" in md and "변호사 검토 전" in md
    h = diagnosis.to_html(D)
    assert h.startswith("<!doctype html>") and "<script" not in h and "통제 매트릭스" in h
    rcm = diagnosis.rcm_csv(D)
    assert rcm.startswith("﻿통제 ID") and "\r\n" in rcm and rcm.count("\r\n") == 8
    assert diagnosis.obligations_csv(D).count("\r\n") == D["assessment"]["summary"]["applicable"] + 1


def test_html_escapes_and_csv_formula_guard(D):
    evil = dict(D, agent={**D["agent"], "name": "<img src=x onerror=alert(1)>"})
    assert "<img src=x" not in diagnosis.to_html(evil)
    out = diagnosis._csv(["a"], [["=HYPERLINK(\"x\")"], ["+1"], ["보통"]])
    assert "'=HYPERLINK" in out and "'+1" in out and "\r\n보통" in out


def test_needs_profile():
    with pytest.raises(diagnosis.ReportError):
        diagnosis.diagnose({"id": "agt_x", "levels": {}, "tools": []}, [])


def test_josa():
    assert [diagnosis._josa(w, "을", "를") for w in ("최소 권한", "인벤토리", "AI", "10")] == ["최소 권한을", "인벤토리를", "AI를", "10을"]


def test_cli_diagnose(tmp_path, capsys):
    assert cli.main(["diagnose", str(SPEC), "--out", str(tmp_path), "--company", "가상 증권사 B"]) == 0
    assert {f.name for f in tmp_path.iterdir()} == {"report.html", "report.md", "rcm.csv", "obligations.csv"}
    assert "걸리는 조문" in capsys.readouterr().out
