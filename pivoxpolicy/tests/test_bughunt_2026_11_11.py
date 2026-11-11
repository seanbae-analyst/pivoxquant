"""2026-11-11 코드 리뷰(에이전트)가 재현한 버그의 회귀 테스트. 각 테스트는 고치기 전 코드에서 실패했다."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

from pivoxpolicy import agreement, assess, fetch, incidents, intel, kappa, matrix, rubric, schema, site
from pivoxpolicy.fetch import FetchResult
from pivoxpolicy.registry import load_controls, load_documents

RSS = """<?xml version="1.0" encoding="{enc}"?><rss version="2.0"><channel><title>t</title>
<item><title>AI agent 보안</title><link>https://ex.org/a</link></item></channel></rss>"""


def _fetcher(bodies: dict[str, bytes]):
    def f(url: str, **_kw) -> FetchResult:
        b = bodies[url]
        return FetchResult(200, b, "application/xml")
    return f


# ── High 1 · Medium 4·5: 피드 하나가 수집 전체를 멈추지 않는다 ──

@pytest.mark.parametrize("enc", ["euc-kr", "cp949"])
def test_multibyte_declared_encoding_parses(enc):
    items = intel.parse_feed(RSS.format(enc=enc).encode(enc))
    assert [i.title for i in items] == ["AI agent 보안"]


def test_bad_feed_is_marked_failed_and_others_still_collected():
    feeds = [
        {"id": "bad", "url": "https://bad/kev", "adapter": "kev", "kind": "primary"},
        {"id": "boom", "url": "https://boom/rss", "kind": "primary"},
        {"id": "ok", "url": "https://ok/rss", "kind": "primary"},
    ]

    def f(url: str, **_kw) -> FetchResult:
        if url == "https://boom/rss":
            raise TimeoutError("slow")
        return FetchResult(200, {"https://bad/kev": b'[{"cveID": null}]',
                                 "https://ok/rss": RSS.format(enc="utf-8").encode()}[url])

    new, status = intel.collect(feeds, [], fetcher=f, now="2026-11-11T00:00:00Z")
    by = {s["id"]: s for s in status}
    assert [i.link for i in new] == ["https://ex.org/a"]
    assert "parse" in by["bad"]["error"] and "fetch" in by["boom"]["error"]


@pytest.mark.parametrize("raw", [
    {"vulnerabilities": [{"cveID": "CVE-1", "shortDescription": None, "product": None}]},
    {"vulnerabilities": [None, {"cveID": "CVE-1"}]},
])
def test_kev_null_fields_do_not_crash(raw):
    items = intel.parse_adapter("kev", json.dumps(raw).encode(), "k")
    assert [i.title for i in items] == ["CVE-1"]


def test_other_adapters_tolerate_nulls():
    nvd = {"vulnerabilities": [{"cve": {"id": "CVE-2", "descriptions": None}}]}
    assert intel.parse_adapter("nvd", json.dumps(nvd).encode(), "n")[0].link.endswith("CVE-2")
    fr = {"results": [{"title": None, "html_url": "https://fr/x"}]}
    assert intel.parse_adapter("federalregister", json.dumps(fr).encode(), "f") == []
    asm = {"svc": [{"head": []}, {"row": [{"BILL_NAME": None, "DETAIL_LINK": "https://a/1"}]}]}
    assert intel.parse_adapter("assembly", json.dumps(asm).encode(), "a") == []
    fsi = {"resultData": [{"title": "AI", "bbsNo": None}, {"title": "AI 2", "bbsNo": 7}]}
    links = [i.link for i in intel.parse_adapter("fsi_bbs", json.dumps(fsi).encode(), "s")]
    assert links == ["https://www.fsec.or.kr/bbs/detail?menuNo=69&bbsNo=7"]


@pytest.mark.parametrize("body", [
    b"\n" + RSS.format(enc="utf-8").encode(),
    b"\xef\xbb\xbf\n" + RSS.format(enc="utf-8").encode(),
    RSS.format(enc="utf-8").replace("AI agent", "AI&nbsp;agent").encode(),
])
def test_whitespace_bom_and_html_entities_still_parse(body):
    assert len(intel.parse_feed(body)) == 1


