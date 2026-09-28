"""Fill-screen screenshot rows → ``RawTrade`` (docs/product/SCREENSHOT_IMPORT_DESIGN.md).

The screenshot never reaches the server. The browser runs OCR
(Tesseract.js) and the rule parser (``frontend/src/lib/fill-ocr/parse.ts``),
the user fills every cell the parser could not prove, and only the finished
rows arrive here as JSON. This module re-validates them (the client is not
trusted) and turns them into ``RawTrade`` for the shared
``routes.imports._ingest`` path — so they land in ``pending_trades`` and wait
for a thesis like every other source.

Stock names: an exact master name or a printed code resolves as usual
(``resolve_ticker``). An OCR-garbled name ("하이닉스", "심성전자") may be
matched by ``fuzzy_kr_ticker`` — but only a clear, unique match, and the row
is then marked low-confidence so the inbox asks the user to confirm it.
"""
from __future__ import annotations

import difflib
import re

from services.imports import RawTrade, amount_ok, mask_sensitive, parse_datetime, parse_number, side_from_text

MAX_ROWS = 200
HIGH_CONFIDENCE = 0.9
LOW_CONFIDENCE = 0.6
FUZZY_MIN_RATIO = 0.75
FUZZY_MIN_MARGIN = 0.1

BROKERS = ("unknown", "kis", "kiwoom", "toss", "mirae", "samsung", "nh", "overseas")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$")
_FIELD_LABELS = {
    "date": "날짜", "time": "시각", "name": "종목", "side": "구분",
    "shares": "수량", "price": "단가", "amount": "금액", "currency": "통화",
}


class RowError(Exception):
    def __init__(self, en: str, kr: str):
        super().__init__(en)
        self.en = en
        self.kr = kr


def rows_to_raw(rows) -> list[RawTrade]:
    """Validate the reviewed rows. Every row must be complete — the user
    filled the blanks before sending — so any gap is a 400, never a guess."""
    if not isinstance(rows, list) or not rows:
        raise RowError("rows must be a non-empty list.", "rows 는 비어 있지 않은 배열이어야 합니다.")
    if len(rows) > MAX_ROWS:
        raise RowError(f"rows exceeds {MAX_ROWS} entries.", f"rows 가 {MAX_ROWS}건을 넘습니다.")
    out: list[RawTrade] = []
    for i, item in enumerate(rows):
        label = f"rows[{i}]"
        if not isinstance(item, dict):
            raise RowError(f"{label} must be an object.", f"{label} 은(는) 객체여야 합니다.")
        name = mask_sensitive(str(item.get("name") or "").strip(), limit=100)
        code = str(item.get("code") or "").strip()[:20]
        if not name and not code:
            raise RowError(f"{label}: name or code is required.", f"{label}: 종목명 또는 코드가 필요합니다.")
        side = side_from_text(item.get("action"))
        if side is None:
            raise RowError(f"{label}.action must be buy or sell.", f"{label}.action 은 매수/매도 중 하나여야 합니다.")
        shares = parse_number(item.get("shares"))
        price = parse_number(item.get("price"))
        if not amount_ok(shares) or not amount_ok(price):
            raise RowError(f"{label}: shares and price must be numbers above 0.",
                           f"{label}: 수량과 단가는 0보다 큰 숫자여야 합니다.")
        currency = str(item.get("currency") or "").strip().upper()
        if currency not in ("KRW", "USD"):
            raise RowError(f"{label}.currency must be KRW or USD.", f"{label}.currency 는 KRW 또는 USD 여야 합니다.")
        if currency == "KRW" and float(shares) != int(shares):
            raise RowError(f"{label}: KRW shares must be whole.", f"{label}: 국내 주식 수량은 정수여야 합니다.")
        date_s = str(item.get("date") or "").strip()
        if not _DATE_RE.match(date_s):
            raise RowError(f"{label}.date must be YYYY-MM-DD.", f"{label}.date 는 YYYY-MM-DD 형식이어야 합니다.")
        time_s = str(item.get("time") or "").strip() or None
        if time_s is not None and not _TIME_RE.match(time_s):
            raise RowError(f"{label}.time must be HH:MM[:SS].", f"{label}.time 은 HH:MM[:SS] 형식이어야 합니다.")
        # Only Korea-time clocks are kept: ``_ingest`` shifts KST → UTC. A US
        # screen prints ET (DST-dependent), so its time is dropped rather
        # than converted by a guessed offset — the date stays.
        if str(item.get("tz") or "KST").upper() != "KST":
            time_s = None
        traded_at = parse_datetime(date_s, time_s)
        if traded_at is None:
            raise RowError(f"{label}.date is not a real date.", f"{label}.date 가 실제 날짜가 아닙니다.")

        typed = [f for f in (item.get("user_filled") or []) if f in _FIELD_LABELS]
        source_text = " ".join(str(item.get("source_text") or "").split())
        snippet = source_text[:220] or f"{name or code} {side} {shares:g} @ {price:g} {date_s}"
        if typed:
            snippet += " [직접 입력: " + "·".join(_FIELD_LABELS[f] for f in typed) + "]"
        out.append(RawTrade(
            name=name, code=code, action=side, shares=float(shares), price=float(price),
            currency=currency, traded_at=traded_at, confidence=HIGH_CONFIDENCE,
            raw_snippet=mask_sensitive(snippet), extra={"row": i + 1},
        ))
    return out


