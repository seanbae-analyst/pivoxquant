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


def _to_kst_str(dt: datetime) -> str:
    return dt.astimezone(KST).strftime("%H:%M")


def _us_status_now() -> dict:
    now_et = datetime.now(ET)
    weekday = now_et.weekday()  # 0=Mon, 6=Sun
    t = now_et.time()
    today_et = now_et.replace(hour=0, minute=0, second=0, microsecond=0)

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

    if weekday >= 5:
        days_until_mon = 2 if weekday == 5 else 1
        next_open = today_kst + timedelta(days=days_until_mon)
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
            while next_day.weekday() >= 5:
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
