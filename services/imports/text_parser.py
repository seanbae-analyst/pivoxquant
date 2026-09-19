"""Fill-notification text parser (screenshot → device OCR → paste).

One fill per line. Recognised shapes (design §파서):

KR  ``삼성전자 10주 매수 체결 71,200원``
    ``매수 체결 삼성전자 10주 @ 71,200원``
    ``[체결] 삼성전자 매도 5주 체결단가 71,200원 09/01 10:32``
US  ``Bought 5 AAPL @ $190.12``
    ``Sold 3 TSLA @ 250.00 2026-09-01 14:05``
    ``매수 5주 AAPL 190.12``

No date on the line → today (UTC, 00:00) and confidence 0.6. Lines that
do not contain a fill are returned with ``skip_reason`` so the route can
tell the user which lines it could not read.

Order-lifecycle notices are not fills. A broker app pushes "주문이 접수되었습니다",
"정정 주문 완료", "주문 취소", "미체결", "Order placed", "cancelled" with the
same 매수/N주/원 vocabulary as a fill, and with the webhook path every
notification the user's macro matches arrives here unread. Those lines are
skipped before any parsing (``_non_fill_reason``); a line that says 체결 /
filled / executed is still a fill even if it also says 정정 (a modified order
that then filled), except "체결 취소" (a fill reversal).
"""
from __future__ import annotations

import re

from . import (
    RawTrade,
    mask_sensitive,
    parse_datetime,
    parse_number,
    today_naive,
)

_NUM = r"\d[\d,]*(?:\.\d+)?"

_SIDE_KR = re.compile(r"(매수|매도)")
_SIDE_EN = re.compile(r"\b(bought|buy|sold|sell)\b", re.IGNORECASE)

_SHARES_KR = re.compile(rf"(?P<n>{_NUM})\s*주(?!문|식|가)")
# "Bought 5 AAPL", "매수 5주 AAPL", "Sold 3 shares TSLA", "Bought 5 shares of AAPL"
_US_FILL = re.compile(
    rf"(?:bought|buy|sold|sell|매수|매도)\s+(?P<n>{_NUM})\s*(?:주|shares?)?\s*(?:of\s+)?"
    r"(?P<code>(?-i:[A-Z]{1,6}(?:[.\-][A-Z]{1,2})?))\b",
    re.IGNORECASE,
)
# KIS 해외주식 체결통보 word order: "TSLA 매도 2주 체결단가 250.00 USD"
_US_CODE_FIRST = re.compile(
    rf"\b(?P<code>[A-Z]{{1,6}}(?:[.\-][A-Z]{{1,2}})?)\s+(?:매수|매도|bought|sold|buy|sell)\s*(?:체결)?\s*"
    rf"(?P<n>{_NUM})\s*(?:주|shares?)\b",
    re.IGNORECASE,
)
# "5 AAPL @ 190.12" without a verb
_US_QTY_CODE = re.compile(
    rf"(?P<n>{_NUM})\s*(?:주|shares?)\s+(?P<code>[A-Z]{{1,6}}(?:[.\-][A-Z]{{1,2}})?)\b"
)
# "NVDA 5주 매수 체결 118.5달러" — code, then the quantity
_US_CODE_QTY = re.compile(
    rf"\b(?P<code>[A-Z]{{1,6}}(?:[.\-][A-Z]{{1,2}})?)\s+(?P<n>{_NUM})\s*(?:주|shares?)\b"
)
_CODE_KR = re.compile(r"(?<!\d)(?P<code>\d{6})(?:\.(?:KS|KQ))?(?!\d)")

_PRICE_LABELLED = re.compile(
    rf"(?:체결단가|체결가격|체결가|단가|평균단가|가격|@|\bat)\s*:?\s*\$?(?P<p>{_NUM})", re.IGNORECASE
)
_PRICE_WON = re.compile(rf"(?P<p>{_NUM})\s*원")
_PRICE_USD = re.compile(rf"\$\s*(?P<p>{_NUM})")
# "118.5달러", "250.00 USD" — Korean broker apps spell the dollar out.
_PRICE_DOLLAR_WORD = re.compile(rf"(?P<p>{_NUM})\s*(?:달러|USD|불)\b")
_USD_MARK = re.compile(r"\$|달러|\bUSD\b")
_AMOUNT_LABELLED = re.compile(rf"(?:체결금액|거래금액|매매금액|금액|total)\s*:?\s*\$?(?P<p>{_NUM})", re.IGNORECASE)

