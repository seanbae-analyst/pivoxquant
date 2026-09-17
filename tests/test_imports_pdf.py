"""tests/test_imports_pdf.py — broker trade-history PDF → import inbox.

Two layers:

* ``grid_from_pages`` is pure (lists in, list out), so the page-merge rules —
  repeated per-page headers dropped, multi-line header cells normalised, row
  cap — are tested without a PDF.
* One real PDF, written by hand in the test (Helvetica, ASCII), goes through
  pdfplumber → csv_parser → the route, so the wiring is exercised end to end
  without adding a PDF writer to the dev requirements. Korean cells are
  covered by the pure layer; the header synonym table is shared with CSV and
  already tested there.
"""
from __future__ import annotations

import io

import pytest

from services.imports import ImportParseError
from services.imports.csv_parser import parse_table
from services.imports.pdf_parser import MAX_PDF_PAGES, grid_from_pages, read_pdf, rows_from_words

BASE = "/api/portfolio/imports"


# ── a minimal text PDF, built by hand ────────────────────────────────

COL_X = (40, 130, 210, 270, 340, 410)  # left edge of each column, points


def _make_pdf(rows: list[list[str]], pages: int = 1) -> bytes:
    """One content stream per page; every cell is its own Tj at its column's
    x, lines 14pt apart — the aligned layout a real statement has."""
    objs: list[bytes] = []

    def add(body: bytes) -> int:
        objs.append(body)
        return len(objs)

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    pages_id_placeholder = None
    for _ in range(pages):
        stream = b"BT /F1 10 Tf\n"
        for li, cells in enumerate(rows):
            y = 780 - 14 * li
            for ci, cell in enumerate(cells):
                stream += f"1 0 0 1 {COL_X[ci]} {y} Tm ({esc(cell)}) Tj\n".encode("latin-1")
        stream += b"ET"
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_ids.append((content, None))
    pages_id_placeholder = len(objs) + len(page_ids) + 1
    real_page_ids = []
    for content, _ in page_ids:
        pid = add(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (pages_id_placeholder, font, content)
        )
        real_page_ids.append(pid)
    kids = b" ".join(b"%d 0 R" % p for p in real_page_ids)
    pages_id = add(b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(real_page_ids)))
    assert pages_id == pages_id_placeholder
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
              % (len(objs) + 1, catalog, xref))
    return out.getvalue()


EN_LINES = [
    ["Trade history 2026-09"],
    ["date", "symbol", "side", "quantity", "price", "amount"],
    ["2026-09-01", "AAPL", "buy", "10", "180.5", "1805"],
    ["2026-09-02", "AAPL", "sell", "4", "190", "760"],
    ["2026-09-03", "AAPL", "dividend", "0", "0", "12"],
]


# ── pure page-merge rules ────────────────────────────────────────────

class TestGridFromPages:
    HEADER = ["거래일자", "종목명", "종목코드", "거래구분", "수량", "단가"]
    ROW1 = ["2026-09-01", "삼성전자", "005930", "매수", "10", "71,200"]
    ROW2 = ["2026-09-02", "SK하이닉스", "000660", "매도", "3", "210,000"]

    def test_repeated_page_headers_dropped(self):
        page1 = [["거래내역 조회"], self.HEADER, self.ROW1]
        page2 = [self.HEADER, self.ROW2]
        grid = grid_from_pages([page1, page2])
        assert grid == [["거래내역 조회"], self.HEADER, self.ROW1, self.ROW2]

    def test_multiline_header_cells_still_match(self):
        wrapped = ["거래\n일자", "종목명", "종목코드", "거래 구분", "수량", "단가"]
        # pdf_parser._clean turns "\n" into " "; _norm strips whitespace,
        # so the wrapped header on page 2 equals the flat one on page 1.
        page2_header = [" ".join(h.split()) for h in wrapped]
        grid = grid_from_pages([[self.HEADER, self.ROW1], [page2_header, self.ROW2]])
        assert page2_header not in grid
        assert self.ROW2 in grid

    def test_rows_before_header_are_kept_for_the_scanner(self):
        grid = grid_from_pages([[["계좌", "12-3456"], ["기간", "2026.09"], self.HEADER, self.ROW1]])
        assert grid[2] == self.HEADER
        parsed_rows = parse_table_grid(grid)
        assert [r.name for r in parsed_rows] == ["삼성전자"]

    def test_row_cap(self):
        from services.imports.csv_parser import MAX_ROWS
        many = [[self.HEADER] + [self.ROW1] * (MAX_ROWS + 500)]
        grid = grid_from_pages(many)
        assert len(grid) <= MAX_ROWS + 20


def _w(text, x0, top, width=None):
    """A pdfplumber word dict; 6pt per character unless given."""
    x1 = x0 + (width if width is not None else 6 * len(text))
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": top + 10}


