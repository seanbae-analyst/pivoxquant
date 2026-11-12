"""사건 코드북 v2 — 칸마다 failed · level(stated/inferred) · layer(agent/analog)."""

from __future__ import annotations

import pytest
import yaml

from pivoxpolicy import agreement as ag

CTL = ag.CONTROL_IDS


def rec(**true_cells):
    """주지 않은 통제는 false."""
    return {"basis": "source", "controls": {c: true_cells.get(c, {"failed": False}) for c in CTL}}


def t(level="stated", layer="agent", quote="the agent ran it", reason="r"):
    return {"failed": True, "level": level, "layer": layer, "quote": quote, "reason": reason}


def raw(incs, coder="x"):
    return {"coder": coder, "codebook": 2, "incidents": incs}


def test_views_split_level_and_layer():
    r = raw({"i1": rec(least_privilege=t("stated", "agent"), audit_trail=t("inferred", "analog"))})
    assert ag.incident_view(r, "any")["i1"]["audit_trail"] is True
    assert ag.incident_view(r, "stated")["i1"]["audit_trail"] is False
    assert ag.incident_view(r, "agent")["i1"] == {c: c == "least_privilege" for c in CTL}
    assert ag.incident_view(r, "analog")["i1"]["audit_trail"] is True


def test_thin_or_null_incidents_are_left_out():
    thin = {"basis": "thin", "controls": {c: {"failed": None} for c in CTL}}
    part = rec(); part["controls"]["kill_switch"] = {"failed": None}
    assert ag.incident_view(raw({"a": thin, "b": part, "c": rec()}), "any") == {"c": {c: False for c in CTL}}


def test_validation_requires_level_layer_quote_and_checks_corpus(tmp_path):
    bad = raw({"i1": rec(vendors={"failed": True, "level": "maybe", "layer": "agent"})})
    probs = ag.validate_incident_v2(bad)
    assert any("level" in p for p in probs) and any("quote" in p for p in probs)
    (tmp_path / "i1.txt").write_text("Line one.\n  the agent   ran it without approval.", encoding="utf-8")
    ok = raw({"i1": rec(human_approval=t(quote="the agent ran it"))})
    assert ag.validate_incident_v2(ok, corpus_dir=tmp_path) == []          # 공백 차이는 무시
    miss = raw({"i1": rec(human_approval=t(quote="no such sentence"))})
    assert any("원문에 없음" in p for p in ag.validate_incident_v2(miss, corpus_dir=tmp_path))
    assert any("모르는 사건" in p for p in ag.validate_incident_v2(ok, incident_ids={"other"}))


def test_v2_feeds_old_comparison_as_any_view():
    r = raw({"i1": rec(inventory=t("inferred", "analog"))})
    assert ag.second_controls(r) == {"i1": {c: c == "inventory" for c in CTL}}


def test_render_v2_agreement_counts_views():
    a = raw({"i1": rec(least_privilege=t("stated")), "i2": rec(audit_trail=t("inferred", "analog"))}, "a")
    b = raw({"i1": rec(least_privilege=t("inferred")), "i2": rec()}, "b")
    out = ag.render_incident_v2_agreement(a, b, "a", "b")
    assert "공통 사건 2건" in out and "`i2` × audit_trail — A 만 참 (inferred/analog)" in out
    # 최소 권한: '적은 것만' 에선 둘 다 참 0, '적었거나 추론' 에선 1
    row = next(line for line in out.splitlines() if line.startswith("| least_privilege"))
    assert row.startswith("| least_privilege | 0 · ") and "| 1 · " in row


def test_yaml_writer_round_trips():
    res = {"incidents": {"i1": {"basis": "source", "note": "borderline: x",
                                "controls": {"vendors": t("stated", "analog", quote='a "quoted" bit'), "inventory": {"failed": "false"}}}}}
    y = yaml.safe_load(ag.incident_coding_yaml_v2(res, "c", "2026-11-12", "corpus"))
    assert y["codebook"] == 2 and y["incidents"]["i1"]["controls"]["vendors"]["quote"] == 'a "quoted" bit'
    assert y["incidents"]["i1"]["controls"]["inventory"]["failed"] is False
    assert y["incidents"]["i1"]["controls"]["kill_switch"]["failed"] is None
    with pytest.raises(ValueError):
        ag.incident_coding_yaml_v2({"incidents": {"i1": {"controls": {"vendors": {"failed": "yes"}}}}}, "c", "d", "b")


# ── 고정 코퍼스 ──

def test_corpus_build_writes_text_and_manifest(tmp_path):
    from types import SimpleNamespace

    from pivoxpolicy import incident_corpus as ic
    from pivoxpolicy.fetch import FetchResult
    pages = {"https://a/x": FetchResult(200, b"<html><nav>menu</nav><article><p>" + b"agent ran rm -rf. " * 200 + b"</p></article></html>", "text/html"),
             "https://b/y": FetchResult(403, b"", "")}
    incs = [SimpleNamespace(id="i1", source_url="https://a/x"), SimpleNamespace(id="i2", source_url="https://b/y")]
    data = ic.build(incs, out_dir=tmp_path / "c", manifest=tmp_path / "m.json", fetcher=lambda u: pages[u])
    txt = (tmp_path / "c" / "i1.txt").read_text(encoding="utf-8")
    assert "menu" not in txt and "agent ran rm -rf." in txt
    assert data["documents"]["i1"]["kind"] == "html" and not data["documents"]["i1"]["thin"]
    assert data["documents"]["i2"] == {"source": "https://b/y", "http_status": 403}
    assert (tmp_path / "m.json").exists()


def test_kev_subset_keeps_only_matching_entries():
    import json

    from pivoxpolicy import incident_corpus as ic
    body = json.dumps({"catalogVersion": "1", "dateReleased": "d", "vulnerabilities": [
        {"cveID": "C-1", "product": "Langflow"}, {"cveID": "C-2", "product": "Other"}]}).encode()
    t = ic.kev_subset(body, "langflow")
    assert "C-1" in t and "C-2" not in t