_DATE_ANY = re.compile(
    r"(\d{4}[-./]\d{1,2}[-./]\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?"
    r"|(?<!\d)\d{8}(?:[ T]?\d{1,2}:\d{2}(?::\d{2})?)?(?!\d)"
    r"|\d{1,2}월\s*\d{1,2}일(?:\s*\d{1,2}:\d{2}(?::\d{2})?)?"
    r"|(?<!\d)\d{1,2}/\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?(?![\d/]))"
)
_TIME_ONLY = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?::(\d{2}))?(?![\d:])")

_KEYWORDS = {
    "매수", "매도", "체결", "알림", "주문", "단가", "체결단가", "체결가", "가격", "금액",
    "체결금액", "수량", "완료", "되었습니다", "체결되었습니다", "계좌", "종목", "국내",
    "해외", "주식", "정정", "취소", "총", "원", "주", "건", "시장가", "지정가",
    # compounds broker apps emit as one token — never the security name
    "해외주식", "국내주식", "미국주식", "해외주식체결", "체결통보", "체결알림", "매수체결", "매도체결",
    "달러", "미체결", "미체결수량", "잔량", "체결수량", "체결시간", "체결일시",
}
_TOKEN = re.compile(r"[A-Za-z0-9가-힣&+\-.]+")
_HANGUL = re.compile(r"[가-힣]")

# ── order-lifecycle notices (not fills) ─────────────────────────────
# "미체결" and "체결 취소" are decisive on their own. The rest only count when
# the line has no fill word at all — "정정 주문이 체결되었습니다" is a fill.
# A fill push often reports the unfilled remainder on the same line
# ("매수체결 10주 71,200원 미체결수량 0", "(잔량/미체결 0)"): that field is
# stripped before the test, so only a bare 미체결 notice is skipped. The
# remainder is a count, so the 주 unit is optional — but the number has to be
# whole and must not carry a Korean unit, or the price in a real 미체결 notice
# ("매수 미체결 71,200원") would be eaten and the notice read as a fill.
_UNFILLED_QTY = r"\d[\d,]*(?![\d,])\s*주?(?![가-힣])"
_UNFILLED_FIELD = re.compile(
    # 미체결수량 0 · (미체결 0) · 잔량/미체결 0주
    rf"(?:잔량\s*[/·]?\s*)?미\s*체결\s*(?:수량|잔량)?\s*:?\s*{_UNFILLED_QTY}"
    rf"|잔량\s*:?\s*{_UNFILLED_QTY}"                     # 잔량 0
)
_UNFILLED_KR = re.compile(r"미\s*체결")
_FILL_REVERSAL_KR = re.compile(r"체결\s*취소")
_FILL_WORD_KR = re.compile(r"(?<!미)체결")
_ORDER_NOTICE_KR = re.compile(
    r"접수|정정|취소|거부|만료|주문\s*완료|주문이\s*완료|주문\s*확인|주문이\s*확인|주문\s*내역|주문\s*(?:을|이)?\s*(?:냈|넣)"
)
_FILL_WORD_EN = re.compile(r"\b(?:filled|fill|executed|execution|bought|sold)\b", re.IGNORECASE)
_ORDER_NOTICE_EN = re.compile(
    r"\b(?:cancel(?:l)?ed|cancellation|placed|accepted|received|submitted|modified|replaced|"
    r"rejected|expired|open\s+order|pending|unfilled|working\s+order)\b",
    re.IGNORECASE,
)

_SKIP_UNFILLED = "미체결 알림 (체결 아님)"
_SKIP_REVERSAL = "체결 취소 알림 (기록할 체결 아님)"
_SKIP_ORDER_NOTICE = "주문 접수·정정·취소 알림 (체결 아님)"


def _non_fill_reason(line: str) -> str | None:
    """Return a skip reason when the line is an order notice rather than a fill."""
    stripped = _UNFILLED_FIELD.sub(" ", line)
    if _UNFILLED_KR.search(stripped):
        return _SKIP_UNFILLED
    if _FILL_REVERSAL_KR.search(line):
        return _SKIP_REVERSAL
    has_fill = bool(_FILL_WORD_KR.search(stripped) or _FILL_WORD_EN.search(line))
    if has_fill:
        return None
    if _ORDER_NOTICE_KR.search(line) or _ORDER_NOTICE_EN.search(line):
        return _SKIP_ORDER_NOTICE
    return None


