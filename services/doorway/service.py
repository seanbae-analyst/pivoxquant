"""문 앞의 한 줄 — 증권 앱을 여는 순간의 답을 받고, 그 뒤 체결과 맞춰 되비춘다.

docs/design/doorway-pause_2026-10-15.md · models/doorway_check.py.

무엇인가 (그리고 무엇이 아닌가)
--------------------------------
「멈춤」은 유저가 사기 전에 우리 화면을 스스로 열어야 작동한다 — 그래서 이미
망설이는 거래에만 쓰인다(friction_outcome 의 "선택 편향"). 문 앞의 한 줄은
멈춤을 목적지에서 문턱으로 옮긴다: 유저 폰의 자동화가 증권 앱이 열릴 때
"뭘 하러 왔어요?"를 묻고, 답(그냥 보기 / 살 게 있음 / 팔 게 있음 + 한 줄)을
본인 가져오기 토큰으로 보낸다. 근거: one sec 현장실험(PNAS 2023, 280명·6주)
에서 앱을 열 때의 자기 넛지로 열기 시도의 36% 가 그 자리에서 접혔다.

이 모듈은 그 답을 저장하고, 읽을 때 같은 유저의 체결과 맞춰 **개수만** 센다:

* 그냥 보러 왔다가 체결한 열림 수
* 살/팔 게 있다고 한 열림 중 — 말한 대로 체결 / 다른 체결 / 체결 없음
* 체결 없이 끝난 살/팔 열림이 그 뒤 30일 안에 결국 체결됐나 ("일어나지 않은
  거래"가 회피였나 미룸이었나 — friction_outcome 의 '취소의 지속성'과 같은 질문)
* 문을 거친 체결 vs 거치지 않은 체결 (자동화가 실제로 돌고 있나)

아닌 것: 효과 판정이 아니다("문 앞 질문이 도움이 된다"를 말하지 않는다). 점수·
등급·연속 기록·지시가 없다. 인과 주장이 아니다 — 한계는 ``caveats`` 로 내보낸다.

시세를 쓰지 않는다
------------------
본인 ``DoorwayCheck`` · ``TradeHistory`` · 대기 중인 ``PendingTrade`` 만 읽는다.
네트워크·시세·FX 호출이 없다. ``summarize`` 는 순수 함수다 — DB·시계를 만지지
않으므로 모든 분기를 결정론적으로 시험한다 (behavior/* 와 같은 규율).

맞추는 규칙
-----------
* 체결 하나는 **그 체결 직전의 열림 하나**에만 이어진다: 체결 시각 기준
  ``FOLLOW_MINUTES`` 안에서 가장 늦게 연 열림. 같은 체결을 두 열림이 나눠 갖지
  않는다. 체결 문자는 분 단위라 열기 직전으로 찍힐 수 있어
  ``EARLY_GRACE_SECONDS`` 만큼 앞선 체결도 그 열림에 잇는다.
* 체결 = 본인 기록 체결(등록 경로가 쓴 행 제외, ``fifo_util.is_registration_row``)
  + 가져오기 대기 목록에 아직 있는 체결. 승인된 대기 행은 이미 trade_history 에
  있으므로 다시 세지 않는다 — my_rules.month_fill_count 와 같은 단위.
"""
from __future__ import annotations

import bisect
import logging
import re
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta, timezone
from typing import Iterable, Sequence

from extensions import db
from models.doorway_check import (
    APP_MAX_LEN,
    INTENT_BUY,
    INTENT_LOOK,
    INTENT_SELL,
    INTENTS,
    MAX_NOTE_CHARS,
    SOURCES,
    DoorwayCheck,
    offline_name,
)
from services.pre_trade.friction_outcome import ticker_key

log = logging.getLogger(__name__)

_KST = timedelta(hours=9)

FOLLOW_MINUTES = 60
EARLY_GRACE_SECONDS = 60
LATER_DAYS = 30
WINDOW_DAYS = (7, 30, 90)
DEFAULT_WINDOW_DAYS = 30
# 하루(KST) 열림 상한 — 자동화가 고장 나 같은 요청을 반복해도 표를 덮지
# 않게. 하루 100번 증권 앱을 여는 사람은 없다고 본다.
DAILY_LIMIT = 100
RECENT_LIMIT = 10
LIST_LIMIT_MAX = 100

