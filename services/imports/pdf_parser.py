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
* streams that unpack past the caps below   → IMPORT_FILE_TOO_LARGE
* no extractable text (scan, photo export)  → IMPORT_NO_ROWS, pointing at
  the screenshot → text path the import page already documents

The file is read from memory and never written anywhere — same rule as
CSV/XLSX (the consent copy promises "원본 파일은 파싱 후 저장하지 않고").
"""
from __future__ import annotations

import io
import re
import zlib
from collections.abc import Iterable

from . import ImportParseError

# A broker statement for a year of an active account is a few pages; forty
# is well past any real export while keeping a hostile PDF's CPU bill
# bounded (pdfminer parses each page's content stream in full).
MAX_PDF_PAGES = 40

_WS_RUN = re.compile(r"\s{2,}|\t")
# Words whose ``top`` differ by less than this sit on one line (points).
_LINE_TOLERANCE = 3.0

# ── how big a PDF is allowed to be once unpacked ───────────────────────
#
# Neither the 2MB upload cap nor MAX_PDF_PAGES bounds the work, because
# both count the file as it arrives: one page whose content stream is a
# FlateDecode'd run of text-showing operators arrives small and unpacks
# without limit. Measured on this repo (2026-09-17), parse_table(data,
# "statement.pdf"):
#
#     upload   pages  unpacked      elapsed
#      4,136B    1      1.7MB          2.4s
#     32,279B    1     13.3MB         21.3s
#    106,140B    1     43.6MB        >90s (did not finish)
#
# and the Procfile runs one gevent worker with a 120s timeout, so one
# upload holds up every other request and then takes the worker down with
# it. So: unpack the streams ourselves first, cheaply, and refuse before
# pdfplumber ever sees the file.
#
# The two numbers below are measured against real documents, not guessed.
#
# MAX_PDF_UNCOMPRESSED — total bytes all streams unpack to. Reference
# points: the 2-page mirror report services/reports/mirror_pdf.py renders
# unpacks to 317,653B (three embedded OpenType faces, the largest single
# stream 103,404B; the two page content streams are 18,678B and 15,258B),
# and the largest statement this module will even look at — 40 pages
# (MAX_PDF_PAGES) of 47 rows, built by tests/test_imports_pdf.py's
# _make_pdf — unpacks to 328,320B. 6MB is ~18x either, which leaves room
# for a statement carrying a non-subset Korean font, and is below every
# attack above (13.3MB / 43.6MB, and ~8.6MB for the 1.7MB vector-line
# variant that drew 360,000 lines over 3 pages in 19.1s).
MAX_PDF_UNCOMPRESSED = 6 * 1024 * 1024

# MAX_PDF_TEXT_OPS — text-showing operators (Tj / TJ / ' / ") across all
# streams. Bytes alone are a loose proxy: what pdfminer actually pays for
# is one object per shown glyph, and embedded fonts are most of a real
# PDF's bytes while costing nothing to show. The same 40-page/1,880-row
# statement carries 11,080 of these operators and the mirror report 207;
# the structural ceiling is csv_parser.MAX_ROWS (2,000) rows of a dozen
# columns, ~24,000 cells, one operator each. 50,000 is ~2x that ceiling
# and ~4.5x the measured document, and refuses all three measured bombs,
# the 4,136B one (58,666 operators, 2.4s) included.
#
# It cannot usefully go lower: a bomb that stays just under this cap costs
# pdfminer ~1.9s, and the legitimate 40-page statement above already costs
# 0.96s. Below that the guard would start refusing real statements to save
# time it cannot save.
MAX_PDF_TEXT_OPS = 50_000

# MAX_PDF_OBJECTS — page-level backstop, counted after pdfminer has laid
# out a page: chars plus the vector objects extract_tables() works over.
# The byte guard above cannot see inside an encrypted PDF (the streams are
# ciphertext, zlib refuses them and they are counted at their on-disk
# size), and a locked bomb is a plausible upload here — the form takes a
# pdf_password. The same 40-page statement lays out 52,560 chars, so
# 120,000 is ~2.3x it and stops a multi-page bomb on its first page
# instead of its fortieth.
MAX_PDF_OBJECTS = 120_000

# "stream" starts a stream body; "endstream" ends one and must not match.
_STREAM_START = re.compile(rb"(?<!end)stream(?:\r\n|\r|\n)")
# Tj / TJ, and the ' / " forms, which always follow a closing paren.
_TEXT_SHOW_OP = re.compile(rb"T[jJ]|\)\s*['\"]")
_INFLATE_CHUNK = 64 * 1024
# Bytes let out of zlib per call. A run of one repeated operator deflates
# ~1000:1, so a single 64KB input chunk would otherwise hand back tens of
# megabytes at once — the very thing being guarded against. max_length
# keeps what is in memory at any moment to this, and the rest waits in
# ``unconsumed_tail`` for a check that never comes once a cap is passed.
_INFLATE_OUT = 256 * 1024


def _too_large() -> ImportParseError:
    return ImportParseError(
        "IMPORT_FILE_TOO_LARGE",
        en="PDF contents are too large to read. Export a shorter period and retry.",
        kr="PDF 내용이 너무 큽니다. 기간을 줄여 다시 내려받아 주세요.",
    )


def _guard_pdf_size(data: bytes) -> None:
    """Refuse a PDF that unpacks past the caps above, before opening it.

    The PDF pair of ``csv_parser._guard_xlsx_size``. Walks the raw bytes,
    inflates each stream body in bounded pieces and keeps only the running
    totals — no more than ``_INFLATE_OUT`` of unpacked PDF is in memory at
    a time, and the walk stops the moment a cap is passed, so the work is
    bounded by the caps and not by what the file claims to hold.

    A stream zlib cannot read is not Flate — an inline image, a JPEG, an
    already-plain content stream, or the ciphertext of an encrypted PDF.
    For those the bytes on disk are all pdfminer can ever get, so they are
    counted at that size; ``_page_rows`` carries the backstop for the
    encrypted case, where the plaintext is only visible after the open.
    """
    total = 0
    shows = 0

    def count(chunk: bytes, carry: bytes) -> bytes:
        nonlocal total, shows
        total += len(chunk)
        # one byte of the piece before, so a two-byte operator split across
        # pieces is still counted once
        shows += len(_TEXT_SHOW_OP.findall(carry + chunk))
        if total > MAX_PDF_UNCOMPRESSED or shows > MAX_PDF_TEXT_OPS:
            raise _too_large()
        return chunk[-1:]

    for match in _STREAM_START.finditer(data):
        start = match.end()
        end = data.find(b"endstream", start)
        body = data[start:end] if end >= 0 else data[start:]
        inflate = zlib.decompressobj()
        produced = 0
        readable = True
        carry = b""
        for i in range(0, len(body), _INFLATE_CHUNK):
            pending = body[i:i + _INFLATE_CHUNK]
            while pending:
                try:
                    out = inflate.decompress(pending, _INFLATE_OUT)
                except zlib.error:
                    readable = False
                    break
                pending = inflate.unconsumed_tail
                if not out:
                    break
                produced += len(out)
                carry = count(out, carry)
            if not readable:
                break
        if not readable and produced == 0:
            count(body, b"")


def read_pdf(data: bytes, password: str | None = None) -> list[list]:
    """Return a grid (list of rows) for ``csv_parser._parse_grid``."""
    _guard_pdf_size(data)
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
            budget = [MAX_PDF_OBJECTS]
            pages = [_page_rows(p, budget) for p in pdf.pages]
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


def _page_rows(page, budget: list[int] | None = None) -> list[list]:
    """Rows of one page, by the first strategy that yields any.

    ``budget`` is a one-element list of objects still allowed across the
    whole document, spent before any extraction runs: reading ``page.chars``
    is the pdfminer pass the later calls reuse, so counting here costs
    nothing extra and stops a bomb on the page that blew the budget.
    """
    if budget is not None:
        # chars, plus the vector objects extract_tables() has to sort — a
        # page can be hostile with no text at all (360,000 ruling lines).
        budget[0] -= (len(page.chars) + len(page.lines)
                      + len(page.curves) + len(page.rects))
        if budget[0] < 0:
            raise _too_large()
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

    Nearest-centre alone is not enough. Header centres put the boundary
    halfway between two headers, but a left-aligned 종목명 runs on past
    that halfway point long before the next column's text starts, so the
    last token of a spaced name ("KODEX 미국나스닥100 TR") used to land in
    종목코드 — which then read as the ticker, and a KRW ETF with a
    non-numeric ticker was booked as a US holding in USD. The gap the
    token sits behind is the tell: the space inside a name is narrower
    than the whitespace between two columns, so a word only moves to a
    later column when it is at least ``_min_column_gap`` past the word
    before it, and otherwise stays with it.
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
        min_gap = _min_column_gap(ln)
        prev_col: int | None = None
        prev_x1 = 0.0
        for w in ln:
            j = col_of(w)
            if prev_col is not None and j > prev_col and (w["x0"] - prev_x1) < min_gap:
                j = prev_col  # a space inside one cell, not a column change
            cells[j] = (cells[j] + " " + w["text"]).strip() if cells[j] else w["text"]
            prev_col, prev_x1 = j, w["x1"]
        if any(cells):
            rows.append([_clean(c) for c in cells])
    return rows


# A word's height is its font size in points; a space is roughly 0.28 of
# that, while brokers leave several points of air between columns. 0.6 of
# the line's typical height sits well above any space and below the gap of
# even a tightly set table (6pt for a 10pt font), and the floor keeps a
# tiny font from making the test meaningless.
_COL_GAP_RATIO = 0.6
_MIN_COL_GAP = 2.5


def _min_column_gap(line: list[dict]) -> float:
    """Whitespace a word must sit behind before it counts as a new column."""
    heights = sorted(h for h in (float(w.get("bottom", w["top"])) - float(w["top"])
                                 for w in line) if h > 0)
    height = heights[len(heights) // 2] if heights else 10.0
    return max(_MIN_COL_GAP, _COL_GAP_RATIO * height)


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


__all__ = ["read_pdf", "grid_from_pages", "rows_from_words", "MAX_PDF_PAGES",
           "MAX_PDF_UNCOMPRESSED", "MAX_PDF_TEXT_OPS", "MAX_PDF_OBJECTS"]
