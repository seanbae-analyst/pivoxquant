"""
PivoxQuant — Kiwoom (키움증권 영웅문) balance-file parser service.

Scope (Week 2 interim; replaces the OAuth sync that requires Kiwoom API
approval): the user exports a 잔고 file from 영웅문 HTS
(계좌관리 > 잔고조회 > 엑셀 저장) and uploads it here. We parse the
spreadsheet, normalise tickers to the yfinance-style `.KS` / `.KQ`
suffix convention that the rest of the codebase already uses, and return
a clean list of rows ready for the `positions` table.

The parser is intentionally defensive: 영웅문 changes its export format
between versions, users sometimes re-save through Excel (destroying cell
types), and column order is not guaranteed. So instead of hard-coding
column positions we:

  1. Scan the first ~20 rows to find the header row, identified by the
     presence of any Korean keyword from each required category
     (ticker-ish, shares-ish, avg-cost-ish).
  2. Resolve each logical column via keyword matching (Korean + English
     synonyms).
  3. Fall back to the KR stock registry for `.KS` / `.KQ` suffix when
     the source row does not carry a market code.

Public API:
    parse_kiwoom_balance_file(source, filename) -> list[dict]
        source   : bytes | str (path) | file-like
        filename : used only for extension sniffing (.xls / .xlsx / .csv)
        returns  : [{"ticker": "005930.KS", "shares": 10, "avg_cost": 70000.0}, ...]
        raises   : UserKiwoomCSVError with a friendly Korean message

Security notes:
    - Parser NEVER executes macros. openpyxl's default (data_only=True,
      read_only=True) strips formulas; .xls via xlrd ignores VBA; .csv
      path uses Python's stdlib csv module.
    - Callers must enforce the 5 MB size limit before handing bytes here;
      this module will happily try to parse whatever it's given.
"""
from __future__ import annotations

import csv
import io
import logging
import os
import re
from typing import Any, Iterable, Optional, Union

logger = logging.getLogger(__name__)


class UserKiwoomCSVError(Exception):
    """Raised for parse/format errors; `.message` is Korean-ready for UI."""

    def __init__(self, message: str, code: str = "CSV_INVALID"):
        super().__init__(message)
        self.message = message
        self.code = code


# ── Header / column synonym dictionaries ───────────────────────────────────
# Lowercased for matching; values are the canonical logical columns.
#
# 영웅문 잔고 엑셀 표준 헤더 (2024~2026 관측) 예시:
#   종목코드 | 종목명 | 보유수량 | 매도가능 | 평균단가 | 현재가 | 평가금액 | 평가손익 | 수익률
# 구버전 / 해외주식 잔고 / 엑셀 재저장 버전은 표기가 다를 수 있어 synonym 다수.
_TICKER_KEYS = (
    "종목코드", "단축코드", "코드", "종목번호",
    "ticker", "symbol", "code",
)
_NAME_KEYS = (
    "종목명", "종목", "상품명", "name",
)
_SHARES_KEYS = (
    "보유수량", "잔고수량", "수량", "보유주수", "결제수량", "현재수량",
    "shares", "qty", "quantity",
)
_AVG_COST_KEYS = (
    "평균단가", "매입단가", "평단가", "평균매입가", "매입가",
    "avg_cost", "avg cost", "average price", "average cost", "buy price",
)
_MARKET_KEYS = (
    "시장", "시장구분", "거래소", "market", "exchange",
)


def _norm(s: Any) -> str:
    """Lowercase + strip whitespace + drop punctuation for fuzzy matching."""
    if s is None:
        return ""
    return re.sub(r"[\s_\-()/.,]+", "", str(s).strip().lower())


def _match_any(cell: Any, keys: Iterable[str]) -> bool:
    n = _norm(cell)
    if not n:
        return False
    for k in keys:
        kn = _norm(k)
        if kn and (kn == n or kn in n):
            return True
    return False


