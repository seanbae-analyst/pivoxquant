#!/usr/bin/env python3
"""보유 등록 시드·조정 백필 — 이력이 설명하지 못하는 보유분에 시드를, 이력보다 적은 보유분에 조정 행을 쓴다.

왜
--
2026-09-29 전까지 보유 등록 경로(POST /api/portfolio/positions · /position ·
보유 캡처 가져오기)는 ``positions`` 만 쓰고 ``trade_history`` 를 쓰지 않았다.
거울들은 FIFO 로트를 ``trade_history`` 에서만 세우므로 그 보유분을 팔면 매도가
버려진다. 지금은 등록이 ``source="holding_seed"`` 매수 행을 쓰지만, 그 전에
등록된 보유분에는 행이 없다. 이 스크립트가 그 빈칸을 메운다.

무엇을 하나
-----------
유저·종목마다 열린 ``Position`` 수량 S 와 ``trade_history`` 순수량
N = 매수 − 매도 (모든 source 포함 — 이미 심은 시드도 N 에 들어가므로 다시
돌려도 같은 결과다) 를 비교해 S − N > 0.0001 이면 S − N 주의 시드를 한 줄
쓴다. 단가 = ``Position.avg_cost``, 시각 = ``Position.added_at``, 통화 = 종목
접미사(.KS/.KQ → KRW, 나머지 USD), 이름 = 정적 마스터(네트워크 없음).
S − N < −0.0001 (보유가 이력이 설명하는 것보다 적다 — 기록된 매도 없이 줄었다)
이면 N − S 주의 조정 매도 행(``source="holding_adjust"``)을 쓴다. 단가 =
``Position.avg_cost``, 시각 = 지금(줄어든 시각을 모르므로 모든 이력 뒤), pnl 0.
조정도 N 에 들어가므로(매도) 다시 돌려도 같은 결과다. 열린 ``Position`` 이 없는
종목(전량 삭제 등)은 평단이 없어 건드리지 않는다.

스케줄에 걸지 않는다. 기본은 dry-run(출력만), ``--apply`` 때만 쓴다.

사용법
------
    ./venv/bin/python scripts/backfill_holding_seeds.py            # dry-run
    ./venv/bin/python scripts/backfill_holding_seeds.py --user 12  # 한 유저
    ./venv/bin/python scripts/backfill_holding_seeds.py --apply    # 쓰기
"""
from __future__ import annotations

import argparse
import os
import sys

# 스케줄러/캐시워밍 없이 앱 컨텍스트만 필요하다 — import 전에 꺼야 한다.
os.environ.setdefault("RUN_SCHEDULER", "0")
os.environ.setdefault("POPULATE_CACHE_ON_BOOT", "0")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GAP_EPSILON = 0.0001


def _currency(ticker: str) -> str:
    t = (ticker or "").upper()
    return "KRW" if t.endswith(".KS") or t.endswith(".KQ") else "USD"


def _name(ticker: str) -> str:
    try:
        if _currency(ticker) == "KRW":
            from services.kr_stock_registry import get_name
        else:
            from services.us_stock_registry import get_name
        return get_name(ticker) or ticker
    except Exception:
        return ticker


def run(*, apply: bool = False, user_id: int | None = None) -> list[dict]:
    """Plan (and with ``apply`` write) the missing seeds. Needs an app context.

    Returns one dict per row: ``{user_id, ticker, action, source, shares,
    price, currency, traded_at}`` — ``action`` "BUY" for a seed, "SELL" for a
    holding adjust (``traded_at`` None = now at write time)."""
    from extensions import db
    from models import Position, TradeHistory
    from models.trade_history import HOLDING_ADJUST_SOURCE, HOLDING_SEED_SOURCE
    from services.position_writes import add_holding_adjust, add_holding_seed

    q = Position.query.filter(Position.shares > GAP_EPSILON)
    if user_id is not None:
        q = q.filter(Position.user_id == user_id)
    positions = q.order_by(Position.user_id.asc(), Position.id.asc()).all()

    net: dict[tuple[int, str], float] = {}
    th = TradeHistory.query
    if user_id is not None:
        th = th.filter(TradeHistory.user_id == user_id)
    for t in th.all():
        action = (t.action or "").upper()
        if action not in ("BUY", "SELL") or not t.ticker:  # // legal-ok — stored enum values
            continue
        key = (int(t.user_id), t.ticker.upper())
        sh = float(t.shares or 0.0)
        net[key] = net.get(key, 0.0) + (sh if action == "BUY" else -sh)  # // legal-ok

    planned: list[dict] = []
    for p in positions:
        gap = float(p.shares) - net.get((int(p.user_id), p.ticker.upper()), 0.0)
        if abs(gap) <= GAP_EPSILON:
            continue
        is_seed = gap > 0
        row = {
            "user_id": int(p.user_id),
            "ticker": p.ticker,
            "action": "BUY" if is_seed else "SELL",  # // legal-ok — stored enum values
            "source": HOLDING_SEED_SOURCE if is_seed else HOLDING_ADJUST_SOURCE,
            "shares": round(abs(gap), 6),
            "price": float(p.avg_cost),
            "currency": _currency(p.ticker),
            # A seed sits at registration; the decrease happened at an unknown
            # time, so the adjust goes after all history (write time).
            "traded_at": p.added_at if is_seed else None,
        }
        planned.append(row)
        if apply:
            write = add_holding_seed if is_seed else add_holding_adjust
            write(row["user_id"], p.ticker, row["shares"], row["price"],
                  row["currency"], _name(p.ticker), traded_at=row["traded_at"])
    if apply and planned:
        db.session.commit()
    return planned


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="write the seeds (default: dry-run)")
    ap.add_argument("--user", type=int, default=None, help="only this user id")
    args = ap.parse_args()

    from app import create_app

    app = create_app()
    with app.app_context():
        planned = run(apply=args.apply, user_id=args.user)
    for s in planned:
        at = s["traded_at"].isoformat() if s["traded_at"] else "-"
        sign = "+" if s["action"] == "BUY" else "-"  # // legal-ok — stored enum value
        print(f"user={s['user_id']} {s['ticker']} {sign}{s['shares']:g} @ {s['price']:g} "
              f"{s['currency']} at {at} ({s['source']})")
    mode = "written" if args.apply else "dry-run (use --apply to write)"
    print(f"{len(planned)} row(s) — {mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
