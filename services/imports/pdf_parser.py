"""PDF reader for broker trade-history statements.

Turns the PDF a broker app hands out ("거래내역 내보내기 → PDF") into the
same header-row grid ``csv_parser`` already understands, so the header
synonym dictionary, the broker guess and every row rule stay in one place.
This module only gets cells out of pages.

How a page becomes rows (first strategy that yields something wins):

1. ``page.extract_tables()`` with ruling lines — most Korean broker PDFs
   draw the table, and this keeps 종목명 with spaces in one cell.
2. Words placed under the header's columns — statements laid out on
   whitespace without borders. The header line (≥3 known column names)
   fixes the column centres; every later word goes to the nearest one, so
   "TIGER 미국S&P500" stays one cell and a right-aligned 수량 still lands
   under 수량. (pdfplumber's own text-strategy tables were tried first and
   merged neighbouring header cells on a plain statement — dropped.)
3. Plain text lines split on whitespace — last resort when no header line
   is found; a name with a space then spills a column, and the user sees
   it in the waiting list and rejects the row.

Repeated header rows (one per page) are dropped once the first header is
found, so a 6-page statement is one table, not six.

What it refuses, with the code the UI already maps:

* needs a password / wrong password         → IMPORT_PDF_PASSWORD — the
  statement Kiwoom's 영웅문S# emails is locked with the holder's birth date
  (6 digits), so the form carries an optional ``pdf_password`` that is
  used for this open() call and never stored or logged
* corrupt / not-a-PDF                       → IMPORT_UNSUPPORTED_FORMAT
* more than ``MAX_PDF_PAGES`` pages         → IMPORT_FILE_TOO_LARGE
* no extractable text (scan, photo export)  → IMPORT_NO_ROWS, pointing at
  the screenshot → text path the import page already documents

The file is read from memory and never written anywhere — same rule as
CSV/XLSX (the consent copy promises "원본 파일은 파싱 후 저장하지 않고").
"""
from __future__ import annotations

import io
import re
from collections.abc import Iterable

from . import ImportParseError

# A broker statement for a year of an active account is a few pages; forty
# is well past any real export while keeping a hostile PDF's CPU bill
# bounded (pdfminer parses each page's content stream in full).
MAX_PDF_PAGES = 40

_WS_RUN = re.compile(r"\s{2,}|\t")
# Words whose ``top`` differ by less than this sit on one line (points).
_LINE_TOLERANCE = 3.0


def read_pdf(data: bytes, password: str | None = None) -> list[list]:
    """Return a grid (list of rows) for ``csv_parser._parse_grid``."""
    try:
        import pdfplumber
        from pdfminer.pdfdocument import PDFEncryptionError
    except ImportError as exc:  # pragma: no cover — requirements.txt pins it
        raise ImportParseError(
            "IMPORT_UNSUPPORTED_FORMAT",
            en="PDF import is not available on this server.",
            kr="이 서버에서는 PDF 가져오기를 쓸 수 없습니다.",
        ) from exc

    def _is_password_error(exc: BaseException) -> bool:
        # pdfplumber ≥0.11 wraps pdfminer's error in its own PdfminerException;
        # the PDFPasswordIncorrect sits behind it as __cause__ / __context__.
        seen: set[int] = set()
        cur: BaseException | None = exc
        while cur is not None and id(cur) not in seen:
            if isinstance(cur, PDFEncryptionError):
                return True
            seen.add(id(cur))
            cur = cur.__cause__ or cur.__context__
        return False

    try:
        pdf = pdfplumber.open(io.BytesIO(data), password=password or "")
    except Exception as exc:
        if not _is_password_error(exc):
            raise ImportParseError(
                "IMPORT_UNSUPPORTED_FORMAT",
                en="PDF could not be opened.",
                kr="PDF 를 열 수 없습니다.",
            ) from exc
        # locked, or the password given is wrong
        raise ImportParseError(
            "IMPORT_PDF_PASSWORD",
            en="This PDF needs a password, or the one given is wrong. "
               "Broker-emailed statements usually use your 6-digit birth date.",
            kr="이 PDF 는 암호가 필요하거나 입력한 암호가 틀렸습니다. "
               "증권사가 이메일로 보낸 거래내역서는 보통 생년월일 6자리입니다.",
        ) from exc

    with pdf:
        if len(pdf.pages) > MAX_PDF_PAGES:
            raise ImportParseError(
                "IMPORT_FILE_TOO_LARGE",
                en=f"PDF has more than {MAX_PDF_PAGES} pages. Export a shorter period and retry.",
                kr=f"PDF 가 {MAX_PDF_PAGES}쪽을 넘습니다. 기간을 줄여 다시 내려받아 주세요.",
            )
        try:
            pages = [_page_rows(p) for p in pdf.pages]
        except ImportParseError:
            raise
        except Exception as exc:  # a page pdfminer cannot decode
            raise ImportParseError(
                "IMPORT_UNSUPPORTED_FORMAT",
                en="PDF could not be read.",
                kr="PDF 를 읽을 수 없습니다.",
            ) from exc

    grid = grid_from_pages(pages)
    if not grid:
        raise ImportParseError(
            "IMPORT_NO_ROWS",
            en="No text could be read from this PDF (a scan or image export). "
               "Take a screenshot instead and paste it as text.",
            kr="이 PDF 에서 글자를 읽지 못했습니다(스캔·이미지 저장본). "
               "화면을 캡처해 텍스트로 뽑아 붙여넣기 경로를 써 주세요.",
        )
    return grid


