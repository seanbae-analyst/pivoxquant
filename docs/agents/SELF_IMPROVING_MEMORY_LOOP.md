# Self-Improving Memory Loop (v57-C2)

**작성**: 2026-05-28
**작성자**: engineering agent (CEO 지시 v57-C2)
**상태**: SPEC (구현은 v58 이후)
**비용**: ₩0 (Max 플랜 + 기존 인프라만)
**선행 의존**: v52~v56 자동화 인프라 (autopilot_log / cron 16개 / 옵저버빌리티)

---

## 0. TL;DR

지금 76개 agent는 **stateless**다. 매번 새로 시작하고 어제 무엇을 했는지 기억하지 못한다. autopilot_log v44~v55 마라톤에서 동일 패턴(KIS 500 / FX stale / cron timeout / 같은 P0)이 **반복 fix됐다**.

이 문서는 agent에 **4개 학습 loop**를 붙여서, 시간이 지날수록 똑똑해지게 하는 spec이다. ML 라이브러리 없이 JSON + 단순 통계만 사용. 추가 비용 0원.

---

## 1. 현 stateless 한계 (Phase 1 실측)

### 1-1. 메모리 활용 agent: 14/76 (18%)

```bash
$ grep -l "memory" .claude/agents/*.md
bkit-orchestrator.md, bug-hunter.md, cache-poisoning-sentinel.md,
compliance-gatekeeper.md, docs.md, email-deliverability.md,
frontend-test-runner.md, fx-consistency-guard.md, launch-coordinator.md,
launch-runner.md, legal.md, qa.md, regulatory-monitor.md, stripe-billing.md
```

이 중 "memory"는 대부분 **CEO 메모리 룰 read** 용도. **학습 메모리**(과거 호출 결과 누적 → 다음 호출 시 활용)는 **0개**.

### 1-2. issue_patterns / sprint_outcomes / agent_kpi: 0/76

```bash
$ grep -l "issue_patterns\|sprint_outcomes\|agent_kpi\|past.*learning" .claude/agents/*.md
(empty)
```

→ **현 agent는 "지난주 같은 issue를 어떻게 fix했는지" 모른다**.

### 1-3. autopilot_log 반복 패턴 (458줄, 30일치)

api-sentinel 호출 4회(2026-05-28 07:53 / 09:47 / 09:49 / 14:36 / 14:52) — **거의 동일한 결과**:
- health 200, version 갱신
- indices/macro/fx 401 (auth-gated, route loaded, no 500)
- git dirty (CEO WIP) → autofix 스킵
- "no regression"

같은 5엔드포인트, 같은 결론, 같은 텍스트 — 결과를 **누적 학습하면 다음 호출은 "변경 없음, skip recommendation"** 으로 끝낼 수 있다.

### 1-4. 마라톤 wave 반복 P0

v47 / v49 / v51 / v53 / v55 wave 전부에서 등장한 P0:
- legal_filter 패턴 누락 (take-profit / stop-loss / 매수의견 등)
- FX 변환 누락 (KRW raw 합산)
- ticker normalization (005930 vs 005930.KS)
- per-metric try-except 누락
- SWR dedup 3계층

**9-bug-pattern은 메모리에 정의돼 있지만 agent가 호출 시 자동 적용 안 함**. CEO 메모리 룰 reload는 매 세션 1회만 — agent prompt 안에서 자동 점검 X.

---

## 2. 4-Loop 설계

### Loop 1: Issue Pattern Library

#### 목적
같은 issue 다시 만나면 "전에 어떻게 fix했는지" 즉시 reuse.

#### 파일
`/Users/seanbae/dev/pivoxquant/.claude/memory/issue_patterns.json`

