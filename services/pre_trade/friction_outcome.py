"""Friction Outcome — 멈춤이 실제로 무엇으로 이어졌는지 되비추는 거울.

무엇인가 (그리고 무엇이 아닌가)
--------------------------------
사전 기록(pre-trade)을 시작한 뒤 사용자가 실제로 무엇을 했는지 — 진행했는지,
취소했는지, 취소한 종목을 나중에 결국 샀는지 — 를 **자기 기록만으로** 집계한
사실 거울이다. 그리고 멈춤을 거친 매수와 거치지 않은 매수의 **실현 수익률
분포**를 나란히 놓는다.

이 모듈이 **아닌** 것:

* **효과 판정이 아니다.** "멈춤이 도움이 된다 / 안 된다"를 말하지 않는다.
  두 분포를 나란히 놓을 뿐이고, 해석은 사용자 몫이다. 이 모듈 어디에도
  점수·등급·승패·"개선됨" 같은 판정 어휘가 없다 (DECISIONS.md — AI 점수화 폐기).
* **지시가 아니다.** "앞으로 더 멈추세요" 류의 문장을 만들지 않는다.
* **인과 주장이 아니다.** 사용자가 어떤 거래에 멈춤을 쓸지 스스로 고르므로
  이건 무작위 배정이 아니다. 그 한계는 payload 의 ``caveats`` 에 명시해서
  내보낸다 — 숨기지 않는다. 아래 "왜 비교가 어려운가" 참조.

시세를 쓰지 않는다
------------------
전 구간이 사용자 자신의 ``TradeHistory`` 와 ``PreTradeReflection`` 만 읽는다.
네트워크 호출, 시세 조회, FX 변환이 **하나도 없다.** 수익률은 FIFO 로 맞춘
매수/매도 슬라이스의 체결가로만 계산하므로 통화 변환도 필요 없다 — 한 쌍의
매수와 매도는 같은 통화이기 때문이다. 다른 5종 behavior mirror 와 같은 규율이며
(``averaging_down_mirror`` 의 "no live price / FX call"), 이 덕분에 순수 함수로
남아 결정론적으로 테스트된다.

세 가지를 센다
--------------
1. **멈춤의 귀결** — 시작 N건이 진행 / 취소 / 미결 중 무엇으로 끝났나.
2. **취소의 지속성** — 취소한 종목을 그 뒤에 결국 샀는가. 취소가 *회피*였는지
   *지연*이었는지는 이것으로만 갈린다. 취소해 놓고 이틀 뒤 사면 그건 멈춤이
   아니라 미룸이다.
3. **두 분포** — 멈춤을 거친 매수에서 나온 실현 수익률과, 거치지 않은 매수에서
   나온 실현 수익률.

왜 비교가 어려운가 (payload 로도 나간다)
----------------------------------------
* **선택 편향.** 사용자가 멈춤을 쓸 거래를 고른다. 이미 망설이는 거래에만
  쓴다면 두 그룹은 애초에 다른 거래다.
* **귀속의 불확실성.** reflection 은 주문이 아니다. ``proceeded_at`` 이후
  :data:`ATTRIBUTION_WINDOW_DAYS` 안에 같은 종목을 매수하면 그 매수로 귀속하는데,
  이건 추정이지 확정이 아니다. 같은 종목을 자주 사는 사용자는 오귀속될 수 있다.
* **표본.** 그룹당 :data:`MIN_GROUP_N` 미만이면 비교를 **거부한다**
  (``comparable=False``). 3건과 2건을 비교해 주는 건 정보가 아니라 소음이다.
* **쿨다운이 현재 0초다** (``DEFAULT_COOLDOWN_SECONDS``). 지금의 멈춤은 강제
  대기가 아니라 7문항 자체다. "시간이 벌어준 효과"로 읽으면 안 된다.

통계
----
* **median 우선, mean 보조** — 실현 수익률은 꼬리가 길다. 한 번의 +300% 가
  평균을 통째로 옮긴다. 다른 mirror 들과 같은 규약이다.
* 수익률은 슬라이스 단위 ``(sell_price - buy_price) / buy_price`` 로 **직접**
  계산한다. ``TradeHistory.pnl_pct`` 를 쓰지 않는 이유가 있다 — 그건 매도 **행**
  단위 값이라, 한 번의 매도가 여러 매수를 닫으면 같은 pnl_pct 가 모든 슬라이스에
  중복 부여된다 (``fifo_util`` 이 문서화한 collision 문제). 여기서는 분포를 보는
  게 목적이므로 슬라이스마다 자기 값이 있어야 한다. 그래서 pnl 을 실어 주는
  ``..._with_pnl`` 변형 대신 :func:`fifo_match_closed_trades` 를 쓰고 체결가로
  직접 계산한다.
"""
from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta, timezone
from collections.abc import Iterable
from typing import Any

