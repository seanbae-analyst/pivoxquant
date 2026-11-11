"""빠른 동향 수집 — RSS/Atom/JSON 피드를 받아 AI 에이전트 관련 항목만 걸러 쌓는다.

- 피드 목록: registry/feeds.yaml  (id · issuer · jurisdiction · kind(primary/secondary) · topic · type · url · keywords)
- 저장: snapshots/intel.jsonl — 한 줄 = 한 항목. link 로 중복 제거. 처음 본 시각 first_seen 을 기록.
- 외부 의존 없음: xml.etree + json. 네트워크는 fetch.http_fetch 를 그대로 쓴다(테스트에선 fetcher 를 바꾼다).

"가장 빨리" 의 뜻: 이 모듈은 발행 주체의 피드를 직접 읽는다. 뉴스 집계 사이트를 거치지 않으니
발표와 수집 사이의 지연은 cron 주기 하나뿐이다. 1차(primary) 소스는 kind 로 구분해 먼저 보여 준다.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from .fetch import AGENT_RE, FetchResult, http_fetch, keyword_regex, text_of
from .registry import REGISTRY_DIR, SNAPSHOT_DIR

Fetcher = Callable[[str], FetchResult]

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rss1": "http://purl.org/rss/1.0/",
}


@dataclass
class Item:
    feed_id: str
    title: str
    link: str
    published: str          # ISO 8601 or ""
    summary: str = ""
    matched: list[str] = field(default_factory=list)  # 걸린 키워드
    first_seen: str = ""
    issuer: str = ""
    jurisdiction: str = ""
    kind: str = ""          # primary / secondary
    topic: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


# ── 날짜 ──────────────────────────────────────────────────────────────

def parse_date(s: str | None) -> str:
    """RFC 822 · ISO 8601 · 'YYYY-MM-DD' · 'YYYY.MM.DD' → ISO 8601(UTC). 못 읽으면 ''."""
    if not s:
        return ""
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            d = datetime.strptime(s.replace("Z", "+0000") if fmt.endswith("%z") else s, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    m = re.search(r"(20\d\d)[.\-/](\d{1,2})[.\-/](\d{1,2})", s)
    if m:
        y, mo, d_ = (int(x) for x in m.groups())
        try:
            return datetime(y, mo, d_, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return ""
    return ""


# ── 파서 ──────────────────────────────────────────────────────────────

def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def parse_feed(body: bytes, feed_id: str = "") -> list[Item]:
    """RSS 2.0 · RSS 1.0(RDF) · Atom · JSON Feed. 형식을 못 알아보면 빈 목록."""
    head = body.lstrip()[:200]
    if head.startswith(b"{"):
        return _parse_json_feed(body, feed_id)
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        # BOM·선행 공백·cp949 선언 등을 한 번 더 시도
        try:
            txt = body.decode("utf-8", errors="replace").lstrip("﻿")
            root = ET.fromstring(txt.encode("utf-8"))
        except ET.ParseError:
            return []
    tag = root.tag.lower()
    if tag.endswith("rss") or root.find("channel") is not None:
        return _parse_rss2(root, feed_id)
    if tag.endswith("feed"):
        return _parse_atom(root, feed_id)
    if tag.endswith("rdf"):
        return _parse_rss1(root, feed_id)
    return []


def _parse_rss2(root: ET.Element, feed_id: str) -> list[Item]:
    out: list[Item] = []
    for it in root.iter("item"):
        title = _strip(_text(it.find("title")))
        link = _text(it.find("link")) or _text(it.find("guid"))
        if not link:
            # 일부 한국 사이트: <link/> 비우고 guid 에 URL
            g = it.find("guid")
            link = _text(g)
        pub = _text(it.find("pubDate")) or _text(it.find("dc:date", _NS))
        desc = _strip(_text(it.find("description")) or _text(it.find("content:encoded", _NS)))
        if title or link:
            out.append(Item(feed_id, title, link, parse_date(pub), desc[:600]))
    return out


def _parse_atom(root: ET.Element, feed_id: str) -> list[Item]:
    out: list[Item] = []
    ns = root.tag[1:].split("}")[0] if root.tag.startswith("{") else _NS["atom"]
    q = lambda t: f"{{{ns}}}{t}"  # noqa: E731
    for e in root.findall(q("entry")):
        title = _strip(_text(e.find(q("title"))))
        link = ""
        for l in e.findall(q("link")):
            rel = l.get("rel", "alternate")
            if rel == "alternate" and l.get("href"):
                link = l.get("href", "")
                break
        if not link:
            l0 = e.find(q("link"))
            link = (l0.get("href", "") if l0 is not None else "") or _text(e.find(q("id")))
        pub = _text(e.find(q("published"))) or _text(e.find(q("updated")))
        desc = _strip(_text(e.find(q("summary"))) or _text(e.find(q("content"))))
        if title or link:
            out.append(Item(feed_id, title, link, parse_date(pub), desc[:600]))
    return out


def _parse_rss1(root: ET.Element, feed_id: str) -> list[Item]:
    out: list[Item] = []
    for it in root.iter(f"{{{_NS['rss1']}}}item"):
        title = _strip(_text(it.find(f"{{{_NS['rss1']}}}title")))
        link = _text(it.find(f"{{{_NS['rss1']}}}link")) or it.get(f"{{{_NS['rdf']}}}about", "")
        pub = _text(it.find("dc:date", _NS))
        desc = _strip(_text(it.find(f"{{{_NS['rss1']}}}description")))
        if title or link:
            out.append(Item(feed_id, title, link, parse_date(pub), desc[:600]))
    return out


def _parse_json_feed(body: bytes, feed_id: str) -> list[Item]:
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    out: list[Item] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        title = _strip(str(it.get("title", "")))
        link = str(it.get("url") or it.get("external_url") or it.get("id") or "")
        pub = str(it.get("date_published") or it.get("date_modified") or "")
        desc = _strip(str(it.get("summary") or it.get("content_text") or it.get("content_html") or ""))
        if title or link:
            out.append(Item(feed_id, title, link, parse_date(pub), desc[:600]))
    return out


# ── 필터 · 저장 ──────────────────────────────────────────────────────

def match_keywords(item: Item, pattern: re.Pattern[str]) -> list[str]:
    """제목+요약에서 걸린 키워드(소문자, 중복 제거)."""
    hay = f"{item.title} {item.summary}"
    return sorted({m.group(0).lower() for m in pattern.finditer(hay)})


def load_feeds(registry_dir: Path = REGISTRY_DIR) -> list[dict[str, Any]]:
    p = registry_dir / "feeds.yaml"
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return list(data.get("feeds") or [])


def load_items(snapshot_dir: Path = SNAPSHOT_DIR) -> list[Item]:
    p = snapshot_dir / "intel.jsonl"
    if not p.exists():
        return []
    out: list[Item] = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            out.append(Item(**{k: d.get(k, "" if k not in ("matched",) else []) for k in Item.__dataclass_fields__}))
    return out


def append_items(items: list[Item], snapshot_dir: Path = SNAPSHOT_DIR) -> None:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    with (snapshot_dir / "intel.jsonl").open("a", encoding="utf-8") as f:
        for it in items:
            f.write(it.to_json() + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── 커스텀 API 어댑터 ─────────────────────────────────────────────────
# JSON Feed 가 아닌 공공 API 를 피드처럼 읽는다. feeds.yaml 의 `adapter:` 로 고른다.
# 각 어댑터 = (요청 만들기, 응답 → Item 목록). 2026-11-11 실측한 응답 모양 기준.

def _request_for(feed: dict[str, Any], today: datetime) -> tuple[str, dict[str, Any]]:
    """(url, fetcher kwargs). NVD 는 최근 90일 창을 붙이고, 금보원은 POST 본문을 만든다."""
    url = feed["url"]
    ad = feed.get("adapter")
    if ad == "nvd":
        # NVD 기본 정렬은 오래된 순 — 최근 공개 창을 지정해야 새 CVE 를 본다(최대 120일).
        import urllib.parse as up
        parts = up.urlsplit(url)
        q = [(k, v) for k, v in up.parse_qsl(parts.query, keep_blank_values=True)
             if k not in ("pubStartDate", "pubEndDate")]
        start = (today - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00.000")
        end = today.strftime("%Y-%m-%dT23:59:59.999")
        q += [("pubStartDate", start), ("pubEndDate", end)]
        url = up.urlunsplit((parts.scheme, parts.netloc, parts.path, up.urlencode(q), ""))
        return url, {}
    if ad == "fsi_bbs":
        body = json.dumps({"menuNo": str(feed.get("menu_no", "69")),
                           "pagingSearchDto": {"page": 1, "pageSize": 20, "searchContents": "", "searchType": ""}})
        return url, {"method": "POST", "body": body.encode("utf-8"),
                     "headers": {"Content-Type": "application/json", "Accept": "application/json"}}
    return url, {}


def _jload(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def parse_adapter(adapter: str, body: bytes, feed_id: str, feed: dict[str, Any] | None = None) -> list[Item]:
    d = _jload(body)
    if d is None:
        return []
    out: list[Item] = []
    if adapter == "kev":
        for v in d.get("vulnerabilities") or []:
            cve = v.get("cveID", "")
            title = f"{cve} · {v.get('vendorProject', '')} {v.get('product', '')} — {v.get('vulnerabilityName', '')}".strip()
            out.append(Item(feed_id, title, f"https://nvd.nist.gov/vuln/detail/{cve}",
                            parse_date(v.get("dateAdded")), _strip(v.get("shortDescription", ""))[:600]))
    elif adapter == "nvd":
        for v in d.get("vulnerabilities") or []:
            c = v.get("cve") or {}
            desc = next((x.get("value", "") for x in c.get("descriptions", []) if x.get("lang") == "en"), "")
            cid = c.get("id", "")
            out.append(Item(feed_id, f"{cid} — {desc[:120]}", f"https://nvd.nist.gov/vuln/detail/{cid}",
                            parse_date((c.get("published") or "")[:19]), desc[:600]))
    elif adapter == "federalregister":
        for r in d.get("results") or []:
            out.append(Item(feed_id, _strip(r.get("title", "")), r.get("html_url", ""),
                            parse_date(r.get("publication_date")), _strip(r.get("abstract") or "")[:600]))
    elif adapter == "assembly":
        # {서비스ID: [{head:[...]}, {row:[...]}]}
        blocks = next(iter(d.values()), []) if isinstance(d, dict) else []
        rows: list[dict[str, Any]] = []
        for b in blocks if isinstance(blocks, list) else []:
            if isinstance(b, dict) and "row" in b:
                rows = b["row"] or []
        for r in rows:
            name = r.get("BILL_NAME", "")
            res = r.get("PROC_RESULT") or "계류"
            summary = " · ".join(x for x in (r.get("COMMITTEE"), r.get("PROPOSER"), res) if x)
            out.append(Item(feed_id, f"{name} ({res})", r.get("DETAIL_LINK", ""),
                            parse_date(r.get("PROPOSE_DT")), summary))
    elif adapter == "fsi_bbs":
        menu = str((feed or {}).get("menu_no", "69"))
        for r in d.get("resultData") or []:
            no = r.get("bbsNo")
            out.append(Item(feed_id, _strip(html_unescape(r.get("title", ""))),
                            f"https://www.fsec.or.kr/bbs/detail?menuNo={menu}&bbsNo={no}",
                            parse_date(r.get("regDate")), _strip(html_unescape(r.get("contents") or ""))[:600]))
    return out


def html_unescape(s: str) -> str:
    import html as _h
    return _h.unescape(s or "")


def collect(
    feeds: list[dict[str, Any]],
    known: list[Item],
    fetcher: Fetcher = http_fetch,
    only_matching: bool = True,
    now: str | None = None,
) -> tuple[list[Item], list[dict[str, Any]]]:
    """피드를 전부 받아 새 항목(known 에 없는 link)만 돌려준다. 두 번째 값은 피드별 상태."""
    seen = {it.link for it in known if it.link}
    new: list[Item] = []
    status: list[dict[str, Any]] = []
    ts = now or _now()
    try:
        today_dt = datetime.strptime(ts[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        today_dt = datetime.now(timezone.utc)
    for feed in feeds:
        fid, url = feed["id"], feed["url"]
        if feed.get("enabled") is False:
            status.append({"id": fid, "url": url, "status": "disabled"})
            continue
        req_url, kw = _request_for(feed, today_dt)
        res = fetcher(req_url, **kw) if kw else fetcher(req_url)
        st: dict[str, Any] = {"id": fid, "url": url, "http_status": res.status, "parsed": 0, "new": 0, "matched": 0}
        if res.status != 200 or not res.body:
            st["error"] = res.error or f"HTTP {res.status}"
            status.append(st)
            continue
        ad = feed.get("adapter")
        items = parse_adapter(ad, res.body, fid, feed) if ad else parse_feed(res.body, fid)
        if not items and feed.get("type") == "html":
            # HTML 목록은 fetch.extract_links 로 — intel 은 피드만 다룬다
            st["error"] = "html list — use `watch`"
        st["parsed"] = len(items)
        pattern = keyword_regex(feed.get("keywords")) if feed.get("keywords") else AGENT_RE
        for it in items:
            it.issuer = feed.get("issuer", "")
            it.jurisdiction = feed.get("jurisdiction", "")
            it.kind = feed.get("kind", "")
            it.topic = feed.get("topic", "")
            it.matched = match_keywords(it, pattern)
            if it.matched:
                st["matched"] += 1
            if only_matching and not it.matched and not feed.get("keep_all"):
                continue
            if not it.link or it.link in seen:
                continue
            seen.add(it.link)
            it.first_seen = ts
            new.append(it)
            st["new"] += 1
        status.append(st)
    # 1차 먼저, 각 그룹 안에서는 최신순 (안정 정렬 두 번)
    new.sort(key=lambda i: i.published, reverse=True)
    new.sort(key=lambda i: i.kind != "primary")
    return new, status


def render_new(new: list[Item], status: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    prim = [i for i in new if i.kind == "primary"]
    sec = [i for i in new if i.kind != "primary"]
    for label, group in (("1차 (발행 주체)", prim), ("2차 (매체·분석)", sec)):
        if not group:
            continue
        lines.append(f"## {label} — 새 항목 {len(group)}")
        for it in sorted(group, key=lambda i: i.published, reverse=True):
            d = it.published[:10] if it.published else "날짜 없음"
            kw = ", ".join(it.matched[:4])
            lines.append(f"- {d} · {it.issuer} · {it.title}  <{it.link}>  [{kw}]")
        lines.append("")
    bad = [s for s in status if s.get("error")]
    if bad:
        lines.append(f"## 실패 {len(bad)}")
        for s in bad:
            lines.append(f"- `{s['id']}` {s.get('error')}  {s['url']}")
        lines.append("")
    ok = [s for s in status if not s.get("error") and s.get("status") != "disabled"]
    lines.append(f"피드 {len(status)} · 정상 {len(ok)} · 파싱 {sum(s.get('parsed', 0) for s in ok)} · 키워드 일치 {sum(s.get('matched', 0) for s in ok)} · 새 항목 {len(new)}")
    return "\n".join(lines) + "\n"


def text_mentions(body: bytes, content_type: str = "") -> int:
    """본문에서 에이전트 언급 수 — fetch.text_of 재사용 (HTML/텍스트만)."""
    return len(AGENT_RE.findall(text_of(body, content_type)))