def _resolve_header_columns(header_row: list[Any]) -> dict[str, int]:
    """Map logical column names -> index. Unmatched logical columns are omitted."""
    cols: dict[str, int] = {}
    for i, cell in enumerate(header_row):
        for key_name, keys in (
            ("ticker", _TICKER_KEYS),
            ("name", _NAME_KEYS),
            ("shares", _SHARES_KEYS),
            ("avg_cost", _AVG_COST_KEYS),
            ("market", _MARKET_KEYS),
        ):
            if key_name in cols:
                continue
            if _match_any(cell, keys):
                cols[key_name] = i
    return cols


def _find_header_row(rows: list[list[Any]]) -> tuple[int, dict[str, int]]:
    """Search the first ~20 rows for the header. Return (row_index, cols).

    Raises UserKiwoomCSVError if required columns cannot be found anywhere.
    A valid header must contain at least ticker-or-name + shares + avg_cost.
    """
    max_scan = min(len(rows), 20)
    best: tuple[int, dict[str, int]] | None = None
    for i in range(max_scan):
        cols = _resolve_header_columns(rows[i])
        has_id = "ticker" in cols or "name" in cols
        has_qty = "shares" in cols
        has_cost = "avg_cost" in cols
        if has_id and has_qty and has_cost:
            return i, cols
        # Track best-effort match for diagnostics.
        if best is None or len(cols) > len(best[1]):
            best = (i, cols)
    missing = []
    found = (best[1] if best else {})
    if "ticker" not in found and "name" not in found:
        missing.append("종목코드/종목명")
    if "shares" not in found:
        missing.append("보유수량")
    if "avg_cost" not in found:
        missing.append("평균단가")
    raise UserKiwoomCSVError(
        "잔고 엑셀 포맷이 아닙니다. 영웅문 계좌관리 > 잔고 > 엑셀 저장을 확인해주세요. "
        f"(누락 컬럼: {', '.join(missing) or '없음'})",
        code="CSV_HEADER_NOT_FOUND",
    )


# ── Numeric coercion ───────────────────────────────────────────────────────
_NUM_STRIP_RE = re.compile(r"[^\d.\-]")