from models import PreTradeReflection, TradeHistory
from services.profile.fifo_util import fifo_match_closed_trades

logger = logging.getLogger(__name__)

# reflection 을 실제 매수에 귀속시키는 창. reflection 은 주문이 아니라 기록이고,
# 사용자는 기록 후 증권사 앱에서 따로 주문한다. 브로커 동기화 지연까지 감안해
# 넉넉히 잡되, 너무 넓히면 무관한 매수를 빨아들인다. 7일은 타협이며 이 값에
# 결과가 민감하다는 사실 자체를 payload 에 실어 보낸다.
ATTRIBUTION_WINDOW_DAYS = 7

# 그룹당 최소 표본. 이보다 적으면 median 이 사실상 개별 거래 한 건이라
# 비교를 거부한다.
MIN_GROUP_N = 5


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _norm(ticker: Any) -> str:
    return str(ticker or "").strip().upper()


def _median_mean(values: list[float]) -> tuple[float | None, float | None]:
    """median 우선 / mean 보조. 빈 리스트는 (None, None)."""
    if not values:
        return None, None
    return (
        round(statistics.median(values), 2),
        round(statistics.fmean(values), 2),
    )


def compute_friction_outcome(
    reflections: Iterable[PreTradeReflection],
    trades: Iterable[TradeHistory],
    *,
    window_days: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """사용자 자신의 기록만으로 멈춤의 귀결을 집계한다.

    다른 5종 behavior mirror 와 같은 계약이다 — **호출자가 행을 읽어서 넘기고,
    이 함수는 계산만 한다.** DB 세션도 네트워크도 건드리지 않으므로 영속되지
    않은 객체로 결정론적 테스트가 가능하다.

    Parameters
    ----------
    reflections:
        대상 사용자의 :class:`PreTradeReflection` 행들.
    trades:
        같은 사용자의 :class:`TradeHistory` 행들.
    window_days:
        None 이면 넘어온 행 전부. 정수면 ``now`` 기준 그 일수 안의 행만 본다.
    now:
        창을 자르는 기준 시각. None 이면 현재 UTC (naive).

    Returns
    -------
    dict
        ``stopped`` / ``cancelled_followthrough`` / ``realised`` /
        ``caveats`` 를 담은 순수 데이터. 판정 문구는 들어 있지 않다.
    """
    now = now or _utc_now()
    since = now - timedelta(days=window_days) if window_days else None

    reflections = [
        r for r in reflections
        if since is None or (r.created_at is not None and r.created_at >= since)
    ]
    trades = [
        t for t in trades
        if since is None or (t.traded_at is not None and t.traded_at >= since)
    ]

    # ── 1. 멈춤의 귀결 ────────────────────────────────────────────────────
    proceeded = [r for r in reflections if r.proceeded_at is not None]
    cancelled = [
        r for r in reflections
        if r.cancelled_at is not None and r.proceeded_at is None
    ]
    stopped = {
        "started": len(reflections),
        "proceeded": len(proceeded),
        "cancelled": len(cancelled),
        # 진행도 취소도 아닌 것 — 쿨다운 중이거나 그냥 방치된 기록.
        "open": len(reflections) - len(proceeded) - len(cancelled),
    }

    # 매수만 종목·시각으로 색인 (취소 추적과 귀속 양쪽에 쓴다)
    buys: dict[str, list[datetime]] = {}
    for t in trades:
        # // legal-ok — 아래 리터럴은 TradeHistory.action 의 저장값이다
        # (매수/매도 구분 필드). 자문 어휘가 아니라 데이터 값이며, 훅의
        # 화이트리스트가 `trade.action` 형태만 인식해서 여기선 안 걸린다.
        if str(t.action or "").upper() != "BUY" or t.traded_at is None:  # // legal-ok
            continue
        buys.setdefault(_norm(t.ticker), []).append(t.traded_at)
    for v in buys.values():
        v.sort()

    # ── 2. 취소가 회피였나 지연이었나 ────────────────────────────────────
    revisit_days: list[float] = []
    bought_anyway = 0
    for r in cancelled:
        tk = _norm(r.intended_ticker)
        later = [b for b in buys.get(tk, []) if b > r.cancelled_at]
        if later:
            bought_anyway += 1
            revisit_days.append((later[0] - r.cancelled_at).total_seconds() / 86400.0)
    revisit_median, _ = _median_mean(revisit_days)
    cancelled_followthrough = {
        "cancelled": len(cancelled),
        "bought_later_anyway": bought_anyway,
        "never_bought": len(cancelled) - bought_anyway,
        "median_days_until_bought": revisit_median,
    }

    # ── 3. 멈춤 경유 매수 vs 미경유 매수의 실현 수익률 분포 ──────────────
    # proceeded reflection 마다 창 안의 첫 매수 시각을 잡아 "멈춤 경유 매수"로
    # 표시한다. (ticker, buy_time) 쌍으로 FIFO 슬라이스와 맞춘다.
    window = timedelta(days=ATTRIBUTION_WINDOW_DAYS)
    friction_buys: set[tuple[str, datetime]] = set()
    for r in proceeded:
        tk = _norm(r.intended_ticker)
        for b in buys.get(tk, []):
            if r.proceeded_at <= b <= r.proceeded_at + window:
                friction_buys.add((tk, b))
                break

    with_f: list[float] = []
    without_f: list[float] = []
    for pair in fifo_match_closed_trades(trades):
        if not pair.buy_price:            # 체결가 없는 행은 수익률을 못 낸다
            continue
        ret = (pair.sell_price - pair.buy_price) / pair.buy_price * 100.0
        key = (_norm(pair.ticker), pair.buy_time)
        (with_f if key in friction_buys else without_f).append(ret)

    w_med, w_mean = _median_mean(with_f)
    o_med, o_mean = _median_mean(without_f)
    comparable = len(with_f) >= MIN_GROUP_N and len(without_f) >= MIN_GROUP_N

    realised = {
        "with_friction": {"n": len(with_f), "median_pct": w_med, "mean_pct": w_mean},
        "without_friction": {"n": len(without_f), "median_pct": o_med, "mean_pct": o_mean},
        # 두 분포를 나란히 놓아도 되는 표본인가. False 면 프론트는 숫자 비교를
        # 렌더하지 않는다 — 이 판단을 프론트에 맡기지 않는다.
        "comparable": comparable,
        "min_group_n": MIN_GROUP_N,
    }

    return {
        "window_days": window_days,
        "stopped": stopped,
        "cancelled_followthrough": cancelled_followthrough,
        "realised": realised,
        # 한계는 계산 결과와 같은 봉투에 담아 보낸다. 읽는 쪽이 빼먹을 수 없게.
        "caveats": {
            "not_randomised": True,
            "attribution_window_days": ATTRIBUTION_WINDOW_DAYS,
            "cooldown_seconds_currently": 0,
        },
        "insufficient": stopped["started"] == 0,
    }