def test_bom_json_feed_and_bom_adapter():
    jf = b'\xef\xbb\xbf{"version":"https://jsonfeed.org/version/1.1","items":[{"url":"https://ex.org/j","title":"AI agent"}]}'
    assert [i.link for i in intel.parse_feed(jf)] == ["https://ex.org/j"]
    kev = b'\xef\xbb\xbf{"vulnerabilities":[{"cveID":"CVE-9"}]}'
    assert len(intel.parse_adapter("kev", kev, "k")) == 1


def test_zero_item_feed_is_not_reported_healthy():
    empty = b'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title></channel></rss>'
    new, status = intel.collect([{"id": "e", "url": "https://e/rss"}], [], fetcher=_fetcher({"https://e/rss": empty}),
                                now="2026-11-11T00:00:00Z")
    assert status[0].get("warning") and not status[0].get("error")
    out = intel.render_new(new, status)
    assert "## 0건 1" in out and "정상 0" in out


# ── Medium 2: 한글이 붙은 짧은 키워드 ──

@pytest.mark.parametrize("text", ["금융권 AI가 바꾸는 여신심사", "생성형AI 활용", "AI기본법 시행", "Securing LLMs", "LLMjacking"])
def test_short_keyword_matches_next_to_hangul_and_plurals(text):
    assert fetch.keyword_regex(["AI", "LLM"]).search(text)


@pytest.mark.parametrize("text", ["Daily briefing", "she said", "aim high", "AIRLINE", "OpenAI"])
def test_short_keyword_still_rejects_inside_words(text):
    assert not fetch.keyword_regex(["AI"]).search(text)


def test_agent_re_next_to_hangul():
    assert fetch.AGENT_RE.search("AI agent가 결제를 실행") and fetch.AGENT_RE.search("생성형AI agents")


# ── Medium 3: NVD 로 먼저 본 CVE 가 KEV 에 오르면 새 항목 ──

def test_kev_listing_of_a_cve_seen_via_nvd_is_new():
    nvd = json.dumps({"vulnerabilities": [{"cve": {"id": "CVE-7", "descriptions": [{"lang": "en", "value": "AI agent RCE"}]}}]}).encode()
    kev = json.dumps({"vulnerabilities": [{"cveID": "CVE-7", "vulnerabilityName": "AI agent RCE"}]}).encode()
    known, _ = intel.collect([{"id": "n", "url": "https://nvd", "adapter": "nvd"}], [], fetcher=_fetcher({"https://nvd": nvd}),
                             now="2026-11-11T00:00:00Z")
    new, _ = intel.collect([{"id": "k", "url": "https://kev", "adapter": "kev"}], known, fetcher=_fetcher({"https://kev": kev}),
                           now="2026-11-12T00:00:00Z")
    assert [i.feed_id for i in new] == ["k"]


# ── Medium 6: 상대 링크 · URL 아닌 guid ──

def test_relative_links_resolve_per_feed_and_guid_is_not_a_link():
    atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>AI agent</title><link href="/news/1"/></entry></feed>'
    a = intel.parse_feed(atom, base_url="https://a.example/atom")
    b = intel.parse_feed(atom, base_url="https://b.example/atom")
    assert a[0].link == "https://a.example/news/1" and b[0].link == "https://b.example/news/1"
    rss = b'<rss><channel><item><title>AI agent</title><guid isPermaLink="false">12345</guid></item></channel></rss>'
    assert intel.parse_feed(rss)[0].link == ""


def test_titles_unescape_xhtml_and_null():
    rss = b'<rss><channel><item><title>Fed&amp;rsquo;s AI</title><link>https://x/1</link></item></channel></rss>'
    assert intel.parse_feed(rss)[0].title == "Fed’s AI"
    atom = (b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title type="xhtml">'
            b'<div xmlns="http://www.w3.org/1999/xhtml">AI agent alert</div></title><link href="https://x/2"/></entry></feed>')
    assert intel.parse_feed(atom)[0].title == "AI agent alert"
    jf = b'{"items":[{"url":"https://x/3","title":null}]}'
    assert intel.parse_feed(jf)[0].title == ""


# ── Medium 7 · Low: covered/observed 는 진짜 bool 만 ──

def test_covered_one_is_rejected():
    docs, controls = load_documents(), load_controls()
    did = next(d for d, x in docs.items() if x.binding == 2)
    probs = schema.validate_coding({"coder": "x", "coded_at": "2026-11-11",
                                    "items": {did: {"inventory": {"covered": 1, "evidence": "e"}}}}, docs, controls)
    assert any("covered 는 true/false/null" in p for p in probs)


