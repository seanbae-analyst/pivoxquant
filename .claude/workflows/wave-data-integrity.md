---
name: wave-data-integrity
description: 데이터 무결성 wave — fx-consistency-guard + data-freshness-monitor + cache-poisoning-sentinel 3 agent 병렬 dispatch
---

# wave-data-integrity

## 목적

PivoxQuant 데이터 파이프라인의 3축 invariant 를 한 번에 회귀 검증한다.
이전 대형 사고가 정확히 이 3축에 집중되어 있다 (메모리 v44.9 5 critical SHIP-BLOCKER).

| Axis | 사고 precedent | Agent |
|------|----------------|-------|
| FX consistency (Pattern 7) | portfolio_history +52,281% (PR #484) / risk_summary 700배 (commit eea051e5) | `fx-consistency-guard` |
| Data freshness | KIS/FMP stale 60s+ / yfinance fallback | `data-freshness-monitor` |
| Cache poisoning (Pattern 6) | earnings_tone 24h cross-user (PR #488) / SignalCache sizing leak | `cache-poisoning-sentinel` |

3 agent 모두 메모리 [[project_agent_inventory]] 상 **호출 0회 dormant** — 본 workflow 가 게이트 역할.

## 실행 방법 (Claude Code 에서 직접 호출)

```
3개의 Task 를 동시에 띄우세요:

Task 1 — FX consistency 회귀:
  agent: fx-consistency-guard
  prompt: "~/dev/pivoxquant/services/ + routes/ 전수 sweep.
           aggregation 패턴 grep → 각 hit 직전 100줄 fx_service / convert_to_krw /
           value_krw|value_usd 별도 필드 검증. 화이트리스트 (portfolio.py:260-272,
           fx_service.py) 외에서 user-facing aggregation 이면서 FX 변환 없으면 P0 FLAG.
           recent diff scan 도 포함 — origin/main..HEAD 신규 aggregation 라인."

Task 2 — 데이터 freshness 회귀:
  agent: data-freshness-monitor
  prompt: "~/dev/pivoxquant/services/ + scripts/nightly/ sweep.
           KIS / DART / KRX / FMP / SEC EDGAR / Alpaca 6 소스 staleness 임계값
           준수 여부 + budget 80% 한도 + 비공식 데이터 (yfinance/pykrx/naver/daum
           finance) grep 0건. fx_service.STALE_SECONDS / cache_ttl 모듈 / price_overlay
           3-tier fallback 보존 검증. mocked 만 — 실 외부 API 호출 금지."

Task 3 — Cache poisoning 회귀:
  agent: cache-poisoning-sentinel
  prompt: "~/dev/pivoxquant/services/ai/ + services/data/ + services/agents/ +
           services/quant/ + routes/ 전수 sweep. 모든 cache write (_cache.set /
           _set_cache / @lru_cache / SignalCache / Redis) 의 key composition 에
           user_id 포함 여부 검증. 화이트리스트 (sector_regime / vix_level / fx_service
           / feature_flags / SignalCache ticker prices / earnings_tone ticker-only) 외
           hit 은 P0 FLAG. recent diff 신규 cache.set 라인 강제 통과."

Task 4 (Task 1-3 완료 후) — 통합 게이트 회귀 테스트:
  Bash: cd ~/dev/pivoxquant && ./venv/bin/python -m pytest \
        tests/test_data_integrity_gates.py \
        tests/test_fx_staleness.py \
        tests/test_fx_historical.py \
        -v 2>&1 | tail -40

  목적: 위 3 agent 가 detect 한 invariant 가 자동 회귀 테스트로도 검증됨을 확인.
       (agent 보고 + 테스트 결과 cross-validate)
```

## 예상 소요

- Task 1-3 병렬: ~10분 (grep + Read 만, API 호출 없음)
- Task 4 pytest: ~10초 (15 + 기존 fx tests)

## 완료 기준

- 3 agent 모두 `## Status: COMPLETE` 보고
- P0 FLAG 0건 (있으면 별도 fix PR + 본 wave 재실행)
- pytest tests/test_data_integrity_gates.py 15/15 PASS
- HANDOVER.md 외부 액션 카드 0건 추가 (= 회귀 없음)

## Trigger 자동화 (권고)

다음 PR 에서 본 wave 강제:
- `services/ai/**` 신규 파일 또는 `_cache.set` / `@lru_cache` 라인 추가
- `services/quant/portfolio.py` / `services/quant/risk_*.py` aggregation 추가
- `services/data/fmp.py` / `services/data/kis*.py` 응답 처리 변경
- `routes/portfolio/**` total / aggregate endpoint 변경
- `routes/risk/**` 변경
- `services/artifacts/*_service.py` 다종목 합산 변경

## 비용

**0원** — grep + Read + Bash (pytest) 만. 추가 API/dependency 없음.
Slack alert 는 기존 `#alerts` free tier webhook 재사용.

## Related

- `tests/test_data_integrity_gates.py` — 본 wave 의 자동 회귀 게이트 (15 cases)
- `services/scheduler/cron_jobs.py` — `ops_data_integrity_sweep` 일일 cron (04:00 KST)
- `scripts/nightly/data_integrity_sweep.py` — cron entrypoint
- Memory: `feedback_bug_fix_patterns.md` Pattern 6 (cache) / Pattern 7 (FX)
- Memory: `project_agent_inventory.md` — dormant 3 agent 활용도 게이지
