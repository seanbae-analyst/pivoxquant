"""네트워크 없이 가짜 fetcher 로 스냅숏·변경 감지를 검사."""

import re

from pivoxpolicy.fetch import (
    FetchResult, agent_mentions, extract_links, load_manifest, save_manifest,
    snapshot_documents, text_of, watch_sources,
)
from pivoxpolicy.schema import Document


def _doc(id, url):
    return Document.from_dict({
        "id": id, "title": id, "issuer": "x", "jurisdiction": "US", "doc_type": "guideline",
        "status": "final", "binding": 1, "url": url,
    })


def test_iri_to_uri_encodes_korean_path_only():
    from pivoxpolicy.fetch import iri_to_uri
    assert iri_to_uri("https://www.law.go.kr/행정규칙/전자금융감독규정") == (
        "https://www.law.go.kr/%ED%96%89%EC%A0%95%EA%B7%9C%EC%B9%99/%EC%A0%84%EC%9E%90%EA%B8%88%EC%9C%B5%EA%B0%90%EB%8F%85%EA%B7%9C%EC%A0%95")
    u = "https://www.fsc.go.kr/no010101?srchCtgry=&curPage=1&srchKey=sj&srchText=%EB%B3%B4%EC%95%88"
    assert iri_to_uri(u) == u


def test_keyword_regex_word_boundary_for_short_ascii_only():
    from pivoxpolicy.fetch import keyword_regex
    r = keyword_regex(["AI", "보안", "model risk"])
    assert r.search("AI agent rule") and r.search("금융보안원 소식") and r.search("Model Risk Management")
    assert not r.search("Daily Treasury Rates") and not r.search("Mailing List")


def test_text_of_and_agent_mentions():
    html = b"<html><head><style>a{}</style></head><body><p>AI agents and agentic AI; \xec\x97\x90\xec\x9d\xb4\xec\xa0\x84\xed\x8a\xb8</p><script>x</script></body></html>"
    t = text_of(html, "text/html")
    assert "agents" in t and "<" not in t
    assert agent_mentions(t) == 3
    assert text_of(b"%PDF-1.7 ...", "application/pdf") == ""


def test_extract_links_filters_by_keyword_and_absolutises():
    body = b'<a href="/x/1">AI agent rule</a> <a href="/x/2">Budget</a> <a href="/x/1">AI agent rule</a>'
    links = extract_links(body, "https://ex.org/list", re.compile("AI"))
    assert links == [{"url": "https://ex.org/x/1", "text": "AI agent rule"}]
    assert len(extract_links(body, "https://ex.org/list", None)) == 2


def test_snapshot_detects_change_and_keeps_hash_on_failure(tmp_path):
    docs = {"a": _doc("a", "https://ex.org/a")}
    manifest = load_manifest(tmp_path)

    ev = snapshot_documents(docs, manifest, fetcher=lambda u: FetchResult(200, b"<p>v1 AI agent</p>", "text/html"), snapshot_dir=tmp_path)
    assert ev[0]["kind"] == "first_snapshot"
    h1 = manifest["documents"]["a"]["sha256"]
    assert (tmp_path / "content" / "a.html").read_bytes() == b"<p>v1 AI agent</p>"

    ev = snapshot_documents(docs, manifest, fetcher=lambda u: FetchResult(200, b"<p>v1 AI agent</p>", "text/html"), snapshot_dir=tmp_path)
    assert ev == []

    ev = snapshot_documents(docs, manifest, fetcher=lambda u: FetchResult(200, b"<p>v2 AI agent agentic</p>", "text/html"), snapshot_dir=tmp_path)
    assert ev[0]["kind"] == "changed" and ev[0]["agent_mentions"] == (1, 2)
    assert manifest["documents"]["a"]["previous_sha256"] == h1

    ev = snapshot_documents(docs, manifest, fetcher=lambda u: FetchResult(403, b"", error="403"), snapshot_dir=tmp_path)
    assert ev[0]["kind"] == "fetch_failed"
    assert manifest["documents"]["a"]["sha256"] != h1  # v2 해시 보존
    assert manifest["documents"]["a"]["status"] == 403

    save_manifest(manifest, tmp_path)
    assert load_manifest(tmp_path)["documents"]["a"]["url"] == "https://ex.org/a"


def test_watch_reports_only_new_links(tmp_path):
    src = [{"id": "s", "issuer": "x", "url": "https://ex.org/list", "keywords": ["AI"]}]
    manifest = load_manifest(tmp_path)
    page1 = b'<a href="/1">AI rule</a><a href="/2">tax</a>'
    page2 = b'<a href="/1">AI rule</a><a href="/3">AI agents guide</a>'
    ev = watch_sources(src, manifest, fetcher=lambda u: FetchResult(200, page1, "text/html"), snapshot_dir=tmp_path)
    assert ev[0]["kind"] == "first_snapshot" and ev[0]["n_links"] == 1
    ev = watch_sources(src, manifest, fetcher=lambda u: FetchResult(200, page2, "text/html"), snapshot_dir=tmp_path)
    assert ev[0]["kind"] == "new_links"
    assert [l["url"] for l in ev[0]["links"]] == ["https://ex.org/3"]
    ev = watch_sources(src, manifest, fetcher=lambda u: FetchResult(200, page2, "text/html"), snapshot_dir=tmp_path)
    assert ev == []