#### 스키마
```json
{
  "schema_version": "1.0",
  "last_updated": "2026-05-28T14:52:00+09:00",
  "patterns": [
    {
      "id": "KIS_HTTP_500_KOSPI_BURST",
      "category": "data_freshness",
      "first_seen": "2026-05-15",
      "last_seen": "2026-05-27",
      "occurrences": 23,
      "root_cause": "KIS Open API KOSPI 종목 측 instability — 09:00~09:15 KST 장 개장 직후 burst 발생",
      "symptoms": [
        "GET /api/market/quote?ticker=005930 → 500",
        "Sentry msg contains 'KIS rate limit exceeded'",
        "morning-briefing 06:25 직후 30분 내 6회+ 재현"
      ],
      "recommended_action": "1초 backoff retry x3 + cache stale fallback (TTL 만료시 stale 응답 + 비동기 refresh)",
      "code_path": "services/data/kis_market_adapter.py:fetch_quote_with_retry",
      "agents_that_handled": ["data-freshness-monitor", "bug-hunter", "investigate-bug"],
      "last_fix_commit": "06cbc88b",
      "regression_guard": "tests/test_kis_burst_recovery.py",
      "confidence": 0.92
    },
    {
      "id": "LEGAL_FILTER_NAKED_BUY_SELL",
      "category": "compliance",
      "first_seen": "2026-05-04",
      "last_seen": "2026-05-22",
      "occurrences": 8,
      "root_cause": "legal_filter.py case-sensitive BUY/SELL는 의도적(산문 over-scrub 방지) — IGNORECASE로 '고치지' 말 것",
      "symptoms": ["PR diff에 re.IGNORECASE 추가 시도"],
      "recommended_action": "feedback_legal_filter_design.md 메모리 룰 인용 + 변경 차단",
      "agents_that_handled": ["legal-kr-fintech", "compliance-gatekeeper"],
      "last_fix_commit": "c3801359",
      "confidence": 1.0,
      "ANTI_PATTERN": true
    }
  ]
}
```

#### Cron 통합
- `ops_pattern_library_sync` 신규 cron, **매일 06:23 KST** (morning-briefing 06:25 직전 2분 윈도)
- 스크립트: `services/observability/pattern_extractor.py` (신규)
- 입력: autopilot_log.md 최근 30일 + git log --since="30 days ago" + Sentry 이슈 (free tier)
- 출력: `issue_patterns.json` 누적 갱신
- 알고리즘 (ML 없음):
  - 키워드 빈도 + Levenshtein 거리 < 0.3 → 같은 패턴으로 클러스터
  - occurrences ≥ 3 → 정식 등록
  - occurrences = 1 → "watching" 상태

#### Agent 통합
`bug-hunter`, `investigate-bug`, `data-freshness-monitor`, `cache-poisoning-sentinel` 프롬프트 상단에 추가:
```
## 사전 검증
1. `/Users/seanbae/dev/pivoxquant/.claude/memory/issue_patterns.json` 먼저 read
2. 현재 symptom과 매칭되는 pattern id 검색
3. 매칭되면 `recommended_action` 우선 적용 (confidence ≥ 0.8)
4. ANTI_PATTERN = true 이면 즉시 차단 + 메모리 룰 인용
```

---

### Loop 2: Predictive Issue Detection

#### 목적
"내일 fail할 것 같은 cron" / "burst 발생 시간대"를 사전 예측 → 사전 fix.

#### 파일
- `services/observability/predictor.py` (신규)
- `/Users/seanbae/dev/pivoxquant/.claude/memory/predictions.json` (출력)

#### 입력 데이터
- `autopilot_log.md` 90일 (지금 458줄, 충분)
- crontab 16 entries 실행 history (각 cron이 stdout/stderr를 `~/Library/Logs/pivoxquant/` 에 남김 — 이미 존재)
- Sentry free tier API (월 5K 이벤트 — 추가 비용 X)

#### 통계 모델 (ML 없음, simple stats)

1. **요일별 fail rate**
   - 각 cron × 7요일 → fail count / total run
   - rate > 0.2 → "weekday-X fragile" 태그
   - 예: `ops_morning_briefing` 일요일 fail rate 0.4 → 주말 보강 로직 필요

2. **시간대별 burst window**
   - 1시간 bucket 30일 누적 → fail count
   - poisson 분포 mean + 2σ 초과 → burst window
   - 예: KIS 500 09:00~09:15 → "pre-fetch warm cache 08:55"

3. **연쇄 실패 chain**
   - cron A fail → 5분 내 cron B fail 빈도
   - 0.7 초과 → "A가 B의 upstream blocker" 태그

4. **회귀 신호 (regression signal)**
   - 신규 commit X 후 24h 내 fail rate 변화
   - +50% 이상 → "commit X 의심" 태그 → 다음 morning-briefing prepend

