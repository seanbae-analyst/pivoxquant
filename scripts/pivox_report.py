#!/usr/bin/env python3
"""PivoxReport — 내 토스증권 계좌 하나를 읽어 거울 리포트를 만든다.

무엇을 하나
-----------
1. ``TOSS_CLIENT_ID`` / ``TOSS_CLIENT_SECRET`` 로 토큰을 받고
2. 계좌 목록 → 보유 주식 → 최근 N일 종료 주문 → 대기 주문 → 환율을 **GET 으로만** 읽어
3. ``services/toss/report.py`` 로 계산한 뒤 markdown + json 을 ``reports/personal/`` 에 쓴다.

주문을 내는 코드는 이 스크립트에도, 클라이언트에도 없다. 토스 토큰은 scope 가
없어서(같은 토큰으로 주문이 가능하다) 이 프로세스 경계가 유일한 방어선이다 —
``TossReadOnlyClient`` 가 allowlist 밖 경로를 요청 전에 거부한다.

사용법
------
    export TOSS_CLIENT_ID=... TOSS_CLIENT_SECRET=...      # 또는 .env
    ./venv/bin/python scripts/pivox_report.py                # 이력 730일 + 최근 90일 거울
    ./venv/bin/python scripts/pivox_report.py --since 1500   # 계좌가 더 오래됐으면 넓혀서 — 리포트 첫 줄이 "일치"가 될 때까지
    ./venv/bin/python scripts/pivox_report.py --days 30 --json
    ./venv/bin/python scripts/pivox_report.py --dump-raw raw.json   # 응답 원본 저장
    ./venv/bin/python scripts/pivox_report.py --from-raw raw.json   # 네트워크 없이 재렌더

알아둘 것
---------
* 토스는 client 당 유효 토큰 1개다. 이 스크립트를 두 개 동시에 돌리면 서로 토큰을
  무효화한다. 한 번에 하나만.
* 403 ``edge-blocked`` 면 이 머신의 공인 IP 가 WTS 설정 → Open API → 허용 IP 에
  없는 것이다.
* 출력 디렉터리는 gitignore 다. 계좌번호는 마스킹돼 저장되지만 보유 내역은 그대로
  들어가니 다른 곳으로 옮길 땐 그 점을 알고 옮길 것.
* ``--dump-raw`` 파일에는 계좌번호 원문이 들어간다 (토큰·시크릿은 안 들어간다).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.toss.client import TossApiError, TossReadOnlyClient  # noqa: E402
from services.toss.mirror_report import build_mirror_report, render_mirror_markdown  # noqa: E402
from services.toss.report import KST  # noqa: E402

DEFAULT_OUT = os.path.join("reports", "personal")


def _load_dotenv_if_present() -> None:
    """Same convention as app.py — .env wins. Only the two TOSS_* keys matter."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        return
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)


def fetch_raw(client: TossReadOnlyClient, *, days: int, since_days: int, account_seq: int | None, as_of: datetime) -> dict:
    accounts = client.accounts()
    if not accounts:
        raise SystemExit("토스 계좌 목록이 비어 있다 (종합매매 계좌만 노출됨).")
    if account_seq is None:
        account = accounts[0]
    else:
        match = [a for a in accounts if int(a.get("accountSeq", -1)) == account_seq]
        if not match:
            raise SystemExit(f"accountSeq {account_seq} 가 계좌 목록에 없다: {[a.get('accountSeq') for a in accounts]}")
        account = match[0]
    seq = int(account["accountSeq"])
    date_to = as_of.date().isoformat()
    date_from = (as_of.date() - timedelta(days=since_days)).isoformat()
    holdings = client.holdings(seq)
    closed = list(client.iter_closed_orders(seq, date_from=date_from, date_to=date_to, max_pages=200))
    held = {it.get("symbol") for it in holdings.get("items") or []}
    departed = sorted({o.get("symbol") for o in closed if o.get("symbol")} - held)
    names: dict[str, str] = {}
    if departed:
        try:  # reference data only; a failure here costs names, not numbers
            names = {s["symbol"]: s.get("name") or "" for s in client.stocks(departed)}
        except TossApiError as e:  # pragma: no cover - network path
            print(f"종목명 조회 실패 (무시): {e}", file=sys.stderr)
    return {
        "fetched_at": as_of.isoformat(timespec="seconds"),
        "window_days": days,
        "history_since": date_from,
        "account": account,
        "accounts_count": len(accounts),
        "holdings": holdings,
        "closed_orders": closed,
        "open_orders": client.open_orders(seq),
        "fx": client.exchange_rate("USD", "KRW"),
        "names": names,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--days", type=int, default=90, help="'최근' 거울의 창 (기본 90일)")
    ap.add_argument("--since", type=int, default=730, help="주문 이력을 며칠 전부터 받을지 (기본 730일). 계좌 개설 이전까지 덮어야 이력이 완전하다")
    ap.add_argument("--account-seq", type=int, default=None, help="계좌가 여럿일 때 accountSeq 지정")
    ap.add_argument("--out", default=DEFAULT_OUT, help=f"출력 디렉터리 (기본 {DEFAULT_OUT})")
    ap.add_argument("--json", action="store_true", help="markdown 대신 JSON 을 stdout 에 출력")
    ap.add_argument("--dump-raw", metavar="FILE", help="API 응답 원본을 이 파일에 저장")
    ap.add_argument("--from-raw", metavar="FILE", help="네트워크 없이 저장된 원본으로 렌더")
    ap.add_argument("--no-write", action="store_true", help="파일을 쓰지 않고 stdout 만")
    args = ap.parse_args(argv)

    if args.from_raw:
        with open(args.from_raw, encoding="utf-8") as fh:
            raw = json.load(fh)
        as_of = datetime.fromisoformat(raw["fetched_at"]) if raw.get("fetched_at") else datetime.now(KST)
    else:
        _load_dotenv_if_present()
        client = TossReadOnlyClient()
        if not client.configured:
            print("TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 가 없다. WTS 설정 → Open API 에서 발급해 .env 에 넣을 것.",
                  file=sys.stderr)
            return 2
        as_of = datetime.now(KST)
        try:
            raw = fetch_raw(client, days=args.days, since_days=args.since, account_seq=args.account_seq, as_of=as_of)
        except TossApiError as e:
            print(f"토스 API 실패: {e}", file=sys.stderr)
            if e.code == "edge-blocked" or e.status == 403:
                print("→ 이 머신의 공인 IP 를 WTS 설정 → Open API → 허용 IP 에 등록했는지 확인.", file=sys.stderr)
            return 1
        if args.dump_raw:
            with open(args.dump_raw, "w", encoding="utf-8") as fh:
                json.dump(raw, fh, ensure_ascii=False, indent=2)

    report = build_mirror_report(
        account=raw["account"],
        holdings=raw["holdings"],
        closed_orders=raw["closed_orders"],
        open_orders=raw.get("open_orders"),
        fx=raw["fx"],
        history_since=raw.get("history_since"),
        window_days=int(raw.get("window_days") or args.days),
        names=raw.get("names"),
        as_of=as_of,
    )
    md = render_mirror_markdown(report)

    if not args.no_write:
        os.makedirs(args.out, exist_ok=True)
        stem = os.path.join(args.out, f"pivox_report_{as_of.date().isoformat()}")
        with open(stem + ".md", "w", encoding="utf-8") as fh:
            fh.write(md)
        with open(stem + ".json", "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print(f"wrote {stem}.md / .json", file=sys.stderr)

    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
