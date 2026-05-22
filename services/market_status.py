"""
PivoxQuant — Market Status (KST 기준)

장 거래 가능 시간 + 다음 이벤트 시각 계산.
US (NYSE) + KR (KOSPI/KOSDAQ).
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
ET = ZoneInfo("America/New_York")  # auto-handles DST

# Status codes
S_REGULAR = "regular"
S_PRE = "pre_market"
S_AFTER = "after_hours"
S_CLOSED = "closed"

LABELS_US = {
    S_REGULAR: "정규장",
    S_PRE: "Pre-market",
    S_AFTER: "After-hours",
    S_CLOSED: "장 마감",
}
LABELS_KR = {
    S_REGULAR: "정규장",
    S_PRE: "장 시작 전",
    S_AFTER: "시간외 거래",
    S_CLOSED: "장 마감",
}

# US schedule (Eastern Time)
US_PRE_OPEN = time(4, 0)
US_REG_OPEN = time(9, 30)
US_REG_CLOSE = time(16, 0)
US_AFTER_CLOSE = time(20, 0)

# KR schedule (KST)
KR_PRE_OPEN = time(8, 0)
KR_REG_OPEN = time(9, 0)
KR_REG_CLOSE = time(15, 30)
KR_AFTER_OPEN = time(15, 40)
KR_AFTER_CLOSE = time(18, 0)

# KR market holidays (KRX 휴장일).
# 거래소 공식 휴장일 — 공휴일 + 대체공휴일 + 임시휴장.
# 갱신: 매년 12월 KRX 발표 후 다음 연도 추가.
# Format: (year, month, day) -> 사유 (Korean).
KR_HOLIDAYS = {
    # 2026
    (2026, 1, 1): "신정",
    (2026, 2, 16): "설날 연휴",
    (2026, 2, 17): "설날",
    (2026, 2, 18): "설날 연휴",
    (2026, 3, 1): "삼일절",
    (2026, 3, 2): "삼일절 대체공휴일",  # 삼일절이 일요일
    (2026, 5, 5): "어린이날",
    (2026, 5, 15): "부처님오신날",  # 정확한 음력 4월 8일
    (2026, 6, 3): "공직선거",  # 21대 대선 (가능성)
    (2026, 6, 6): "현충일",
    (2026, 8, 15): "광복절",
    (2026, 8, 17): "광복절 대체공휴일",  # 광복절이 토요일
    (2026, 9, 24): "추석 연휴",
    (2026, 9, 25): "추석",
    (2026, 9, 26): "추석 연휴",
    (2026, 9, 28): "추석 대체공휴일",  # 9/26이 토요일이라 월요일 대체
    (2026, 10, 3): "개천절",
    (2026, 10, 5): "개천절 대체공휴일",  # 개천절이 토요일
    (2026, 10, 9): "한글날",
    (2026, 12, 25): "성탄절",
    (2026, 12, 31): "연말 휴장",
    # 2027 (잠정 — 공식 발표 전)
    (2027, 1, 1): "신정",
    (2027, 2, 5): "설날 연휴",
    (2027, 2, 8): "설날",
    (2027, 2, 9): "설날 연휴",
    (2027, 3, 1): "삼일절",
    (2027, 5, 5): "어린이날",
    (2027, 5, 13): "부처님오신날",  # 음력 4월 8일 (잠정)
    (2027, 6, 7): "현충일 대체공휴일",  # 현충일(6/6)이 일요일
    (2027, 8, 16): "광복절 대체공휴일",  # 광복절(8/15)이 일요일
    (2027, 9, 14): "추석 연휴",
    (2027, 9, 15): "추석",
    (2027, 9, 16): "추석 연휴",
    (2027, 10, 4): "개천절 대체공휴일",  # 개천절(10/3)이 일요일
    (2027, 10, 11): "한글날 대체공휴일",  # 한글날(10/9)이 토요일
    (2027, 12, 25): "성탄절",
    (2027, 12, 31): "연말 휴장",
}


# US (NYSE) full-closure holidays.
# Source: NYSE official holiday calendar (nyse.com/markets/hours-calendars).
# Coverage: 2026 + 2027. Dates are the OBSERVED dates the exchange is fully
# closed (when a fixed holiday falls on Sat → observed Fri; on Sun → observed
# Mon). Good Friday is included (NYSE closes) though it is not a federal
# holiday. Early-close half-days (e.g. day after Thanksgiving, Christmas Eve)
# are NOT listed here — the market is still open/tradable on those.
# 갱신: 매년 NYSE 발표 후 다음 연도 추가.
# Format: (year, month, day) -> reason.
US_HOLIDAYS = {
    # 2026
    (2026, 1, 1): "New Year's Day",
    (2026, 1, 19): "Martin Luther King Jr. Day",
    (2026, 2, 16): "Washington's Birthday (Presidents' Day)",
    (2026, 4, 3): "Good Friday",
    (2026, 5, 25): "Memorial Day",
    (2026, 6, 19): "Juneteenth National Independence Day",
    (2026, 7, 3): "Independence Day (observed, Jul 4 = Sat)",
    (2026, 9, 7): "Labor Day",
    (2026, 11, 26): "Thanksgiving Day",
    (2026, 12, 25): "Christmas Day",
    # 2027
    (2027, 1, 1): "New Year's Day",
    (2027, 1, 18): "Martin Luther King Jr. Day",
    (2027, 2, 15): "Washington's Birthday (Presidents' Day)",
    (2027, 3, 26): "Good Friday",
    (2027, 5, 31): "Memorial Day",
    (2027, 6, 18): "Juneteenth (observed, Jun 19 = Sat)",
    (2027, 7, 5): "Independence Day (observed, Jul 4 = Sun)",
    (2027, 9, 6): "Labor Day",
    (2027, 11, 25): "Thanksgiving Day",
    (2027, 12, 24): "Christmas Day (observed, Dec 25 = Sat)",
}


def is_us_holiday(dt: datetime) -> tuple[bool, str]:
    """Return (is_holiday, reason). dt는 ET(America/New_York) 기준이어야 함."""
    key = (dt.year, dt.month, dt.day)
    if key in US_HOLIDAYS:
        return True, US_HOLIDAYS[key]
    return False, ""


def is_kr_holiday(dt: datetime) -> tuple[bool, str]:
    """Return (is_holiday, reason). dt는 KST 기준이어야 함."""
    key = (dt.year, dt.month, dt.day)
    if key in KR_HOLIDAYS:
        return True, KR_HOLIDAYS[key]
    return False, ""


def _next_kr_trading_day(dt: datetime) -> datetime:
    """Return the next KR trading day (skip weekends + holidays). dt는 KST."""
    candidate = dt + timedelta(days=1)
    # Cap to 14 days lookahead to avoid infinite loops on bad data.
    for _ in range(14):
        if candidate.weekday() < 5 and not is_kr_holiday(candidate)[0]:
            return candidate
        candidate += timedelta(days=1)
    return candidate


def _next_us_trading_day(dt: datetime) -> datetime:
    """Return the next US trading day (skip weekends + holidays). dt는 ET."""
    candidate = dt + timedelta(days=1)
    # Cap to 14 days lookahead to avoid infinite loops on bad data.
    for _ in range(14):
        if candidate.weekday() < 5 and not is_us_holiday(candidate)[0]:
            return candidate
        candidate += timedelta(days=1)
    return candidate


def _to_kst_str(dt: datetime) -> str:
    return dt.astimezone(KST).strftime("%H:%M")


def _us_status_now() -> dict:
    now_et = datetime.now(ET)
    weekday = now_et.weekday()  # 0=Mon, 6=Sun
    t = now_et.time()
    today_et = now_et.replace(hour=0, minute=0, second=0, microsecond=0)

    # Holiday check (highest priority — overrides time-of-day status).
    # Mirrors the KR holiday handling in _kr_status_now.
    is_hol, hol_reason = is_us_holiday(now_et)
    if is_hol:
        next_trading = _next_us_trading_day(today_et)
        next_open_et = next_trading.replace(hour=US_PRE_OPEN.hour, minute=US_PRE_OPEN.minute)
        return {
            "status": S_CLOSED,
            "label": f"휴장 ({hol_reason})",
            "next_event": "Pre-market 시작",
            "next_event_kst": _to_kst_str(next_open_et),
            "tradable": False,
        }

    if weekday >= 5:  # weekend
        # next Monday pre-open
        days_until_mon = (7 - weekday) % 7 or 1
        if weekday == 5:
            days_until_mon = 2
        next_open_et = today_et + timedelta(days=days_until_mon)
        next_open_et = next_open_et.replace(hour=US_PRE_OPEN.hour, minute=US_PRE_OPEN.minute)
        return {
            "status": S_CLOSED,
            "label": "주말",
            "next_event": "Pre-market 시작",
            "next_event_kst": _to_kst_str(next_open_et),
            "tradable": False,
        }

    if US_PRE_OPEN <= t < US_REG_OPEN:
        next_et = now_et.replace(hour=US_REG_OPEN.hour, minute=US_REG_OPEN.minute, second=0)
        return {"status": S_PRE, "label": LABELS_US[S_PRE], "next_event": "정규장 개장",
                "next_event_kst": _to_kst_str(next_et), "tradable": True}
    elif US_REG_OPEN <= t < US_REG_CLOSE:
        next_et = now_et.replace(hour=US_REG_CLOSE.hour, minute=US_REG_CLOSE.minute, second=0)
        return {"status": S_REGULAR, "label": LABELS_US[S_REGULAR], "next_event": "정규장 마감",
                "next_event_kst": _to_kst_str(next_et), "tradable": True}
    elif US_REG_CLOSE <= t < US_AFTER_CLOSE:
        next_et = now_et.replace(hour=US_AFTER_CLOSE.hour, minute=US_AFTER_CLOSE.minute, second=0)
        return {"status": S_AFTER, "label": LABELS_US[S_AFTER], "next_event": "After-hours 마감",
                "next_event_kst": _to_kst_str(next_et), "tradable": True}
    else:
        # closed - find next pre-open (today if before 04:00 ET, else tomorrow)
        if t < US_PRE_OPEN:
            next_et = today_et.replace(hour=US_PRE_OPEN.hour, minute=US_PRE_OPEN.minute)
        else:
            # tomorrow (skip weekend)
            next_day = today_et + timedelta(days=1)
            while next_day.weekday() >= 5:
                next_day += timedelta(days=1)
            next_et = next_day.replace(hour=US_PRE_OPEN.hour, minute=US_PRE_OPEN.minute)
        return {"status": S_CLOSED, "label": LABELS_US[S_CLOSED], "next_event": "Pre-market 시작",
                "next_event_kst": _to_kst_str(next_et), "tradable": False}


def _kr_status_now() -> dict:
    now_kst = datetime.now(KST)
    weekday = now_kst.weekday()
    t = now_kst.time()
    today_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)

    # Holiday check (highest priority — overrides time-of-day status).
    is_hol, hol_reason = is_kr_holiday(now_kst)
    if is_hol:
        next_trading = _next_kr_trading_day(today_kst)
        next_open = next_trading.replace(hour=KR_PRE_OPEN.hour, minute=KR_PRE_OPEN.minute)
        return {"status": S_CLOSED, "label": f"휴장 ({hol_reason})", "next_event": "장 시작 전",
                "next_event_kst": _to_kst_str(next_open), "tradable": False}

    if weekday >= 5:
        days_until_mon = 2 if weekday == 5 else 1
        next_open = today_kst + timedelta(days=days_until_mon)
        # Skip holidays after weekend.
        while is_kr_holiday(next_open)[0]:
            next_open += timedelta(days=1)
        next_open = next_open.replace(hour=KR_PRE_OPEN.hour, minute=KR_PRE_OPEN.minute)
        return {"status": S_CLOSED, "label": "주말", "next_event": "장 시작 전",
                "next_event_kst": _to_kst_str(next_open), "tradable": False}

    if KR_PRE_OPEN <= t < KR_REG_OPEN:
        next_kst = today_kst.replace(hour=KR_REG_OPEN.hour, minute=KR_REG_OPEN.minute)
        return {"status": S_PRE, "label": LABELS_KR[S_PRE], "next_event": "정규장 개장",
                "next_event_kst": _to_kst_str(next_kst), "tradable": True}
    elif KR_REG_OPEN <= t < KR_REG_CLOSE:
        next_kst = today_kst.replace(hour=KR_REG_CLOSE.hour, minute=KR_REG_CLOSE.minute)
        return {"status": S_REGULAR, "label": LABELS_KR[S_REGULAR], "next_event": "정규장 마감",
                "next_event_kst": _to_kst_str(next_kst), "tradable": True}
    elif KR_AFTER_OPEN <= t < KR_AFTER_CLOSE:
        next_kst = today_kst.replace(hour=KR_AFTER_CLOSE.hour, minute=KR_AFTER_CLOSE.minute)
        return {"status": S_AFTER, "label": LABELS_KR[S_AFTER], "next_event": "시간외 마감",
                "next_event_kst": _to_kst_str(next_kst), "tradable": True}
    else:
        if t < KR_PRE_OPEN:
            next_kst = today_kst.replace(hour=KR_PRE_OPEN.hour, minute=KR_PRE_OPEN.minute)
        else:
            next_day = today_kst + timedelta(days=1)
            while next_day.weekday() >= 5 or is_kr_holiday(next_day)[0]:
                next_day += timedelta(days=1)
            next_kst = next_day.replace(hour=KR_PRE_OPEN.hour, minute=KR_PRE_OPEN.minute)
        return {"status": S_CLOSED, "label": LABELS_KR[S_CLOSED], "next_event": "장 시작 전",
                "next_event_kst": _to_kst_str(next_kst), "tradable": False}


def get_market_status() -> dict:
    """Return both US and KR market status (KST 기준 표시)."""
    return {
        "us": _us_status_now(),
        "kr": _kr_status_now(),
    }
