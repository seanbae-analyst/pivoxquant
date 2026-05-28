# CC Scheduled-Tasks 확장 spec (4 → 20+)

**작성**: 2026-05-28 v55-X4 DevOps wave
**대상**: PivoxQuant 자율 운영 인프라 (Max 토큰 한정, 추가 비용 0원)
**상태**: SPEC ONLY — 실제 enable 안 함, CEO 결정 대기

---

## 1. 현행 인프라 실측 (2026-05-28)

`ls ~/.claude/scheduled-tasks/` 출력:

| dir | mtime | SKILL.md size | 상태 |
|---|---|---|---|
| `morning-briefing/` | 2026-05-28 14:32 | 1441 B | ENABLED — 06:35 KST 마크다운 브리핑 → `~/.claude/briefings/morning-YYYY-MM-DD.md` |
| `noon-briefing/` | 2026-04-09 11:30 | 655 B | DISABLED (4월 9일 이후 갱신 없음) |
| `evening-briefing/` | 2026-04-09 11:30 | 663 B | DISABLED |
| `pivoxquant-bug-hunter-daily/` | 2026-05-28 14:33 | 2465 B | ENABLED — 03:37 KST 일일 bug sweep + P0 auto-fix |
| `pivoxquant-api-sentinel/` | 2026-05-28 14:33 | 2699 B | ENABLED — 15분 timebox API regression 감지 |
| `pivoxquant-legal-guard/` | 2026-05-28 14:33 | 3817 B | ENABLED — 25분 timebox 법적 회귀 + auto-fix |
| `pivoxquant-v2-autopilot/` | 2026-04-28 08:00 | 2710 B | DISABLED |

**ENABLED 4개 확정**: morning-briefing / bug-hunter-daily / api-sentinel / legal-guard.
**결과 path 패턴 (실측)**: `~/.claude/briefings/morning-2026-05-28.md` (7.2 KB) — JSON 아닌 마크다운, 사람용 카본.
**로그 패턴 (실측)**: `~/.claude/projects/-Users-seanbae-Desktop---/memory/autopilot_log.md` 공통 append.

**확장 메커니즘**: `mcp__scheduled-tasks__create_scheduled_task` (taskId, prompt, description, cronExpression — LOCAL time KST). 본 문서는 spec만, 실제 호출 안 함.

---

## 2. 신규 16 task spec

각 task 표준 필드:
- **taskId** (kebab-case, dir 이름과 동일)
- **cron** (KST 로컬, 충돌 매트릭스 §3 준수)
- **cwd** (CC가 작업할 디렉토리)
- **prompt 요지** (SKILL.md 본문 골격)
- **결과 cache path** (백엔드가 read할 위치 — §4 패턴 따름)
- **Max 토큰 추정** (5h 윈도우 부담 가늠)
- **의존 agent** (서브 dispatch 대상)
- **회귀 시 emit_failure** (T1 헬퍼 — autopilot_log.md append + 다음 wave carry-over)

### 2.1 새벽 무거운 작업 (03:00 ~ 07:30 KST)

