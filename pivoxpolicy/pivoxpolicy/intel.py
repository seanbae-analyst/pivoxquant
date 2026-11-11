"""빠른 동향 수집 — RSS/Atom/JSON 피드를 받아 AI 에이전트 관련 항목만 걸러 쌓는다.

- 피드 목록: registry/feeds.yaml  (id · issuer · jurisdiction · kind(primary/secondary) · topic · type · url · keywords)
- 저장: snapshots/intel.jsonl — 한 줄 = 한 항목. link 로 중복 제거. 처음 본 시각 first_seen 을 기록.
- 외부 의존 없음: xml.etree + json. 네트워크는 fetch.http_fetch 를 그대로 쓴다(테스트에선 fetcher 를 바꾼다).

"가장 빨리" 의 뜻: 이 모듈은 발행 주체의 피드를 직접 읽는다. 뉴스 집계 사이트를 거치지 않으니
발표와 수집 사이의 지연은 cron 주기 하나뿐이다. 1차(primary) 소스는 kind 로 구분해 먼저 보여 준다.
"""

from __future__ import annotations

import html
import html.entities
import json
import re
import sys
import urllib.parse
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

# 이메일 날짜 파서가 모르는 시간대 약어 (모르면 UTC 로 읽어 9시간 틀린다 — 자정 근처면 날짜가 바뀐다)
_TZ_ABBR = {"KST": "+0900", "JST": "+0900", "CET": "+0100", "CEST": "+0200", "SGT": "+0800", "HKT": "+0800"}
_TZ_RE = re.compile(r"\b(" + "|".join(_TZ_ABBR) + r")\s*$")
_KO_DATE = re.compile(r"(20\d\d)\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")


def _iso_utc(d: datetime) -> str:
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_date(s: str | None) -> str:
    """RFC 822 · ISO 8601 · 'YYYY-MM-DD' · 'YYYY.MM.DD' · '2026년 11월 5일' → ISO 8601(UTC). 못 읽으면 ''."""
    if not s or not isinstance(s, str):
        return ""
    s = s.strip()
    s_tz = _TZ_RE.sub(lambda m: _TZ_ABBR[m.group(1)], s)
    try:
        return _iso_utc(parsedate_to_datetime(s_tz))
    except (TypeError, ValueError, IndexError):
        pass
    iso = s.replace("Z", "+00:00") if s.endswith("Z") else s
    # 나노초 등 6자리 넘는 소수 초는 잘라 fromisoformat 이 읽게 한다
    iso = re.sub(r"(\.\d{6})\d+", r"\1", iso)
    try:
        return _iso_utc(datetime.fromisoformat(iso))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M",
                "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y.%m.%d", "%Y/%m/%d", "%Y%m%d",
                "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y", "%a, %d %b %Y"):
        try:
            return _iso_utc(datetime.strptime(iso, fmt))
        except ValueError:
            continue
    m = _KO_DATE.search(s)
    if m:
        y, mo, d_ = (int(x) for x in m.groups())
        try:
            return _iso_utc(datetime(y, mo, d_))
        except ValueError:
            return ""
    return ""


# ── 파서 ──────────────────────────────────────────────────────────────

def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    # itertext — Atom type="xhtml" 처럼 자식 요소 안에 글이 있어도 읽는다
    return "".join(el.itertext()).strip()


