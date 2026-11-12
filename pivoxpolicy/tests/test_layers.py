"""코드북 v2 — 두 층(일반 통제 · AI·에이전트 적용) 코딩."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pivoxpolicy import agreement, kappa, matrix, report, schema, site
from pivoxpolicy.registry import REGISTRY_DIR, load_controls, load_documents

DOCS = load_documents()
CONTROLS = load_controls()
KR_BINDING = "kr-efsr-art13"                 # binding 2 · names_agents false
KR_VOLUNTARY = "kr-fsi-agent-criteria-2026-10"  # binding 1 · names_agents true
US_BINDING = "us-nydfs-part500"              # binding 2


def cell(analog=None, agent=None, subject=None):
    a = {"covered": analog}
    g = {"covered": agent, "subject": subject}
    if analog is True:
        a["evidence"] = "§a"
    if agent is True:
        g["evidence"] = "§g"
    return {"analog": a, "agent": g}


def coding(items, coder="x"):
    return {"coder": coder, "coded_at": "2026-11-11", "codebook": 2, "items": items}


def full(**cells):
    """통제 7개를 모두 채운 문서 한 건 — 안 준 통제는 둘 다 false."""
    return {c.id: cells.get(c.id, cell(False, False)) for c in CONTROLS}


def test_fixture_documents_are_what_the_tests_assume():
    assert DOCS[KR_BINDING].binding == 2 and DOCS[KR_BINDING].names_agents is False
    assert DOCS[KR_VOLUNTARY].binding == 1 and DOCS[KR_VOLUNTARY].names_agents is True
    assert DOCS[US_BINDING].binding == 2


# ── 스키마 ──

def test_coding_version_and_views():
    c = coding({KR_BINDING: {"inventory": cell(True, False), "kill_switch": cell(False, True, "agent"),
                             "vendors": cell(None, False), "audit_trail": cell(False, False)}})
    assert schema.coding_version(c) == 2 and schema.coding_version({"items": {}}) == 1
    view = lambda layer: {k: (v["covered"], v["names_agent"]) for k, v in schema.layer_view(c, layer)["items"][KR_BINDING].items()}  # noqa: E731
    assert view("analog") == {"inventory": (True, False), "kill_switch": (False, False), "vendors": (None, False), "audit_trail": (False, False)}
    assert view("agent") == {"inventory": (False, False), "kill_switch": (True, True), "vendors": (False, False), "audit_trail": (False, False)}
    # either: 하나라도 true → true · 둘 다 false → false · 모르는 것이 섞이면 null
    assert view("either") == {"inventory": (True, False), "kill_switch": (True, True), "vendors": (None, False), "audit_trail": (False, False)}
    v1 = {"coder": "d", "items": {}}
    assert schema.layer_view(v1, "agent") is v1
    with pytest.raises(ValueError):
        schema.layer_view(c, "nope")


def test_cell_score_uses_cell_level_agent_naming_when_given():
    b2, b1 = DOCS[KR_BINDING], DOCS[KR_VOLUNTARY]
    assert schema.cell_score(b2, True) == 2                      # 문서 단위 names_agents false
    assert schema.cell_score(b2, True, names_agent=True) == 3    # 칸의 근거가 에이전트를 명시
    assert schema.cell_score(b1, True) == 1 and schema.cell_score(b1, True, names_agent=True) == 1   # 자율은 늘 1
    assert schema.cell_score(b2, False, names_agent=True) == 0


def test_validate_two_layer_coding():
    ok = coding({KR_BINDING: full(inventory=cell(True, False), kill_switch=cell(False, True, "ai"))})
    assert schema.validate_coding(ok, DOCS, CONTROLS) == []
    bad = coding({KR_BINDING: {
        "inventory": {"analog": {"covered": True}, "agent": {"covered": False}},                       # evidence 없음
        "vendors": {"analog": {"covered": False}},                                                    # agent 층 없음
        "unique_id": {"analog": {"covered": False}, "agent": {"covered": True, "evidence": "e"}},      # subject 없음
        "least_privilege": {"analog": {"covered": False}, "agent": {"covered": False, "subject": "ai"}},  # true 아닌데 subject
        "human_approval": {"analog": {"covered": 1}, "agent": {"covered": False}},                     # bool 아님
        "audit_trail": {"covered": True, "evidence": "v1 모양"},
    }})
    probs = "\n".join(schema.validate_coding(bad, DOCS, CONTROLS))
    for frag in ("inventory.analog: covered true 면 evidence", "vendors.agent: covered 필드 필요",
                 "unique_id.agent: covered true 면 subject", "least_privilege.agent: covered 가 true 가 아니면 subject 는 null",
                 "human_approval.analog: covered 는 true/false/null", "audit_trail.analog: covered 필드 필요"):
        assert frag in probs, frag


def test_primary_coder_prefers_two_layer_codings():
    assert schema.primary_coder({"deck": {"items": {}}, "zz": coding({}), "mm": coding({})}) == "mm"
    assert schema.primary_coder({"b": {}, "a": {}}) == "a" and schema.primary_coder({}) is None


# ── 매트릭스 ──

def test_layer_matrices_score_each_layer_separately():
    c = coding({
        KR_BINDING: full(kill_switch=cell(True, False), human_approval=cell(True, True, "ai"), audit_trail=cell(False, True, "agent")),
        KR_VOLUNTARY: full(kill_switch=cell(False, True, "agent"), least_privilege=cell(False, True, "ai")),
    })
    ms = matrix.layer_matrices(DOCS, CONTROLS, c)
    a, g = ms["analog"]["KR"], ms["agent"]["KR"]
    assert (a["kill_switch"].score, g["kill_switch"].score) == (2, 1)        # 일반은 구속력, AI 는 자율 문서뿐
    assert g["kill_switch"].agent_specific_voluntary == [KR_VOLUNTARY]      # 그 자율 문서는 에이전트를 명시
    assert (a["human_approval"].score, g["human_approval"].score) == (2, 2)  # 구속력 있고 AI 일반 대상
    assert g["audit_trail"].score == 3 and g["audit_trail"].names_agents     # 구속력 + 근거 조항이 에이전트 명시
    assert g["least_privilege"].score == 1 and g["least_privilege"].agent_specific_voluntary == []  # subject ai → 에이전트 명시 아님
    assert max(x.score for x in a.values()) <= 2                             # 일반 층엔 3 이 없다
    assert set(matrix.layer_matrices(DOCS, CONTROLS, {"items": {}})) == {""}  # v1 코딩은 층이 없다


def test_analog_layer_never_scores_three_even_for_agent_naming_documents():
    us_agentic = next(d for d in DOCS.values() if d.binding == 2 and d.status != "superseded")
    c = coding({us_agentic.id: full(inventory=cell(True, True, "agent"))})
    ms = matrix.layer_matrices(DOCS, CONTROLS, c)
    assert ms["analog"][us_agentic.jurisdiction]["inventory"].score == 2
    assert ms["agent"][us_agentic.jurisdiction]["inventory"].score == 3


def test_superseded_documents_are_left_out_of_the_matrix():
    old = next(d for d in DOCS.values() if d.status == "superseded" and d.binding == 2)
    v1 = {"items": {old.id: {"inventory": {"covered": True, "evidence": "e"}}}}
    assert matrix.build_matrix(DOCS, CONTROLS, v1)[old.jurisdiction]["inventory"].score is None
    assert "us-cisa-bod-26-04" in DOCS and DOCS["us-cisa-bod-26-04"].status == "in_force"   # 대체한 문서가 등록돼 있다


def test_render_layers_lists_the_gap_and_counts_score_three():
    c = coding({KR_BINDING: full(kill_switch=cell(True, False)), KR_VOLUNTARY: full(kill_switch=cell(False, True, "agent"))})
    ms = matrix.layer_matrices(DOCS, CONTROLS, c)
    md = matrix.render_layers(ms["analog"], ms["agent"], CONTROLS, "x")
    assert "| 7 | 즉시 중단 (Kill switch) | 2 / 1* |" in md
    assert "간극 — 일반 통제는 구속력(2)인데 AI·에이전트 층은 2 미만: 1칸" in md
    assert f"- KR · 7 즉시 중단: 일반 **2** ← `{KR_BINDING}` · AI·에이전트 **1*** ← `{KR_VOLUNTARY}`" in md
    assert "(점수 3): **0**" in md


# ── κ ──

def test_compare_two_layer_codings_per_layer():
    a = coding({KR_BINDING: full(kill_switch=cell(True, False), inventory=cell(True, True, "ai"), vendors=cell(False, True, "agent"))}, "A")
    b = coding({KR_BINDING: full(kill_switch=cell(True, True, "ai"), inventory=cell(False, True, "agent"), vendors=cell(False, True, "agent"))}, "B")
    res = kappa.compare(a, b, DOCS, CONTROLS)
    assert list(res["views"]) == ["analog", "agent", "either"] and res["versions"] == (2, 2)
    assert res["views"]["analog"]["directions"] == [(KR_BINDING, "inventory", True)]      # A 만 다룸
    assert res["views"]["agent"]["directions"] == [(KR_BINDING, "kill_switch", False)]    # B 만 다룸
    assert res["views"]["either"]["disagreements"] == []                                  # 접으면 같다
    assert res["subject"] == {"n": 2, "same": 1, "diff": [(KR_BINDING, "inventory", "ai", "agent")]}
    md = kappa.render_compare(res)
    assert "| 일반 통제 층 | 7 |" in md and "`kr-efsr-art13` × `kill_switch` — B 만 다룸" in md and "(ai/agent)" in md


def test_compare_mixed_and_v1_pairs():
    v2 = coding({KR_BINDING: full(kill_switch=cell(True, False))}, "V2")
    v1 = {"coder": "V1", "coded_at": "d", "items": {KR_BINDING: {c.id: {"covered": c.id == "kill_switch"} for c in CONTROLS}}}
    mixed = kappa.compare(v1, v2, DOCS, CONTROLS)
    assert list(mixed["views"]) == ["either"] and mixed["views"]["either"]["disagreements"] == [] and "subject" not in mixed
    assert "참고용" in kappa.render_compare(mixed)
    assert list(kappa.compare(v1, v1, DOCS, CONTROLS)["views"]) == [""]


def test_null_cells_are_left_out_of_kappa():
    a = coding({KR_BINDING: full(inventory=cell(None, True, "ai"))}, "A")
    b = coding({KR_BINDING: full(inventory=cell(True, True, "ai"))}, "B")
    res = kappa.compare(a, b, DOCS, CONTROLS)
    assert res["views"]["analog"]["n_cells"] == 6 and res["views"]["agent"]["n_cells"] == 7


# ── 쓰기 · 리포트 · 대시보드 ──

def test_coding_yaml_v2_roundtrip_and_refusals():
    res = {"items": {KR_BINDING: {"kill_switch": {"analog": {"covered": True, "evidence": '①11호: "계정 사용 중지"'},
                                                  "agent": {"covered": "false", "subject": None}, "note": "borderline: x"},
                                  "inventory": {"analog": {"covered": False}, "agent": {"covered": True, "subject": "agent", "evidence": "p.3"}}}}}
    c = yaml.safe_load(agreement.coding_yaml_v2(res, "ai_x", "코퍼스", "2026-11-11", ["머리말"]))
    assert c["codebook"] == 2 and schema.validate_coding(c, DOCS, CONTROLS) == []
    ks = c["items"][KR_BINDING]["kill_switch"]
    assert ks == {"analog": {"covered": True, "evidence": '①11호: "계정 사용 중지"'}, "agent": {"covered": False, "subject": None}, "note": "borderline: x"}
    assert c["items"][KR_BINDING]["vendors"] == {"analog": {"covered": None}, "agent": {"covered": None, "subject": None}}   # 빠진 통제 = 미코딩
    for bad in ({"analog": {"covered": True}, "agent": {"covered": False}},                       # evidence 없음
                {"analog": {"covered": False}, "agent": {"covered": True, "evidence": "e"}}):      # subject 없음
        with pytest.raises(ValueError):
            agreement.coding_yaml_v2({"items": {KR_BINDING: {"inventory": bad}}}, "c", "b", "d")


def test_report_writes_layer_tables_and_summary(tmp_path: Path):
    a = coding({KR_BINDING: full(kill_switch=cell(True, False))}, "A")
    b = coding({KR_BINDING: full(kill_switch=cell(True, True, "ai"))}, "B")
    v1 = {"coder": "V1", "coded_at": "d", "items": {KR_BINDING: {"kill_switch": {"covered": True, "evidence": "e"}}}}
    names = {p.name for p in report.write_all(DOCS, CONTROLS, {"a2": a, "b2": b, "v1": v1}, tmp_path)}
    for n in ("matrix-a2.md", "matrix-a2-analog.md", "matrix-a2-agent.csv", "gaps-a2.md", "matrix-v1.md",
              "kappa-a2-vs-b2.md", "kappa-a2-vs-v1.md", "matrix-diff-a2-vs-b2.md", "kappa-summary.md"):
        assert n in names, n
    assert "matrix-diff-a2-vs-v1.md" not in names          # 모양이 다른 코딩끼리는 매트릭스를 견주지 않는다
    diff = (tmp_path / "matrix-diff-a2-vs-b2.md").read_text(encoding="utf-8")
    assert "· 일반 통제 층" in diff and "· AI·에이전트 적용 층" in diff and "| KR | kill_switch | 0 | 2 |" in diff
    summary = (tmp_path / "kappa-summary.md").read_text(encoding="utf-8")
    assert summary.count("| `a2` | `b2` |") == 3 and "| `a2` | `v1` | 둘 중 하나" in summary
    gaps = (tmp_path / "gaps-a2.md").read_text(encoding="utf-8")
    assert "| KR | 7 | 즉시 중단 | 2 | 0 | AI 를 대상으로 한 요구가 없음 — 일반 통제는 구속력 있음(간극) |" in gaps


def test_site_two_layer_cells_mark_coder_differences_and_put_gaps_first():
    a = coding({KR_BINDING: full(kill_switch=cell(True, False), inventory=cell(False, False))}, "A")
    b = coding({KR_BINDING: full(kill_switch=cell(True, True, "ai"), inventory=cell(False, False))}, "B")
    html_, (ma, mg) = site._matrix_section_v2(DOCS, CONTROLS, a, {"kill_switch": {"total": 3, "primary": 1}}, b)
    assert "<th>KR<small>일반 · AI</small></th>" in html_
    row = next(r for r in html_.split("</tr>") if "즉시 중단" in r)
    assert '<td class="duo"><span class="h-2" title="일반 통제 층: 2">2</span><span class="h-0" title="AI·에이전트 층: 0 · 다른 코더 2">0<sup' in row
    assert row.count("‡") == 1 and '3<span class="fine"> (1)</span>' in row
    gaps = site._gaps_section_v2(ma, mg, CONTROLS)
    assert gaps.index("즉시 중단 · 간극") < gaps.index("통제 1 · 인벤토리")   # 간극이 먼저
    assert "AI·에이전트 층 0 — AI를 대상으로 한 요구 없음 · 일반 통제 층 2" in gaps


# ── 코드북 ──

def test_codebook_has_rules_for_every_control_and_layer():
    cb = yaml.safe_load((REGISTRY_DIR / "controls.yaml").read_text(encoding="utf-8"))
    assert cb["codebook_version"] == 2 and set(cb["layers"]) == set(schema.LAYERS)
    assert [r["id"] for r in cb["rules"]] == [f"G{i}" for i in range(1, 9)]
    for c in cb["controls"]:
        for layer in schema.LAYERS:
            assert c[layer]["true_if"] and c[layer]["false_if"], (c["id"], layer)
    for c in CONTROLS:
        assert c.analog["true_if"] and c.agent["false_if"]


def test_codebook_rules_do_not_name_registry_documents():
    """코드북이 특정 문서·조문의 답을 알려 주면 κ 가 부풀려진다 — 규칙은 조항 유형으로만 쓴다."""
    cb = yaml.safe_load((REGISTRY_DIR / "controls.yaml").read_text(encoding="utf-8"))
    text = " ".join(r["text"] for r in cb["rules"]) + " " + " ".join(
        x for c in cb["controls"] for layer in schema.LAYERS for k in ("true_if", "false_if") for x in c[layer][k])
    for token in ("NYDFS", "CISA", "FSB", "NIST", "전자금융감독규정", "제13조", "§500", "500.", "Art. 14", "금융보안원", "가이드라인」"):
        assert token not in text, token
    for doc_id in DOCS:
        assert doc_id not in text
