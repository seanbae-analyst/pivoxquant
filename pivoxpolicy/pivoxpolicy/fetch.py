"""문서 URL·발표 목록 페이지 스냅숏과 변경 감지.

snapshots/manifest.json 에 id 별 {url, sha256, bytes, fetched_at, status, agent_mentions, links}
를 기록한다. 본문은 snapshots/content/ 에 저장하되 git 에는 올리지 않는다(.gitignore).

네트워크를 쓰는 함수는 `fetcher` 인자를 받아 테스트에서 가짜로 바꿀 수 있다.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .registry import SNAPSHOT_DIR

USER_AGENT = "Mozilla/5.0 (compatible; pivoxpolicy/0.1; research snapshot)"
AGENT_RE = re.compile(r"(?i)\bagentic\b|\bai agents?\b|에이전트")
TAG_RE = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.S)
LINK_RE = re.compile(r"""<a\s[^>]*?href=["']([^"'#]+)["'][^>]*>(.*?)</a>""", re.S | re.I)
WS_RE = re.compile(r"\s+")


@dataclass
class FetchResult:
    status: int
    body: bytes
    content_type: str = ""
    error: str | None = None


Fetcher = Callable[[str], FetchResult]


def iri_to_uri(url: str) -> str:
    """한글 경로(law.go.kr 등)를 퍼센트 인코딩. 이미 인코딩된 부분은 그대로."""
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path, safe="/%:@!$&'()*+,;=-._~")
    query = urllib.parse.quote(parts.query, safe="=&%?/:@!$'()*+,;-._~")
    host = parts.netloc.encode("idna").decode("ascii")
    return urllib.parse.urlunsplit((parts.scheme, host, path, query, parts.fragment))


def http_fetch(url: str, timeout: int = 30) -> FetchResult:
    req = urllib.request.Request(iri_to_uri(url), headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — 레지스트리의 http(s) URL 만
            return FetchResult(resp.status, resp.read(), resp.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as e:
        return FetchResult(e.code, e.read() if e.fp else b"", error=str(e))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        return FetchResult(0, b"", error=str(e))


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def text_of(body: bytes, content_type: str = "") -> str:
    """HTML 이면 태그를 벗긴 텍스트, PDF 등 바이너리면 빈 문자열."""
    if b"%PDF" in body[:8]:
        return ""
    for enc in ("utf-8", "cp949", "latin-1"):
        try:
            s = body.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return ""
    if "<" not in s:
        return s
    s = TAG_RE.sub(" ", s)
    s = html.unescape(s)
    return WS_RE.sub(" ", s).strip()


def agent_mentions(text: str) -> int:
    return len(AGENT_RE.findall(text))


def extract_links(body: bytes, base_url: str, keyword_re: re.Pattern[str] | None = None) -> list[dict[str, str]]:
    """목록 페이지의 링크 (절대 URL, 앵커 텍스트). keyword_re 가 있으면 텍스트가 맞는 것만."""
    try:
        s = body.decode("utf-8", errors="replace")
    except Exception:  # pragma: no cover
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for href, inner in LINK_RE.findall(s):
        text = WS_RE.sub(" ", html.unescape(TAG_RE.sub(" ", inner))).strip()
        if not text:
            continue
        if keyword_re and not keyword_re.search(text):
            continue
        absu = urllib.parse.urljoin(base_url, html.unescape(href))
        if absu in seen:
            continue
        seen.add(absu)
        out.append({"url": absu, "text": text[:200]})
    return out


def keyword_regex(keywords: list[str] | None) -> re.Pattern[str]:
    """키워드 목록 → 정규식. 짧은 ASCII 키워드('AI')는 단어 경계를 붙여 'Daily'·'Mailing' 을 안 잡는다.
    한글 키워드는 복합어 안에서도 잡히도록 경계를 안 붙인다('금융보안원' ⊃ '보안')."""
    if not keywords:
        return AGENT_RE
    parts = []
    for k in keywords:
        e = re.escape(k)
        if k.isascii() and len(k) <= 4:
            e = rf"\b{e}\b"
        parts.append(e)
    return re.compile("|".join(parts), re.I)


def load_manifest(snapshot_dir: Path = SNAPSHOT_DIR) -> dict[str, Any]:
    p = snapshot_dir / "manifest.json"
    if not p.exists():
        return {"documents": {}, "sources": {}}
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def save_manifest(manifest: dict[str, Any], snapshot_dir: Path = SNAPSHOT_DIR) -> None:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    with (snapshot_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ext(content_type: str, url: str) -> str:
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        return "pdf"
    if "json" in content_type or url.lower().endswith(".json"):
        return "json"
    return "html"


def snapshot_documents(
    docs: dict[str, Any],
    manifest: dict[str, Any],
    fetcher: Fetcher = http_fetch,
    snapshot_dir: Path = SNAPSHOT_DIR,
    only: set[str] | None = None,
) -> list[dict[str, Any]]:
    """url 이 있는 문서를 받아 매니페스트를 갱신. 변경 요약 목록을 돌려준다."""
    content_dir = snapshot_dir / "content"
    content_dir.mkdir(parents=True, exist_ok=True)
    events: list[dict[str, Any]] = []
    for doc_id, doc in sorted(docs.items()):
        if only and doc_id not in only:
            continue
        url = getattr(doc, "url", None)
        if not url:
            continue
        res = fetcher(url)
        prev = manifest["documents"].get(doc_id, {})
        entry: dict[str, Any] = {
            "url": url,
            "fetched_at": _now(),
            "status": res.status,
        }
        if res.error:
            entry["error"] = res.error
        if res.status == 200 and res.body:
            digest = sha256(res.body)
            text = text_of(res.body, res.content_type)
            entry.update(
                sha256=digest,
                bytes=len(res.body),
                content_type=res.content_type.split(";")[0].strip(),
                agent_mentions=agent_mentions(text),
            )
            (content_dir / f"{doc_id}.{_ext(res.content_type, url)}").write_bytes(res.body)
            if prev.get("sha256") and prev["sha256"] != digest:
                entry["previous_sha256"] = prev["sha256"]
                entry["changed_at"] = entry["fetched_at"]
                events.append({"id": doc_id, "kind": "changed", "url": url,
                               "agent_mentions": (prev.get("agent_mentions"), entry["agent_mentions"])})
            elif not prev.get("sha256"):
                events.append({"id": doc_id, "kind": "first_snapshot", "url": url,
                               "agent_mentions": entry["agent_mentions"]})
            else:
                entry["changed_at"] = prev.get("changed_at")
                entry["first_seen"] = prev.get("first_seen")
        else:
            # 실패해도 이전 해시는 보존
            for k in ("sha256", "bytes", "content_type", "agent_mentions", "changed_at", "first_seen"):
                if k in prev:
                    entry[k] = prev[k]
            events.append({"id": doc_id, "kind": "fetch_failed", "url": url, "status": res.status, "error": res.error})
        entry.setdefault("first_seen", prev.get("first_seen") or entry["fetched_at"])
        manifest["documents"][doc_id] = entry
    return events


def watch_sources(
    sources: list[dict[str, Any]],
    manifest: dict[str, Any],
    fetcher: Fetcher = http_fetch,
    snapshot_dir: Path = SNAPSHOT_DIR,
) -> list[dict[str, Any]]:
    """발표 목록 페이지에서 키워드가 든 링크를 뽑아 이전과 비교. 새 링크를 이벤트로 돌려준다."""
    content_dir = snapshot_dir / "content"
    content_dir.mkdir(parents=True, exist_ok=True)
    events: list[dict[str, Any]] = []
    for src in sources:
        sid, url = src["id"], src["url"]
        kw_re = keyword_regex(src.get("keywords"))
        res = fetcher(url)
        prev = manifest["sources"].get(sid, {})
        entry: dict[str, Any] = {"url": url, "fetched_at": _now(), "status": res.status, "issuer": src.get("issuer")}
        if res.error:
            entry["error"] = res.error
        if res.status == 200 and res.body:
            links = extract_links(res.body, url, kw_re)
            (content_dir / f"source-{sid}.html").write_bytes(res.body)
            prev_urls = {l["url"] for l in prev.get("links", [])}
            new_links = [l for l in links if l["url"] not in prev_urls]
            entry["links"] = links
            entry["sha256"] = sha256(res.body)
            if prev.get("links") is not None and new_links:
                events.append({"id": sid, "kind": "new_links", "url": url, "links": new_links})
            elif prev.get("links") is None:
                events.append({"id": sid, "kind": "first_snapshot", "url": url, "n_links": len(links)})
        else:
            entry["links"] = prev.get("links", [])
            events.append({"id": sid, "kind": "fetch_failed", "url": url, "status": res.status, "error": res.error})
        entry["first_seen"] = prev.get("first_seen") or entry["fetched_at"]
        manifest["sources"][sid] = entry
    return events


def render_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "변경 없음.\n"
    lines = []
    for e in events:
        k = e["kind"]
        if k == "changed":
            a, b = e["agent_mentions"]
            lines.append(f"- 변경  `{e['id']}` — 에이전트 언급 {a} → {b}  {e['url']}")
        elif k == "first_snapshot":
            n = e.get("agent_mentions", e.get("n_links"))
            lines.append(f"- 첫 스냅숏  `{e['id']}` — {n}  {e['url']}")
        elif k == "new_links":
            lines.append(f"- 새 글 {len(e['links'])}건  `{e['id']}`  {e['url']}")
            for l in e["links"][:20]:
                lines.append(f"    - {l['text']}  <{l['url']}>")
        elif k == "fetch_failed":
            lines.append(f"- 실패  `{e['id']}` — HTTP {e.get('status')} {e.get('error') or ''}  {e['url']}")
    return "\n".join(lines) + "\n"
