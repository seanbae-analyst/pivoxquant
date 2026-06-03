"""`.xlsx` Excel export — GET /api/profile/export?format=xlsx.

A multi-sheet workbook of the user's own raw-fact datasets (positions /
watchlist / trades / journal / pulse / capital-gains), reusing the same column
specs + formula-injection guard as the CSV export. Same PIPA §35 self-only
scope and no-store headers.

Covers: auth gate, workbook shape (mimetype / attachment / sheets), that the
now-encrypted columns (thesis / note / worry) export as the owner's PLAINTEXT
(encryption composes with export), single-dataset narrowing, formula-injection
neutralisation, self-only scope, and the bad-dataset 400.
"""
from __future__ import annotations

from io import BytesIO

from openpyxl import load_workbook

from extensions import db
from models import Position, Watchlist, WeeklyPulse


_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _all_cell_strings(wb) -> list[str]:
    out = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if isinstance(cell, str):
                    out.append(cell)
    return out


def test_xlsx_requires_auth(client):
    resp = client.get("/api/profile/export?format=xlsx")
    assert resp.status_code == 401, resp.data


def test_xlsx_returns_multisheet_workbook(app, client, auth_user):
    uid = auth_user["id"]
    with app.app_context():
        db.session.add(Position(
            user_id=uid, ticker="AAPL", shares=3, avg_cost=190.0,
            thesis="내 매수 이유 비밀번호 같은 생각",
        ))
        db.session.add(Watchlist(user_id=uid, ticker="MSFT", note="관심 메모 비밀"))
        db.session.add(WeeklyPulse(
            user_id=uid, mood=2, confidence=3, worry="오를까봐 무섭다", learn="",
        ))
        db.session.commit()

    resp = client.get("/api/profile/export?format=xlsx")
    assert resp.status_code == 200, resp.data
    assert resp.headers["Content-Type"].startswith(_XLSX_MIME)
    cd = resp.headers.get("Content-Disposition", "")
    assert "attachment" in cd and cd.endswith('.xlsx"'), cd
    assert "no-store" in resp.headers.get("Cache-Control", "")

    wb = load_workbook(BytesIO(resp.data))
    titles = set(wb.sheetnames)
    # Every dataset becomes its own sheet (friendly Korean titles).
    assert {"보유종목", "관심종목", "매매일지", "주간펄스"} <= titles, titles


def test_xlsx_exports_encrypted_columns_as_owner_plaintext(app, client, auth_user):
    """watchlist.note and weekly_pulse.worry are encrypted at rest — the owner's
    own export must still show the PLAINTEXT (proves encryption composes with the
    export). These are the encrypted columns carried by the tabular export specs;
    free-text like positions.thesis lives in the full JSON §35 export instead."""
    uid = auth_user["id"]
    with app.app_context():
        db.session.add(Watchlist(user_id=uid, ticker="TSLA", note="NOTE_SECRET_메모"))
        db.session.add(WeeklyPulse(
            user_id=uid, mood=1, confidence=1, worry="WORRY_SECRET_걱정", learn="",
        ))
        db.session.commit()

    resp = client.get("/api/profile/export?format=xlsx")
    assert resp.status_code == 200
    blob = "\n".join(_all_cell_strings(load_workbook(BytesIO(resp.data))))
    assert "NOTE_SECRET_메모" in blob
    assert "WORRY_SECRET_걱정" in blob


def test_xlsx_single_dataset(app, client, auth_user):
    uid = auth_user["id"]
    with app.app_context():
        db.session.add(Position(user_id=uid, ticker="AAPL", shares=2, avg_cost=100.0))
        db.session.commit()

    resp = client.get("/api/profile/export?format=xlsx&dataset=positions")
    assert resp.status_code == 200, resp.data
    wb = load_workbook(BytesIO(resp.data))
    assert wb.sheetnames == ["보유종목"], wb.sheetnames


def test_xlsx_neutralizes_formula_injection(app, client, auth_user):
    """A watchlist note that starts with '=' must not become a live formula —
    it is prefixed with ' (same CWE-1236 guard as the CSV path)."""
    uid = auth_user["id"]
    payload = "=HYPERLINK(\"http://evil\",\"x\")"
    with app.app_context():
        db.session.add(Watchlist(user_id=uid, ticker="GOOG", note=payload))
        db.session.commit()

    resp = client.get("/api/profile/export?format=xlsx&dataset=watchlist")
    assert resp.status_code == 200
    wb = load_workbook(BytesIO(resp.data))
    cells = _all_cell_strings(wb)
    # The raw payload must NOT appear unprefixed; the neutralised form must.
    assert payload not in cells
    assert ("'" + payload) in cells


