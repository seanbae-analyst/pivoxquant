"""사건 코딩용 고정 코퍼스 — incidents.yaml 의 source_url 을 받아 본문 텍스트로.

두 코더가 같은 글을 읽게 하려고 한 번 받아 고정한다. 본문은 저작권 때문에 git 에 넣지 않고(snapshots/incident_content/),
snapshots/incident_corpus.json 에 사건별 출처·받은 시각·글자 수·sha256(본문 텍스트) 만 남긴다.
같은 해시가 나오면 같은 원문을 읽은 것이다.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .fetch import http_fetch
from .registry import SNAPSHOT_DIR

CONTENT_DIR = SNAPSHOT_DIR / "incident_content"
MANIFEST = SNAPSHOT_DIR / "incident_corpus.json"
# 브라우저 UA — 몇몇 보안 블로그가 봇 UA 에 403/빈 본문을 준다 (2026-11-12 실측: 45건 모두 이 UA 로 200)
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

_DROP = re.compile(r"(?is)<(script|style|noscript|svg|nav|footer|header|form)[^>]*>.*?</\1>")
_BLOCK = re.compile(r"(?i)<(br|/p|/div|/li|/h\d|/tr)[^>]*>")


def html_text(s: str) -> str:
    """HTML → 본문 텍스트. <article>/<main> 이 충분히 길면 그것만."""
    s = _DROP.sub(" ", s)
    m = re.search(r"(?is)<article[^>]*>(.*)</article>", s) or re.search(r"(?is)<main[^>]*>(.*)</main>", s)
    body = m.group(1) if m and len(re.sub("<[^>]+>", "", m.group(1))) > 1500 else s
    body = _BLOCK.sub("\n", body)
    return html.unescape(re.sub(r"<[^>]+>", " ", body))


def pdf_text(b: bytes) -> str:
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext 가 없다 (poppler-utils)")
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(b)
        f.flush()
        return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, check=False).stdout.decode("utf-8", "replace")


def kev_subset(b: bytes, needle: str) -> str:
    """CISA KEV 카탈로그 JSON 전체(1.5 MB) → needle 을 담은 항목만."""
    d = json.loads(b)
    rows = [x for x in d.get("vulnerabilities", []) if needle.lower() in json.dumps(x).lower()]
    return (f"CISA Known Exploited Vulnerabilities catalog — entries mentioning {needle} only "
            f"(catalog version {d.get('catalogVersion')}, {d.get('dateReleased')})\n\n" + json.dumps(rows, indent=1, ensure_ascii=False))


def normalize(t: str) -> str:
    t = re.sub(r"[ \t ]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n\n", t).strip()


def to_text(body: bytes, url: str, kev_needle: str | None = None) -> tuple[str, str]:
    """(텍스트, 종류). 종류 = pdf · html · kev."""
    if body[:5] == b"%PDF-":
        return normalize(pdf_text(body)), "pdf"
    if kev_needle and "known_exploited_vulnerabilities" in url:
        return kev_subset(body, kev_needle), "kev"
    return normalize(html_text(body.decode("utf-8", "replace"))), "html"


def build(incidents: list[Any], out_dir: Path = CONTENT_DIR, manifest: Path = MANIFEST,
          fetcher=None, now: datetime | None = None) -> dict[str, Any]:
    """사건마다 source_url 을 받아 out_dir/<id>.txt 에 쓰고 manifest 를 돌려준다(파일에도 쓴다)."""
    fetcher = fetcher or (lambda u: http_fetch(u, timeout=40, headers={"User-Agent": BROWSER_UA}))
    out_dir.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now(timezone.utc)
    docs: dict[str, Any] = {}
    for inc in incidents:
        r = fetcher(inc.source_url)
        rec: dict[str, Any] = {"source": inc.source_url, "http_status": r.status}
        if r.status == 200 and r.body:
            needle = "langflow" if "langflow" in inc.id else None
            text, kind = to_text(r.body, inc.source_url, needle)
            (out_dir / f"{inc.id}.txt").write_text(text, encoding="utf-8")
            rec.update(kind=kind, chars=len(text), sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                       thin=len(text) < 2500)
        docs[inc.id] = rec
    data = {"built_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": "사건 코딩 고정 원문. sha256 은 추출한 본문 텍스트(UTF-8)의 해시. 본문은 snapshots/incident_content/ (git 추적 안 함). "
                    "thin = 2,500자 미만 — 코더가 basis: thin 으로 둘 수 있다.",
            "documents": docs}
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return data