# 의도별로 "말한 대로"의 체결 방향. trade_history.action 값과 비교만 한다.
_SIDE_FOR_INTENT = {INTENT_BUY: "BUY", INTENT_SELL: "SELL"}  # // legal-ok — data values

CAVEATS = (
    f"체결은 문을 연 뒤 {FOLLOW_MINUTES}분 안에 들어온 것만 그 열림에 잇습니다. "
    "한 체결은 바로 앞의 열림 하나에만 이어집니다.",
    "자동화가 꺼져 있던 때나 다른 기기·PC에서 한 거래는 '문을 거치지 않은 체결'로 셉니다.",
    "기록 대기 목록에 아직 있는 체결도 함께 셉니다.",
    "누가 언제 앱을 열지는 무작위가 아니므로, 이 숫자로 질문의 효과를 말할 수는 없습니다.",
)


class DoorwayInputError(ValueError):
    def __init__(self, en: str, kr: str, *, code: str = "DOORWAY_BAD_INPUT", status: int = 400):
        super().__init__(en)
        self.en = en
        self.kr = kr
        self.code = code
        self.status = status


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive(now: datetime | None) -> datetime:
    if now is None:
        return utcnow()
    if now.tzinfo is not None:
        return now.astimezone(timezone.utc).replace(tzinfo=None)
    return now


def kst_day_start_utc(now: datetime) -> datetime:
    """``now`` 가 속한 KST 하루의 시작을 naive UTC 로."""
    kst = now + _KST
    return kst.replace(hour=0, minute=0, second=0, microsecond=0) - _KST


# ─────────────────────────────────────────────────────────────────────
# 입력 — 자동화가 보내는 한 줄을 읽는다
# ─────────────────────────────────────────────────────────────────────

# 단축어 '메뉴에서 선택'의 각 항목이 내보내는 글의 머리. 안내 화면은
# "보기" / "살 …" / "팔 …" 을 쓰게 하지만 사람이 고쳐 쓴 것도 받는다.
_HEAD_RE = re.compile(
    r"^\s*(?P<head>그냥\s*보기|그냥|보기|보러|살\s*게\s*있음|살\s*것|사러|살|매수|"
    r"팔\s*게\s*있음|팔\s*것|팔러|팔|매도|look|buy|sell)"
    r"(?=$|[\s:：,·\-—])[\s:：,·\-—]*(?P<rest>.*)$",
    re.IGNORECASE | re.DOTALL,
)


def _intent_of_head(head: str) -> str:
    h = re.sub(r"\s+", "", head).lower()
    if h in ("그냥보기", "그냥", "보기", "보러", "look"):
        return INTENT_LOOK
    if h.startswith("팔") or h in ("매도", "sell"):
        return INTENT_SELL
    return INTENT_BUY


def parse_text(text: str) -> tuple[str, str]:
    """``"살 삼성전자 실적 발표 전"`` → ``("buy", "삼성전자 실적 발표 전")``.

    머리말이 없으면 ``DoorwayInputError`` — 잘못 만든 자동화가 조용히 "그냥
    보기"로 쌓이는 것보다 폰에 오류가 뜨는 편이 고치기 쉽다.
    """
    m = _HEAD_RE.match(text or "")
    if not m:
        raise DoorwayInputError(
            "Start the text with 보기 / 살 / 팔.",
            "보낸 글이 '보기', '살', '팔' 중 하나로 시작해야 합니다.",
        )
    return _intent_of_head(m.group("head")), (m.group("rest") or "").strip()


