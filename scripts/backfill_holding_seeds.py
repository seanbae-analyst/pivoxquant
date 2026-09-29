#!/usr/bin/env python3
"""보유 등록 시드 백필 — 등록만 되고 매수 행이 없는 보유분에 시드를 심는다.

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
S − N ≤ 0 (이력이 보유보다 많거나 같다)은 건드리지 않는다.

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

    Returns one dict per seed: ``{user_id, ticker, shares, price, currency,
    traded_at}``."""
    from extensions import db
    from models import Position, TradeHistory
    from services.position_writes import add_holding_seed

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
        if gap <= GAP_EPSILON:
            continue
        seed = {
            "user_id": int(p.user_id),
            "ticker": p.ticker,
            "shares": round(gap, 6),
            "price": float(p.avg_cost),
            "currency": _currency(p.ticker),
            "traded_at": p.added_at,
        }
        planned.append(seed)
        if apply:
            add_holding_seed(seed["user_id"], p.ticker, seed["shares"], seed["price"],
                             seed["currency"], _name(p.ticker), traded_at=p.added_at)
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
        print(f"user={s['user_id']} {s['ticker']} +{s['shares']:g} @ {s['price']:g} "
              f"{s['currency']} at {at}")
    mode = "written" if args.apply else "dry-run (use --apply to write)"
    print(f"{len(planned)} seed(s) — {mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