# ── page → rows ────────────────────────────────────────────────────────

def _clean(cell) -> str:
    if cell is None:
        return ""
    return " ".join(str(cell).split())


def _page_rows(page) -> list[list]:
    """Rows of one page, by the first strategy that yields any."""
    tables = page.extract_tables() or []
    rows = [[_clean(c) for c in row] for t in tables for row in t]
    rows = [r for r in rows if any(r)]
    if rows:
        return rows
    words = page.extract_words() or []
    rows = rows_from_words(words)
    if rows:
        return rows
    text = page.extract_text() or ""
    return [cells for cells in (_split_line(ln) for ln in text.splitlines()) if cells]


def _lines(words: list[dict]) -> list[list[dict]]:
    """Group pdfplumber words into lines by their ``top``, left to right."""
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(w["top"] - lines[-1][0]["top"]) <= _LINE_TOLERANCE:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(ln, key=lambda w: w["x0"]) for ln in lines]


def rows_from_words(words: list[dict]) -> list[list]:
    """Column-assign words under the first header line; ``[]`` if none.

    Pure: ``words`` are dicts with ``text``/``x0``/``x1``/``top`` as
    ``page.extract_words()`` returns them, so the unit tests build them by
    hand. Lines above the header are emitted word-per-cell (the header
    scanner ignores them); lines below get exactly one cell per header
    column, words joined with a space.
    """
    from .csv_parser import _MIN_HEADER_HITS, map_headers

    lines = _lines(words)
    header_i = None
    for i, ln in enumerate(lines):
        idx, _, _ = map_headers([w["text"] for w in ln])
        if len(idx) >= _MIN_HEADER_HITS:
            header_i = i
            break
    if header_i is None:
        return []

    header = lines[header_i]
    centres = [(w["x0"] + w["x1"]) / 2 for w in header]
    # Column boundaries sit halfway between neighbouring header centres.
    bounds = [(a + b) / 2 for a, b in zip(centres, centres[1:])]

    def col_of(w: dict) -> int:
        c = (w["x0"] + w["x1"]) / 2
        for j, b in enumerate(bounds):
            if c < b:
                return j
        return len(bounds)

    rows: list[list] = [[w["text"] for w in ln] for ln in lines[:header_i]]
    rows.append([_clean(w["text"]) for w in header])
    for ln in lines[header_i + 1:]:
        cells = [""] * len(header)
        for w in ln:
            j = col_of(w)
            cells[j] = (cells[j] + " " + w["text"]).strip() if cells[j] else w["text"]
        if any(cells):
            rows.append([_clean(c) for c in cells])
    return rows


def _split_line(line: str) -> list[str]:
    line = line.strip()
    if not line:
        return []
    cells = [c for c in _WS_RUN.split(line) if c.strip()]
    if len(cells) < 3:
        cells = line.split()
    return [_clean(c) for c in cells]


# ── pages → one grid ───────────────────────────────────────────────────

def grid_from_pages(pages: Iterable[list[list]]) -> list[list]:
    """Concatenate page rows, dropping every repeat of the header row.

    Pure: takes lists, returns a list — the unit tests feed it directly.
    The header is located with the same scorer ``csv_parser`` uses, so the
    two can never disagree about which row is the header.
    """
    from .csv_parser import MAX_ROWS, _find_header_row, _norm, _MAX_HEADER_SCAN

    grid: list[list] = []
    header_norm: list[str] | None = None
    for rows in pages:
        for row in rows:
            if header_norm is None:
                grid.append(row)
                hdr_i = _find_header_row(grid)
                if hdr_i is not None:
                    header_norm = [_norm(c) for c in grid[hdr_i]]
                continue
            if [_norm(c) for c in row] == header_norm:
                continue  # the same header printed again on a later page
            grid.append(row)
            if len(grid) > MAX_ROWS + _MAX_HEADER_SCAN:
                return grid
    return grid


__all__ = ["read_pdf", "grid_from_pages", "rows_from_words", "MAX_PDF_PAGES"]
