"""Import Inbox — /api/portfolio/imports (docs/product/IMPORT_INBOX_DESIGN.md).

Flow: the user uploads a broker CSV/XLSX or pastes a fill notification →
rows land in ``pending_trades`` → the user attaches their own thesis and
approves each one → ``services.imports.ledger`` writes ``trade_history`` /
``positions``. Nothing reaches the mirror before approval, and seed
capital is never touched.

Every query is filtered by ``user_id == current_user.id``.
"""
from __future__ import annotations

import logging
import re
from functools import wraps

from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import db
from models.import_batch import (
    ImportBatch,
    PendingTrade,
    SOURCE_CSV,
    SOURCE_SCREENSHOT_TEXT,
    STATUS_APPROVED,
    STATUS_DUPLICATE,
    STATUS_PENDING,
    STATUS_REJECTED,
)
from security import general_rate_limit
from services.error_responses import api_error
from services.imports import ImportParseError, RawTrade, parse_datetime, parse_number, utcnow_naive
from services.imports.csv_parser import parse_table
from services.imports.dedupe import is_duplicate, make_key
from services.imports.ledger import LedgerError, apply_pending, match_pre_trade
from services.imports.text_parser import parse_text
from services.kr_stock_registry import get_name, search as registry_search
from services.ticker_normalizer import is_korean_ticker, normalize_ticker
from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

imports_bp = Blueprint("imports", __name__, url_prefix="/api/portfolio/imports")

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TEXT_CHARS = 20_000
PENDING_LIST_LIMIT = 200
THESIS_MIN, THESIS_MAX = 3, 500

_US_TICKER_RE = re.compile(r"^[A-Za-z]{1,6}(?:[.\-][A-Za-z]{1,2})?$")
_KR_CODE_RE = re.compile(r"^\d{6}(?:\.(?:KS|KQ|KRX))?$", re.IGNORECASE)

# ``PendingTrade.action`` is the TradeHistory.action data value ("BUY" /  // legal-ok
# "SELL"), not user copy. ``legal_scrub_response`` rewrites every string  // legal-ok
# leaf, including that field (→ "ENTRY" / "EXIT"), which would break the
# DTO the journal reads. This restores only that one data field on
# pending rows, after the scrub has run over everything else.
_ACTION_RESTORE = {"ENTRY": "BUY", "EXIT": "SELL"}  # // legal-ok — trade action data value, not user copy