#### 출력 구조
```json
{
  "generated_at": "2026-05-28T23:00:00+09:00",
  "horizon_hours": 24,
  "predictions": [
    {
      "type": "fragile_window",
      "cron_id": "ops_kis_warmup",
      "window": "2026-05-29 09:00~09:15 KST",
      "expected_fail_probability": 0.78,
      "based_on": "burst pattern N=23 occurrences in last 30 days",
      "preventive_action": "pre-fetch 08:55 + 1s backoff retry x3",
      "auto_executable": true
    },
    {
      "type": "regression_signal",
      "suspect_commit": "abc1234",
      "metric": "vitest pass rate",
      "change": "-3.2%",
      "based_on": "12h post-commit observation",
      "preventive_action": "vitest --run + bisect",
      "auto_executable": false
    }
  ],
  "precision_30d": 0.71,
  "recall_30d": 0.58
}
```

#### Self-evaluation
- 예측 vs 실제 발생 → precision/recall 자동 계산
- precision < 0.6 → 모델 파라미터 자동 조정 (cluster threshold 완화)
- recall < 0.5 → 입력 데이터 범위 확장 권장 (60일 → 90일)

#### Cron 통합
- `ops_predictive_scan` 매일 23:00 KST (autopilot_log + cron history 분석)
- 결과를 `~/.claude/briefings/morning-{date}.md` 에 prepend (morning-briefing이 다음 06:25 read)

---

### Loop 3: Agent Performance Tracking

#### 목적
- 어떤 agent가 자주 호출되는지 (workhorse)
- 어떤 agent가 한 번도 안 호출됐는지 (dormant → deprecate 후보)
- 어떤 agent의 audit 통과율이 낮은지 (refactor 후보)

#### 파일
`/Users/seanbae/dev/pivoxquant/.claude/memory/agent_kpi.json`

#### 스키마
```json
{
  "schema_version": "1.0",
  "last_updated": "2026-05-28T23:00:00+09:00",
  "window_days": 30,
  "agents": {
    "bug-hunter": {
      "calls": 47,
      "avg_tokens_per_call": 18420,
      "audit_pass_rate": 0.89,
      "regressions_introduced": 1,
      "avg_wall_time_sec": 412,
      "category": "workhorse",
      "last_called": "2026-05-28T14:36:00+09:00",
      "frequent_patterns": ["KIS_HTTP_500_KOSPI_BURST", "LEGAL_FILTER_NAKED_BUY_SELL"]
    },
    "secrets-rotator": {
      "calls": 0,
      "category": "dormant",
      "last_called": null,
      "deprecate_candidate": true,
      "reason": "0 calls in 30 days; manual rotation via Vercel REST API preferred"
    },
    "ux-researcher": {
      "calls": 2,
      "audit_pass_rate": 0.5,
      "category": "low_signal",
      "refactor_candidate": true,
      "reason": "calls < 5, pass rate < 0.7"
    }
  },
  "summary": {
    "workhorse_count": 9,
    "dormant_count": 21,
    "deprecate_candidates": 5
  }
}
```

#### 데이터 소스
- CC scheduled-tasks fire log: `~/Library/Logs/claude-code/scheduled-tasks.log`
- agent invocation log: 각 agent의 markdown frontmatter에 invocation_id 추가 권장 (v58)
- audit 통과율: post-audit commit에서 grep "audit: PASS" / "audit: FAIL"
- token 사용: CC 세션 transcript의 `usage` 필드 (Anthropic SDK 응답)

#### Cron 통합
- `ops_agent_kpi_weekly` 매주 일요일 22:00 KST
- 출력을 `project_agent_inventory.md` 에 prepend (수동 inventory 자동화)
- workhorse / dormant 자동 분류 → CEO 메모리 룰 inventory 자동 갱신

---

### Loop 4: Sprint Outcome Learning

#### 목적
"이런 wave는 추정 X시간이지만 실제 1.5X 걸린다" 학습 → 다음 sprint 추정 정확도 향상.

#### 파일
`/Users/seanbae/.claude/projects/-Users-seanbae-Desktop---/memory/sprint_outcomes.md`

#### 구조
```markdown
## v52~v56 Outcome Log

### v55 (2026-05-26 ~ 2026-05-28)
- **목표**: 변호사 PDF 재발송 + 출시검증 + 4 wave 헌팅
- **추정 시간**: 8h
- **실제 시간**: 14h (1.75x)
- **달성**: PDF 100% / wave 4/4 / 6 commit
- **미달**: prefs 잔여 6건 (carry-over)
- **blocker**: Vercel CLI 토큰 만료 → REST API 우회 (2h 추가)
- **unblock 패턴**: Vercel env는 항상 REST API 직접 호출 (CLI stdin 미지원)
- **learning**:
  - "변호사 PDF" wave는 항상 audit 1회 추가 → 1.3x buffer
  - "출시검증" wave는 always Vercel rotation 포함 → +2h 고정 비용

### v54 (2026-05-24)
- **목표**: 마라톤 R1+R2 헌팅 + 출시하드닝
- **추정 시간**: 6h
- **실제 시간**: 9h (1.5x)
- **learning**: "출시하드닝" 항상 한글폰트 CSP 등 cosmetic 1~2건 → +1h
```

