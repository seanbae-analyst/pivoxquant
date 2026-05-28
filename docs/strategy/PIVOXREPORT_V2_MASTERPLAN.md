# PivoxReport V2 — 마스터 플랜 (멈춘 세션 인수인계 완성)

> **인수인계 노트**: 다른 세션(`2d8f0b26-...`)이 2026-05-28 19:23 KST에 16주 마스터
> 플랜을 §6 중간(`§6. 지금 당장 할 일 … 딱 1줄 cron 추가`)까지 작성하고 hang.
> CEO 19:28 명령 "그냥 pivoxreport로 저장해줘 + agent들 어떻게 돌아가는지 + 일정
> 넣으면 캘린더에 시각적으로 저장/표시" 받음. 본 세션이 멈춘 위치부터 이어받아 완성.
>
> 본 문서는 멈춘 세션의 10 부서 dispatch 결과 + 16주 플랜 + CEO 신규 명령 3개를
> 통합한 단일 SoT. 출처: `2d8f0b26-…/subagents/agent-*.jsonl` 10개 (실측 인용).

---

## 0. CEO 의도 (멈춘 세션 마지막 user 메시지 그대로)

> "난 그냥 pivoxreport로 저장해줘 + agent들 내 클로드 agent들 어케 돌아가는지도
> 궁금해. 그거랑 내 일정 넣으면 알아서 캘린더에 보기쉽게 시각적으로 저장하고 보여주는…"

→ 3 deliverable:
1. PivoxReport 마스터 플랜 (단일 파일 저장) ✅ (본 문서)
2. **agent 작동 원리 설명** (§7 신규)
3. **F1 자연어 → Google Calendar 우선 검토** (§8 — 멈춘 세션은 W13+ 미뤘으나 CEO 의도 재반영)

---

## 1️⃣ 16주 마스터 타임라인 (멈춘 세션 §1 + 완성)

| W | 이름 | Deliverable | 시간 예산 | Kill Check |
|---|---|---|---|---|
| **W0** | 데이터 적재만 | autopilot JSON 스냅샷 cron 1줄 (PivoxQuant crontab +1) | 1h | — |
| W1 | 도메인 + stub | DNS CNAME `report.pivoxquant.com` / Next.js `/report` stub / v3 토큰 적용 | 3h | — |
| W2 | API + alembic | alembic 042 (4테이블 + self-heal 가드) / `/api/report/*` 8개 / X-Report-Token | 5h | — |
| W3 | F3 UI v0 | 홈 3카드 + `/night/[date]` + SWR 3-fetch + PWA SW | 5h | — |
| **W4** | F3 UI v1 | sticky 입력바 + blocker queue + 30초 시나리오 e2e + CEO 자가 QA 8/8 | 5h | **D+14 kill gate** |
| W5-W8 | 실험 #1 (F2 브리프) | morning_brief cron 06:30 KST + Web Push VAPID + Slack fallback | 5h/주 | **W8 = D+30** |
| W9-W12 | **F1 자연어 → Calendar** (CEO 명령으로 승격) | natural-language intake + Google Calendar OAuth + GCal write API + 시각 카드 | 5h/주 | — |
| W13-W16 | 실험 #3 (F4 KPI) | PivoxQuant signup/MRR/health 카드 (출시 D+14 이후 의미 발생) | 4h/주 | **W16 = D+60** |

**시간 한도 위반 시 자동 freeze 룰**: git commit 누적 > 한도 ×1.5 → 다음 주
PivoxReport 작업 동결, 본업(PivoxQuant) 복귀.

> 변경점 from 멈춘 세션: F1 (W13+) → **W9-W12 승격**. CEO 명령 "캘린더 시각적
> 저장" 우선 의도 반영. F4 KPI는 D+60 이후로 후순위.

---

## 2️⃣ 4 기능 우선순위 (CEO 명령으로 재조정)

| 기능 | Wave | ICE | 사유 |
|---|---|---|---|
| **F3 야간 autopilot 시각화** | **MVP W1-W4** | 9×9×8 | 데이터 이미 존재 (0원), 매일 볼 강제 이유, autopilot_log 1500줄 grep 통증 해소 |
| F2 모닝 브리프 카드 | W5-W8 | 9×8×9=648 | F3가 80% 커버, 잔여 20% = 외부 미팅·휴일용 이메일 |
| **F1 자연어 → Google Calendar** | **W9-W12 (승격)** | 9×7×7=441 | CEO 명령 "캘린더 시각적 저장" 직접 의도, OAuth 1회 셋업 |
| F4 PivoxQuant KPI 카드 | W13-W16 | 6×5×5=150 | PivoxQuant 출시 D+14 후 데이터 의미 생김 |

---