# 앱 꼬리표 — 자동화가 붙이는 이름. 한글로 적어도 받는다.
_APP_RE = re.compile(r"^[a-z0-9_\-]{1,%d}$" % APP_MAX_LEN)
_APP_ALIASES = {
    "토스": "toss", "토스증권": "toss",
    "키움": "kiwoom", "키움증권": "kiwoom", "영웅문": "kiwoom",
    "미래에셋": "mirae", "미래에셋증권": "mirae", "m-stock": "mirae",
    "삼성": "samsung", "삼성증권": "samsung", "mpop": "samsung",
    "한국투자": "kis", "한국투자증권": "kis", "한투": "kis",
    "nh": "nh", "nh투자증권": "nh", "나무": "nh",
    "kb": "kb", "kb증권": "kb",
    "신한": "shinhan", "신한투자증권": "shinhan",
    "카카오페이증권": "kakaopay", "카카오페이": "kakaopay",
}


def normalize_app(raw) -> str | None:
    if not isinstance(raw, str):
        return None
    a = raw.strip().lower()
    if not a:
        return None
    a = _APP_ALIASES.get(re.sub(r"\s+", "", a), a)
    return a if _APP_RE.match(a) else None


# 대문자 약어 중 종목 기호와 겹치는 흔한 말 — 한 줄에 "AI 관련" 이라고 쓰면
# C3.ai(AI)로 읽지 않게.
_LATIN_STOP = frozenset({
    "AI", "ETF", "ETN", "IPO", "PER", "PBR", "EPS", "ROE", "CEO", "IR", "DCA",
    "FOMC", "CPI", "GDP", "USD", "KRW", "US", "KR", "OK", "VS", "TV", "IT",
    "PC", "EV", "UP", "GO", "ALL", "NEW", "NOW", "ONE", "SO", "AM", "PM",
    # 2026-10-21 — 미국 마스터에 기호로 있는 흔한 영어 낱말.
    "A", "FOR", "ARE", "CAN", "ANY", "KEY", "GOOD", "CASH", "LOW", "HIGH",
    "HOLD",  # // legal-ok — 낱말 거르기용, 화면에 나가지 않는다
})
# 이름 끝에 붙는 조사 — "삼성전자를" → "삼성전자".
_PARTICLES = ("에서", "으로", "까지", "부터", "이랑", "하고", "처럼",
              "을", "를", "이", "가", "은", "는", "도", "만", "에", "로", "랑", "와", "과", "의")
_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣&.\-]+")


def _name_candidates(tok: str) -> list[str]:
    out = [tok]
    for p in _PARTICLES:
        if len(tok) > len(p) + 1 and tok.endswith(p):
            out.append(tok[: -len(p)])
    return out