def parse_text(text: str) -> list[RawTrade]:
    out: list[RawTrade] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        t = _parse_line(line)
        t.raw_snippet = mask_sensitive(line)
        out.append(t)
    return out


def _parse_line(line: str) -> RawTrade:
    t = RawTrade()
    notice = _non_fill_reason(line)
    if notice:
        t.skip_reason = notice
        return t
    side = _side(line)
    if side is None:
        t.skip_reason = "매수/매도 표시 없음"
        return t
    t.action = side

    us = _US_FILL.search(line) or _US_CODE_FIRST.search(line)
    if us and not _HANGUL.search(us.group("code")):
        t.shares = parse_number(us.group("n")) or 0.0
        t.code = us.group("code").upper()
    else:
        m = _SHARES_KR.search(line)
        if m:
            t.shares = parse_number(m.group("n")) or 0.0
            cq = _US_CODE_QTY.search(line)
            if cq and cq.group("n") == m.group("n"):
                t.code = cq.group("code").upper()
        else:
            m2 = _US_QTY_CODE.search(line)
            if m2:
                t.shares = parse_number(m2.group("n")) or 0.0
                t.code = m2.group("code").upper()
        if not t.code:
            kr = _CODE_KR.search(line)
            if kr:
                t.code = kr.group("code")
    if t.shares <= 0:
        t.skip_reason = "수량 미인식"
        return t

    if not t.code:
        t.name = _kr_name(line)
        if not t.name:
            us_code = _US_QTY_CODE.search(line)
            if us_code:
                t.code = us_code.group("code").upper()
            else:
                # "KODEX 200 20주 …", "TIGER 미국S&P500 10주 …" — the security
                # is the text before the quantity, and it is not Hangul-only.
                t.name = _leading_name(line)
    if not t.name and not t.code:
        t.skip_reason = "종목 미인식"
        return t

    price, from_amount = _price(line, t.shares)
    if price is None:
        t.skip_reason = "단가 미인식"
        return t
    t.price = price

    # An explicit money mark wins over the name's script: 토스 shows US
    # stocks under Korean names ("애플 3주 매수 체결 $190.12").
    if _USD_MARK.search(line) and "원" not in line and "₩" not in line:
        t.currency = "USD"
    elif "원" in line or "₩" in line or re.fullmatch(r"\d{6}", t.code or ""):
        t.currency = "KRW"
    elif t.code:
        t.currency = "USD"
    elif t.name and _HANGUL.search(t.name):
        t.currency = "KRW"

    dt = _date(line)
    if dt is None:
        t.traded_at = today_naive()
        t.confidence = 0.6
    else:
        t.traded_at = dt
        t.confidence = 0.9
    if from_amount:
        t.confidence = round(t.confidence - 0.1, 2)
    return t


def _side(line: str) -> str | None:
    m = _SIDE_KR.search(line)
    if m:
        return "BUY" if m.group(1) == "매수" else "SELL"  # // legal-ok — trade action data value, not user copy
    m = _SIDE_EN.search(line)
    if m:
        return "BUY" if m.group(1).lower() in ("bought", "buy") else "SELL"  # // legal-ok — trade action data value, not user copy
    return None


def _price(line: str, shares: float) -> tuple[float | None, bool]:
    m = _PRICE_LABELLED.search(line)
    if m:
        p = parse_number(m.group("p"))
        if p and p > 0:
            return p, False
    m = _PRICE_USD.search(line) or _PRICE_DOLLAR_WORD.search(line)
    if m:
        p = parse_number(m.group("p"))
        if p and p > 0:
            return p, False
    won = [parse_number(x.group("p")) for x in _PRICE_WON.finditer(line)]
    won = [w for w in won if w and w > 0]
    if won:
        # "10주 ... 71,200원 ... 712,000원": prefer the value that is not
        # shares×another value (i.e. the per-share one).
        if len(won) >= 2 and shares:
            for cand in won:
                if any(abs(cand * shares - other) < 1e-6 for other in won if other != cand):
                    return cand, False
        return won[0], False
    m = _AMOUNT_LABELLED.search(line)
    if m and shares:
        p = parse_number(m.group("p"))
        if p and p > 0:
            return p / shares, True
    # Last resort: a bare number after the ticker (``매수 5주 AAPL 190.12``)
    tail = re.search(rf"\b[A-Z]{{1,6}}(?:[.\-][A-Z]{{1,2}})?\s+\$?(?P<p>{_NUM})(?!\s*주)", line)
    if tail:
        p = parse_number(tail.group("p"))
        if p and p > 0:
            return p, False
    return None, False