def test_empty_coding_file_is_a_problem_not_a_crash():
    assert schema.validate_coding(None, {}, []) and schema.validate_coding({"items": []}, {}, [])  # type: ignore[arg-type]


# ── Medium 8 · Low: 평가 파일 ──

@pytest.fixture(scope="module")
def rub():
    return rubric.load_rubric()


@pytest.mark.parametrize("scores", [
    {"inventory": {"verified_inventory": True}},
    {"inventory": {"verified_inventory": "yes"}},
    {"inventory": ["x"]},
    ["x"],
])
def test_validate_assessment_reports_instead_of_crashing(rub, scores):
    a = {"subject": "s", "period": "2026", "assessor": "a", "scores": scores}
    assert rubric.validate_assessment(a, rub)
    assess.build_profile(a, rub)  # 모양이 틀려도 프로필은 만든다(빈 칸으로)


def test_observed_one_is_rejected_and_never_fires(rub):
    dim = rub.dimensions[0]
    sid = dim.signals[0].id
    a = {"subject": "s", "period": "p", "assessor": "a", "scores": {dim.id: {sid: {"observed": 1, "evidence": "e", "evidence_level": "primary"}}}}
    assert any("observed 는" in p for p in rubric.validate_assessment(a, rub))
    assert rubric.derive_level(dim, a["scores"][dim.id]).level is None


def test_only_downgraded_signals_is_unrated_not_zero(rub):
    dim = next(d for d in rub.dimensions if any(s.min_evidence == "primary" for s in d.signals))
    s = next(s for s in dim.signals if s.min_evidence == "primary")
    der = rubric.derive_level(dim, {s.id: {"observed": True, "evidence": "보도", "evidence_level": "press"}})
    assert der.level is None and der.downgraded == [s.id]


def test_compare_assessors_flags_different_subjects(rub):
    a = {"subject": "A", "period": "2026", "assessor": "x", "scores": {}}
    b = {"subject": "B", "period": "2025", "assessor": "y", "scores": {}}
    res = assess.compare_assessors(a, b, rub)
    assert res["mismatch"] == ["subject", "period"] and "⚠" in assess.render_kappa(res)


# ── Medium 9: 문서 날짜 ──

def _doc(**over):
    d = {"id": "x", "title": "t", "issuer": "i", "jurisdiction": "KR", "doc_type": "law", "status": "in_force",
         "binding": 2, "url": "https://x", "date": "2026-01-05"}
    d.update(over)
    return d


@pytest.mark.parametrize("bad", ["2026-01", "2026년 1월", 2026])
def test_bad_document_dates_are_schema_errors(bad):
    with pytest.raises(schema.SchemaError):
        schema.Document.from_dict(_doc(date=bad))


def test_yaml_timestamp_becomes_a_date():
    assert schema.Document.from_dict(_doc(date=datetime(2026, 1, 5, 10, 0))).date == date(2026, 1, 5)


# ── Medium 10 · Low: 대시보드 ──

def test_placeholder_in_feed_title_is_not_expanded_and_js_links_are_text(tmp_path: Path):
    items = [intel.Item("f", "AI agent note {{DOCS}} {{METHOD}}", "javascript:alert(1)", "2026-11-10T00:00:00Z",
                        "agentic", first_seen="2026-11-11T00:00:00Z", issuer="X", jurisdiction="US", kind="primary",
                        topic="regulation")]
    intel.append_items(items, tmp_path)
    page = site.build(out_dir=tmp_path / "out", snapshot_dir=tmp_path,
                      now=datetime(2026, 11, 11)).read_text(encoding="utf-8")
    assert "AI agent note {{DOCS}} {{METHOD}}" in page
    assert 'href="javascript:' not in page


def test_undated_item_shows_collection_label_and_sorts_last():
    dated = intel.Item("f", "AI agent dated", "https://x/1", "2026-11-10T00:00:00Z", first_seen="2026-11-11T00:00:00Z",
                       kind="primary", topic="regulation")
    undated = intel.Item("f", "AI agent undated", "https://x/2", "", first_seen="2026-11-11T05:00:00Z",
                         kind="primary", topic="regulation")
    html_now = site._now_and_incidents([undated, dated])[0]
    assert html_now.index("AI agent dated") < html_now.index("AI agent undated")
    assert "수집 11-11" in html_now


