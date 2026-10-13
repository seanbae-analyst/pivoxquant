"""Table parser for broker exports (CSV / XLSX / XLS / PDF) and our own export.

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
    amount_ok,
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

def parse_table(data: bytes, filename: str, password: str | None = None) -> ParseResult:
    """Parse ``data`` (file bytes) into fills. Raises ImportParseError.

    ``password`` is only meaningful for ``.pdf`` (a broker-emailed statement
    locked with the holder's birth date); it is used for the open and dropped.
    """
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    if ext in ("csv", "txt", "tsv", ""):
        grid = _read_csv(data)
    elif ext == "xlsx" or ext == "xlsm":
        grid = _read_xlsx(data)
    elif ext == "xls":
        grid = _read_xls(data)
    elif ext == "pdf":
        # 2026-09-17: the PDF a broker app exports is a table too; pdf_parser
        # only lifts the cells, every column/row rule below is shared.
        from .pdf_parser import read_pdf
        grid = read_pdf(data, password=password)
    else:
        raise ImportParseError(
            "IMPORT_UNSUPPORTED_FORMAT",
            en=f"Unsupported file type: .{ext}. Use CSV, XLSX, XLS or PDF.",
            kr=f"지원하지 않는 파일 형식입니다(.{ext}). CSV·XLSX·XLS·PDF 파일을 올려 주세요.",
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


MAX_XLSX_UNCOMPRESSED = 32 * 1024 * 1024
MAX_XLSX_ENTRIES = 512


def _guard_xlsx_size(data: bytes) -> None:
    """A 2MB upload can inflate ~1000:1; openpyxl parses sharedStrings.xml
    in full before any row cap applies. Refuse archives that would."""
    import zipfile
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            total = sum(i.file_size for i in infos)
    except zipfile.BadZipFile as exc:
        raise ImportParseError(
            "IMPORT_UNSUPPORTED_FORMAT",
            en="XLSX file could not be opened.",
            kr="XLSX 파일을 열 수 없습니다.",
        ) from exc
    if len(infos) > MAX_XLSX_ENTRIES or total > MAX_XLSX_UNCOMPRESSED:
        raise ImportParseError(
            "IMPORT_FILE_TOO_LARGE",
            en="XLSX contents are too large to read. Save the sheet as CSV and retry.",
            kr="XLSX 내용이 너무 큽니다. CSV 로 저장해 다시 올려 주세요.",
        )


def _read_xlsx(data: bytes) -> list[list]:
    _guard_xlsx_size(data)
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


def _rank(h: str) -> tuple[int, int, int]:
    """Exact-match preference: never an ORDER column when another matches
    (a 주문체결 export has 주문수량 10 / 체결수량 4 — the fill is 4; its
    주문구분 is often 지정가/시장가, not the side), a 체결 column first, then
    the longer header. 2026-10-13: 주문수량 and 체결수량 tied on length and
    the first column won, so a partial fill was stored with the order size."""
    return (0 if h.startswith("주문") else 1, 1 if h.startswith("체결") else 0, len(h))


def map_headers(headers: list) -> tuple[dict[str, int], dict[str, str], list[str]]:
    """Return (field→column index, field→raw header, unmapped raw headers)."""
    normed = [_norm(h) for h in headers]
    idx: dict[str, int] = {}
    raw: dict[str, str] = {}
    used: set[int] = set()

    # Pass 1: exact matches — ranked by :func:`_rank`, so a file laid out as
    # ``구분(현금/신용), …, 매매구분`` maps side to 매매구분, ``체결수량`` beats
    # ``수량`` and ``주문수량`` regardless of column order.
    for fld, syns in HEADER_SYNONYMS.items():
        best = None
        for i, h in enumerate(normed):
            if i in used or not h:
                continue
            if h in syns and (best is None or _rank(h) > _rank(normed[best])):
                best = i
        if best is not None:
            idx[fld] = best
            raw[fld] = str(headers[best]).strip()
            used.add(best)

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


# A currency named in the header ("단가(원)", "단가(USD)", "거래금액(달러)").
# _norm strips the brackets, so the hint is read from the raw header.
_HDR_USD = re.compile(r"usd|달러|\$|외화", re.IGNORECASE)
_HDR_KRW = re.compile(r"\(원\)|원화|krw|₩|\[원\]", re.IGNORECASE)


def _currency_hint(header) -> str | None:
    h = str(header or "")
    if _HDR_USD.search(h):
        return "USD"
    if _HDR_KRW.search(h):
        return "KRW"
    return None


def currency_columns(headers: list) -> dict[str, dict[str, int]]:
    """field → {currency → column} for price/amount columns that name their
    currency. A US row in a file with 단가(원) and 단가(USD) took whichever
    came first — "TSLA 2주 @ 497,000 USD" (2026-10-13 bug hunt)."""
    out: dict[str, dict[str, int]] = {"price": {}, "amount": {}}
    for i, h in enumerate(headers):
        hint = _currency_hint(h)
        if not hint:
            continue
        n = _norm(re.sub(r"usd|krw|달러|원화|외화|₩|\$|\(원\)|\[원\]", "", str(h or ""), flags=re.IGNORECASE))
        for fld in ("price", "amount"):
            syns = HEADER_SYNONYMS[fld]
            if n in syns or any(len(sy) >= 2 and sy in n for sy in syns):
                out[fld].setdefault(hint, i)
                break
    return out


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

    cur_cols = currency_columns(headers)
    cur_cols["order_price"] = _norm(raw_map.get("price", "")).startswith("주문")
    body = grid[hdr_i + 1: hdr_i + 1 + MAX_ROWS]
    for offset, row in enumerate(body):
        row_no = hdr_i + 2 + offset  # 1-based line number for the user
        if not any(str(c or "").strip() for c in row):
            continue
        trade = _row_to_trade(row, idx, cur_cols)
        trade.raw_snippet = mask_sensitive(" | ".join(str(c) for c in row if str(c or "").strip()))
        trade.extra["row"] = row_no
        if trade.skip_reason:
            result.skipped.append({"row": row_no, "reason": trade.skip_reason})
        result.rows.append(trade)
    # Rows past the cap used to vanish with no skip reason (2026-10-13).
    if any(any(str(c or "").strip() for c in r) for r in grid[hdr_i + 1 + MAX_ROWS:]):
        result.skipped.append({
            "row": hdr_i + 2 + MAX_ROWS,
            "reason": f"{MAX_ROWS}행까지만 읽었습니다 — 나머지는 기간을 나눠 다시 올려 주세요",
        })
    return result


def _cell(row: list, idx: dict[str, int], fld: str):
    i = idx.get(fld)
    if i is None or i >= len(row):
        return None
    return row[i]


# A currency itself in the security column is an FX row ("외화매수 · USD").
_CURRENCY_NAME = re.compile(r"^(?:USD|JPY|EUR|CNY|HKD|미국\s*달러|달러|엔화?|유로|위안화?)$", re.IGNORECASE)


def _row_to_trade(row: list, idx: dict[str, int], cur_cols: dict | None = None) -> RawTrade:
    cur_cols = cur_cols or {}
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
    if _CURRENCY_NAME.match(t.name or "") or _CURRENCY_NAME.match(t.code or ""):
        t.skip_reason = f"환전 항목: {t.name or t.code}"
        return t

    # Some brokers sign sells (매도, -10): take the magnitude, then range-check.
    shares = parse_number(_cell(row, idx, "shares"))
    shares = abs(shares) if shares is not None else None
    if not amount_ok(shares):
        t.skip_reason = "수량 없음" if not shares else "수량 범위 초과"
        return t
    t.shares = shares

    # The row's own currency, when the file states it — it picks between
    # 단가(원) / 단가(USD) columns below.
    cur = str(_cell(row, idx, "currency") or "").strip().upper()
    if cur in ("₩", "원", "WON"):
        cur = "KRW"
    elif cur in ("$", "달러"):
        cur = "USD"
    if cur not in ("KRW", "USD"):
        cur = ""

    def col(fld: str) -> int | None:
        by_cur = cur_cols.get(fld) or {}
        if cur and cur in by_cur:
            return by_cur[cur]
        return idx.get(fld)

    def hint(i: int | None) -> str | None:
        for c, j in (cur_cols.get("price") or {}).items():
            if j == i:
                return c
        for c, j in (cur_cols.get("amount") or {}).items():
            if j == i:
                return c
        return None

    price_i, amount_i = col("price"), col("amount")
    price = parse_number(row[price_i]) if price_i is not None and price_i < len(row) else None
    price = abs(price) if price is not None else None
    amount = parse_number(row[amount_i]) if amount_i is not None and amount_i < len(row) else None
    used_i = price_i
    # Only an ORDER price column (주문단가) and a fill amount: the amount over
    # the filled shares is the fill price (주문단가 71,000 · 체결 4주 284,800원
    # → 71,200, 2026-10-13).
    if price and amount and t.shares and cur_cols.get("order_price"):
        price, used_i = abs(amount) / t.shares, amount_i
    if not price:
        if amount and t.shares:
            price, used_i = abs(amount) / t.shares, amount_i
            t.confidence -= 0.1
    if not amount_ok(price):
        t.skip_reason = "단가·금액 없음" if not price else "단가 범위 초과"
        return t
    t.price = price
    # A price read from a column that names its currency fixes the row's
    # currency when the file has no 통화 column; disagreeing with a stated
    # 통화 is surfaced instead of storing won as dollars.
    col_cur = hint(used_i)
    if col_cur and cur and col_cur != cur:
        t.skip_reason = f"통화 불일치 — 통화 {cur}, 단가 열 {col_cur}"
        return t

    dt = parse_datetime(_cell(row, idx, "date"), _cell(row, idx, "time"))
    if dt is None:
        if "date" in idx and str(_cell(row, idx, "date") or "").strip():
            t.skip_reason = "날짜 형식 미인식"
            return t
        dt = today_naive()
        t.confidence = min(t.confidence, 0.6)
    t.traded_at = dt

    if cur:
        t.currency = cur
    elif col_cur:
        t.currency = col_cur
    t.confidence = round(max(0.0, min(1.0, t.confidence)), 2)
    return t


__all__ = ["ParseResult", "parse_table", "map_headers", "currency_columns", "guess_broker",
           "HEADER_SYNONYMS", "BROKER_SIGNATURES"]