class TestRowsFromWords:
    def test_name_with_space_stays_one_cell_and_right_aligned_numbers_land(self):
        words = [
            _w("거래내역", 40, 20),
            # header: 거래일자 | 종목명 | 거래구분 | 수량 | 단가   (x0 anchors)
            _w("거래일자", 40, 60), _w("종목명", 120, 60), _w("거래구분", 260, 60),
            _w("수량", 340, 60), _w("단가", 420, 60),
            # row: the ETF name is two words; 수량 / 단가 are right-aligned so
            # their x0 is LEFT of the header word's x0
            _w("2026-09-01", 40, 80), _w("TIGER", 120, 80), _w("미국S&P500", 160, 80),
            _w("매수", 260, 80), _w("120", 330, 80), _w("18,950", 405, 80),
            _w("2026-09-02", 40, 94.5), _w("KODEX", 120, 94.5), _w("200", 160, 94.5),
            _w("매도", 260, 94.5), _w("5", 345, 94.5), _w("41,000", 405, 94.5),
        ]
        rows = rows_from_words(words)
        assert rows[0] == ["거래내역"]
        assert rows[1] == ["거래일자", "종목명", "거래구분", "수량", "단가"]
        assert rows[2] == ["2026-09-01", "TIGER 미국S&P500", "매수", "120", "18,950"]
        assert rows[3] == ["2026-09-02", "KODEX 200", "매도", "5", "41,000"]
        parsed = parse_table_grid(rows)
        assert [(r.name, r.shares, r.price) for r in parsed] == [
            ("TIGER 미국S&P500", 120.0, 18950.0), ("KODEX 200", 5.0, 41000.0),
        ]

    def test_no_header_line_returns_empty(self):
        assert rows_from_words([_w("안내문", 40, 20), _w("계좌", 40, 40)]) == []


def parse_table_grid(grid):
    """Run the shared grid parser the way parse_table does after read_pdf."""
    from services.imports.csv_parser import _parse_grid
    return _parse_grid(grid).rows


# ── real PDF through pdfplumber + csv_parser ────────────────────────

class TestReadPdf:
    def test_text_pdf_parses_to_fills(self):
        res = parse_table(_make_pdf(EN_LINES), "statement.pdf")
        fills = [r for r in res.rows if not r.skip_reason]
        assert [(r.action, r.shares, r.price) for r in fills] == [("BUY", 10.0, 180.5), ("SELL", 4.0, 190.0)]
        assert res.mapping["date"] == "date" and res.mapping["shares"] == "quantity"
        assert any("dividend" in s["reason"] for s in res.skipped)
        assert res.broker_guess == "generic_en"

    def test_two_pages_one_table(self):
        res = parse_table(_make_pdf(EN_LINES, pages=2), "statement.pdf")
        fills = [r for r in res.rows if not r.skip_reason]
        assert len(fills) == 4  # header printed twice, counted once

    def test_no_text_is_no_rows(self):
        with pytest.raises(ImportParseError) as ei:
            read_pdf(_make_pdf([]))
        assert ei.value.code == "IMPORT_NO_ROWS"
        assert "스캔" in ei.value.kr

    def test_corrupt_pdf_unsupported(self):
        with pytest.raises(ImportParseError) as ei:
            read_pdf(b"%PDF-1.4 ... not really")
        assert ei.value.code == "IMPORT_UNSUPPORTED_FORMAT"

    def test_page_cap(self):
        with pytest.raises(ImportParseError) as ei:
            read_pdf(_make_pdf(EN_LINES, pages=MAX_PDF_PAGES + 1))
        assert ei.value.code == "IMPORT_FILE_TOO_LARGE"


# ── the route ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _fixed_fx(monkeypatch):
    monkeypatch.setattr("services.fx_service.get_rate", lambda: 1300.0)


def _upload(client, data: bytes, filename: str):
    form = {"file": (io.BytesIO(data), filename), "consent": "true"}
    return client.post(f"{BASE}/", data=form, content_type="multipart/form-data")


class TestRoute:
    def test_pdf_upload_lands_in_inbox(self, client, auth_user):
        r = _upload(client, _make_pdf(EN_LINES), "statement.pdf")
        assert r.status_code == 201, r.get_json()
        body = r.get_json()
        assert len(body["pending"]) == 2
        assert body["batch"]["filename"] == "statement.pdf"
        assert any("dividend" in s["reason"] for s in body["skipped"])

    def test_scanned_pdf_400_points_to_text_path(self, client, auth_user):
        r = _upload(client, _make_pdf([]), "scan.pdf")
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_NO_ROWS"


# ── locked PDFs (Kiwoom 영웅문S# emails the statement with a birth-date lock) ─

def _lock(data: bytes, password: str) -> bytes:
    pypdf = pytest.importorskip("pypdf")  # dev-only; not a runtime dependency
    reader = pypdf.PdfReader(io.BytesIO(data))
    writer = pypdf.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


class TestLockedPdf:
    def test_no_password_is_a_password_error_not_a_format_error(self):
        with pytest.raises(ImportParseError) as ei:
            read_pdf(_lock(_make_pdf(EN_LINES), "900101"))
        assert ei.value.code == "IMPORT_PDF_PASSWORD"
        assert "생년월일" in ei.value.kr

    def test_wrong_password(self):
        with pytest.raises(ImportParseError) as ei:
            read_pdf(_lock(_make_pdf(EN_LINES), "900101"), password="000000")
        assert ei.value.code == "IMPORT_PDF_PASSWORD"

    def test_right_password_parses(self):
        res = parse_table(_lock(_make_pdf(EN_LINES), "900101"), "kiwoom.pdf", password="900101")
        assert len([r for r in res.rows if not r.skip_reason]) == 2

    def test_route_passes_pdf_password_and_keeps_only_the_filename(self, client, auth_user):
        form = {
            "file": (io.BytesIO(_lock(_make_pdf(EN_LINES), "900101")), "kiwoom.pdf"),
            "consent": "true",
            "pdf_password": "900101",
        }
        r = client.post(f"{BASE}/", data=form, content_type="multipart/form-data")
        assert r.status_code == 201, r.get_json()
        body = r.get_json()
        assert len(body["pending"]) == 2
        assert "900101" not in r.get_data(as_text=True)

    def test_route_locked_without_password_400(self, client, auth_user):
        r = _upload(client, _lock(_make_pdf(EN_LINES), "900101"), "kiwoom.pdf")
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_PDF_PASSWORD"
