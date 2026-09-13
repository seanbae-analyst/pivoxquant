"""Table parser for broker exports (CSV / XLSX / XLS) and our own export.

No per-broker fixture: a header-synonym dictionary maps whatever column
names the file carries onto the fields we need. Encoding fallback
utf-8-sig → utf-8 → cp949 covers Korean broker CSVs saved from Excel.

Output is a :class:`ParseResult` — the rows as :class:`RawTrade`, the
header→field mapping actually used (returned to the UI), headers we did
not understand, a best-effort broker guess from the header signature,
and every skipped row with its reason.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

from . import (
    ImportParseError,
    RawTrade,
    mask_sensitive,
    parse_datetime,
    parse_number,
    side_from_text,
    today_naive,
)

MAX_ROWS = 2000

# field → synonyms (Korean + English). Matching is done on a normalised
# header (lower-case, whitespace / underscores / brackets removed) — exact
# first, then "header contains synonym" for the longer synonyms.
HEADER_SYNONYMS: dict[str, tuple[str, ...]] = {
    "date": (
        "거래일자", "체결일자", "체결일", "거래일", "일자", "매매일자", "매매일",
        "주문일자", "주문일", "거래일시", "체결일시", "체결시각", "일시", "날짜",
        "traded_at", "tradedat", "date", "tradedate", "filldate", "executiondate",
        "datetime", "timestamp", "time",
    ),
    "time": ("체결시간", "거래시간", "주문시간", "시간", "tradetime", "filltime"),
    "name": (
        "종목명", "상품명", "종목", "명칭", "종목이름", "stockname", "name",
        "security", "securityname", "description", "instrument",
    ),
    "code": (
        "종목코드", "단축코드", "표준코드", "코드", "티커", "심볼",
        "ticker", "symbol", "code", "stockcode", "isin",
    ),
    "side": (
        "거래구분", "매매구분", "거래유형", "거래종류", "매매유형", "주문구분",
        "구분", "유형", "종류", "action", "side", "type", "transactiontype",
        "buysell", "buy/sell", "b/s",
    ),
    "shares": (
        "수량", "체결수량", "거래수량", "매매수량", "주문수량", "체결량",
        "shares", "quantity", "qty", "units", "volume",
    ),
    "price": (
        "단가", "체결단가", "거래단가", "매매단가", "체결가", "체결가격", "가격",
        "price", "price_per_share", "pricepershare", "unitprice", "fillprice",
        "averageprice", "avgprice",
    ),
    "amount": (
        "거래금액", "체결금액", "매매금액", "약정금액", "금액", "정산금액",
        "total_value", "totalvalue", "amount", "total", "value", "netamount",
        "grossamount",
    ),
    "currency": ("통화", "통화코드", "거래통화", "currency", "ccy", "cur"),
    "fee": ("수수료", "제세금", "세금", "fee", "commission", "tax"),
}

# Header-signature heuristics for ``broker_guess``. Each entry lists
# raw-header substrings that must all be present. First match wins.
BROKER_SIGNATURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pivoxquant", ("traded_at", "price_per_share", "total_value")),
    ("korea_investment", ("거래일자", "종목코드", "거래구분", "단가")),
    ("kiwoom", ("체결일자", "매매구분", "체결단가")),
    ("toss", ("거래일시", "거래유형", "종목명")),
    ("mirae_asset", ("거래일", "거래종류", "종목명")),
    ("samsung", ("매매일자", "매매구분", "매매단가")),
    ("nh", ("거래일자", "거래종류", "체결가")),
    ("generic_kr", ("종목명", "수량")),
    ("generic_en", ("symbol", "quantity")),
)

_MAX_HEADER_SCAN = 15
_MIN_HEADER_HITS = 3
_NORMALISE = re.compile(r"[\s_\-()\[\]/]+")


@dataclass
class ParseResult:
    rows: list[RawTrade] = field(default_factory=list)
    mapping: dict[str, str] = field(default_factory=dict)          # field → header
    unmapped_headers: list[str] = field(default_factory=list)
    broker_guess: str = "unknown"
    skipped: list[dict] = field(default_factory=list)              # {row, reason}


# ── Public entry point ─────────────────────────────────────────────────

def parse_table(data: bytes, filename: str) -> ParseResult:
    """Parse ``data`` (file bytes) into fills. Raises ImportParseError."""
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    if ext in ("csv", "txt", "tsv", ""):
        grid = _read_csv(data)
    elif ext == "xlsx" or ext == "xlsm":
        grid = _read_xlsx(data)
    elif ext == "xls":
        grid = _read_xls(data)
    else:
        raise ImportParseError(
            "IMPORT_UNSUPPORTED_FORMAT",
            en=f"Unsupported file type: .{ext}. Use CSV, XLSX or XLS.",
            kr=f"지원하지 않는 파일 형식입니다(.{ext}). CSV·XLSX·XLS 파일을 올려 주세요.",
        )
    return _parse_grid(grid)


# ── Readers ────────────────────────────────────────────────────────────

def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ImportParseError(
        "IMPORT_UNSUPPORTED_FORMAT",
        en="File encoding not recognised (utf-8 / cp949 expected).",
        kr="파일 인코딩을 읽을 수 없습니다(utf-8 또는 cp949만 지원).",
    )


def _read_csv(data: bytes) -> list[list]:
    text = _decode(data)
    sample = text[:4096]
    delimiter = ","
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
    except csv.Error:
        if "\t" in sample and sample.count("\t") > sample.count(","):
            delimiter = "\t"
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    grid: list[list] = []
    for row in reader:
        grid.append([c.strip() if isinstance(c, str) else c for c in row])
        if len(grid) > MAX_ROWS + _MAX_HEADER_SCAN:
            break
    return grid


def _read_xlsx(data: bytes) -> list[list]:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # corrupt / not an xlsx
        raise ImportParseError(
            "IMPORT_UNSUPPORTED_FORMAT",
            en="XLSX file could not be opened.",
            kr="XLSX 파일을 열 수 없습니다.",
        ) from exc
    try:
        ws = wb.worksheets[0]
        grid: list[list] = []
        for row in ws.iter_rows(values_only=True):
            grid.append([("" if v is None else v) for v in row])
            if len(grid) > MAX_ROWS + _MAX_HEADER_SCAN:
                break
        return grid
    finally:
        wb.close()


def _read_xls(data: bytes) -> list[list]:
    try:
        import pandas as pd
        df = pd.read_excel(io.BytesIO(data), header=None, dtype=object)
    except Exception as exc:  # xlrd missing or file unreadable
        raise ImportParseError(
            "IMPORT_UNSUPPORTED_FORMAT",
            en="XLS file could not be read. Save it as CSV or XLSX and retry.",
            kr="XLS 파일을 읽을 수 없습니다. CSV 또는 XLSX 로 저장해 다시 올려 주세요.",
        ) from exc
    grid: list[list] = []
    for row in df.itertuples(index=False):
        grid.append([("" if _is_nan(v) else v) for v in row])
        if len(grid) > MAX_ROWS + _MAX_HEADER_SCAN:
            break
    return grid


def _is_nan(v) -> bool:
    try:
        return v is None or v != v  # NaN != NaN
    except Exception:
        return False


# ── Header mapping ─────────────────────────────────────────────────────

def _norm(h) -> str:
    return _NORMALISE.sub("", str(h or "").strip().lower())


def map_headers(headers: list) -> tuple[dict[str, int], dict[str, str], list[str]]:
    """Return (field→column index, field→raw header, unmapped raw headers)."""
    normed = [_norm(h) for h in headers]
    idx: dict[str, int] = {}
    raw: dict[str, str] = {}
    used: set[int] = set()

    # Pass 1: exact matches.
    for fld, syns in HEADER_SYNONYMS.items():
        for i, h in enumerate(normed):
            if i in used or not h:
                continue
            if h in syns:
                idx[fld] = i
                raw[fld] = str(headers[i]).strip()
                used.add(i)
                break

    # Pass 2: containment (longest synonym first, ≥2 chars, skip 1-char).
    for fld, syns in HEADER_SYNONYMS.items():
        if fld in idx:
            continue
        for syn in sorted(syns, key=len, reverse=True):
            if len(syn) < 2:
                continue
            for i, h in enumerate(normed):
                if i in used or not h or syn not in h:
                    continue
                idx[fld] = i
                raw[fld] = str(headers[i]).strip()
                used.add(i)
                break
            if fld in idx:
                break

    unmapped = [str(h).strip() for i, h in enumerate(headers)
                if i not in used and str(h or "").strip()]
    return idx, raw, unmapped


def _find_header_row(grid: list[list]) -> int | None:
    best_i, best_hits = None, 0
    for i, row in enumerate(grid[:_MAX_HEADER_SCAN]):
        if not any(str(c or "").strip() for c in row):
            continue
        idx, _, _ = map_headers(row)
        hits = len(idx)
        if hits > best_hits:
            best_i, best_hits = i, hits
    if best_i is None or best_hits < _MIN_HEADER_HITS:
        return None
    return best_i


def guess_broker(headers: list) -> str:
    joined = [str(h or "").strip().lower() for h in headers]
    for name, needles in BROKER_SIGNATURES:
        if all(any(n.lower() in h for h in joined) for n in needles):
            return name
    return "unknown"


# ── Row → RawTrade ─────────────────────────────────────────────────────

def _parse_grid(grid: list[list]) -> ParseResult:
    result = ParseResult()
    hdr_i = _find_header_row(grid)
    if hdr_i is None:
        raise ImportParseError(
            "IMPORT_NO_ROWS",
            en="No header row with date / name / side / shares columns was found.",
            kr="날짜·종목·구분·수량 열이 있는 헤더 행을 찾지 못했습니다.",
        )
    headers = grid[hdr_i]
    idx, raw_map, unmapped = map_headers(headers)
    result.mapping = raw_map
    result.unmapped_headers = unmapped
    result.broker_guess = guess_broker(headers)

    body = grid[hdr_i + 1: hdr_i + 1 + MAX_ROWS]
    for offset, row in enumerate(body):
        row_no = hdr_i + 2 + offset  # 1-based line number for the user
        if not any(str(c or "").strip() for c in row):
            continue
        trade = _row_to_trade(row, idx)
        trade.raw_snippet = mask_sensitive(" | ".join(str(c) for c in row if str(c or "").strip()))
        trade.extra["row"] = row_no
        if trade.skip_reason:
            result.skipped.append({"row": row_no, "reason": trade.skip_reason})
        result.rows.append(trade)
    return result


def _cell(row: list, idx: dict[str, int], fld: str):
    i = idx.get(fld)
    if i is None or i >= len(row):
        return None
    return row[i]


def _row_to_trade(row: list, idx: dict[str, int]) -> RawTrade:
    t = RawTrade()
    side_raw = _cell(row, idx, "side")
    side = side_from_text(side_raw)
    if side is None:
        label = str(side_raw or "").strip() or "구분 없음"
        t.skip_reason = f"체결 외 항목: {label}"
        return t
    t.action = side

    t.name = str(_cell(row, idx, "name") or "").strip()
    t.code = str(_cell(row, idx, "code") or "").strip()
    if not t.name and not t.code:
        t.skip_reason = "종목명·종목코드 없음"
        return t

    shares = parse_number(_cell(row, idx, "shares"))
    if shares is None or shares <= 0:
        t.skip_reason = "수량 없음"
        return t
    t.shares = abs(shares)

    price = parse_number(_cell(row, idx, "price"))
    if price is None or price <= 0:
        amount = parse_number(_cell(row, idx, "amount"))
        if amount and t.shares:
            price = abs(amount) / t.shares
            t.confidence -= 0.1
    if price is None or price <= 0:
        t.skip_reason = "단가·금액 없음"
        return t
    t.price = price

    dt = parse_datetime(_cell(row, idx, "date"), _cell(row, idx, "time"))
    if dt is None:
        if "date" in idx and str(_cell(row, idx, "date") or "").strip():
            t.skip_reason = "날짜 형식 미인식"
            return t
        dt = today_naive()
        t.confidence = min(t.confidence, 0.6)
    t.traded_at = dt

    cur = str(_cell(row, idx, "currency") or "").strip().upper()
    if cur in ("KRW", "USD"):
        t.currency = cur
    elif cur in ("₩", "원", "WON"):
        t.currency = "KRW"
    elif cur in ("$", "달러"):
        t.currency = "USD"
    t.confidence = round(max(0.0, min(1.0, t.confidence)), 2)
    return t


__all__ = ["ParseResult", "parse_table", "map_headers", "guess_broker",
           "HEADER_SYNONYMS", "BROKER_SIGNATURES"]