def _restore_action_field(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "action" and isinstance(v, str) and v in _ACTION_RESTORE and "shares" in obj:
                out[k] = _ACTION_RESTORE[v]
            else:
                out[k] = _restore_action_field(v)
        return out
    if isinstance(obj, list):
        return [_restore_action_field(x) for x in obj]
    return obj


def keep_trade_action(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        result = f(*args, **kwargs)
        resp, status = (result if isinstance(result, tuple) else (result, None))
        if hasattr(resp, "get_json") and getattr(resp, "is_json", False):
            try:
                data = resp.get_json()
            except Exception:
                return result
            fixed = jsonify(_restore_action_field(data))
            return (fixed, status) if status is not None else (fixed, resp.status_code)
        return result
    return wrapped


# ── helpers ──────────────────────────────────────────────────────────

def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


def resolve_ticker(code: str, name: str) -> tuple[str | None, str]:
    """Return ``(ticker or None, display_name)``.

    code  → ``normalize_ticker`` (6-digit / .KS / .KQ / US symbol).
    name  → ``kr_stock_registry.search`` exact ``name_kr`` match only;
            a bare Latin 1–6 letter name is taken as a US symbol.
    """
    code = (code or "").strip()
    name = (name or "").strip()
    ticker: str | None = None
    if code:
        if _KR_CODE_RE.match(code) or _US_TICKER_RE.match(code):
            ticker = normalize_ticker(code) or None
    if ticker is None and name:
        for hit in registry_search(name, limit=15):
            if hit.get("name_kr") == name:
                ticker = normalize_ticker(hit["ticker"])
                break
        if ticker is None and _US_TICKER_RE.match(name):
            ticker = normalize_ticker(name)
    display = name
    if ticker and is_korean_ticker(ticker):
        display = get_name(ticker) or name or ticker
    elif not display:
        display = ticker or ""
    return ticker, display[:100]


def _currency_for(ticker: str | None, given: str | None, name: str) -> str:
    if given in ("KRW", "USD"):
        return given
    if ticker:
        return "KRW" if is_korean_ticker(ticker) else "USD"
    return "KRW" if any("가" <= ch <= "힣" for ch in name) else "USD"


def _pending_for_user(pid: int) -> PendingTrade | None:
    return PendingTrade.query.filter_by(id=pid, user_id=current_user.id).first()


def _recompute(row: PendingTrade, seen: set[str] | None = None) -> None:
    """Recalculate dedupe_key / needs_ticker / status(duplicate) for ``row``."""
    row.needs_ticker = not bool(row.ticker)
    row.dedupe_key = make_key(
        current_user.id, row.ticker or row.name, row.action,
        row.shares, row.price, row.traded_at,
    )
    dup = is_duplicate(
        current_user.id, row.dedupe_key, row.ticker, row.action,
        row.shares, row.price, row.traded_at, exclude_id=row.id,
    )
    if seen is not None:
        if row.dedupe_key in seen:
            dup = True
        seen.add(row.dedupe_key)
    # A freshly built row has status None until INSERT applies the default.
    if row.status in (None, STATUS_PENDING, STATUS_DUPLICATE):
        row.status = STATUS_DUPLICATE if dup else STATUS_PENDING


# ── POST / ───────────────────────────────────────────────────────────

@imports_bp.route("/", methods=["POST"], strict_slashes=False)
@api_auth
@general_rate_limit
@keep_trade_action
@legal_scrub_response
def create_import():
    upload = request.files.get("file")
    if upload is not None:
        consent = _truthy(request.form.get("consent"))
        source = SOURCE_CSV
        text = None
    else:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        consent = _truthy(data.get("consent"))
        source = data.get("source") or SOURCE_SCREENSHOT_TEXT
        text = data.get("text")

    if not consent:
        return api_error(
            en="Upload consent is required before a file or text is processed.",
            kr="파일·텍스트 처리에 대한 동의가 필요합니다.",
            code="IMPORT_CONSENT_REQUIRED", status=400,
        )

    filename = None
    raw_rows: list[RawTrade]
    mapping: dict = {}
    unmapped: list = []
    broker_guess = "unknown"
    skipped: list[dict] = []

    if upload is not None:
        filename = (upload.filename or "")[:255]
        blob = upload.read(MAX_FILE_BYTES + 1)
        if len(blob) > MAX_FILE_BYTES:
            return api_error(
                en="File exceeds the 2MB limit.",
                kr="파일이 2MB 제한을 넘습니다.",
                code="IMPORT_FILE_TOO_LARGE", status=413,
            )
        if not blob:
            return api_error(
                en="A file or text is required.",
                kr="파일 또는 텍스트가 필요합니다.",
                code="IMPORT_FILE_REQUIRED", status=400,
            )
        try:
            parsed = parse_table(blob, filename)
        except ImportParseError as exc:
            return api_error(en=exc.en, kr=exc.kr, code=exc.code, status=400)
        raw_rows = parsed.rows
        mapping = parsed.mapping
        unmapped = parsed.unmapped_headers
        broker_guess = parsed.broker_guess
        skipped = list(parsed.skipped)
    else:
        if not isinstance(text, str) or not text.strip():
            return api_error(
                en="A file or text is required.",
                kr="파일 또는 텍스트가 필요합니다.",
                code="IMPORT_FILE_REQUIRED", status=400,
            )
        if len(text) > MAX_TEXT_CHARS:
            return api_error(
                en=f"Text exceeds {MAX_TEXT_CHARS} characters.",
                kr=f"텍스트가 {MAX_TEXT_CHARS}자를 넘습니다.",
                code="IMPORT_FILE_TOO_LARGE", status=413,
            )
        source = SOURCE_SCREENSHOT_TEXT
        raw_rows = parse_text(text)
        skipped = [
            {"row": i + 1, "reason": r.skip_reason, "snippet": r.raw_snippet}
            for i, r in enumerate(raw_rows) if r.skip_reason
        ]

    fills = [r for r in raw_rows if not r.skip_reason]
    if not fills:
        return api_error(
            en="No fills were found in the input.",
            kr="체결 내역을 찾지 못했습니다.",
            code="IMPORT_NO_ROWS", status=400,
            skipped=skipped, mapping=mapping, unmapped_headers=unmapped,
        )

    now = utcnow_naive()
    batch = ImportBatch(
        user_id=current_user.id, source=source, broker_guess=broker_guess,
        filename=filename, row_count=len(raw_rows), consent_at=now, created_at=now,
    )
    db.session.add(batch)
    db.session.flush()

    seen: set[str] = set()
    rows: list[PendingTrade] = []
    for r in fills:
        ticker, display = resolve_ticker(r.code, r.name)
        row = PendingTrade(
            batch_id=batch.id, user_id=current_user.id,
            ticker=ticker, name=display, action=r.action,
            shares=float(r.shares), price=float(r.price),
            currency=_currency_for(ticker, r.currency, display),
            traded_at=r.traded_at or now, confidence=float(r.confidence),
            raw_snippet=r.raw_snippet or None, created_at=now,
        )
        _recompute(row, seen)
        row.pre_trade_reflection_id = match_pre_trade(current_user.id, ticker, row.traded_at)
        db.session.add(row)
        rows.append(row)

    batch.parsed_count = len(rows)
    batch.duplicate_count = sum(1 for x in rows if x.status == STATUS_DUPLICATE)
    batch.unresolved_count = sum(1 for x in rows if x.needs_ticker)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("imports.create commit failed user_id=%s", current_user.id)
        return api_error(
            en="Failed to save the import.", kr="가져오기 저장에 실패했습니다.",
            code="IMPORT_SAVE_FAILED", status=500,
        )
    return jsonify({
        "batch": batch.to_dict(),
        "pending": [x.to_dict() for x in rows],
        "mapping": mapping,
        "unmapped_headers": unmapped,
        "skipped": skipped,
    }), 201


# ── GET /pending ─────────────────────────────────────────────────────

@imports_bp.route("/pending", methods=["GET"])
@api_auth
@general_rate_limit
@keep_trade_action
@legal_scrub_response
def list_pending():
    rows = (
        PendingTrade.query
        .filter_by(user_id=current_user.id, status=STATUS_PENDING)
        .order_by(PendingTrade.created_at.desc(), PendingTrade.id.desc())
        .limit(PENDING_LIST_LIMIT)
        .all()
    )
    return jsonify({"pending": [x.to_dict() for x in rows], "count": len(rows)})


# ── PATCH /pending/<id> ──────────────────────────────────────────────

@imports_bp.route("/pending/<int:pid>", methods=["PATCH"])
@api_auth
@general_rate_limit
@keep_trade_action
@legal_scrub_response
def patch_pending(pid: int):
    row = _pending_for_user(pid)
    if row is None:
        return api_error(en="Pending fill not found.", kr="대기 항목을 찾을 수 없습니다.",
                         code="IMPORT_NOT_FOUND", status=404)
    if row.status != STATUS_PENDING:
        return api_error(en=f"Fill is {row.status}, not pending.",
                         kr="대기 상태가 아닌 항목은 수정할 수 없습니다.",
                         code="IMPORT_NOT_PENDING", status=400)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}

    if "ticker" in data:
        t = normalize_ticker(str(data.get("ticker") or ""))
        row.ticker = t or None
        if row.ticker and is_korean_ticker(row.ticker):
            row.name = (get_name(row.ticker) or row.name or row.ticker)[:100]
    if "name" in data:
        row.name = str(data.get("name") or "").strip()[:100]
    if "action" in data:
        a = str(data.get("action") or "").strip().upper()
        if a not in ("BUY", "SELL"):  # // legal-ok — trade action data value, not user copy
            return api_error(en="action must be BUY or SELL.", kr="action 값이 올바르지 않습니다.",  # // legal-ok — trade action data value, not user copy
                             code="IMPORT_INVALID_FIELD", status=400)
        row.action = a
    if "shares" in data:
        v = parse_number(data.get("shares"))
        if v is None or v <= 0:
            return api_error(en="shares must be a positive number.", kr="수량은 0보다 커야 합니다.",
                             code="IMPORT_INVALID_FIELD", status=400)
        row.shares = float(v)
    if "price" in data:
        v = parse_number(data.get("price"))
        if v is None or v <= 0:
            return api_error(en="price must be a positive number.", kr="단가는 0보다 커야 합니다.",
                             code="IMPORT_INVALID_FIELD", status=400)
        row.price = float(v)
    if "traded_at" in data:
        dt = parse_datetime(data.get("traded_at"))
        if dt is None:
            return api_error(en="traded_at is not a recognised date.", kr="거래 일시 형식을 인식하지 못했습니다.",
                             code="IMPORT_INVALID_FIELD", status=400)
        row.traded_at = dt
    if "currency" in data and str(data.get("currency") or "").upper() in ("KRW", "USD"):
        row.currency = str(data["currency"]).upper()
    elif "ticker" in data:
        row.currency = _currency_for(row.ticker, None, row.name)

    _recompute(row)
    row.pre_trade_reflection_id = match_pre_trade(current_user.id, row.ticker, row.traded_at)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("imports.patch commit failed pid=%s", pid)
        return api_error(en="Failed to update the fill.", kr="항목 수정에 실패했습니다.",
                         code="IMPORT_SAVE_FAILED", status=500)
    return jsonify({"pending": row.to_dict()})


# ── POST /pending/<id>/approve ───────────────────────────────────────

@imports_bp.route("/pending/<int:pid>/approve", methods=["POST"])
@api_auth
@general_rate_limit
@keep_trade_action
@legal_scrub_response
def approve_pending(pid: int):
    row = _pending_for_user(pid)
    if row is None:
        return api_error(en="Pending fill not found.", kr="대기 항목을 찾을 수 없습니다.",
                         code="IMPORT_NOT_FOUND", status=404)
    if row.status != STATUS_PENDING:
        return api_error(en=f"Fill is {row.status}, not pending.",
                         kr="대기 상태가 아닌 항목은 승인할 수 없습니다.",
                         code="IMPORT_NOT_PENDING", status=400)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    thesis = str(data.get("thesis") or "").strip()
    if not (THESIS_MIN <= len(thesis) <= THESIS_MAX):
        return api_error(
            en=f"A thesis of {THESIS_MIN}–{THESIS_MAX} characters is required.",
            kr=f"이 거래를 한 이유를 {THESIS_MIN}~{THESIS_MAX}자로 적어 주세요.",
            code="IMPORT_THESIS_REQUIRED", status=400,
        )
    if not row.ticker:
        return api_error(en="A ticker is required before approval.",
                         kr="승인하려면 티커를 먼저 지정해 주세요.",
                         code="IMPORT_TICKER_REQUIRED", status=400)

    try:
        trade_id, position_id = apply_pending(current_user.id, row, thesis)
        row.approved_thesis = thesis
        row.approved_trade_id = trade_id
        row.approved_at = utcnow_naive()
        row.status = STATUS_APPROVED
        db.session.commit()
    except LedgerError as exc:
        db.session.rollback()
        return api_error(en=exc.en, kr=exc.kr, code=exc.code, status=400)
    except Exception:
        db.session.rollback()
        logger.exception("imports.approve failed pid=%s", pid)
        return api_error(en="Failed to record the fill.", kr="거래 기록에 실패했습니다.",
                         code="IMPORT_SAVE_FAILED", status=500)
    return jsonify({
        "ok": True,
        "pending": row.to_dict(),
        "trade_id": trade_id,
        "position_id": position_id,
    })


# ── POST /pending/<id>/reject ────────────────────────────────────────

@imports_bp.route("/pending/<int:pid>/reject", methods=["POST"])
@api_auth
@general_rate_limit
@keep_trade_action
@legal_scrub_response
def reject_pending(pid: int):
    row = _pending_for_user(pid)
    if row is None:
        return api_error(en="Pending fill not found.", kr="대기 항목을 찾을 수 없습니다.",
                         code="IMPORT_NOT_FOUND", status=404)
    if row.status != STATUS_PENDING:
        return api_error(en=f"Fill is {row.status}, not pending.",
                         kr="대기 상태가 아닌 항목은 거절할 수 없습니다.",
                         code="IMPORT_NOT_PENDING", status=400)
    row.status = STATUS_REJECTED
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("imports.reject commit failed pid=%s", pid)
        return api_error(en="Failed to update the fill.", kr="항목 수정에 실패했습니다.",
                         code="IMPORT_SAVE_FAILED", status=500)
    return jsonify({"ok": True})