#### T01 — ops_artifact_pregeneration
- **taskId**: `ops-artifact-pregeneration`
- **cron**: `0 3 * * *` (03:00 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: 다음 오전 09:00 발송 예정 17 Artifact (12 routine + 5 conditional) 사전 생성. Weekly Memo / Brag Card / Earnings Pre-Brief 우선. 활성 유저 list는 `/api/internal/active-users-tomorrow` (auth-free internal, 추가 endpoint 필요 — 다음 wave). 산출물은 HTML + PNG.
- **결과 cache**: `cache/artifacts/2026-05-29/<type>/<user_id>.{html,png}`
- **Max 토큰 추정**: 40K (Anthropic API 직접 호출 아님 — CC가 services/artifacts/*.py CLI 호출)
- **의존**: services/artifacts/* (기존 코드), brand-voice agent
- **emit_failure**: `cache/ops/artifact_pregeneration/2026-05-29.failure.json` + `autopilot_log.md` append `"artifacts: generated N/M, failed K (user_ids: ...)"`

#### T02 — ops_competitor_scan
- **taskId**: `ops-competitor-scan`
- **cron**: `0 4 * * *` (04:00 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: 경쟁사 가격/기능 모니터링. 대상: 토스증권, 카카오페이증권, 키움증권 영웅문, 미래에셋 m-Stock, NH투자증권, KB증권. WebFetch로 공식 가격 페이지 + Apple App Store description fetch (베타 비번 같은 비인증 영역만). diff 감지 시 marketing_copy.md carry-over.
- **결과 cache**: `cache/ops/competitor_scan/2026-05-29.json` (schema: `{competitor, plan, price_krw, features[], diff_from_previous}[]`)
- **Max 토큰 추정**: 25K
- **의존**: WebFetch, marketing agent (변동 시)
- **emit_failure**: fetch 실패 경쟁사 list

#### T03 — ops_user_feedback_digest
- **taskId**: `ops-user-feedback-digest`
- **cron**: `30 4 * * *` (04:30 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: 슬랙(있다면) + 이메일 인박스 + 베타 유저 카페 댓글 감정 분석. positive/negative/neutral + 핵심 키워드 추출. 1주일 trend chart 데이터 산출.
- **결과 cache**: `cache/ops/user_feedback/2026-05-29.json` (schema: `{sources[], positive_count, negative_count, neutral_count, top_keywords[], notable_quotes[]}`)
- **Max 토큰 추정**: 20K
- **의존**: customer agent
- **emit_failure**: 채널별 누락 표시

#### T04 — ops_kpi_dashboard_build
- **taskId**: `ops-kpi-dashboard-build`
- **cron**: `0 5 * * *` (05:00 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: 매일 KPI 1장 요약. signup / activation / DAU / WAU / churn / MRR 산출. analytics_metrics.md North Star (WAMR) 기준. backend `/api/internal/kpi-snapshot` 호출 (auth-free internal).
- **결과 cache**: `cache/ops/kpi_dashboard/2026-05-29.md` (markdown 1 page) + `cache/ops/kpi_dashboard/2026-05-29.json` (raw)
- **Max 토큰 추정**: 15K
- **의존**: analytics agent
- **emit_failure**: 누락된 지표 list

#### T05 — ops_legal_packet_diff
- **taskId**: `ops-legal-packet-diff`
- **cron**: `30 5 * * *` (05:30 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: regulatory 변화 + 변호사 큐 진행 변화 추적. `legal_question_queue.md` + `regulatory_changes_2026-05.md` diff. 21건 큐 변동 감지. 다음 스캔 2026-08-15 카운트다운.
- **결과 cache**: `cache/ops/legal_packet/2026-05-29.json` (schema: `{queue_count, closed_since_last, new_since_last, regulatory_alerts[]}`)
- **Max 토큰 추정**: 10K
- **의존**: legal-kr-fintech agent
- **emit_failure**: log only

### 2.2 오전 routine (08:00 ~ 12:00 KST)

#### T06 — ops_marketing_calendar_dispatch
- **taskId**: `ops-marketing-calendar-dispatch`
- **cron**: `0 9 * * *` (09:00 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: 오늘 인스타/Threads/카페 게시 큐 배치. `docs/marketing/calendar.yml` (다음 wave 신규) 읽어 오늘 날짜 항목 추출. brand-voice agent로 카피 검수. 실제 게시는 CEO 수동 (자동 게시 금지 — 출시 전 룰).
- **결과 cache**: `cache/ops/marketing_calendar/2026-05-29.md` (오늘 게시 큐 카피 + brand-voice 검수 결과)
- **Max 토큰 추정**: 15K
- **의존**: brand-voice agent, marketing agent
- **emit_failure**: 카피 검수 실패 항목

#### T07 — ops_sprint_review
- **taskId**: `ops-sprint-review`
- **cron**: `0 10 * * *` (10:00 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: 어제 push된 commit + bug-hunter 결과 리뷰. `git log --since=yesterday --until=today --oneline` + `cache/ops/bug_sweep/2026-05-28.md` 비교. 회귀 가능성 P1+ 추출.
- **결과 cache**: `cache/ops/sprint_review/2026-05-29.md`
- **Max 토큰 추정**: 20K
- **의존**: verify-policy agent
- **emit_failure**: 회귀 의심 commit SHA list

#### T08 — ops_inbox_triage
- **taskId**: `ops-inbox-triage`
- **cron**: `0 12 * * *` (12:00 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: 이메일 인박스 카테고리 분류 + 응답 초안. Gmail MCP 활용 가능 (이미 연결됨 — `mcp__bb45a940...__search_threads`). 분류: 고객문의 / 법적 / 광고 / 협업. 응답 초안만, 실제 send 금지.
- **결과 cache**: `cache/ops/inbox_triage/2026-05-29.md` (분류 결과 + 초안 텍스트)
- **Max 토큰 추정**: 15K
- **의존**: Gmail MCP
- **emit_failure**: Gmail API fail

### 2.3 오후 routine (13:00 ~ 18:00 KST)

#### T09 — ops_security_sweep
- **taskId**: `ops-security-sweep`
- **cron**: `0 14 * * *` (14:00 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: NSA Red Team 수준 보안 스캔. Sentry recent issues + bandit SAST + npm audit + pip-audit. P0 = 외부 노출 secret leak / RCE / SQL injection. P1 = dependency CVE. fix 자동 적용은 P0만, P1은 backlog.
- **결과 cache**: `cache/ops/security_sweep/2026-05-29.json` (P0/P1/P2 분류 + 패키지명 + CVE id)
- **Max 토큰 추정**: 30K
- **의존**: cso skill, security agent
- **emit_failure**: 스캔 도구 실행 실패 표시

#### T10 — ops_design_drift_check
- **taskId**: `ops-design-drift-check`
- **cron**: `0 15 * * *` (15:00 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: v3 디자인 토큰 위반 / Bloomberg 톤 + Apple HIG 회귀 감지. design-token-drift skill 활용. component-usage-analytics dump도. v3 락-인 (Vantablack/Bronze/Playfair) 기준.
- **결과 cache**: `cache/ops/design_drift/2026-05-29.json` (violation file:line list)
- **Max 토큰 추정**: 20K
- **의존**: design-token-drift skill, component-usage-analytics skill
- **emit_failure**: skill 실행 실패

#### T11 — ops_data_freshness_full
- **taskId**: `ops-data-freshness-full`
- **cron**: `0 16 * * *` (16:00 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: 공식 라이선스 6 소스 staleness. KIS / FMP / DART / FRED / SEC EDGAR / KRX Open Data Portal. 각 소스별 `last_fetched_at` + `expected_refresh_interval` 비교. stale > 2x threshold면 P1.
- **결과 cache**: `cache/ops/data_freshness/2026-05-29.json` (schema: `{source, last_fetched, age_seconds, status}[]`)
- **Max 토큰 추정**: 10K
- **의존**: backend-dev agent (fix 필요 시)
- **emit_failure**: API key 만료 / quota 초과 감지

#### T12 — ops_pwa_sanity
- **taskId**: `ops-pwa-sanity`
- **cron**: `0 17 * * *` (17:00 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: PWA cache / SW / manifest 무결성. `frontend/public/manifest.webmanifest` + `frontend/src/sw.ts` (or next-pwa generated) 검증. service worker 버전 hash diff. 캐시 stampede 방지.
- **결과 cache**: `cache/ops/pwa_sanity/2026-05-29.json`
- **Max 토큰 추정**: 8K
- **의존**: frontend agent (fix 필요 시)
- **emit_failure**: manifest schema invalid

### 2.4 저녁 routine (19:00 ~ 23:00 KST)

#### T13 — ops_evening_recap
- **taskId**: `ops-evening-recap`
- **cron**: `0 19 * * *` (19:00 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: 오늘 일자 자동 회고. commit count / bug auto-fix count / metric 변동 / 외부 이벤트. 어제 evening-recap diff. CEO가 18:00에 퇴근(없지만) 후 잠들기 전 1장 요약.
- **결과 cache**: `cache/ops/evening_recap/2026-05-29.md`
- **Max 토큰 추정**: 15K
- **의존**: retro skill (gstack)
- **emit_failure**: log only

#### T14 — ops_next_day_planner
- **taskId**: `ops-next-day-planner`
- **cron**: `0 21 * * *` (21:00 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: 내일 sprint 후보 자동 제안 (Self-Evolving Sprint Engine 핵심). AUTOPILOT_BACKLOG.md + 변호사 큐 + 회귀 의심 + CEO 우선순위 (메모리) 종합. Top 3 후보 + estimated effort.
- **결과 cache**: `cache/ops/next_day_planner/2026-05-29.md` (내일 sprint 후보 3개 + 의사결정 사유)
- **Max 토큰 추정**: 25K
- **의존**: plan-ceo-review skill, autopilot agent
- **emit_failure**: backlog 파일 없음 알림

#### T15 — ops_growth_experiment_check
- **taskId**: `ops-growth-experiment-check`
- **cron**: `0 22 * * *` (22:00 KST)
- **cwd**: `/Users/seanbae/dev/pivoxquant`
- **prompt 요지**: A/B 테스트 결과 + 다음 실험 후보. `growth_experiments.md` 갱신. 통계적 유의성 (p<0.05) 도달 실험 마감 알림. 다음 실험 backlog 추출.
- **결과 cache**: `cache/ops/growth_experiment/2026-05-29.json` (실험 ID + 통계 + 결정)
- **Max 토큰 추정**: 15K
- **의존**: growth agent
- **emit_failure**: 메트릭 fetch 실패

#### T16 — ops_memory_consolidate
- **taskId**: `ops-memory-consolidate`
- **cron**: `0 23 * * *` (23:00 KST)
- **cwd**: `/Users/seanbae/.claude/projects/-Users-seanbae-Desktop---/memory`
- **prompt 요지**: MEMORY.md + session_*.md 통합 + stale prune. 30일 이상 미참조 항목은 archive로 이동. 인덱스 갱신. consolidate-memory skill 활용.
- **결과 cache**: `cache/ops/memory_consolidate/2026-05-29.md` (변경 summary)
- **Max 토큰 추정**: 20K
- **의존**: anthropic-skills:consolidate-memory
- **emit_failure**: archive 디렉토리 권한 문제

---

## 3. 스케줄 충돌 매트릭스

20+ task가 동시 fire 안 하도록 5분 minimum spacing. CC scheduled-tasks 는 dispatch 시 deterministic delay (몇 분) 적용된다고 schema 문서화됨 — 그래도 명시 spacing.

| KST 시각 | Task ID | Max 토큰 추정 | 의존 | 비고 |
|---|---|---|---|---|
| 03:00 | ops-artifact-pregeneration | 40K | brand-voice | 새벽 무거운 1 |
| 03:37 | pivoxquant-bug-hunter-daily | 50K | bug-hunter | **현행 ENABLED** |
| 04:00 | ops-competitor-scan | 25K | WebFetch | |
| 04:30 | ops-user-feedback-digest | 20K | customer | |
| 05:00 | ops-kpi-dashboard-build | 15K | analytics | |
| 05:30 | ops-legal-packet-diff | 10K | legal-kr-fintech | |
| 06:35 | morning-briefing | 8K | — | **현행 ENABLED** |
| 06:42 | pivoxquant-legal-guard | 18K | legal | **현행 ENABLED** |
| 07:00 | pivoxquant-api-sentinel | 10K | backend-dev | **현행 ENABLED** |
| 09:00 | ops-marketing-calendar-dispatch | 15K | brand-voice | |
| 10:00 | ops-sprint-review | 20K | verify-policy | |
| 12:00 | ops-inbox-triage | 15K | Gmail MCP | |
| 14:00 | ops-security-sweep | 30K | cso | |
| 15:00 | ops-design-drift-check | 20K | design-token-drift | |
| 16:00 | ops-data-freshness-full | 10K | backend-dev | |
| 17:00 | ops-pwa-sanity | 8K | frontend | |
| 19:00 | ops-evening-recap | 15K | retro | |
| 21:00 | ops-next-day-planner | 25K | plan-ceo-review | |
| 22:00 | ops-growth-experiment-check | 15K | growth | |
| 23:00 | ops-memory-consolidate | 20K | consolidate-memory | |

**합계 일일 Max 토큰 추정**: 약 389K / day = 389K * 30 = 11.67M / month.

Max plan (Claude Code) 한도 5h 윈도우 기준 (실제 한도는 동적이지만 finance_token_ops.md §6 윈도우 관리 룰): 
- **새벽 윈도우 (03:00 ~ 08:00 KST, 5h)**: T01+T02+T03+T04+T05+bug-hunter+morning+legal+api = 40+25+20+15+10+50+8+18+10 = **196K** — 한 윈도우 내 집중. 
- **오전 윈도우 (09:00 ~ 14:00 KST)**: 15+20+15 = 50K.
- **오후 윈도우 (14:00 ~ 19:00 KST)**: 30+20+10+8 = 68K.
- **저녁 윈도우 (19:00 ~ 24:00 KST)**: 15+25+15+20 = 75K.

새벽 윈도우 196K가 가장 무거움 — Max plan 5h 한도 80% 도달 위험. 미티게이션 §5 (lock + 큐잉).

**Pre-Launch Full Throttle override**: feedback_pre_launch_full_throttle 룰 적용 — 출시 전이라 토큰 절약 안 함. 출시 후 archive 시점에 윈도우 압축 (예: 일부 task를 격일로) 재검토.

---

## 4. 결과 file cache 패턴

상세는 `CACHE_PATTERN.md` 참조. 요약:

```
/Users/seanbae/dev/pivoxquant/cache/
├── artifacts/<date>/<type>/<user_id>.{html,png}    # T01
├── ops/
│   ├── competitor_scan/<date>.json                  # T02
│   ├── user_feedback/<date>.json                    # T03
│   ├── kpi_dashboard/<date>.{md,json}               # T04
│   ├── legal_packet/<date>.json                     # T05
│   ├── marketing_calendar/<date>.md                 # T06
│   ├── sprint_review/<date>.md                      # T07
│   ├── inbox_triage/<date>.md                       # T08
│   ├── security_sweep/<date>.json                   # T09
│   ├── design_drift/<date>.json                     # T10
│   ├── data_freshness/<date>.json                   # T11
│   ├── pwa_sanity/<date>.json                       # T12
│   ├── evening_recap/<date>.md                      # T13
│   ├── next_day_planner/<date>.md                   # T14
│   ├── growth_experiment/<date>.json                # T15
│   └── memory_consolidate/<date>.md                 # T16
```

**백엔드 read 패턴 예**:
- `/api/artifacts/today?type=weekly_memo&user_id=123` → `cache/artifacts/<today>/weekly_memo/123.html` exists? → return file content (X-Cache: HIT). 없으면 Anthropic API direct fallback (X-Cache: MISS).
- `/api/internal/kpi-today` → `cache/ops/kpi_dashboard/<today>.json` read.

**TTL**: 24h (다음 새벽 03:00 fire 시 overwrite).
**gitignore**: 신규 `cache/` 디렉토리 추가 (§7).

---

## 5. 동시 실행 / lock 메커니즘

CC scheduled-tasks가 자체 lock 안 함 — task spec에서 명시.

**lockfile 패턴** (각 task SKILL.md 본문 첫 step):
```bash
LOCK=/tmp/pivox-<taskId>.lock
if [ -f "$LOCK" ]; then
  AGE=$(( $(date +%s) - $(stat -f %m "$LOCK") ))
  if [ $AGE -gt 1800 ]; then  # 30min 강제 unlock
    rm "$LOCK"
  else
    echo "lock held ${AGE}s — skip"
    exit 0
  fi
fi
trap "rm -f $LOCK" EXIT
echo "$$" > "$LOCK"
```

**Max 토큰 80% 큐잉**: CC가 자체 토큰 사용량 모니터 못 함. 대신 task 시작 시 `~/.claude/projects/-Users-seanbae-Desktop---/memory/autopilot_log.md` tail에서 최근 1h 동안 fire된 task 수 카운트 — 6개 초과면 skip + carry-over.

**충돌 안전판**:
- bug-hunter / legal-guard / api-sentinel 모두 `git status --short` guard 이미 가짐 (§1 실측). 신규 16 task 중 commit 가능성 있는 항목 (T01 artifact, T07 sprint_review fix-spawn, T09 security_sweep)에 동일 guard 추가.
- 동시 commit 방지: T01-T16은 commit 안 함. spec 단계에서는 read-only + cache write만. 회귀 fix는 별도 enable된 bug-hunter/legal-guard/api-sentinel에 위임.

---

## 6. emit_failure (T1 헬퍼) 통합

기존 4 task는 `autopilot_log.md` append 형식 다 다름 (§1 SKILL.md 실측). 신규 16 task는 통일 schema:

```
## YYYY-MM-DD HH:MM <taskId>
- status: clean | warning | failure
- token_used: ~XK (추정)
- cache_written: <path>
- carry_over: [...]   # 다음 wave가 처리할 항목
- notes: ...
```

`carry_over` 필드 → autopilot-monitor agent가 일일 종합 → `cache/ops/carry_over/<date>.md` 종합본. CEO 모닝 브리핑(06:35)에 자동 합본.

---

## 7. gitignore + 신규 디렉토리

추가 항목 (작업 별도 wave, 본 spec에서는 명시만):

```
# Cache (CC scheduled-tasks 결과)
cache/
```

`cache/` 자체는 commit 안 하되, `cache/.gitkeep` + `cache/README.md` (디렉토리 구조 설명, §4)는 commit하여 백엔드 read 경로 documentation 유지.

---

## 8. 신규 task 생성 자동화 (다음 wave)

본 spec 승인 후, 다음 wave에서 16번 `mcp__scheduled-tasks__create_scheduled_task` 호출:

```python
# 의사 코드 (실제 실행은 CEO 결정 후)
for task in [T01, T02, ..., T16]:
    create_scheduled_task(
        taskId=task.id,
        prompt=open(f"~/.claude/scheduled-tasks/{task.id}/SKILL.md").read(),
        description=task.desc,
        cronExpression=task.cron,
    )
```

⚠️ `create_scheduled_task` 호출 시 approval dialog 발생 — CEO가 16번 클릭해야 함. AskUserQuestion 금지 룰과 별개 (CC 내장 메커니즘).

---

## 9. 절대 금지 (본 wave)

- ✅ 실제 `create_scheduled_task` 호출 안 함 — spec/SKILL.md만 작성 (本 문서 + 16개 SKILL.md placeholder는 다음 wave 권한)
- ✅ push / commit 안 함
- ✅ AskUserQuestion 안 함
- ✅ 추가 비용 0원 — Max + Railway + 도메인 외 신규 결제 X

---

## 10. 다음 wave carry-over

1. **internal endpoints 4개** 필요 (`/api/internal/active-users-tomorrow`, `/kpi-snapshot`, `/data-freshness`, `/growth-experiment-status`) — backend-dev 위임
2. **docs/marketing/calendar.yml** 신규 (T06 종속) — marketing 위임
3. **16 SKILL.md placeholder** 작성 — DevOps 위임
4. **cache/.gitkeep + cache/README.md** + .gitignore 업데이트 — DevOps 위임
5. **autopilot-monitor agent에 carry_over 종합 로직** 추가 — engineering 위임
6. **CEO 승인 후** `create_scheduled_task` 16회 호출 — DevOps 위임

---

**파일 경로**: `/Users/seanbae/dev/pivoxquant/docs/devops/CC_SCHEDULED_TASKS_EXPANSION.md`
**작성 cwd**: `/Users/seanbae/dev/pivoxquant/`
**총 줄수**: 약 290줄 (800줄 한도 ✅)