def extract_ticker(text: str | None) -> str | None:
    """한 줄에서 종목 하나를 읽는다 — 마스터에 있는 것만, 못 읽으면 None.

    순서: 한글 종목명(국내 마스터 정확 일치) → 미국 종목의 한글 이름
    (us_kr_names.json) → 6자리 코드 → 대문자 기호(미국 마스터). 가져오기
    (services/imports/holdings_import)와 같은 마스터를 쓴다 — 두 벌 금지.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    from services.imports.holdings_import import (
        _kr_index,
        _us_kr_index,
        canonical_known_ticker,
    )

    tokens = _TOKEN_RE.findall(text)
    kr = _kr_index()
    us_kr = _us_kr_index()
    # 붙여 쓴 두 낱말("KODEX 200")도 이름일 수 있다.
    phrases = [f"{a} {b}" for a, b in zip(tokens, tokens[1:])] + tokens
    for ph in phrases:
        for cand in _name_candidates(ph):
            if cand in kr:
                return canonical_known_ticker(kr[cand]) or kr[cand]
            if cand in us_kr:
                return canonical_known_ticker(us_kr[cand])
    for tok in tokens:
        if re.fullmatch(r"\d{6}", tok):
            hit = canonical_known_ticker(tok)
            if hit:
                return hit
    for tok in tokens:
        if re.fullmatch(r"[A-Z][A-Z.\-]{0,5}", tok) and tok not in _LATIN_STOP:
            hit = canonical_known_ticker(tok)
            if hit:
                return hit
    return None


def record_check(user_id: int, payload: dict, *, source: str, now: datetime | None = None) -> dict:
    """열림 하나를 저장한다. ``payload`` = ``{intent?, text?, note?, ticker?, app?}``.

    ``intent`` 가 있으면 그대로, 없으면 ``text`` 의 머리말에서 읽는다.
    한 줄은 ``MAX_NOTE_CHARS`` 에서 자른다 — 폰 입력창에서 길게 쓴 것을
    거절하면 문 앞에서 오류만 보게 된다.
    """
    if source not in SOURCES:
        raise DoorwayInputError("bad source", "요청 형식이 올바르지 않습니다.")
    if not isinstance(payload, dict):
        payload = {}
    now = _naive(now)

    intent = payload.get("intent")
    note = payload.get("note")
    if intent is not None:
        intent = str(intent).strip().lower()
        if intent not in INTENTS:
            raise DoorwayInputError(
                f"intent must be one of {INTENTS}.",
                "답은 '보기', '살', '팔' 중 하나여야 합니다.",
            )
    else:
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise DoorwayInputError(
                "Send intent or text.",
                "보낸 글이 비어 있습니다.",
            )
        intent, rest = parse_text(text)
        if note is None:
            note = rest
    note = note.strip()[:MAX_NOTE_CHARS] if isinstance(note, str) else ""

    ticker = None
    raw_ticker = payload.get("ticker")
    if isinstance(raw_ticker, str) and raw_ticker.strip():
        from services.imports.holdings_import import canonical_known_ticker

        ticker = canonical_known_ticker(raw_ticker) or extract_ticker(raw_ticker)
    if ticker is None and note:
        ticker = extract_ticker(note)

    today_start = kst_day_start_utc(now)
    today = (
        DoorwayCheck.query
        .filter(DoorwayCheck.user_id == user_id, DoorwayCheck.created_at >= today_start)
        .count()
    )
    if today >= DAILY_LIMIT:
        raise DoorwayInputError(
            f"Daily limit of {DAILY_LIMIT} reached.",
            f"오늘 남길 수 있는 문 앞 기록 {DAILY_LIMIT}건을 모두 썼습니다.",
            code="DOORWAY_DAILY_LIMIT", status=429,
        )

    row = DoorwayCheck(
        user_id=user_id,
        intent=intent,
        ticker=ticker,
        note=note or None,
        app=normalize_app(payload.get("app")),
        source=source,
        created_at=now,
    )
    db.session.add(row)
    db.session.commit()
    return {"check": row.to_dict(), "today": today + 1}


def reply_line(check: dict, today: int) -> str:
    """자동화가 '알림 보기'로 띄울 한 줄 — 사실만, 판정·지시 없음."""
    head = "기록했어요"
    if check.get("name"):
        head = f"{head} · {check['name']}"
    return f"{head} · 오늘 {today}번째 열림"


def pause_path(check: dict) -> str | None:
    """살 게 있다고 했고 종목을 읽었으면 「멈춤」으로 가는 길. 한 줄은 URL 에
    넣지 않는다 — 종목만."""
    if check.get("intent") != INTENT_BUY or not check.get("ticker"):
        return None
    from urllib.parse import quote

    return f"/pre-trade?ticker={quote(check['ticker'])}"


# ─────────────────────────────────────────────────────────────────────
# 읽기 — 열림과 체결을 맞춘다 (순수 함수)
# ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Fill:
    traded_at: datetime
    ticker: str | None
    side: str
    # 시각 없이 날짜만 아는 체결(``services.imports.is_date_only`` — KST 날짜
    # 00:00 으로 저장). 체결 수에는 들지만 어느 열림에도 잇지 않는다: 그 00:00
    # 은 시각이 아니라서 09:00 KST 장 전 열림에 붙으면 안 된다.
    untimed: bool = False


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _attribute(checks: Sequence, fills: Sequence[Fill]) -> dict[int, list[Fill]]:
    """체결마다 바로 앞의 열림 하나를 찾는다 → ``{check index: [fills]}``."""
    times = [c.created_at for c in checks]
    follow = timedelta(minutes=FOLLOW_MINUTES)
    grace = timedelta(seconds=EARLY_GRACE_SECONDS)
    out: dict[int, list[Fill]] = {}
    for f in fills:
        if f.untimed:
            continue
        # 체결 시각 + 유예 안쪽에서 가장 늦은 열림.
        i = bisect.bisect_right(times, f.traded_at + grace) - 1
        if i < 0:
            continue
        if f.traded_at - checks[i].created_at > follow:
            continue
        out.setdefault(i, []).append(f)
    return out


def _lands_between(f: Fill, after: datetime, until: datetime) -> bool:
    """``after < 체결 <= until``. 날짜만 아는 체결은 그 KST 날짜로 본다: 열림과
    같은 날이면 든다 — 00:00 을 시각으로 비교하면 그날 오전 10시 열림 뒤에 산
    것이 '끝내 안 함'으로 셌다 (2026-10-22)."""
    if f.untimed:
        return (after + _KST).date() <= f.traded_at.date() <= (until + _KST).date()
    return after < f.traded_at <= until


def _fill_in_range(f: Fill, since: datetime, end: datetime | None) -> bool:
    """``since <= 체결 < end``. 날짜만 아는 체결은 KST 날짜로 — 00:00 을 시각으로
    비교하면 첫 열림(``since``)과 같은 날의 체결이 빠졌다 (2026-10-22)."""
    if f.untimed:
        day = f.traded_at.date()
        if day < (since + _KST).date():
            return False
        if end is None:
            return True
        # ``end`` is a KST midnight (a year's end) or ``now`` (this year, so
        # far). Exclusive at a midnight; at ``now`` today's date-only fills
        # are in — "day < today" dropped them (2026-10-22 regression).
        end_kst = end + _KST
        if end_kst.time() == dt_time.min:
            return day < end_kst.date()
        return day <= end_kst.date()
    return f.traded_at >= since and (end is None or f.traded_at < end)


def _same_ticker(a: str | None, b: str | None) -> bool:
    """.KS/.KQ/접미사 없는 코드는 같은 종목 — ``friction_outcome.ticker_key`` 한 벌."""
    return bool(a) and bool(b) and ticker_key(a) == ticker_key(b)


def _outcome(check, attributed: list[Fill]) -> str:
    """look → traded | none · buy/sell → as_said | other | none."""
    if not attributed:
        return "none"
    if check.intent == INTENT_LOOK:
        return "traded"
    side = _SIDE_FOR_INTENT.get(check.intent)
    for f in attributed:
        if f.side == side and (check.ticker is None or _same_ticker(f.ticker, check.ticker)):
            return "as_said"
    return "other"


def summarize(
    checks: Iterable,
    fills: Iterable[Fill],
    *,
    now: datetime,
    days: int = DEFAULT_WINDOW_DAYS,
    first_check_at: datetime | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict:
    """열림 × 체결 → 개수. 순수 함수 — ``now`` 를 받는다.

    ``checks`` 는 창보다 조금 앞의 열림을 포함해도 된다(창 경계 직후의 체결을
    바르게 잇기 위해). 세는 것은 ``created_at >= now - days`` 인 열림뿐이다.
    ``start`` / ``end`` 를 주면 그 [시작, 끝) 으로 센다 — 올해의 기록이 한 해를
    셀 때 (``year_section``). 30일 뒤를 보는 "일어나지 않은 거래" 판정은 언제나
    ``now`` 까지의 체결로 한다.
    """
    now = _naive(now)
    window_start = start if start is not None else now - timedelta(days=days)

    def in_window(ts: datetime) -> bool:
        return ts >= window_start and (end is None or ts < end)
    later = timedelta(days=LATER_DAYS)

    all_checks = sorted(
        (c for c in checks if c.created_at is not None and c.intent in INTENTS),
        key=lambda c: (c.created_at, c.id or 0),
    )
    all_fills = sorted((f for f in fills if f.traded_at is not None), key=lambda f: f.traded_at)
    attributed = _attribute(all_checks, all_fills)

    intents = {k: 0 for k in INTENTS}
    look = {"n": 0, "traded": 0}
    said = {k: {"n": 0, "as_said": 0, "other": 0, "none": 0} for k in (INTENT_BUY, INTENT_SELL)}
    not_happened = {"n": 0, "later": 0, "never": 0, "open": 0}
    by_hour = [0] * 24
    window_rows: list[tuple] = []

    for i, c in enumerate(all_checks):
        if not in_window(c.created_at):
            continue
        mine = attributed.get(i, [])
        outcome = _outcome(c, mine)
        intents[c.intent] += 1
        by_hour[(c.created_at + _KST).hour] += 1
        if c.intent == INTENT_LOOK:
            look["n"] += 1
            if outcome == "traded":
                look["traded"] += 1
        else:
            bucket = said[c.intent]
            bucket["n"] += 1
            bucket[outcome] += 1
            # 체결 없이 끝난 열림 중 종목을 아는 것 — 그 뒤 30일 안에 결국
            # 같은 종목을 같은 방향으로 체결했나.
            if outcome == "none" and c.ticker:
                not_happened["n"] += 1
                side = _SIDE_FOR_INTENT[c.intent]
                # 함수 인자 start/end 를 덮어쓰지 않는다 — in_window 와 체결 집계가
                # 그 둘을 읽는다 (2026-10-21: 덮어써서 90일·연간 창이 잘렸다).
                # 창은 열림 바로 뒤부터 — 60분 안의 체결이 그 뒤 다시 연 열림에
                # 이어졌어도(앱을 다시 열고 "그냥 보기") 그 종목을 산 것은 맞다.
                after, until = c.created_at, c.created_at + later
                if any(_same_ticker(f.ticker, c.ticker) and f.side == side and _lands_between(f, after, until)
                       for f in all_fills):
                    not_happened["later"] += 1
                elif now < until:
                    not_happened["open"] += 1
                else:
                    not_happened["never"] += 1
        window_rows.append((c, outcome))

    # 문을 거친 체결 — 첫 열림 이후(그 전엔 자동화가 없었다), 창 안의 체결만.
    # 첫 열림 바로 앞 유예 안의 체결도 그 열림에 이어지므로 함께 센다.
    door_ids = {id(f) for fs in attributed.values() for f in fs}
    grace = timedelta(seconds=EARLY_GRACE_SECONDS)
    since = max(window_start, first_check_at - grace) if first_check_at else None
    fills_total = fills_door = 0
    if since is not None:
        for f in all_fills:
            if _fill_in_range(f, since, end):
                fills_total += 1
                if id(f) in door_ids:
                    fills_door += 1

    recent = []
    for c, outcome in reversed(window_rows[-RECENT_LIMIT:]):
        recent.append({
            "id": int(c.id) if getattr(c, "id", None) is not None else None,
            "at": _iso(c.created_at),
            "intent": c.intent,
            "ticker": c.ticker,
            "name": offline_name(c.ticker) if c.ticker else None,
            "note": getattr(c, "note", None) or None,
            "app": getattr(c, "app", None),
            "outcome": outcome,
        })

    return {
        "window_days": days,
        "follow_minutes": FOLLOW_MINUTES,
        "later_days": LATER_DAYS,
        "first_check_at": _iso(first_check_at),
        "total": sum(intents.values()),
        "intents": intents,
        "look": look,
        "said": said,
        "not_happened": not_happened,
        "fills": {"total": fills_total, "through_door": fills_door},
        "by_hour_kst": by_hour,
        "recent": recent,
        "caveats": list(CAVEATS),
    }


def year_section(
    checks: Iterable,
    fills: Iterable[Fill],
    *,
    start: datetime,
    end: datetime,
    now: datetime,
    first_check_at: datetime | None,
) -> dict | None:
    """올해의 기록(services/year_recap)의 ``doorway`` 칸 — 그해 [start, end) 의
    문 앞 개수. 그해 열림이 없으면 None (화면이 칸을 그리지 않는다). 최근 기록과
    유저의 한 줄은 넣지 않는다 — 연간 화면은 개수만 (legal-kr-fintech 2026-10-15:
    note 가 본인 화면 밖으로 나가면 재검수)."""
    s = summarize(checks, fills, now=now, first_check_at=first_check_at, start=start, end=end)
    if s["total"] == 0:
        return None
    return {
        "total": s["total"],
        "intents": s["intents"],
        "look": s["look"],
        "said": s["said"],
        "not_happened": s["not_happened"],
        "fills": s["fills"],
        "follow_minutes": s["follow_minutes"],
        "later_days": s["later_days"],
    }


# ─────────────────────────────────────────────────────────────────────
# DB 경계
# ─────────────────────────────────────────────────────────────────────

def load_fills(user_id: int, since: datetime) -> list[Fill]:
    """``since`` 이후의 본인 체결 — 기록된 체결(등록 행 제외) + 대기 중 체결."""
    from models import TradeHistory
    from models.import_batch import STATUS_PENDING, PendingTrade
    from services.imports import is_date_only
    from services.profile.fifo_util import is_registration_row

    # A date-only fill is stored as its KST date at 00:00, which can sit
    # before ``since`` (a UTC instant) on the very KST day ``since`` falls
    # on — the DB filter dropped it before the KST-date rules
    # (_lands_between / _fill_in_range) could count it (2026-10-22). Load
    # from that KST date's 00:00 too; extra timed rows are filtered later.
    since = min(since, datetime.combine((since + _KST).date(), dt_time.min))
    out: list[Fill] = []
    for t in TradeHistory.query.filter(
        TradeHistory.user_id == user_id, TradeHistory.traded_at >= since,
    ).all():
        if is_registration_row(t) or t.action not in ("BUY", "SELL"):  # // legal-ok — data values
            continue
        out.append(Fill(t.traded_at, t.ticker, t.action, untimed=is_date_only(t.traded_at)))
    for p in PendingTrade.query.filter(
        PendingTrade.user_id == user_id,
        PendingTrade.status == STATUS_PENDING,
        PendingTrade.traded_at >= since,
    ).all():
        if p.action in ("BUY", "SELL"):  # // legal-ok — data values
            out.append(Fill(p.traded_at, p.ticker, p.action, untimed=is_date_only(p.traded_at)))
    return out


def first_check_at(user_id: int) -> datetime | None:
    from sqlalchemy import func

    return (
        db.session.query(func.min(DoorwayCheck.created_at))
        .filter(DoorwayCheck.user_id == user_id)
        .scalar()
    )


def doorway_summary(user_id: int, *, days: int = DEFAULT_WINDOW_DAYS, now: datetime | None = None) -> dict:
    if days not in WINDOW_DAYS:
        raise DoorwayInputError(
            f"days must be one of {WINDOW_DAYS}.",
            "기간은 7·30·90일 중 하나여야 합니다.",
        )
    now = _naive(now)
    window_start = now - timedelta(days=days)
    lead = timedelta(minutes=FOLLOW_MINUTES)
    checks = (
        DoorwayCheck.query
        .filter(DoorwayCheck.user_id == user_id, DoorwayCheck.created_at >= window_start - lead)
        .order_by(DoorwayCheck.created_at.asc(), DoorwayCheck.id.asc())
        .all()
    )
    fills = load_fills(user_id, window_start - lead)
    return summarize(checks, fills, now=now, days=days, first_check_at=first_check_at(user_id))


def list_checks(user_id: int, *, limit: int = 50, before_id: int | None = None) -> dict:
    limit = max(1, min(int(limit or 50), LIST_LIMIT_MAX))
    q = DoorwayCheck.query.filter(DoorwayCheck.user_id == user_id)
    if before_id:
        q = q.filter(DoorwayCheck.id < before_id)
    rows = q.order_by(DoorwayCheck.id.desc()).limit(limit + 1).all()
    more = len(rows) > limit
    rows = rows[:limit]
    return {
        "checks": [r.to_dict() for r in rows],
        "next_before": rows[-1].id if more and rows else None,
    }


def delete_check(user_id: int, check_id: int) -> bool:
    row = DoorwayCheck.query.filter_by(id=check_id, user_id=user_id).first()
    if row is None:
        return False
    db.session.delete(row)
    db.session.commit()
    return True