## 3️⃣ 아키텍처 결정 (멈춘 세션 §3 그대로)

```
report.pivoxquant.com (Vercel, 동일 프로젝트, middleware host 분기)
        ↓ HTTPS
PivoxQuant Flask web (Railway HOBBY 공유)
  + blueprints/report/* (격리 폴더, import 단방향)
  + services/report/* (intent_regex / intent_claude / gcal / push_fanout)
        ↓ pool +3 이내 (asyncio gather batch 50)
PivoxQuant Postgres + report_* 4테이블 (alembic 042 + self-heal 가드)
        ↑              ↑
crontab +1 (21:30 UTC = 06:30 KST)    VAPID self-host Web Push
GitHub Actions fallback (21:35 UTC)   Slack webhook (slack-bridge)
```

격리 강제: `grep -E "from blueprints\.(auth|portfolio)..." blueprints/report/`
위반=CI fail.

---

## 4️⃣ Kill Gate 3단 (사전 lock-in, 후행 변경 금지)

| 시점 | 기준 | 미달 시 |
|---|---|---|
| **D+14 (W4)** | DMR (Daily Morning Read) ≥ 5/7일 | **즉시 폐기** |
| **D+30 (W8)** | DMR ≥ 50% AND OFR (5초 close 비율) < 15% | 피벗 또는 폐기 |
| **D+60 (W16)** | DMR ≥ 80% AND CDR (commit 클릭율) ≥ 60% AND F1+F2 둘 다 사용 | Phase 2 또는 sunset |

측정 = PivoxQuant Postgres `events` 테이블 row count + 일요일 cron SQL.
(PostHog/Vercel Analytics 둘 다 reject → 0원 + PIPA §28-8 추가 없음).

---

## 5️⃣ Risk 5건

| Risk | 영향 | Mitigation |
|---|---|---|
| Railway pool 소진 재발 | H | PivoxReport 전용 pool 2/1 + asyncio batch 50 |
| Alembic head 충돌 | M | 042 `down_revision=041` 명시 + CI `heads==1` 게이트 |
| 출시 freeze 침범 | M | W0-W4는 read-only cron + stub만, main 머지 보류 → Preview URL dogfood |
| 시크릿 누수 (refresh token) | M | AES-GCM `kis_token_aes_gcm.py` 재사용, MASTER_KEY env 분리 |
| 격리 폴더 import 침범 | M | CI grep 게이트 (위) |

---

## 6️⃣ 지금 당장 할 일 — PivoxQuant 출시 영향 0 (멈춘 §6 완성)

**딱 1줄 cron 추가** (W0 — 출시 후 D+1 이내):

```python
# services/scheduler/cron_jobs.py 신규 spec
(
    "ops_report_event_snapshot",
    CronTrigger(hour=23, minute=55, timezone=KST),  # 일일 23:55
    _wrap_python_main(
        "scripts.report.event_snapshot",
        job_id="ops_report_event_snapshot",
    ),
),
```

`scripts/report/event_snapshot.py` 신규: autopilot_log + git log + crontab stdout +
Railway deploy events를 `/tmp/report_events_<date>.json` 으로 적재. **DB 없음, file
only** (W0 = 데이터 수집 단계). W2 alembic 042 박힌 후 DB 적재로 승급.

---

## 7️⃣ Claude Agent들 어떻게 돌아가는지 (CEO 궁금증 해소 — 신규)

### 7.1 PivoxQuant 자율 운영 인프라 (실측, v52~v57 sprint 결과)