# ── Low: 날짜 파싱 ──

@pytest.mark.parametrize("raw,want", [
    ("Tue, 11 Nov 2026 08:00:00 KST", "2026-11-10T23:00:00Z"),
    ("2026-11-11T08:00+09:00", "2026-11-10T23:00:00Z"),
    ("2026-11-11T08:00:00.123456789Z", "2026-11-11T08:00:00Z"),
    ("2026년 11월 5일", "2026-11-05T00:00:00Z"),
    ("2026. 11. 5.", "2026-11-05T00:00:00Z"),
])
def test_parse_date_timezones_and_korean(raw, want):
    assert intel.parse_date(raw) == want


# ── Low: incidents.yaml ──

def _write_inc(tmp_path: Path, text: str) -> Path:
    (tmp_path / "incidents.yaml").write_text(text, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("text", ["incidents: {a: 1}\n", "incidents: [just-a-string]\n", "incidents: [\n"])
def test_malformed_incidents_yaml_raises_incident_error(tmp_path, text):
    with pytest.raises(incidents.IncidentError):
        incidents.load_incidents(_write_inc(tmp_path, text), control_ids={"inventory"})


def test_incident_dates_normalize_for_sorting(tmp_path):
    base = {"title": "t", "jurisdiction": "KR", "ai_role": "attacker_used_ai_agent", "evidence_level": "primary",
            "source_url": "https://x"}
    rows = [dict(base, id="mar", date="2026.03.01"), dict(base, id="dec", date="2026-12-31"), dict(base, id="nov", date="2026-11")]
    incs = incidents.load_incidents(_write_inc(tmp_path, yaml.safe_dump({"incidents": rows}, allow_unicode=True)),
                                    control_ids={"inventory"})
    assert [i.id for i in sorted(incs, key=lambda x: x.date, reverse=True)] == ["dec", "nov", "mar"]


# ── Low: 그 밖 ──

def test_truncated_intel_jsonl_line_is_skipped(tmp_path):
    intel.append_items([intel.Item("f", "AI agent", "https://x/1", "")], tmp_path)
    with (tmp_path / "intel.jsonl").open("a", encoding="utf-8") as f:
        f.write('{"feed_id": "f", "title": "cut')
    assert [i.link for i in intel.load_items(tmp_path)] == ["https://x/1"]


def test_zero_score_ties_credit_every_document():
    docs, controls = load_documents(), load_controls()
    us = [d for d, x in docs.items() if x.jurisdiction == "US" and x.binding > 0 and x.status != "superseded"][:3]
    coding = {"items": {d: {"inventory": {"covered": False}} for d in us}}
    cell = matrix.build_matrix(docs, controls, coding)["US"]["inventory"]
    assert cell.score == 0 and cell.top_docs == us


def test_unknown_document_in_coding_does_not_crash_the_matrix():
    docs, controls = load_documents(), load_controls()
    matrix.build_matrix(docs, controls, {"items": {"no-such-doc": {"inventory": {"covered": True}}}})


def test_extract_links_keeps_hrefs_with_fragments():
    body = b'<a href="/news/1#top">AI news</a><a href="#x">AI x</a><a href="javascript:void(0)">AI j</a>'
    assert fetch.extract_links(body, "https://ex.org/list") == [{"url": "https://ex.org/news/1", "text": "AI news"}]


def test_kappa_with_no_cells_has_no_observed_agreement():
    k = kappa.cohen_kappa([], [])
    assert k.observed_agreement is None and k.kappa is None


def test_agreement_yaml_survives_control_chars_and_odd_coder_names():
    res = {"items": {"d1": {"inventory": {"covered": "true", "evidence": "Art.\x9c14 \x7f  "}}}}
    y = yaml.safe_load(agreement.coding_yaml(res, "gpt: run #2", "원문", "2026-11-11"))
    assert y["coder"] == "gpt: run #2"
    assert y["items"]["d1"]["inventory"] == {"covered": True, "evidence": "Art.\x9c14 \x7f  "}
    with pytest.raises(ValueError):
        agreement.coding_yaml({"items": {"d1": {"inventory": {"covered": "yes"}}}}, "c", "b", "t")


def test_incident_vectors_reject_string_booleans():
    with pytest.raises(agreement.IncidentCodingError):
        agreement.incident_vectors({"i": ["inventory"]}, {"i": {"inventory": "false"}})