#### 학습 활용
다음 sprint planning agent (launch-coordinator)가 호출되면:
1. `sprint_outcomes.md` read
2. 유사 wave 검색 (제목 키워드 matching)
3. 평균 ratio (실제/추정) 계산
4. CEO 요청 시간에 ratio 곱한 값을 권장

예: CEO "버그헌팅 wave 8시간" 요청
→ 과거 헌팅 wave 평균 ratio 1.5x → "권장 추정 12h, carry-over slot 2건 확보"

#### 갱신 주기
- 자동: 매 sprint 종료 시 (`ops_sprint_close` cron 또는 hook)
- 수동: CEO sprint 종료 명령 시 launch-coordinator가 prepend

---

## 3. Phase 구현 단계 (의존성 + 일정)

### Phase A (1주, 0원) — Issue Pattern Library
**의존**: 없음 (autopilot_log + git log만 사용)

1. **D1**: `services/observability/pattern_extractor.py` 작성 (200~300줄)
   - 입력: autopilot_log.md, `git log --pretty=format:'%H %s' --since="30 days ago"`
   - 알고리즘: 키워드 빈도 + simple Levenshtein cluster
   - 출력: `.claude/memory/issue_patterns.json`
2. **D2**: 초기 scan 실행 → 최초 pattern 10~20개 등록
3. **D3**: `ops_pattern_library_sync` cron 추가 (매일 06:23 KST)
   - crontab: `23 6 * * * cd ~/dev/pivoxquant && /usr/bin/env python3 -m services.observability.pattern_extractor >> ~/Library/Logs/pivoxquant/pattern-sync.log 2>&1`
4. **D4**: 4개 agent 프롬프트에 "사전 검증" 섹션 추가
   - bug-hunter / investigate-bug / data-freshness-monitor / cache-poisoning-sentinel
5. **D5**: 단위 테스트 (`tests/observability/test_pattern_extractor.py`)
   - fixture: 합성 autopilot_log 30 entries
   - assert: cluster 정확도, ANTI_PATTERN 플래그 보존
6. **D6**: 라이브 검증 — 다음 헌팅 wave 시 agent가 known pattern 인용하는지 확인
7. **D7**: HANDOVER.md 갱신

**예상 산출물**: pattern_extractor.py + issue_patterns.json + 4 agent prompt 업데이트 + 1 cron + 1 테스트

---

### Phase B (1주, 0원) — Predictive Detection
**의존**: Phase A (pattern_extractor 재사용)

1. **D1~D2**: `services/observability/predictor.py` 작성 (300~400줄)
   - Simple stats: poisson burst detection, weekday fail rate, chain failure
   - **외부 ML 라이브러리 금지** — Python stdlib `statistics` + 직접 구현
2. **D3**: 초기 90일 backfill (autopilot_log + crontab logs)
3. **D4**: `ops_predictive_scan` cron 추가 (매일 23:00 KST)
4. **D5**: morning-briefing 통합 — predictions.json 결과를 briefing top에 prepend
5. **D6**: Self-eval 로직 — precision/recall 자동 계산
6. **D7**: 라이브 검증 — 7일 후 예측 정확도 측정

**경고**: 예측 모델은 첫 30일 동안 false positive 많을 것 — confidence threshold 0.7 시작, 점진 조정.

---

### Phase C (2주, 0원) — Agent KPI Tracking
**의존**: 없음 (독립적으로 가능, 하지만 Phase A/B 데이터 재사용)

1. **D1~D3**: CC scheduled-tasks log scanner 작성 (`scripts/agent_kpi_collector.py`)
   - 입력: `~/Library/Logs/claude-code/scheduled-tasks.log` + autopilot_log
   - 정규식: agent 이름 + 호출 횟수 + audit 결과
2. **D4~D5**: token 사용량 추적
   - CC 세션 transcript에서 `usage` 필드 추출 (가능 시)
   - 어려우면 wall time 기반 추정 (15K token/min 가정)