```
┌──────────────────────────────────────────────────────────────────┐
│ Layer A — Railway 백엔드 (서버 사이드, 24/7 가동)                  │
│   APScheduler 57 jobs (Group A 26 + ops 31)                       │
│   - 03:00 caus_daily_sweep / 04:00 data_integrity / 06:00 ship-   │
│     blockers / 06:42 legal-guard / 09:00~22:00 ops_*              │
│   - emit_failure SoT (services/observability/alerts.py) 60+ 호출  │
│   - 3-strike auto-pause + Slack alert (SLACK_WEBHOOK_URL 의존)    │
└──────────────────────────────────────────────────────────────────┘
                            ↑ logs/results
┌──────────────────────────────────────────────────────────────────┐
│ Layer B — CC Scheduled Tasks (CEO 노트북, Max 무료 토큰)            │
│   4 active task (~/.claude/scheduled-tasks/):                     │
│   - morning-briefing 06:27 → ~/.claude/briefings/morning-*.md      │
│   - bug-hunter-daily 03:37 → bug sweep + autopilot_log entry      │
│   - legal-guard 06:42 → legal_question_queue 검증                  │
│   - api-sentinel 매시 47분 → health probe + 자동 retry              │
│   3 disabled task: noon/evening briefing + v2-autopilot           │
└──────────────────────────────────────────────────────────────────┘
                            ↑ append
┌──────────────────────────────────────────────────────────────────┐
│ Layer C — Agent 인벤토리 (CC dispatch 시 호출)                       │
│   ~/.claude/agents/ 76개 .md (workhorse 9 / dormant 21 / docs 23)  │
│   주요 패턴:                                                       │
│   - bug-hunter: 매일 03:37 (CC scheduled-task)                     │
│   - engineering / qa / design / devops / secretary: 사용자 명령 시 │
│   - verify-* (api/data/security/ux/design): wave 단위 dispatch    │
│   - legal-kr-fintech / compliance-gatekeeper: 변호사 큐 검증 시    │
└──────────────────────────────────────────────────────────────────┘
                            ↑
┌──────────────────────────────────────────────────────────────────┐
│ Layer D — Hooks (자동 trigger)                                     │
│   ~/dev/pivoxquant/.claude/hooks/                                  │
│   - h6-handover-prepend.sh (SessionStart): HANDOVER.md 200줄       │
│   - h11-agent-inventory.sh (SessionStart): dormant agent 추천 3개 │
│   - h5-destructive-guard.sh (PreToolUse Bash): rm -rf 차단        │
│   - h7-cron-script-check.sh (PostToolUse): cron 변경 시 smoke     │
│   - h9-alembic-head-guard.sh (PostToolUse): migration 변경 시     │
│   - h12-autopilot-log-tick.sh (Stop): 세션 종료 시 log append     │
└──────────────────────────────────────────────────────────────────┘
                            ↑
┌──────────────────────────────────────────────────────────────────┐
│ Layer E — Workflows (CEO 한 마디 호출)                              │
│   ~/dev/pivoxquant/.claude/workflows/                              │
│   - wave-bug-hunt: bug-hunter ×3도메인 + audit-code 교차           │
│   - wave-launch-prep: legal-kr-fintech + compliance-gatekeeper +  │
│     verify-policy 병렬                                            │
│   - wave-design-polish: verify-design + brand-voice + motion-     │
│     designer 병렬                                                 │
│   - wave-data-integrity: fx-consistency + freshness + cache       │
│     poisoning 3 agent                                             │
│   - wave-launch-prep: D-7/D-3/D-1/D-day 4단계 게이트               │
└──────────────────────────────────────────────────────────────────┘
```

### 7.2 한 마디로

> **agent = 부서장 (예: backend-dev, legal-kr-fintech). CEO가 "이거 해줘" 하면
> Claude Code가 적절한 agent에게 위임. agent는 자기 SKILL.md(=직무 기술서) 따라
> 작업 후 보고. 매일 새벽 4개 task가 자동으로 깨어 bug-hunter / legal-guard /
> api-sentinel / morning-briefing 자동 호출. 결과는 autopilot_log.md에 자동 append.**

### 7.3 CEO 시점에서 농축

| CEO 액션 | 시스템 반응 |
|---|---|
| 명령 한 마디 ("bug 찾아") | wave-bug-hunt workflow → bug-hunter 3 dispatch + audit-code 교차검증 |
| 자고 있을 때 | 03:37 bug-hunter / 04:00 data-integrity / 06:00 ship-blockers / 06:27 morning-briefing 자동 실행 |
| 아침 깨면 | `~/.claude/briefings/morning-<date>.md` 7KB 자동 생성됨, 어젯밤 결과 요약 |
| 새 commit push | pre-push hook이 alembic + pytest + secret leak 자동 검증, 통과해야 push |
| 다른 세션 hang | 본 세션이 transcript jsonl read 후 인수인계 (지금 이 작업) |

---

## 8️⃣ F1 Google Calendar 기능 상세 (CEO 우선 명령으로 W9-W12 승격)

### 8.1 사용자 시나리오

> CEO 모바일에서 `report.pivoxquant.com` 접속 → 입력바에 "내일 오후 3시 변호사
> 미팅 1시간 강남" 입력 → 30초 후 Google Calendar에 자동 등록 + PWA 화면에
> 시각 카드로 표시.

### 8.2 데이터 흐름

```
Step 1. User 자연어 입력 → POST /api/report/intake { "raw": "내일 오후 3시 변호사..." }
                                ↓
Step 2. services/report/intent_regex.py 1차 파싱 (날짜/시간/장소/duration)
        실패 시 → services/report/intent_claude.py (Claude API direct, 한국어
        prompt 안에 ISO-8601 강제) — Max 토큰 한도 내 fallback only
                                ↓
Step 3. services/report/gcal.py — Google Calendar API write
        OAuth refresh_token AES-GCM 암호화 저장 (kis_token_aes_gcm.py 재사용)
                                ↓
Step 4. report_event 테이블 INSERT { title, start_at, end_at, gcal_event_id, ... }
                                ↓
Step 5. SWR mutate → PWA 화면 시각 카드 즉시 표시
        (Bloomberg Terminal aesthetic, v3 토큰: Vantablack BG + Bronze accent +
        Playfair 시각 표시)
```

