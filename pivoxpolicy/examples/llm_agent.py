"""실제 LLM 에이전트 데모 — Claude 가 정산 업무를 하다가 숨은 지시가 든 뉴스를 읽는다. 도구를 쓸 때마다 PivoxPolicy 가 판정한다.

준비
  pip install "anthropic>=2.8"                      (pivoxpolicy 본체는 이 의존성이 없다 — 이 예제만 쓴다)
  Anthropic 자격 증명: ANTHROPIC_API_KEY 또는 `ant auth login`
  런타임:  PIVOX_ADMIN_TOKEN=<16자 이상> python3 -m pivoxpolicy.cli serve
  콘솔(/admin)에서 '트레이딩·결제 에이전트' 를 등록하고 받은 키를 PIVOX_AGENT_KEY 에 넣는다.

실행
  PIVOX_AGENT_KEY=pvx_... python3 examples/llm_agent.py [--wait-approval 120] [--misconfigured]

  --misconfigured   뉴스 속 공지를 따르도록 잘못 설정된 에이전트를 흉내 낸다. 모델이 숨은 지시를 따르는 경우에도
                    런타임이 막는지 보는 용도다(도구는 모두 모의 — 실제 돈은 움직이지 않는다).
  --wait-approval   사람 승인이 필요한 호출에서 몇 초까지 기다릴지. 기다리는 동안 콘솔에서 승인하면 그 호출이 실행된다.
비용: Claude Opus 5.5 호출 몇 번(대개 3~5회)이 청구된다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pivoxpolicy.runtime.llm_agent import MODEL, SYSTEM, SYSTEM_MISCONFIGURED, GuardedAgent  # noqa: E402
from pivoxpolicy.runtime.sdk import Guard  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", default=os.environ.get("PIVOX_RUNTIME_URL", "http://127.0.0.1:8787"))
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--wait-approval", type=float, default=0, help="승인을 기다릴 최대 초 (0 = 기다리지 않음)")
    ap.add_argument("--misconfigured", action="store_true", help="뉴스 속 공지를 따르도록 잘못 설정된 에이전트")
    ap.add_argument("--no-fallbacks", action="store_true", help="서버 쪽 대체 모델(fallbacks)을 끈다")
    o = ap.parse_args()
    key = os.environ.get("PIVOX_AGENT_KEY")
    if not key:
        print("PIVOX_AGENT_KEY 에 콘솔에서 받은 에이전트 키를 넣는다", file=sys.stderr)
        return 2
    try:
        import anthropic
    except ImportError:
        print('Anthropic SDK 가 없다: pip install "anthropic>=2.8"', file=sys.stderr)
        return 2

    agent = GuardedAgent(anthropic.Anthropic(), Guard(o.url, key), model=o.model, effort=o.effort,
                         system=SYSTEM_MISCONFIGURED if o.misconfigured else SYSTEM, wait_approval=o.wait_approval,
                         fallbacks=not o.no_fallbacks)
    try:
        res = agent.run()
    except anthropic.AuthenticationError:
        print("Anthropic 인증 실패 — ANTHROPIC_API_KEY 또는 `ant auth login` 을 확인한다", file=sys.stderr)
        return 1
    except anthropic.RateLimitError as e:
        print(f"Anthropic 요청 한도 초과 — 잠시 뒤 다시({e.response.headers.get('retry-after', '?')}초)", file=sys.stderr)
        return 1
    except anthropic.APIStatusError as e:
        print(f"Anthropic API 오류 {e.status_code}: {e.message} (request-id {e.response.headers.get('request-id')})", file=sys.stderr)
        return 1
    except TypeError as e:                     # 자격 증명이 아예 없으면 SDK 가 요청 때 TypeError 를 낸다
        if "authentication" not in str(e):
            raise
        print("Anthropic 자격 증명이 없다 — ANTHROPIC_API_KEY 를 넣거나 `ant auth login` 을 한다", file=sys.stderr)
        return 1
    except anthropic.APIConnectionError:
        print("Anthropic API 에 연결하지 못했다", file=sys.stderr)
        return 1

    print("\n── 결과 ──")
    for c in res["calls"]:
        src = ", ".join(f"{s['kind']}{'' if s['trusted'] else '(외부)'}" for s in c["input_sources"])
        print(f"- {c['tool']} {c['input']} · 출처 {src} → {c.get('decision')}" + (f" [{c.get('control')}] {c.get('reason')}" if c.get("decision") != "allow" else ""))
    print(f"실제로 실행된 송금: {res['ledger'] or '없음'}")
    print(f"토큰: 입력 {res['usage']['input_tokens']:,} · 출력 {res['usage']['output_tokens']:,} · 멈춘 이유 {res['stop_reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