def _date(line: str):
    m = _DATE_ANY.search(line)
    if not m:
        # Time only ("09:31 삼성전자 10주 매수 체결 71,200원"): today (KST) at
        # that time. Dropping the time collapsed every same-day partial fill
        # onto 00:00 and the second one was flagged a duplicate.
        tm = _TIME_ONLY.search(line)
        if tm:
            h, mi = int(tm.group(1)), int(tm.group(2))
            if h < 24 and mi < 60:
                return today_naive().replace(hour=h, minute=mi, second=int(tm.group(3) or 0))
        return None
    s = m.group(1)
    if re.fullmatch(r"\d{1,2}/\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?", s):
        # MM/DD [HH:MM] → current year
        mm, rest = s.split("/", 1)
        dd = rest.split()[0]
        s = f"{today_naive().year}-{int(mm):02d}-{int(dd):02d}" + (" " + rest.split()[1] if " " in rest else "")
    dt = parse_datetime(s)
    if dt is None:
        return None
    if dt.hour == 0 and dt.minute == 0:
        tm = _TIME_ONLY.search(line.replace(s, " "))
        if tm:
            h, mi = int(tm.group(1)), int(tm.group(2))
            if h < 24 and mi < 60:
                dt = dt.replace(hour=h, minute=mi, second=int(tm.group(3) or 0))
    return dt


# Push notifications are usually prefixed with the sender — "[키움증권]",
# "토스증권 알림" — and every big broker is itself a listed company, so the
# first Hangul token must not be taken as the security.
_BROKER_WORDS = {
    "키움", "키움증권", "한투", "한국투자", "한국투자증권", "토스", "토스증권", "삼성증권",
    "미래에셋", "미래에셋증권", "NH투자증권", "KB증권", "신한투자증권", "대신증권",
    "하나증권", "메리츠증권", "유안타증권", "카카오페이증권", "체결통보", "체결알림",
}
_BRACKETED = re.compile(r"[\[\(【][^\]\)】]*[\]\)】]")


def _kr_name(line: str) -> str:
    line = _BRACKETED.sub(" ", line)
    # "35,000원" must not split into "35" + "000원" and hand back "000원" as the name.
    line = re.sub(r"(?<=\d),(?=\d{3})", "", line)
    for tok in _TOKEN.findall(line):
        if not _HANGUL.search(tok):
            continue
        cleaned = tok.strip("-.")
        if cleaned in _KEYWORDS or not cleaned:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?(?:원|주|건|달러)?", cleaned):
            continue
        if cleaned in _BROKER_WORDS or cleaned.endswith("증권"):
            continue
        # strip trailing particles/keywords glued to the name ("삼성전자를")
        for suffix in ("체결", "매수", "매도", "을", "를", "이", "가"):
            if cleaned.endswith(suffix) and len(cleaned) > len(suffix) + 1:
                cleaned = cleaned[: -len(suffix)]
                break
        if cleaned in _KEYWORDS:
            continue
        if _SHARES_KR.fullmatch(cleaned):
            continue
        return cleaned
    return ""


_NOISE_TOKEN = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?|[\d/.\-:]+")


def _leading_name(line: str) -> str:
    """Last resort when no Hangul name and no ticker was found: the tokens
    before the quantity, minus broker prefixes and vocabulary."""
    m = _SHARES_KR.search(line)
    if not m:
        return ""
    head = _BRACKETED.sub(" ", line[: m.start()])
    keep: list[str] = []
    for tok in _TOKEN.findall(head):
        cleaned = tok.strip("-.")
        if not cleaned or cleaned in _KEYWORDS or cleaned in _BROKER_WORDS:
            continue
        if cleaned.endswith("증권") or _SIDE_KR.fullmatch(cleaned) or _SIDE_EN.fullmatch(cleaned):
            continue
        if _NOISE_TOKEN.fullmatch(cleaned):
            continue
        keep.append(cleaned)
    return " ".join(keep)[:100]


__all__ = ["parse_text"]