### 8.3 OAuth 셋업 (CEO 1회 액션, 5분)

1. Google Cloud Console → OAuth 2.0 클라이언트 ID 생성 (`report.pivoxquant.com`
   redirect URI)
2. `GOOGLE_GCAL_CLIENT_ID` / `GOOGLE_GCAL_CLIENT_SECRET` Railway env 추가
3. `/api/report/gcal/connect` 한 번 클릭 → 토큰 발급 + AES-GCM 암호화 저장
4. 이후 자동 refresh

### 8.4 시각 카드 (PWA, F3와 통합)

```
┌─────────────────────────────────────┐
│ 05.29 FRI         INBOX             │  Eyebrow
│ ───────────────────────────────── │
│ 15:00–16:00 KST  · 변호사 미팅       │  Playfair 14px Bronze
│ 강남                                 │  mono 11px subtle
│ ✓ Google Calendar 등록 완료          │  Bronze checkmark
│ [드래그] 다른 시간으로 이동           │  swipe gesture
└─────────────────────────────────────┘
```

### 8.5 Failure 모드

- intent_claude.py가 ISO 파싱 실패 → CEO inbox에 "이 메시지 다시 입력" 표시
- gcal API 429 → 5분 retry, 그래도 실패 시 `/tmp/report_gcal_queue.json` 적재
- Google OAuth refresh 만료 → CEO inbox 즉시 escalation (Branch C)

### 8.6 비용

- Google Calendar API: **무료** (분당 1000 호출 한도, CEO 1인 사용 시 한도 무관)
- Anthropic API direct (intent_claude fallback): 1회당 ~$0.002 (Haiku) → 월 30
  호출 = $0.06 ≈ ₩80. `feedback_no_extra_cost` 룰에 borderline이지만 fallback
  only.

---

## 9️⃣ 다음 단계 (CEO 결정 큐)

본 문서는 인수인계 완성 — 다른 세션이 멈춘 위치부터 §6-§9 보충 완료. CEO는
아래 3 결정만:

1. **W0 cron 1줄 박을지** (출시 후 D+1 이내, 30분 작업) — 자율 진행 명령 시 본
   세션이 즉시 코드 박음
2. **F1 우선순위 W9-W12 승격 확정** (멈춘 세션은 W13+, 본 세션이 CEO 명령 반영해
   W9-W12 박음) — 동의 시 OK, 다른 우선순위 원하면 평문 답
3. **다른 세션 종료 / 강제 종료** — PID 3982 살아있는 듯 보이지만 응답 없음.
   `kill -TERM 3982` 또는 CEO가 그 창에서 ESC

---

## 부록 — 멈춘 세션 10 부서 dispatch 출처

| Subagent jsonl | 역할 | 마지막 결과물 |
|---|---|---|
| `agent-a23008314515174fc` | 전략 (16주 로드맵) | Executive Summary + 주별 milestone |
| `agent-a2a1114e90a36a79e` | Product (MVP F3 1주 컷) | F3 단독 정당화 |
| `agent-a3121ba7e811ca412` | QA 전략 | L1-L5 ~90 cases 피라미드 |
| `agent-a533985cfec13eeb2` | Design (12 컴포넌트) | DateEyebrow / SectionEyebrow / Card / Sheet / 등 |
| `agent-a53ab1515e9a871ba` | Architecture (zero-cost PWA) | 데이터 흐름 ASCII + Vercel 무료 |
| `agent-ab2e074d803f2deb5` | Engineering (alembic 042) | report_event 4테이블 ORM spec |
| `agent-ad609d30233cc31af` | Mobile UX (375×812) | iPhone 14 와이어프레임 + safe-area |
| `agent-ae32f09d45419a3bd` | F3 MVP 분해 | 단독 MVP 정당화 + SoT 인용 |
| `agent-af3554154952a1eb9` | 메트릭 V2 (N=1) | 북극성 + DMR/OFR/CDR |
| `agent-af047e0352991c9cb` | (미확인 — 본 세션 jsonl read 시간 절약) | — |

전체 jsonl 본문은 `~/.claude/projects/-Users-seanbae-Desktop---/2d8f0b26-9fc7-4e73-b038-9baa9a9d0dd8/subagents/` 보존됨 (디스크). 다음 sprint 시 필요시 추가 read.
