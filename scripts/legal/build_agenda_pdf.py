#!/usr/bin/env python3
"""변호사 어젠다 MD → HTML → PDF 재생성 (2026-06-05 신규).

`docs/legal/2026-05-29_lawyer_consultation_agenda.md` 를 SoT 로 하여 같은
디렉터리에 `.html` / `.pdf` 를 재생성한다. 기존(2026-05-29) 인라인 CSS(Playfair /
A4)를 그대로 재사용해 스타일 일관성을 유지한다. MD 를 갱신할 때마다 본 스크립트로
형제 PDF 를 다시 만들면 된다(수작업 Chrome 프린트 대체).

실행:
  /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 \
      scripts/legal/build_agenda_pdf.py [MD경로]

의존: markdown, weasyprint (system py3.12 에 설치 확인됨). weasyprint 모듈
import 실패 시 동봉 CLI 바이너리로 폴백한다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import markdown

BASE = Path(__file__).resolve().parents[2]
DEFAULT_MD = BASE / "docs/legal/2026-05-29_lawyer_consultation_agenda.md"
CHROME_MAC = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
  @page { size: A4; margin: 18mm 16mm 18mm 16mm; }
  body {
    font-family: -apple-system, "SF Pro Text", "Helvetica Neue", "Apple SD Gothic Neo", "Pretendard", sans-serif;
    color: #111;
    font-size: 10.5pt;
    line-height: 1.55;
    max-width: 800px;
    margin: 0 auto;
    padding: 24px;
  }
  h1 { font-family: "Playfair Display", "Times New Roman", serif; font-size: 22pt; margin: 0 0 4px; letter-spacing: -0.3px; }
  h2 { font-family: "Playfair Display", "Times New Roman", serif; font-size: 15pt; margin: 26px 0 8px; padding-top: 12px; border-top: 1px solid #ddd; }
  h3 { font-size: 12pt; margin: 18px 0 6px; color: #2a2a2a; }
  h4 { font-size: 11pt; margin: 12px 0 4px; }
  p, li { font-size: 10.5pt; }
  blockquote { border-left: 3px solid #b08d57; padding: 4px 10px; color: #444; background: #faf6ef; margin: 8px 0; }
  table { width: 100%; border-collapse: collapse; margin: 8px 0 14px; font-size: 9.8pt; }
  th { background: #f4ecdc; border: 1px solid #d8c39a; padding: 6px 8px; text-align: left; }
  td { border: 1px solid #e2dccd; padding: 6px 8px; vertical-align: top; }
  code, pre { font-family: "SF Mono", "JetBrains Mono", Menlo, monospace; font-size: 9.5pt; }
  pre { background: #f6f3ec; padding: 10px 12px; border-radius: 4px; overflow-x: auto; border: 1px solid #e8e0c8; }
  strong { color: #6b4d23; }
  hr { border: none; border-top: 1px dashed #c8bda0; margin: 18px 0; }
  ul li { margin: 2px 0; }
  tr { page-break-inside: avoid; }
  .print-hint { background: #fff8d9; border: 1px dashed #b08d57; padding: 10px 14px; margin: 0 0 18px; border-radius: 4px; font-size: 9.5pt; color: #5a4515; }
  @media print { .print-hint { display: none; } }
"""

PRINT_HINT = (
    '<div class="print-hint">📄 PDF로 저장하려면 <strong>Cmd+P</strong> → '
    '"PDF로 저장". 인쇄 미리보기에서 이 안내 박스는 자동 숨김됨. '
    '(본 PDF 는 build_agenda_pdf.py 로 생성됨 — 2026-06-05 최신 규제 반영본)</div>'
)


def build(md_path: Path) -> tuple[Path, Path]:
    html_path = md_path.with_suffix(".html")
    pdf_path = md_path.with_suffix(".pdf")

    md_text = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    html = (
        '<!DOCTYPE html>\n<html lang="ko"><head>\n<meta charset="utf-8">\n'
        "<title>변호사 상담 어젠다 — 2026-05-29 (rev 2026-06-05)</title>\n"
        f"<style>{CSS}</style>\n</head><body>\n{PRINT_HINT}\n{body}\n</body></html>\n"
    )
    html_path.write_text(html, encoding="utf-8")
    engine = _write_pdf(html_path, pdf_path, html)
    print(f"[build_agenda_pdf] PDF engine = {engine}", file=sys.stderr)
    return html_path, pdf_path


def _write_pdf(html_path: Path, pdf_path: Path, html: str) -> str:
    """HTML→PDF. 이 맥에선 weasyprint native-lib 깨짐 → Chrome headless 우선,
    실패 시 weasyprint 폴백. Chrome headless 는 PDF 기록 후에도 프로세스가 안 죽어
    timeout+pkill 로 강제 회수한다(내 user-data-dir 한정 = CEO 실제 Chrome 보호)."""
    if Path(CHROME_MAC).exists():
        if pdf_path.exists():
            pdf_path.unlink()
        cmd = [
            CHROME_MAC, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw", "--virtual-time-budget=12000",
            "--user-data-dir=/tmp/pq-chrome-pdf",
            f"--print-to-pdf={pdf_path}", f"file://{html_path}",
        ]
        try:
            subprocess.run(cmd, timeout=45, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            pass
        finally:
            subprocess.run(["pkill", "-f", "pq-chrome-pdf"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if pdf_path.exists() and pdf_path.stat().st_size > 10_000:
            return "chrome-headless"
    try:
        from weasyprint import HTML as WHTML  # type: ignore

        WHTML(string=html, base_url=str(BASE)).write_pdf(str(pdf_path))
        return "weasyprint"
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"PDF 생성 실패 (chrome headless + weasyprint 둘 다): {exc}")


if __name__ == "__main__":
    md = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_MD
    if not md.exists():
        sys.exit(f"MD not found: {md}")
    h, p = build(md)
    print(f"OK\n  html = {h}\n  pdf  = {p}")