def _strip(s: str | None) -> str:
    """태그 제거 → 엔티티 풀기(이중 이스케이프된 &amp;rsquo; 도) → 공백 정리."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _abs(link: str, base: str = "") -> str:
    """링크를 절대 http(s) URL 로. 상대 경로는 base(xml:base·피드 URL)로 푼다. http(s) 가 아니면 ''.
    링크가 dedup 열쇠라 '/news/1' · guid '12345' 같은 값은 다른 피드의 항목과 부딪힌다."""
    link = (link or "").strip()
    if not link:
        return ""
    if base:
        link = urllib.parse.urljoin(base, link)
    return link if urllib.parse.urlsplit(link).scheme in ("http", "https") else ""


class FeedParseError(ValueError):
    pass


_XML_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}
_ENTITY_RE = re.compile(r"&([A-Za-z][A-Za-z0-9]*);")
_ENC_RE = re.compile(rb"""^<\?xml[^>]*?encoding\s*=\s*["']([A-Za-z0-9._\-]+)["']""")


def _fix_entity(m: re.Match[str]) -> str:
    name = m.group(1)
    if name in _XML_ENTITIES:
        return m.group(0)
    cp = html.entities.name2codepoint.get(name)
    return f"&#{cp};" if cp else f"&amp;{name};"


def _xml_text(body: bytes) -> str:
    """XML 바이트 → 선언 없는 글. 선언된 인코딩(euc-kr · cp949 포함)으로 풀고, HTML 엔티티(&nbsp;)를 숫자로."""
    m = _ENC_RE.match(body)
    tried = [m.group(1).decode("ascii")] if m else []
    txt = None
    for enc in tried + ["utf-8", "cp949"]:
        try:
            txt = body.decode(enc)
            break
        except (LookupError, UnicodeDecodeError):
            continue
    if txt is None:
        txt = body.decode("utf-8", errors="replace")
    txt = re.sub(r"^\s*<\?xml[^>]*\?>", "", txt.lstrip("\ufeff"))
    return _ENTITY_RE.sub(_fix_entity, txt)


def _clean_body(body: bytes) -> bytes:
    if body.startswith(b"\xef\xbb\xbf"):
        body = body[3:]
    return body.lstrip()


def parse_feed_strict(body: bytes, feed_id: str = "", base_url: str = "") -> list[Item]:
    """parse_feed 와 같되 못 읽으면 FeedParseError — collect 가 그 피드를 '실패' 로 적는다."""
    body = _clean_body(body or b"")
    if body.startswith(b"{"):
        return _parse_json_feed(body, feed_id, base_url)
    try:
        root = ET.fromstring(body)
    except (ET.ParseError, ValueError):
        # ValueError = expat 이 다중 바이트 선언(euc-kr)을 거부. ParseError = &nbsp; 같은 HTML 엔티티 등.
        try:
            root = ET.fromstring(_xml_text(body))
        except ET.ParseError as e:
            raise FeedParseError(f"XML 파싱 실패: {e}") from None
    tag = root.tag.lower()
    if tag.endswith("rss") or root.find("channel") is not None:
        return _parse_rss2(root, feed_id, base_url)
    if tag.endswith("feed"):
        return _parse_atom(root, feed_id, base_url)
    if tag.endswith("rdf"):
        return _parse_rss1(root, feed_id, base_url)
    raise FeedParseError(f"피드 형식 아님 (루트 {root.tag})")


def parse_feed(body: bytes, feed_id: str = "", base_url: str = "") -> list[Item]:
    """RSS 2.0 · RSS 1.0(RDF) · Atom · JSON Feed. 형식을 못 알아보면 빈 목록."""
    try:
        return parse_feed_strict(body, feed_id, base_url)
    except FeedParseError:
        return []


def _parse_rss2(root: ET.Element, feed_id: str, base_url: str = "") -> list[Item]:
    out: list[Item] = []
    for it in root.iter("item"):
        title = _strip(_text(it.find("title")))
        link = _abs(_text(it.find("link")), base_url)
        if not link:
            # 일부 한국 사이트: <link/> 비우고 guid 에 URL. isPermaLink="false" 인 guid 는 URL 이 아니다.
            g = it.find("guid")
            if g is not None and (g.get("isPermaLink") or "true").lower() != "false":
                link = _abs(_text(g), base_url)
        pub = _text(it.find("pubDate")) or _text(it.find("dc:date", _NS))
        desc = _strip(_text(it.find("description")) or _text(it.find("content:encoded", _NS)))
        if title or link:
            out.append(Item(feed_id, title, link, parse_date(pub), desc[:600]))
    return out


_XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"


def _parse_atom(root: ET.Element, feed_id: str, base_url: str = "") -> list[Item]:
    out: list[Item] = []
    ns = root.tag[1:].split("}")[0] if root.tag.startswith("{") else _NS["atom"]
    q = lambda t: f"{{{ns}}}{t}"  # noqa: E731
    feed_base = urllib.parse.urljoin(base_url, root.get(_XML_BASE, "")) if base_url or root.get(_XML_BASE) else ""
    for e in root.findall(q("entry")):
        base = urllib.parse.urljoin(feed_base, e.get(_XML_BASE, "")) if feed_base or e.get(_XML_BASE) else ""
        title = _strip(_text(e.find(q("title"))))
        link = ""
        for l in e.findall(q("link")):
            rel = l.get("rel", "alternate")
            if rel == "alternate" and l.get("href"):
                link = _abs(l.get("href", ""), base)
                break
        if not link:
            l0 = e.find(q("link"))
            link = _abs(l0.get("href", "") if l0 is not None else "", base) or _abs(_text(e.find(q("id"))))
        pub = _text(e.find(q("published"))) or _text(e.find(q("updated")))
        desc = _strip(_text(e.find(q("summary"))) or _text(e.find(q("content"))))
        if title or link:
            out.append(Item(feed_id, title, link, parse_date(pub), desc[:600]))
    return out


def _parse_rss1(root: ET.Element, feed_id: str, base_url: str = "") -> list[Item]:
    out: list[Item] = []
    for it in root.iter(f"{{{_NS['rss1']}}}item"):
        title = _strip(_text(it.find(f"{{{_NS['rss1']}}}title")))
        link = _abs(_text(it.find(f"{{{_NS['rss1']}}}link")) or it.get(f"{{{_NS['rdf']}}}about", ""), base_url)
        pub = _text(it.find("dc:date", _NS))
        desc = _strip(_text(it.find(f"{{{_NS['rss1']}}}description")))
        if title or link:
            out.append(Item(feed_id, title, link, parse_date(pub), desc[:600]))
    return out


def _parse_json_feed(body: bytes, feed_id: str, base_url: str = "") -> list[Item]:
    data = _jload(body)
    if data is None:
        raise FeedParseError("JSON 파싱 실패")
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise FeedParseError("JSON Feed 아님 (items 배열 없음)")
    out: list[Item] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        title = _strip(_s(it.get("title")))
        # id 는 URL 일 때만 링크로 쓴다 (JSON Feed 명세상 id 는 아무 문자열이나 된다)
        link = _abs(_s(it.get("url") or it.get("external_url")), base_url) or _abs(_s(it.get("id")))
        pub = _s(it.get("date_published") or it.get("date_modified"))
        desc = _strip(_s(it.get("summary") or it.get("content_text") or it.get("content_html")))
        if title or link:
            out.append(Item(feed_id, title, link, parse_date(pub), desc[:600]))
    return out


def _s(v: Any) -> str:
    """API 값 → 글. null 은 '' (str(None) = 'None' 이 제목이 되던 것)."""
    return "" if v is None else str(v)


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
    bad = 0
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                bad += 1  # 쓰다 끊긴 마지막 줄 등 — 한 줄 때문에 수집·대시보드가 통째로 멈추면 안 된다
                continue
            if not isinstance(d, dict):
                bad += 1
                continue
            out.append(Item(**{k: d.get(k, "" if k not in ("matched",) else []) for k in Item.__dataclass_fields__}))
    if bad:
        print(f"intel.jsonl: 읽지 못한 줄 {bad}개 건너뜀", file=sys.stderr)
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
        return json.loads((body or b"").decode("utf-8-sig", errors="replace"))
    except json.JSONDecodeError:
        return None


def _rows(v: Any) -> list[dict[str, Any]]:
    """API 의 목록 값 → dict 행만. null · 문자열 · 섞인 null 은 건너뛴다."""
    return [r for r in v if isinstance(r, dict)] if isinstance(v, list) else []


# KEV 항목 링크는 NVD 상세 페이지 + '#cisa-kev'. NVD 피드와 같은 URL 이면 전역 dedup 에 먹혀
# 'NVD 에서 먼저 본 CVE 가 나중에 KEV(실제 악용)에 오른' 신호가 사라진다. 조각만 달라 같은 페이지로 간다.
KEV_LINK = "https://nvd.nist.gov/vuln/detail/{cve}#cisa-kev"


def parse_adapter(adapter: str, body: bytes, feed_id: str, feed: dict[str, Any] | None = None) -> list[Item]:
    d = _jload(body)
    if not isinstance(d, dict):
        raise FeedParseError(f"{adapter}: JSON 객체 아님")
    out: list[Item] = []
    if adapter == "kev":
        for v in _rows(d.get("vulnerabilities")):
            cve = _s(v.get("cveID")).strip()
            if not cve:
                continue
            what = " ".join(x for x in (_s(v.get("vendorProject")).strip(), _s(v.get("product")).strip()) if x)
            name = _s(v.get("vulnerabilityName")).strip()
            title = " — ".join(x for x in (" · ".join(x for x in (cve, what) if x), name) if x)
            out.append(Item(feed_id, title, KEV_LINK.format(cve=cve),
                            parse_date(_s(v.get("dateAdded"))), _strip(_s(v.get("shortDescription")))[:600]))
    elif adapter == "nvd":
        for v in _rows(d.get("vulnerabilities")):
            c = v.get("cve") if isinstance(v.get("cve"), dict) else {}
            cid = _s(c.get("id")).strip()
            if not cid:
                continue
            desc = next((_s(x.get("value")) for x in _rows(c.get("descriptions")) if x.get("lang") == "en"), "")
            out.append(Item(feed_id, f"{cid} — {desc[:120]}", f"https://nvd.nist.gov/vuln/detail/{cid}",
                            parse_date(_s(c.get("published"))[:19]), desc[:600]))
    elif adapter == "federalregister":
        for r in _rows(d.get("results")):
            link = _abs(_s(r.get("html_url")))
            title = _strip(_s(r.get("title")))
            if link and title:
                out.append(Item(feed_id, title, link,
                                parse_date(_s(r.get("publication_date"))), _strip(_s(r.get("abstract")))[:600]))
    elif adapter == "assembly":
        # {서비스ID: [{head:[...]}, {row:[...]}]}
        blocks = next(iter(d.values()), [])
        rows: list[dict[str, Any]] = []
        for b in blocks if isinstance(blocks, list) else []:
            if isinstance(b, dict) and "row" in b:
                rows = _rows(b["row"])
        for r in rows:
            name = _strip(_s(r.get("BILL_NAME")))
            link = _abs(_s(r.get("DETAIL_LINK")))
            if not name or not link:
                continue
            res = _s(r.get("PROC_RESULT")) or "계류"
            summary = " · ".join(x for x in (_s(r.get("COMMITTEE")), _s(r.get("PROPOSER")), res) if x)
            out.append(Item(feed_id, f"{name} ({res})", link, parse_date(_s(r.get("PROPOSE_DT"))), summary))
    elif adapter == "fsi_bbs":
        menu = str((feed or {}).get("menu_no", "69"))
        for r in _rows(d.get("resultData")):
            no = _s(r.get("bbsNo")).strip()
            if not no:  # 번호 없는 글이 전부 '…bbsNo=None' 하나로 합쳐지던 것
                continue
            out.append(Item(feed_id, _strip(_s(r.get("title"))),
                            f"https://www.fsec.or.kr/bbs/detail?menuNo={menu}&bbsNo={urllib.parse.quote(no)}",
                            parse_date(_s(r.get("regDate"))), _strip(_s(r.get("contents")))[:600]))
    else:
        raise FeedParseError(f"모르는 어댑터: {adapter}")
    return out


def html_unescape(s: str) -> str:
    return html.unescape(s or "")


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
        st: dict[str, Any] = {"id": fid, "url": url, "http_status": None, "parsed": 0, "new": 0, "matched": 0}
        # 피드 하나의 실패(네트워크 · 이상한 응답)가 수집 전체를 멈추면 안 된다 — 그 피드만 '실패' 로 적는다.
        try:
            req_url, kw = _request_for(feed, today_dt)
            res = fetcher(req_url, **kw) if kw else fetcher(req_url)
        except Exception as e:  # noqa: BLE001
            st["error"] = f"fetch: {type(e).__name__}: {e}"[:200]
            status.append(st)
            continue
        st["http_status"] = res.status
        if res.status != 200 or not res.body:
            st["error"] = res.error or f"HTTP {res.status}"
            status.append(st)
            continue
        ad = feed.get("adapter")
        try:
            items = parse_adapter(ad, res.body, fid, feed) if ad else parse_feed_strict(res.body, fid, url)
        except Exception as e:  # noqa: BLE001 — FeedParseError 와 예상 못 한 모양 모두
            st["error"] = ("html list — use `watch`" if feed.get("type") == "html"
                           else f"parse: {type(e).__name__}: {e}"[:200])
            status.append(st)
            continue
        if not items:
            # 형식은 읽었는데 0건 — 빈 피드일 수도, 모양이 바뀐 것일 수도. '정상' 에 섞지 않는다.
            st["warning"] = "0건 — 피드가 비었거나 형식이 바뀜"
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
    empty = [s for s in status if s.get("warning") and not s.get("error")]
    if empty:
        lines.append(f"## 0건 {len(empty)}")
        for s in empty:
            lines.append(f"- `{s['id']}` {s['warning']}  {s['url']}")
        lines.append("")
    ok = [s for s in status if not s.get("error") and not s.get("warning") and s.get("status") != "disabled"]
    lines.append(f"피드 {len(status)} · 정상 {len(ok)} · 0건 {len(empty)} · 파싱 {sum(s.get('parsed', 0) for s in ok)} · 키워드 일치 {sum(s.get('matched', 0) for s in ok)} · 새 항목 {len(new)}")
    return "\n".join(lines) + "\n"


def text_mentions(body: bytes, content_type: str = "") -> int:
    """본문에서 에이전트 언급 수 — fetch.text_of 재사용 (HTML/텍스트만)."""
    return len(AGENT_RE.findall(text_of(body, content_type)))
