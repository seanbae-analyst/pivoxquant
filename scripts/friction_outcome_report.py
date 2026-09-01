#!/usr/bin/env python3
"""멈춤의 귀결 리포트 — 제품이 자기 효과를 스스로 증명(또는 반증)하게 한다.

왜 이 스크립트가 있나
---------------------
PivoxQuant 의 핵심 주장은 "사기 전에 멈춰 적으면 달라진다"이다. 그런데
`research_habit_premise.md` (2026-08-30) 조사는 그 전제를 **조건부**로만
확증했다 — 처분효과 개입 연구에서 2주까지는 효과가 유의했지만 3개월엔
사라졌다. 즉 이 주장은 믿을 게 아니라 **재야 하는 것**이다.

경쟁자는 이 숫자를 만들 수 없다. 증권사도 MyData 도 체결만 알지 *사려다
말았는지*를 모르고, ChatGPT 는 사용자가 매번 전부 다시 붙여넣지 않는 한
모른다. "일어나지 않은 거래"는 이 제품만 가진 데이터다.

무엇을 출력하나
---------------
:func:`services.pre_trade.friction_outcome.compute_friction_outcome` 의 결과를
사람이 읽는 형태로 찍는다. 계산은 전부 그 모듈에 있고 이 스크립트는 **읽고
찍기만** 한다 — 로직이 두 벌 생기지 않게.

주의 — 이 숫자는 답이 아니라 질문이다
-------------------------------------
* 무작위 배정이 아니다. 어떤 거래에 멈춤을 쓸지 사용자가 고른다.
* 표본이 작으면 모듈이 `comparable: false` 로 비교를 거부한다. 그때는
  숫자를 나란히 놓지 마라 — 그러라고 만든 플래그다.
* **결과가 불리하게 나올 수 있다.** 멈추고 산 거래가 더 나빴다는 답도
  가능하다. 그 답을 모른 채 파는 것보다 아는 게 낫다는 게 이 스크립트의
  존재 이유다.

사용법
------
    ./venv/bin/python scripts/friction_outcome_report.py            # 전체 유저
    ./venv/bin/python scripts/friction_outcome_report.py --user 1
    ./venv/bin/python scripts/friction_outcome_report.py --days 90
    ./venv/bin/python scripts/friction_outcome_report.py --json

₩0. 네트워크·시세 호출 없음 (계산 모듈이 순수 함수다). 읽기 전용.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# 스케줄러/캐시워밍 없이 앱 컨텍스트만 필요하다 — import 전에 꺼야 한다.
os.environ.setdefault("RUN_SCHEDULER", "0")
os.environ.setdefault("POPULATE_CACHE_ON_BOOT", "0")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fmt_pct(v) -> str:
    return "—" if v is None else f"{v:+.2f}%"


def _render(uid: int, email: str, out: dict) -> str:
    s, cf, r = out["stopped"], out["cancelled_followthrough"], out["realised"]
    lines = [
        "",
        "═" * 64,
        f"user {uid}  ({email})" + (f"   최근 {out['window_days']}일" if out["window_days"] else "   전 기간"),
        "═" * 64,
        "",
        "▸ 멈춤은 무엇으로 끝났나",
        f"    시작 {s['started']}건  →  진행 {s['proceeded']} · 취소 {s['cancelled']} · 미결 {s['open']}",
    ]

    if s["started"] == 0:
        lines.append("    (사전 기록이 없다 — 아래 수익률은 멈춤과 무관한 전체 거래다)")

    if cf["cancelled"]:
        lines += [
            "",
            "▸ 취소는 회피였나, 미룸이었나",
            f"    취소 {cf['cancelled']}건 중 {cf['bought_later_anyway']}건은 나중에 결국 샀다"
            f"  (끝내 안 산 것 {cf['never_bought']}건)",
        ]
        if cf["median_days_until_bought"] is not None:
            lines.append(f"    결국 산 경우, 취소로부터 중앙값 {cf['median_days_until_bought']:.1f}일")

    w, o = r["with_friction"], r["without_friction"]
    lines += [
        "",
        "▸ 실현 수익률 분포 (FIFO 슬라이스, 체결가 기준)",
        f"    멈춤 경유   n={w['n']:<4} median {_fmt_pct(w['median_pct'])}   mean {_fmt_pct(w['mean_pct'])}",
        f"    멈춤 미경유 n={o['n']:<4} median {_fmt_pct(o['median_pct'])}   mean {_fmt_pct(o['mean_pct'])}",
    ]
    if not r["comparable"]:
        lines.append(
            f"    ⚠️ 두 분포를 비교하지 마라 — 그룹당 최소 {r['min_group_n']}건이 필요한데 미달이다."
        )
    else:
        lines.append(
            "    ⚠️ 무작위 배정이 아니다. 어떤 거래에 멈춤을 썼는지는 본인이 골랐다."
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="멈춤의 귀결 리포트")
    ap.add_argument("--user", type=int, help="특정 user_id 만")
    ap.add_argument("--days", type=int, help="최근 N일로 제한 (기본: 전 기간)")
    ap.add_argument("--json", action="store_true", help="원시 JSON 출력")
    args = ap.parse_args()

    from app import create_app
    from models import PreTradeReflection, TradeHistory, User
    from services.pre_trade.friction_outcome import compute_friction_outcome

    app = create_app()
    with app.app_context():
        q = User.query
        if args.user:
            q = q.filter(User.id == args.user)
        users = q.all()

        payloads = {}
        for u in users:
            refl = PreTradeReflection.query.filter_by(user_id=u.id).all()
            trades = TradeHistory.query.filter_by(user_id=u.id).all()
            # 기록도 거래도 없는 유저는 찍을 게 없다
            if not refl and not trades:
                continue
            out = compute_friction_outcome(refl, trades, window_days=args.days)
            payloads[u.id] = out
            if not args.json:
                print(_render(u.id, u.email or "?", out))

        if args.json:
            print(json.dumps(payloads, indent=2, ensure_ascii=False, default=str))
        elif not payloads:
            print("기록도 거래도 있는 유저가 없다.")
        else:
            print(f"\n{'─'*64}\n{len(payloads)}명 집계.  이 숫자는 답이 아니라 질문이다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