def test_xlsx_self_scope_only(app, client, auth_user, make_user):
    uid = auth_user["id"]
    other = make_user(email="xlsx-other@test.com", password="otherpw123")
    with app.app_context():
        db.session.add(Watchlist(user_id=uid, ticker="AAPL", note="MINE_내것"))
        db.session.add(Watchlist(user_id=other["id"], ticker="ZZZZ", note="OTHER_남의것"))
        db.session.commit()

    resp = client.get("/api/profile/export?format=xlsx")
    assert resp.status_code == 200
    blob = "\n".join(_all_cell_strings(load_workbook(BytesIO(resp.data))))
    assert "MINE_내것" in blob
    assert "OTHER_남의것" not in blob
    assert "ZZZZ" not in blob


def test_xlsx_bad_dataset_400(client, auth_user):
    resp = client.get("/api/profile/export?format=xlsx&dataset=bogus")
    assert resp.status_code == 400, resp.data


def test_xlsx_control_chars_dont_crash(app, client, auth_user):
    """A note carrying XML-illegal control chars must NOT 500 the workbook.
    openpyxl rejects \\x00-\\x1F; _xlsx_cell strips them and keeps the text."""
    uid = auth_user["id"]
    with app.app_context():
        db.session.add(Watchlist(user_id=uid, ticker="AAPL", note="메모\x00\x07\x1f끝"))
        db.session.commit()

    resp = client.get("/api/profile/export?format=xlsx&dataset=watchlist")
    assert resp.status_code == 200, resp.data
    blob = "\n".join(_all_cell_strings(load_workbook(BytesIO(resp.data))))
    assert "메모끝" in blob       # control chars stripped, surrounding text kept
    assert "\x00" not in blob


def test_xlsx_one_failing_dataset_does_not_kill_workbook(
    app, client, auth_user, monkeypatch,
):
    """If one dataset throws (e.g. a capital-gains FIFO/FX edge case), the rest
    of the workbook still renders — isolation, not a whole-export 500."""
    import routes.profile as profile_mod

    uid = auth_user["id"]
    with app.app_context():
        db.session.add(Position(user_id=uid, ticker="AAPL", shares=1, avg_cost=100.0))
        db.session.commit()

    def _boom(_user_id):
        raise RuntimeError("simulated capital-gains failure")

    monkeypatch.setattr(profile_mod, "_capital_gain_rows", _boom)

    resp = client.get("/api/profile/export?format=xlsx")
    assert resp.status_code == 200, resp.data
    wb = load_workbook(BytesIO(resp.data))
    # The good sheets survived; the failed tax sheets still exist (header + note).
    assert "보유종목" in wb.sheetnames
    assert "양도손익(상세)" in wb.sheetnames


def test_xlsx_cell_guards_every_hazard():
    """Unit-level: _xlsx_cell neutralises every cell-level hazard so no single
    value (user-supplied or computed) can crash workbook generation."""
    from decimal import Decimal

    from routes.profile import _xlsx_cell

    # formula injection → prefixed with '
    assert _xlsx_cell("=SUM(A1)") == "'=SUM(A1)"
    assert _xlsx_cell("+1") == "'+1"
    assert _xlsx_cell("-5") == "'-5"
    assert _xlsx_cell("@x") == "'@x"
    # XML-illegal control chars stripped; surrounding text kept
    assert _xlsx_cell("a\x00\x07b") == "ab"
    assert _xlsx_cell("\x01\x02\x03") == ""          # all stripped → empty, no crash
    # tab/newline/CR are allowed
    assert _xlsx_cell("a\tb\nc\rd") == "a\tb\nc\rd"
    # length cap at Excel's per-cell maximum
    assert len(_xlsx_cell("x" * 50000)) == 32767
    # NaN / ±Inf / Decimal non-finite → None (never an Excel-invalid number)
    assert _xlsx_cell(float("nan")) is None
    assert _xlsx_cell(float("inf")) is None
    assert _xlsx_cell(float("-inf")) is None
    assert _xlsx_cell(Decimal("Infinity")) is None
    assert _xlsx_cell(Decimal("NaN")) is None
    # normal values pass through untouched
    assert _xlsx_cell("삼성전자 😬 中文") == "삼성전자 😬 中文"
    assert _xlsx_cell(Decimal("123.45")) == 123.45
    assert _xlsx_cell(42) == 42
    assert _xlsx_cell(None) is None


def test_xlsx_empty_user_still_valid_workbook(app, client, auth_user):
    """A user with zero data gets a valid workbook — every sheet present with
    just its header row (honest empty, never fabricated)."""
    resp = client.get("/api/profile/export?format=xlsx")
    assert resp.status_code == 200, resp.data
    wb = load_workbook(BytesIO(resp.data))
    assert {"보유종목", "관심종목", "거래내역"} <= set(wb.sheetnames)
    # Positions sheet exists and has at least the header row.
    assert wb["보유종목"].max_row >= 1
