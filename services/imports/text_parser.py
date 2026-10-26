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

2026-10-13 bug hunt (≈190 broker-shaped lines, tests/test_text_parser_hunt.py):
토스증권 says 구매/판매 rather than 매수/매도; 주문번호/계좌 digits were read as a
6-digit KRX code; a 체결금액/정산금액 total was taken as the per-share price; a
partial fill took the ORDER quantity; "(약 262,000원)" after a $ price turned a
US fill into won; ads, holdings pushes and 예약 notices became trades.
"""
from __future__ import annotations

import re

from . import (
    RawTrade,
    mask_sensitive,
    meridiem_hour,
    parse_datetime_has_time,
    parse_number,
    today_naive,
)

_NUM = r"\d[\d,]*(?:\.\d+)?"

_SIDE_KR = re.compile(r"(매수|매도)")
# 토스증권's own words — "삼성전자 3주 구매 완료", "…에 판매했어요". Only with a
# completion word right after, so an ad's "구매하면 …" never becomes a side.
_SIDE_TOSS_DONE = re.compile(
    r"(구매|판매)\s*(?:완료|체결|했어요|했습니다|됐어요|되었어요|되었습니다)"
)
_SIDE_EN = re.compile(r"\b(bought|buy|sold|sell)\b", re.IGNORECASE)

_SHARES_KR = re.compile(rf"(?P<n>{_NUM})\s*주(?!문|식|가)")
# A partial fill quotes the order size first — "매수 10주 중 5주 체결",
# "주문수량 10주 체결수량 5주", "5/10주" — and the fill is the smaller one.
_SHARES_FILLED = (
    re.compile(rf"(?<!미)(?<!미\s)체결\s*수량\s*:?\s*(?P<n>{_NUM})"),
    re.compile(rf"{_NUM}\s*주\s*중\s*(?P<n>{_NUM})\s*주"),
    re.compile(rf"(?<![\d/])(?P<n>{_NUM})\s*/\s*{_NUM}\s*주"),
)
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
# Not inside a dashed number — any dash a phone hands back, not just "-"
# ("123—45—678901" gave code 678901, 2026-10-13).
_CODE_KR = re.compile(r"(?<![\d\-\u2013\u2014\u2212\u2011_*])(?P<code>\d{6})(?:\.(?:KS|KQ))?(?![\d\-\u2013\u2014\u2212\u2011_*])")
# Labelled ID numbers are never the security: "주문번호 123456" was read as KRX
# code 123456 and beat the Hangul name (2026-10-13). Dropped before parsing.
_ID_FIELD = re.compile(
    # "No." / "No:" only — a bare "NO 5" is the tail of a ticker ("CNO 5주")
    r"(?:원?주문\s*번호|체결\s*번호|계좌\s*번호|계좌|\bNo\.|\bNo(?=\s*[:#]))\s*[:#.]?\s*[\dXx*][\dXx*\-\u2013\u2014\u2212\u2011_]*",
    re.IGNORECASE,
)

_PRICE_LABELLED = re.compile(
    rf"(?:체결단가|체결가격|체결가|단가|평균단가|가격|@|\bat)\s*:?\s*\$?(?P<p>{_NUM})", re.IGNORECASE
)
_PRICE_WON = re.compile(rf"(?P<p>{_NUM})\s*원")
_PRICE_USD = re.compile(rf"\$\s*(?P<p>{_NUM})")
# "118.5달러", "250.00 USD" — Korean broker apps spell the dollar out.
_PRICE_DOLLAR_WORD = re.compile(rf"(?P<p>{_NUM})\s*(?:달러|USD|불)\b")
_USD_MARK = re.compile(r"\$|달러|\bUSD\b")
# A won amount ("71,200원", "₩71,200") — not just any 원 ("하나원큐", "회원").
_KRW_MARK = re.compile(r"₩|\d\s*원|\bKRW\b")
_AMOUNT_LABELLED = re.compile(
    rf"(?:체결금액|거래금액|매매금액|정산금액|결제금액|총\s*금액|총액|(?<![가-힣])총|금액|total)\s*:?\s*\$?(?P<p>{_NUM})",
    re.IGNORECASE,
)
# Won amounts that are never the per-share price: a labelled total, a fee or
# tax, an FX rate, or the "(약 262,000원)" won equivalent of a dollar fill.
_WON_NOT_PRICE = re.compile(
    # 약 only as a word ("약 262,000원"), not the end of a name ("삼성제약 15,000원")
    rf"(?:체결금액|거래금액|매매금액|정산금액|결제금액|총\s*금액|총액|(?<![가-힣])총|합계|금액|수수료|제세금|세금|환율|원화\s*환산|원화|(?<![가-힣])약)"
    rf"\s*:?\s*₩?\s*{_NUM}\s*원"
    rf"|\(\s*약\s*₩?\s*{_NUM}\s*원\s*\)"
)
# For the currency call on a line that already has a dollar mark, any
# bracketed won figure is the equivalent ("190.12 USD (261,500원)").
_WON_EQUIV = re.compile(rf"{_WON_NOT_PRICE.pattern}|\(\s*₩?\s*{_NUM}\s*원\s*\)")

_DATE_ANY = re.compile(
    r"(\d{4}[-./]\d{1,2}[-./]\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?"
    r"|(?<!\d)\d{8}(?:[ T]?\d{1,2}:\d{2}(?::\d{2})?)?(?!\d)"
    r"|\d{1,2}월\s*\d{1,2}일(?:\s*\d{1,2}:\d{2}(?::\d{2})?)?"
    r"|(?<!\d)\d{1,2}/\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?(?![\d/]|\s*주))"
)
_TIME_ONLY = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?::(\d{2}))?(?![\d:])")

_KEYWORDS = {
    "매수", "매도", "체결", "알림", "주문", "단가", "체결단가", "체결가", "가격", "금액",
    "체결금액", "수량", "완료", "되었습니다", "체결되었습니다", "계좌", "종목", "국내",
    "해외", "주식", "정정", "취소", "총", "원", "주", "건", "시장가", "지정가",
    # compounds broker apps emit as one token — never the security name
    "해외주식", "국내주식", "미국주식", "해외주식체결", "체결통보", "체결알림", "매수체결", "매도체결",
    "달러", "미체결", "미체결수량", "잔량", "체결수량", "체결시간", "체결일시",
    "구매", "판매", "구매완료", "판매완료", "구매했어요", "판매했어요", "주당",
    "체결안내", "주문체결", "체결확인", "정산금액", "총액",
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
    r"|예약|전송|정상\s*처리"
)
# Holdings / balance pushes carry 매수 + N주 + 원 too ("10주 보유 중 · 매수
# 평균가 70,000원"). Like an order notice, only when the line has no fill word.
_HOLDING_NOTICE_KR = re.compile(
    r"보유\s*중|보유\s*수량|평가\s*손익|평가\s*금액|수익률|(?:매수|매도|주문)\s*가능|가능\s*수량"
)
# Ads are never fills, whatever else the line says ("(광고) … 1주 매수하면
# 10,000원 혜택"). Korean law makes "(광고)" the first word of an ad SMS.
_PROMO_KR = re.compile(r"광고|혜택|이벤트|쿠폰|프로모션|하면\s|하시면|해\s*보세요|받으세요")
_FILL_WORD_EN = re.compile(r"\b(?:filled|fill|executed|execution|bought|sold)\b", re.IGNORECASE)
_ORDER_NOTICE_EN = re.compile(
    r"\b(?:cancel(?:l)?ed|cancellation|placed|accepted|received|submitted|modified|replaced|"
    r"rejected|expired|open\s+order|pending|unfilled|working\s+order)\b",
    re.IGNORECASE,
)

_SKIP_UNFILLED = "미체결 알림 (체결 아님)"
_SKIP_REVERSAL = "체결 취소 알림 (기록할 체결 아님)"
_SKIP_ORDER_NOTICE = "주문 접수·정정·취소 알림 (체결 아님)"
_SKIP_HOLDING = "보유·잔고 안내 (체결 아님)"
_SKIP_PROMO = "광고·안내 알림 (체결 아님)"


def _non_fill_reason(line: str) -> str | None:
    """Return a skip reason when the line is an order notice rather than a fill."""
    stripped = _UNFILLED_FIELD.sub(" ", line)
    if _PROMO_KR.search(line):
        return _SKIP_PROMO
    if _UNFILLED_KR.search(stripped):
        return _SKIP_UNFILLED
    if _FILL_REVERSAL_KR.search(line):
        return _SKIP_REVERSAL
    has_fill = bool(
        _FILL_WORD_KR.search(stripped) or _FILL_WORD_EN.search(line) or _SIDE_TOSS_DONE.search(line)
    )
    if has_fill:
        return None
    if _ORDER_NOTICE_KR.search(line) or _ORDER_NOTICE_EN.search(line):
        return _SKIP_ORDER_NOTICE
    if _HOLDING_NOTICE_KR.search(line):
        return _SKIP_HOLDING
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
    line = _ID_FIELD.sub(" ", line)
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
        m = _filled_shares(line)
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
    # stocks under Korean names ("애플 3주 매수 체결 $190.12"). A won figure
    # that is only the dollar fill's equivalent, a total or the FX rate
    # ("$190.12 (약 262,000원)", "환율 1,380원") does not make it a won fill.
    won_line = _WON_EQUIV.sub(" ", line) if _USD_MARK.search(line) else line
    if _USD_MARK.search(line) and "원" not in won_line and "₩" not in won_line:
        t.currency = "USD"
    elif "원" in line or "₩" in line:
        t.currency, t.currency_guessed = "KRW", not _KRW_MARK.search(line)
    elif re.fullmatch(r"\d{6}", t.code or ""):
        t.currency, t.currency_guessed = "KRW", True
    elif t.code:
        t.currency, t.currency_guessed = "USD", True
    elif t.name and _HANGUL.search(t.name):
        t.currency, t.currency_guessed = "KRW", True

    dt, t.time_given = _date(line)
    if dt is None:
        t.traded_at = today_naive()
        t.confidence = 0.6
    else:
        t.traded_at = dt
        t.confidence = 0.9
    if from_amount:
        t.confidence = round(t.confidence - 0.1, 2)
    return t


def _filled_shares(line: str):
    """The filled quantity's match: a partial-fill shape first, else the
    first "N주"."""
    for rx in _SHARES_FILLED:
        m = rx.search(line)
        if m:
            return m
    return _SHARES_KR.search(line)


def _side(line: str) -> str | None:
    m = _SIDE_KR.search(line)
    if m:
        return "BUY" if m.group(1) == "매수" else "SELL"  # // legal-ok — trade action data value, not user copy
    m = _SIDE_TOSS_DONE.search(line)
    if m:
        return "BUY" if m.group(1) == "구매" else "SELL"  # // legal-ok — trade action data value, not user copy
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
    won = [parse_number(x.group("p")) for x in _PRICE_WON.finditer(_WON_NOT_PRICE.sub(" ", line))]
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
    """``(datetime, time_given)`` for the line, ``(None, False)`` without a
    date or time. ``time_given`` says a time was printed — a 09:00 fill reads
    00:00 UTC once shifted, so 00:00 cannot tell (services.imports.kst_to_utc)."""
    m = _DATE_ANY.search(line)
    if not m:
        # Time only ("09:31 삼성전자 10주 매수 체결 71,200원"): today (KST) at
        # that time. Dropping the time collapsed every same-day partial fill
        # onto 00:00 and the second one was flagged a duplicate.
        tm = _TIME_ONLY.search(line)
        if tm:
            h, mi = int(tm.group(1)), int(tm.group(2))
            if h < 24 and mi < 60:
                h = meridiem_hour(line, tm.start(), tm.end(), h)
                return today_naive().replace(hour=h, minute=mi, second=int(tm.group(3) or 0)), True
        return None, False
    s = m.group(1)
    if re.fullmatch(r"\d{1,2}/\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?", s):
        # MM/DD [HH:MM] → current year
        mm, rest = s.split("/", 1)
        dd = rest.split()[0]
        s = f"{today_naive().year}-{int(mm):02d}-{int(dd):02d}" + (" " + rest.split()[1] if " " in rest else "")
    dt, has_time = parse_datetime_has_time(s)
    if dt is None:
        return None, False
    if not has_time:
        rest = line.replace(s, " ")
        tm = _TIME_ONLY.search(rest)
        if tm:
            h, mi = int(tm.group(1)), int(tm.group(2))
            if h < 24 and mi < 60:
                h = meridiem_hour(rest, tm.start(), tm.end(), h)
                dt = dt.replace(hour=h, minute=mi, second=int(tm.group(3) or 0))
                has_time = True
    else:
        # "2026-09-01 2:05 PM" — the date pattern took "2:05"; the marker is after it.
        dt = dt.replace(hour=meridiem_hour(line, m.start(1), m.end(1), dt.hour))
    return dt, has_time


# Push notifications are usually prefixed with the sender — "[키움증권]",
# "토스증권 알림" — and every big broker is itself a listed company, so the
# first Hangul token must not be taken as the security.
_BROKER_WORDS = {
    "키움", "키움증권", "한투", "한국투자", "한국투자증권", "토스", "토스증권", "삼성증권",
    "미래에셋", "미래에셋증권", "NH투자증권", "KB증권", "신한투자증권", "대신증권",
    "하나증권", "메리츠증권", "유안타증권", "카카오페이증권", "체결통보", "체결알림",
    # the broker apps' own names lead their pushes too ("[NH투자증권] 나무 …")
    "나무", "영웅문", "영웅문S", "신한알파", "엠스톡", "엠팝", "마블", "체결안내", "주문체결",
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
        # a keyword with a particle glued on ("주문이", "체결이") is still vocabulary
        if len(cleaned) > 1 and cleaned[-1] in "이가은는을를" and cleaned[:-1] in _KEYWORDS:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?(?:원|주|건|달러)?", cleaned):
            continue
        if cleaned in _BROKER_WORDS or cleaned.endswith("증권"):
            continue
        # strip trailing particles/keywords glued to the name ("삼성전자를").
        # Not 이/가: they end real names (카카오페이, LG디스플레이, 나무가) —
        # "카카오페이" came out "카카오페" and never matched (2026-10-13). A
        # glued subject particle is tried by the resolver instead.
        for suffix in ("체결", "매수", "매도", "구매", "판매", "을", "를"):
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
        if cleaned.endswith("증권") or _SIDE_KR.fullmatch(cleaned) or _SIDE_EN.fullmatch(cleaned) or cleaned in ("구매", "판매"):
            continue
        if _NOISE_TOKEN.fullmatch(cleaned):
            continue
        keep.append(cleaned)
    return " ".join(keep)[:100]


__all__ = ["parse_text"]