def _to_number(v: Any) -> Optional[float]:
    """Parse cell value to float. Handles '1,234', '1,234주', '70,000원', etc.

    Returns None if value is blank or un-parseable.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    # Remove thousands separators, currency symbols, unit suffixes.
    cleaned = _NUM_STRIP_RE.sub("", s)
    # Protect against leading/trailing dots left by the regex (e.g. "주.").
    cleaned = cleaned.strip(".")
    if not cleaned or cleaned in ("-", ".", "-."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


# ── Ticker normalisation ───────────────────────────────────────────────────
_CODE_RE = re.compile(r"\d{6}")


def _extract_code(raw_ticker: Any, raw_name: Any = None) -> Optional[str]:
    """Extract a 6-digit KRX code from the cell. Leading zeros preserved.

    영웅문 엑셀은 숫자형 셀이라 `5930` 처럼 leading-zero가 날아가 있을 수 있으므로
    (1) 문자열 그대로 6자리면 OK, (2) 6자리보다 짧으면 0 패딩.
    (3) 셀이 'A005930' 같이 혼합되어 있으면 regex로 추출.
    """
    for source in (raw_ticker, raw_name):
        if source is None:
            continue
        if isinstance(source, (int, float)):
            s = str(int(source))
        else:
            s = str(source).strip()
        if not s:
            continue
        m = _CODE_RE.search(s)
        if m:
            return m.group(0)
        # Numeric-like short codes (e.g. "5930" → "005930")
        digits = re.sub(r"\D", "", s)
        if digits and 1 <= len(digits) <= 6:
            return digits.zfill(6)
    return None


def _suffix_for(code: str, market_hint: Any = None) -> str:
    """Decide .KS / .KQ. Priority: explicit market hint > registry lookup > .KS default."""
    # 1) Row-level hint from '시장' column if present.
    if market_hint:
        h = _norm(market_hint)
        if "kosdaq" in h or "코스닥" in str(market_hint) or h == "kq":
            return ".KQ"
        if "kospi" in h or "코스피" in str(market_hint) or h == "ks" or "유가" in str(market_hint):
            return ".KS"

    # 2) Registry lookup (imports at call-time to avoid circular import at module load).
    try:
        from services.kr_stock_registry import KR_STOCKS, KR_STOCKS_FULL  # type: ignore
    except Exception:
        KR_STOCKS, KR_STOCKS_FULL = {}, {}  # type: ignore

    for suffix in (".KS", ".KQ"):
        if f"{code}{suffix}" in KR_STOCKS or f"{code}{suffix}" in KR_STOCKS_FULL:
            return suffix

    # 3) Default: KOSPI. If we're wrong the user can fix via edit position.
    return ".KS"


# ── Row-format loaders (xlsx / xls / csv) ──────────────────────────────────
def _load_xlsx_rows(data: bytes) -> list[list[Any]]:
    try:
        from openpyxl import load_workbook  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise UserKiwoomCSVError(
            "서버에 엑셀 파서(openpyxl)가 설치되어 있지 않습니다. 관리자에게 문의해주세요.",
            code="CSV_PARSER_MISSING",
        ) from e

    try:
        wb = load_workbook(filename=io.BytesIO(data), data_only=True, read_only=True)
    except Exception as e:
        raise UserKiwoomCSVError(
            "엑셀 파일을 읽을 수 없습니다. 손상되었거나 지원하지 않는 형식입니다.",
            code="CSV_CORRUPT",
        ) from e

    ws = wb.active
    if ws is None:
        raise UserKiwoomCSVError("엑셀 파일에 시트가 없습니다.", code="CSV_EMPTY")

    rows: list[list[Any]] = []
    for row in ws.iter_rows(values_only=True):
        # Drop fully-empty rows — 영웅문 export는 여러 빈 행이 섞여 있음.
        if row is None:
            continue
        if all(c is None or (isinstance(c, str) and not c.strip()) for c in row):
            continue
        rows.append(list(row))
    try:
        wb.close()
    except Exception:
        pass
    return rows


def _load_xls_rows(data: bytes) -> list[list[Any]]:
    try:
        import xlrd  # type: ignore
    except ImportError as e:
        raise UserKiwoomCSVError(
            "구버전 .xls 파일은 지원되지 않습니다. 영웅문에서 '엑셀(.xlsx)' 또는 CSV로 저장해주세요.",
            code="CSV_UNSUPPORTED_XLS",
        ) from e

    try:
        book = xlrd.open_workbook(file_contents=data)
    except Exception as e:
        raise UserKiwoomCSVError(
            "엑셀(.xls) 파일을 읽을 수 없습니다. 손상되었거나 지원하지 않는 형식입니다.",
            code="CSV_CORRUPT",
        ) from e

    sheet = book.sheet_by_index(0)
    rows: list[list[Any]] = []
    for r in range(sheet.nrows):
        row = sheet.row_values(r)
        if all((c == "" or c is None) for c in row):
            continue
        rows.append(list(row))
    return rows


def _load_csv_rows(data: bytes) -> list[list[Any]]:
    # 영웅문 CSV는 보통 cp949/euc-kr; 재저장본은 utf-8-sig.
    text: Optional[str] = None
    last_err: Optional[Exception] = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError as e:
            last_err = e
            continue
    if text is None:
        raise UserKiwoomCSVError(
            "CSV 인코딩을 확인할 수 없습니다. UTF-8 또는 CP949로 저장해주세요.",
            code="CSV_ENCODING",
        ) from last_err

    # Sniff the delimiter (영웅문: ','; 일부 재저장본: '\t' or ';').
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        class _D(csv.excel):
            delimiter = ","
        dialect = _D()

    rows: list[list[Any]] = []
    reader = csv.reader(io.StringIO(text), dialect=dialect)
    for row in reader:
        if not row or all((not c or not c.strip()) for c in row):
            continue
        rows.append(list(row))
    return rows


def _load_rows(source: Union[bytes, str], filename: str) -> list[list[Any]]:
    """Dispatch on file extension. Accepts bytes or a filesystem path."""
    if isinstance(source, str):
        if not os.path.exists(source):
            raise UserKiwoomCSVError("업로드된 파일을 찾을 수 없습니다.", code="CSV_NOT_FOUND")
        with open(source, "rb") as f:
            data = f.read()
    elif isinstance(source, (bytes, bytearray, memoryview)):
        data = bytes(source)
    elif hasattr(source, "read"):
        data = source.read()  # type: ignore[union-attr]
    else:
        raise UserKiwoomCSVError(
            "지원하지 않는 입력 형식입니다.", code="CSV_BAD_INPUT"
        )

    if not data:
        raise UserKiwoomCSVError("업로드된 파일이 비어 있습니다.", code="CSV_EMPTY")

    ext = (os.path.splitext(filename or "")[1] or "").lower()
    if ext == ".xlsx":
        return _load_xlsx_rows(data)
    if ext == ".xls":
        return _load_xls_rows(data)
    if ext == ".csv":
        return _load_csv_rows(data)
    # Last-ditch: try xlsx (zip magic bytes) then csv.
    if data[:2] == b"PK":
        return _load_xlsx_rows(data)
    return _load_csv_rows(data)


# ── Public entry point ─────────────────────────────────────────────────────
def parse_kiwoom_balance_file(
    source: Union[bytes, str],
    filename: str,
) -> list[dict]:
    """Parse a 키움 영웅문 balance export into position dicts.

    See module docstring for semantics. Always returns a list; raises
    UserKiwoomCSVError on any user-facing error.
    """
    rows = _load_rows(source, filename)
    if not rows:
        raise UserKiwoomCSVError("데이터가 없습니다.", code="CSV_EMPTY")

    header_idx, cols = _find_header_row(rows)

    parsed: list[dict] = []
    seen_tickers: set[str] = set()

    for row_idx in range(header_idx + 1, len(rows)):
        row = rows[row_idx]
        if not row:
            continue

        def cell(key: str) -> Any:
            idx = cols.get(key)
            if idx is None or idx >= len(row):
                return None
            return row[idx]

        raw_ticker = cell("ticker")
        raw_name = cell("name")
        raw_shares = cell("shares")
        raw_cost = cell("avg_cost")
        raw_market = cell("market")

        # Totals / summary rows at the bottom of the sheet
        # (e.g. '합계', '평가총액') — skip them instead of erroring out.
        name_str = str(raw_name or "").strip()
        if name_str and any(
            tok in name_str for tok in ("합계", "총계", "소계", "평가총액", "Total", "total", "TOTAL")
        ):
            continue

        code = _extract_code(raw_ticker, raw_name)
        if not code:
            # Blank row with stray whitespace — tolerate.
            if raw_shares is None and raw_cost is None:
                continue
            # Otherwise it's garbage; skip but log for debugging.
            logger.debug(f"Kiwoom parse: skipping row {row_idx} (no ticker): {row!r}")
            continue

        shares = _to_number(raw_shares)
        avg_cost = _to_number(raw_cost)
        if shares is None or shares <= 0:
            continue
        if avg_cost is None or avg_cost <= 0:
            # 영웅문은 종종 매도 후 남은 0주 행을 유지 — 그런 행은 위에서 컷.
            # 여기 도달하면 단가 누락이라 무효 행.
            continue

        ticker = f"{code}{_suffix_for(code, raw_market)}"
        if ticker in seen_tickers:
            # 동일 종목이 여러 행으로 나오면 (잔고 + 청산예정 등) 가중평균으로 합치기.
            for existing in parsed:
                if existing["ticker"] == ticker:
                    total_qty = existing["shares"] + shares
                    if total_qty > 0:
                        existing["avg_cost"] = (
                            existing["avg_cost"] * existing["shares"]
                            + avg_cost * shares
                        ) / total_qty
                        existing["shares"] = total_qty
                    break
            continue
        seen_tickers.add(ticker)
        parsed.append({
            "ticker": ticker,
            "shares": shares,
            "avg_cost": avg_cost,
        })

    if not parsed:
        raise UserKiwoomCSVError(
            "유효한 잔고 데이터를 찾을 수 없습니다. 빈 계좌이거나 포맷이 올바르지 않을 수 있습니다.",
            code="CSV_NO_ROWS",
        )

    return parsed