3. **D6~D7**: audit 통과율 계산
   - autopilot_log에서 "audit: PASS/FAIL" 키워드 카운트
4. **D8**: `ops_agent_kpi_weekly` cron 추가
5. **D9~D10**: `project_agent_inventory.md` 자동 prepend 로직
6. **D11~D14**: 워크호스 / dormant 분류 검증 + CEO 메모리 inventory 동기화

---

### Phase D (지속) — Sprint Outcome Learning
**의존**: 없음 (수동 시작 → 점진 자동화)

1. **즉시**: v52~v56 backfill (수동, ~30분)
   - 각 sprint commit count / wall time / blocker / unblock 기록
2. **점진 자동화**:
   - launch-coordinator 호출 시 sprint 종료 hook
   - 추정 ratio 계산 로직
3. **출시 후**: 사용자 친화도 wave (UX wave) 등 더 다양한 wave 카테고리 학습

---

## 4. Phase 4 창의 확장 (Bonus, 출시 후)

### 4-1. Code Memory Loop
- 입력: git log + autopilot_log fail correlation
- 출력: "이 파일 수정 후 X% 회귀 발생" 학습
- 활용: 다음 수정 시 verify-* agent 자동 spawn
- **위험**: false positive 시 CEO 짜증 → confidence ≥ 0.85 게이트 + opt-in

### 4-2. User Friction Memory
- **출시 후** (사용자 데이터 필요)
- Sentry / 백엔드 로그 / 사용자 응답 → "이 user는 X 기능에서 자주 멈춤"
- onboarding 메일 시퀀스 개인화
- PIPA §28-8 외부이전 고려: Sentry / SendGrid 데이터 활용 시 변호사 자문

### 4-3. Self-Replicating Sprint Pattern
- "이런 wave는 효과적이었다" 패턴 자동 추출
- 다음 wave 자동 spawning
- **위험**: CEO 의도 무관 wave → busywork 룰 위반
- **안전장치**: BLOCKER 시에만 CEO inbox로 carry-over, 일반 wave는 carry-over slot로만

---

## 5. 핵심 위험 + 안전장치

### 5-1. 메모리 오염 (poisoning)
- 잘못된 pattern이 등록되면 다음 호출들이 잘못된 fix 적용
- **장치**: confidence < 0.8 패턴은 "watching" 상태 (자동 적용 X)
- **장치**: ANTI_PATTERN 플래그로 "변경하지 마" 명시 (legal_filter IGNORECASE 사례)

### 5-2. JSON 파일 비대화
- 30일 누적 시 issue_patterns.json 1MB+ 가능
- **장치**: occurrence > 0 + last_seen > 90일 → archive로 이동
- **장치**: `.claude/memory/archive/issue_patterns_2026-Q1.json` 분기별 분리

### 5-3. Predictor false positive
- 통계만으로는 신호 vs 노이즈 구분 어려움
- **장치**: precision threshold 자동 모니터, 0.6 미만 시 alert
- **장치**: morning-briefing prepend는 confidence ≥ 0.75 만

### 5-4. Agent KPI 측정 오차
- CC scheduled-tasks log 포맷이 SDK 업데이트로 바뀔 수 있음
- **장치**: schema_version 명시, 미매칭 시 fallback to wall-time 추정

### 5-5. 추가 비용 0원 보장
- Sentry free tier (월 5K 이벤트) 한도 모니터링
- Anthropic API 호출 X (Max 플랜 CC 내부에서만 동작)
- Slack webhook free tier
- **위반 시**: 즉시 cron 비활성화 + CEO inbox

---

## 6. 출력물 매니페스트 (구현 시)

### Phase A
- `services/observability/pattern_extractor.py` (신규, 300줄)
- `.claude/memory/issue_patterns.json` (신규)
- `tests/observability/test_pattern_extractor.py` (신규)
- crontab `+1 entry` (`ops_pattern_library_sync`)
- agent prompt 수정 `x4` (bug-hunter / investigate-bug / data-freshness-monitor / cache-poisoning-sentinel)

### Phase B
- `services/observability/predictor.py` (신규, 400줄)
- `.claude/memory/predictions.json` (신규)
- `tests/observability/test_predictor.py` (신규)
- crontab `+1 entry` (`ops_predictive_scan`)
- morning-briefing 통합 patch