def known_kr_code(code: str, index: dict[str, str]) -> bool:
    """A 6-digit KRX code counts only if it is in the master — a comma-less
    price read off the screen ("372500") has the same shape."""
    bare = (code or "").split(".")[0]
    return bare in {t.split(".")[0] for t in index.values()}


_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"
# (min jamo ratio, min lead over the runner-up): a very close match may have
# a near neighbour ("삼성전자" / "삼성전자우"), a looser one must stand alone.
JAMO_RULES = ((0.80, 0.06), (0.70, 0.10))


def jamo(s: str) -> str:
    """Hangul syllables → their jamo ("뉴" → "ㄴㅠ"). OCR confuses glyphs
    that share most strokes (뉴/느, 워/위/표); syllable-level matching counts
    those as whole misses, jamo-level as one stroke off."""
    out = []
    for ch in s:
        c = ord(ch) - 0xAC00
        if 0 <= c < 11172:
            out += [_CHO[c // 588], _JUNG[(c % 588) // 28]]
            if c % 28:
                out.append(_JONG[c % 28])
        else:
            out.append(ch)
    return "".join(out)


def fuzzy_kr_ticker(name: str, index: dict[str, str]) -> tuple[str, str] | None:
    """Unique close match of an OCR-garbled Korean name in the master
    (``{종목명: ticker}``). Returns ``(ticker, master_name)`` or None.

    Needs a Hangul name of ≥2 characters, a ratio ≥ 0.75 and a clear margin
    over the runner-up; anything less stays unresolved (needs_ticker)."""
    key = re.sub(r"\s+", "", name or "")
    if len(key) < 2 or not re.search(r"[가-힣]", key):
        return None
    # A Latin prefix next to a round logo is where OCR fails ("SK하이닉스" →
    # "이하이닉스", "하이닉스"): one master name ending in the same last four
    # Hangul characters, and no other, is that stock.
    tail = key[-4:]
    if len(key) >= 4 and re.fullmatch(r"[가-힣]{4}", tail):
        ends = [cand for cand in index if cand.endswith(tail) and abs(len(cand) - len(key)) <= 3]
        if len(ends) == 1:
            return index[ends[0]], ends[0]
    scored = sorted(
        ((difflib.SequenceMatcher(None, key, cand).ratio(), cand) for cand in index
         if abs(len(cand) - len(key)) <= 3),
        reverse=True,
    )
    if scored and scored[0][0] >= FUZZY_MIN_RATIO and (len(scored) < 2 or scored[0][0] - scored[1][0] >= FUZZY_MIN_MARGIN):
        best = scored[0][1]
        return index[best], best
    # Stroke-level: compare jamo, ignoring OCR junk ("(", "=u") around the
    # name. Same unique-and-clear rule, a little stricter.
    # Hangul only: Latin letters in an OCR read are junk or a prefix the
    # strokes cannot vouch for ("XX전자" is not LG전자).
    hangul = re.sub(r"[^가-힣0-9]", "", key)
    if len(re.findall(r"[가-힣]", hangul)) < 3:
        return None
    kj = jamo(hangul)
    jscored = sorted(
        ((difflib.SequenceMatcher(None, kj, jamo(cand)).ratio(), cand) for cand in index
         if abs(len(cand) - len(hangul)) <= 3),
        reverse=True,
    )
    if not jscored:
        return None
    top, lead = jscored[0][0], jscored[0][0] - (jscored[1][0] if len(jscored) > 1 else 0)
    if not any(top >= r and lead >= m for r, m in JAMO_RULES):
        return None
    best = jscored[0][1]
    return index[best], best
