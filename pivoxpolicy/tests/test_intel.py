"""피드 파서·수집기 — 네트워크 없이."""


from pivoxpolicy.fetch import FetchResult
from pivoxpolicy.intel import append_items, collect, load_items, parse_date, parse_feed, render_new

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><title>t</title>
<item><title>AI agents in bank SOCs</title><link>https://ex.org/a</link><pubDate>Tue, 10 Nov 2026 09:00:00 GMT</pubDate><description>&lt;p&gt;agentic AI&lt;/p&gt;</description></item>
<item><title>Budget 2027</title><link>https://ex.org/b</link><pubDate>Mon, 09 Nov 2026 09:00:00 +0900</pubDate></item>
<item><title>에이전트 보안 평가기준</title><guid>https://ex.org/c</guid><dc:date>2026-11-08</dc:date></item>
</channel></rss>""".encode("utf-8")

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>x</title>
<entry><title>Prompt injection in AI agent</title><link rel="alternate" href="https://ex.org/atom1"/><id>urn:1</id><updated>2026-11-01T00:00:00Z</updated><summary>s</summary></entry>
<entry><title>Other</title><id>https://ex.org/atom2</id><published>2026-10-30T12:00:00+00:00</published></entry>
</feed>"""

JSONFEED = b'{"version":"https://jsonfeed.org/version/1.1","items":[{"id":"1","url":"https://ex.org/j1","title":"agentic AI alert","date_published":"2026-11-02T10:00:00Z"}]}'

RDF = b"""<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel rdf:about="https://ex.org/"><title>r</title></channel>
<item rdf:about="https://ex.org/r1"><title>AI agent guidance</title><link>https://ex.org/r1</link><dc:date>2026-11-03</dc:date></item></rdf:RDF>"""


def test_parse_date_formats():
    assert parse_date("Tue, 10 Nov 2026 09:00:00 GMT") == "2026-11-10T09:00:00Z"
    assert parse_date("Mon, 09 Nov 2026 09:00:00 +0900") == "2026-11-09T00:00:00Z"
    assert parse_date("2026-11-08") == "2026-11-08T00:00:00Z"
    assert parse_date("2026.11.08") == "2026-11-08T00:00:00Z"
    assert parse_date("2026-11-01T00:00:00Z") == "2026-11-01T00:00:00Z"
    assert parse_date("등록일 2026-11-05 14:00") == "2026-11-05T00:00:00Z"
    assert parse_date("") == "" and parse_date("nonsense") == ""


def test_parse_rss_atom_json_rdf():
    rss = parse_feed(RSS, "f")
    assert [i.link for i in rss] == ["https://ex.org/a", "https://ex.org/b", "https://ex.org/c"]
    assert rss[0].summary == "agentic AI"           # 태그 벗김 + 언이스케이프
    assert rss[2].published == "2026-11-08T00:00:00Z"  # dc:date + guid 링크
    atom = parse_feed(ATOM, "f")
    assert [i.link for i in atom] == ["https://ex.org/atom1", "https://ex.org/atom2"]
    assert parse_feed(JSONFEED, "f")[0].link == "https://ex.org/j1"
    assert parse_feed(RDF, "f")[0].title == "AI agent guidance"
    assert parse_feed(b"<html><body>no feed</body></html>", "f") == []
    assert parse_feed(b"garbage", "f") == []


def test_collect_filters_dedupes_and_tags(tmp_path):
    feeds = [
        {"id": "f1", "url": "https://ex.org/rss", "issuer": "X", "jurisdiction": "US", "kind": "primary", "topic": "regulation", "keywords": ["AI agent", "agentic", "에이전트"]},
        {"id": "f2", "url": "https://ex.org/down", "issuer": "Y", "jurisdiction": "KR", "kind": "secondary", "topic": "incident"},
        {"id": "f3", "url": "https://ex.org/off", "issuer": "Z", "jurisdiction": "KR", "kind": "secondary", "topic": "incident", "enabled": False},
    ]

    def fetcher(url):
        if url.endswith("rss"):
            return FetchResult(200, RSS, "application/rss+xml")
        return FetchResult(503, b"", error="503")

    new, status = collect(feeds, known=[], fetcher=fetcher, now="2026-11-11T00:00:00Z")
    assert [i.link for i in new] == ["https://ex.org/a", "https://ex.org/c"]   # Budget 은 키워드 불일치
    assert new[0].kind == "primary" and new[0].first_seen == "2026-11-11T00:00:00Z"
    assert new[0].matched == ["agentic", "ai agent"] or new[0].matched == ["ai agent", "agentic"]
    st = {s["id"]: s for s in status}
    assert st["f1"]["parsed"] == 3 and st["f1"]["matched"] == 2 and st["f1"]["new"] == 2
    assert st["f2"]["error"] == "503" and st["f3"]["status"] == "disabled"

    append_items(new, tmp_path)
    known = load_items(tmp_path)
    assert len(known) == 2 and known[1].title == "에이전트 보안 평가기준"
    again, _ = collect(feeds, known=known, fetcher=fetcher)
    assert again == []                                 # 이미 본 링크는 다시 안 나옴

    out = render_new(new, status)
    assert "1차 (발행 주체) — 새 항목 2" in out and "실패 1" in out and "`f2` 503" in out


def test_keep_all_feed_bypasses_keyword_filter():
    feeds = [{"id": "f", "url": "u", "issuer": "X", "jurisdiction": "US", "kind": "primary", "topic": "threat_intel", "keep_all": True}]
    new, _ = collect(feeds, [], fetcher=lambda u: FetchResult(200, RSS, ""), now="t")
    assert len(new) == 3
