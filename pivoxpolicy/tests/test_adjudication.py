"""조정본(adjudicates: [A, B]) — 독립 코더 둘을 칸마다 합친 코딩."""

from __future__ import annotations

import copy

from pivoxpolicy import report, schema
from pivoxpolicy.registry import load_codings, load_controls, load_documents

DOCS = load_documents()
CONTROLS = load_controls()
DOC = "kr-efsr-art13"


def cell(analog, agent, subject=None):
    a = {"covered": analog, **({"evidence": "§a"} if analog else {})}
    g = {"covered": agent, "subject": subject, **({"evidence": "§g"} if agent else {})}
    return {"analog": a, "agent": g}


def coding(items, coder, **extra):
    return {"coder": coder, "coded_at": "2026-11-12", "codebook": 2, "items": {DOC: items}, **extra}


def trio(adjudication, consensus_items):
    a = coding({"inventory": cell(True, False), "vendors": cell(False, False)}, "a")
    b = coding({"inventory": cell(False, False), "vendors": cell(False, False)}, "b")
    c = coding(consensus_items, "c", adjudicates=["a", "b"], adjudication=adjudication)
    return {"a": a, "b": b, "c": c}


RULING = [{"document": DOC, "control": "inventory", "layer": "analog", "decision": False, "follows": "b", "reason": "목록 유지 문언 없음"}]


def test_valid_consensus_passes():
    cs = trio(RULING, {"inventory": cell(False, False), "vendors": cell(False, False)})
    assert schema.validate_adjudication(cs["c"], cs) == []


def test_changed_agreeing_cell_is_caught():
    cs = trio(RULING, {"inventory": cell(False, False), "vendors": cell(True, False)})
    assert any("vendors.analog" in p and "같은데" in p for p in schema.validate_adjudication(cs["c"], cs))


def test_unruled_disagreement_is_caught():
    cs = trio([], {"inventory": cell(False, False), "vendors": cell(False, False)})
    assert any("판정 없음" in p for p in schema.validate_adjudication(cs["c"], cs))


def test_ruling_must_pick_one_side_and_give_a_reason():
    bad = [{**RULING[0], "reason": ""}]
    cs = trio(bad, {"inventory": cell(False, False), "vendors": cell(False, False)})
    assert any("reason" in p for p in schema.validate_adjudication(cs["c"], cs))


def test_subject_disagreement_needs_a_ruling():
    a = coding({"kill_switch": cell(False, True, "agent")}, "a")
    b = coding({"kill_switch": cell(False, True, "ai")}, "b")
    c = coding({"kill_switch": cell(False, True, "agent")}, "c", adjudicates=["a", "b"], adjudication=[])
    assert any("kill_switch.agent" in p for p in schema.validate_adjudication(c, {"a": a, "b": b, "c": c}))


def test_consensus_is_primary_but_not_an_independent_coder():
    cs = trio(RULING, {"inventory": cell(False, False), "vendors": cell(False, False)})
    assert schema.primary_coder(cs) == "c"
    assert schema.independent_v2(cs) == ["a", "b"]


def test_report_leaves_consensus_out_of_kappa(tmp_path):
    cs = trio(RULING, {"inventory": cell(False, False), "vendors": cell(False, False)})
    names = {p.name for p in report.write_all(DOCS, CONTROLS, cs, out_dir=tmp_path)}
    assert "kappa-a-vs-b.md" in names and "adjudication-c.md" in names
    assert not any(n.startswith("kappa-") and "-c" in n.replace("kappa-", "") for n in names if n != "kappa-summary.md")


def test_registry_consensus_matches_its_sources():
    codings = load_codings()
    adj = [k for k, c in codings.items() if schema.is_adjudicated(c)]
    assert adj, "조정본이 레지스트리에 있어야 한다"
    for k in adj:
        assert schema.validate_adjudication(codings[k], codings) == [], k
        assert schema.validate_coding(codings[k], DOCS, CONTROLS) == [], k


def test_registry_consensus_tamper_is_detected():
    codings = copy.deepcopy(load_codings())
    k = next(k for k, c in codings.items() if schema.is_adjudicated(c))
    # 원본 둘이 같은 칸 하나를 뒤집으면 check 가 잡아야 한다
    doc, cells = next(iter(codings[k]["items"].items()))
    cid = next(iter(cells))
    lay = cells[cid]["analog"]
    lay["covered"] = not lay["covered"]
    assert schema.validate_adjudication(codings[k], codings)