### Phase C
- `scripts/agent_kpi_collector.py` (신규, 250줄)
- `.claude/memory/agent_kpi.json` (신규)
- crontab `+1 entry` (`ops_agent_kpi_weekly`)
- `project_agent_inventory.md` auto-prepend 로직

### Phase D
- `~/.claude/projects/-Users-seanbae-Desktop---/memory/sprint_outcomes.md` (신규)
- launch-coordinator prompt 갱신
- v52~v56 backfill entries

**총 신규 코드**: ~950줄 Python + ~1500줄 JSON + 3 cron + 5 agent prompt 패치
**기존 코드 수정**: ~50줄 (agent prompt 추가)
**추가 비용**: ₩0

---

## 7. 검증 시나리오 (구현 후)

### 시나리오 A: 같은 KIS 500 burst 재발
1. 09:05 KST KIS 500 발생 → Sentry 알림
2. bug-hunter 호출
3. agent가 `issue_patterns.json` read → `KIS_HTTP_500_KOSPI_BURST` 매칭
4. `recommended_action` 즉시 적용: backoff retry + stale fallback
5. 5분 내 fix → autopilot_log 기록 → occurrences 24로 증가
6. **비교**: 학습 전 평균 fix time 30분 → 학습 후 5분

### 시나리오 B: legal_filter IGNORECASE 시도
1. PR diff에 `re.IGNORECASE` 추가
2. compliance-gatekeeper 호출
3. agent가 `issue_patterns.json` read → `LEGAL_FILTER_NAKED_BUY_SELL` 매칭 (ANTI_PATTERN)
4. **즉시 차단** + 메모리 룰 인용
5. CEO carry-over: "PR #XXX legal_filter 변경 시도 차단"

### 시나리오 C: 새 cron 추가 후 fail 빈도 ↑
1. v58에서 새 cron `ops_xxx` 추가
2. 24h 후 predictor가 `regression_signal` 출력
3. 다음 morning-briefing top에 "ops_xxx fail rate +60%, 의심 commit abc1234"
4. CEO 5분 내 인지 (기존엔 일주일 후 발견)

### 시나리오 D: agent inventory 자동 갱신
1. 30일 누적 후 `ops_agent_kpi_weekly` 실행
2. `agent_kpi.json` 출력: workhorse 11, dormant 23, deprecate 후보 6
3. `project_agent_inventory.md` 자동 prepend
4. CEO가 dormant 6개 archive 결정 → repo 슬림화

---

## 8. 비-목표 (Out of Scope)

- **외부 ML 라이브러리** (sklearn / tensorflow / pytorch) — 추가 비용 + 복잡도
- **자동 코드 수정** (auto-fix) — confidence 어쨌든 < 1.0, CEO 검수 필수
- **사용자 데이터 수집** (출시 전) — PIPA §15 동의 미수령 상태
- **Anthropic API 직접 호출** — Max 플랜 CC 내부만 사용
- **실시간 streaming** — cron 배치로 충분

---

## 9. CEO 결정 필요 (carry-over)

1. **Phase A 착수 승인** — v58 wave에 포함할지?
2. **Sentry free tier 한도 모니터링 임계치** — 월 4K 이벤트 (80%)에서 alert?
3. **agent KPI 측정 시작 시점** — 출시 전 vs 후?
4. **dormant agent 자동 archive 정책** — 90일 0 calls → archive 자동? (반대: 출시 후 갑자기 필요할 수 있음)
5. **predictor false positive 발생 시 어디로 alert?** — Slack vs morning-briefing prepend?

---

## 10. 참고 (메모리 룰)

- `feedback_no_extra_cost.md` — 추가 비용 0원 룰
- `feedback_no_busywork.md` — not-broken은 손대지 마
- `feedback_thorough_fixes.md` — 한 번 손대면 유사 패턴 전수
- `feedback_no_false_reports.md` — 작업 상태 보고 시 grep/test 결과만
- `project_agent_inventory.md` — 현 76 agent 인벤토리 (수동, 자동화 대체 목표)
- `project_automation_v2.md` — 16 crontab + 5 CC hooks 인벤토리 (확장 베이스)
- `feedback_bug_fix_patterns.md` — 9-bug-pattern (issue_patterns seed)

---

## 11. 한 줄 요약

**stateless 76 agent를 stateful로 만든다. JSON 4개 + 통계 + 3 cron으로. 시간이 지날수록 fix가 빨라진다. 추가 비용 0원.**
