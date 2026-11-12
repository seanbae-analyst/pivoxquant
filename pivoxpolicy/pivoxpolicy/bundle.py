"""오프라인 사본 — 서버 없이 파일을 더블클릭해 여는 정적 페이지 (out/offline/).

out/ 은 이미 정적 사이트다(서버·DB 없음). 다만 sim.html 은 스크립트 세 개를 따로 읽고, 보안 헤더(CSP)는 Vercel 이 붙인다.
여기서는 그 스크립트를 페이지 안에 넣어 **파일 하나로 도는** 사본을 만든다 — USB · 메일 · 학회장 노트북(인터넷 없이)용.
  - out/offline/pivoxpolicy-home.html · pivoxpolicy-dashboard.html · pivoxpolicy-sim.html (+ simulation.md · pending-regulations.md)
  - 모의 테스트는 pivoxpolicy-sim.html 하나만 있어도 전부 돈다. 세 파일을 같은 폴더에 두면 서로 링크된다.
  - 보안: 페이지 안 <meta> CSP 로 그 페이지에 넣은 스크립트(sha256)만 실행 — 외부 스크립트·네트워크 요청 없음.
    인라인 데이터의 '</' 와 '<!--' 는 이스케이프한다(피드 제목 같은 외부 글이 <script> 를 끊지 못하게).
  - 글꼴(Pretendard)은 인터넷이 되면 CDN 에서, 안 되면 시스템 글꼴(Apple SD Gothic Neo · 맑은 고딕 등)로 보인다.
"""

from __future__ import annotations

import base64
import hashlib
import re
import shutil
from pathlib import Path

from .registry import OUT_DIR

PAGES = {"index.html": "pivoxpolicy-home.html", "dashboard.html": "pivoxpolicy-dashboard.html", "sim.html": "pivoxpolicy-sim.html"}
EXTRA = ("simulation.md", "pending-regulations.md")
CSP = ("default-src 'none'; script-src {hashes}; style-src 'unsafe-inline' https://cdn.jsdelivr.net; "
       "font-src https://cdn.jsdelivr.net data:; img-src data:; base-uri 'none'; form-action 'none'")
_SCRIPT_TAG = re.compile(r'<script src="\./([a-z0-9-]+\.js)"></script>')


class BundleError(ValueError):
    pass


def inline_js(code: str, data: bool = False) -> str:
    """<script> 안에 넣을 JS. 데이터(JSON)는 '</' · '<!--' 를 이스케이프하고, 코드는 그런 문자열이 없어야 한다."""
    if data:
        return code.replace("</", "<\\/").replace("<!--", "<\\!--")
    if re.search(r"</script|<!--", code, re.I):
        raise BundleError("인라인할 코드에 </script 또는 <!-- 가 있다")
    return code


def _hash(code: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(code.encode("utf-8")).digest()).decode("ascii") + "'"


def _relink(page: str) -> str:
    """사이트 안 링크를 오프라인 파일 이름으로 — ./ · dashboard.html(#...) · sim.html · ./simulation.md."""
    page = re.sub(r'href="\./"', f'href="{PAGES["index.html"]}"', page)
    page = page.replace('href="offline/', 'href="')          # 첫 화면의 '파일로 받기' — 사본 안에서는 같은 폴더
    for src, dst in PAGES.items():
        if src != "index.html":
            page = re.sub(rf'href="(?:\./)?{re.escape(src)}(#[^"]*)?"', lambda m, d=dst: f'href="{d}{m.group(1) or ""}"', page)
    return page


def bundle_page(html: str, out_dir: Path) -> str:
    hashes: list[str] = []

    def put(m: re.Match) -> str:
        name = m.group(1)
        code = inline_js((out_dir / name).read_text(encoding="utf-8"), data=name.endswith("-data.js"))
        hashes.append(_hash(code))
        return "<script>" + code + "</script>"

    html = _SCRIPT_TAG.sub(put, html)
    if re.search(r"<script\s+src=", html):
        raise BundleError("인라인하지 못한 외부 스크립트가 남았다")
    meta = f'<meta http-equiv="Content-Security-Policy" content="{CSP.format(hashes=" ".join(hashes) or chr(39) + "none" + chr(39))}" />'
    html = html.replace('<meta charset="utf-8" />', '<meta charset="utf-8" />\n' + meta, 1)
    return _relink(html)


def build(out_dir: Path = OUT_DIR) -> list[Path]:
    dest = out_dir / "offline"
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for src, dst in PAGES.items():
        p = out_dir / src
        if not p.exists():
            raise BundleError(f"{src} 가 없다 — 먼저 cli site")
        (dest / dst).write_text(bundle_page(p.read_text(encoding="utf-8"), out_dir), encoding="utf-8")
        written.append(dest / dst)
    for name in EXTRA:
        if (out_dir / name).exists():
            shutil.copyfile(out_dir / name, dest / name)
            written.append(dest / name)
    return written
