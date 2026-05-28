# CEO Inbox — Single-Pane Spec

**버전**: v56-M2 / 2026-05-28
**상태**: SPEC ONLY (코드 변경 없음)
**오너**: Product (배상현, 1인)
**의존**: [[product_concept_cfo]] / [[design_system]] v3 / [[project_pwa]] / [[feedback_no_extra_cost]]

---

## 1. 한 줄 요약

CEO가 매일 5-10개 분산된 알림/결정/검증을 **하나의 모바일 화면(PWA `/inbox`) + Slack push**에 통합하고, **3-button 응답(OK/Defer/Drop)** 으로 자율 처리를 트리거하는 단일 컨테이너.

**전제**: 추가 비용 0원. PivoxQuant 출시 직전 1인 운영자 mobile-first.

---

## 2. 문제 정의

### 2.1 현재 통증 (관찰)

| 통증 | 빈도 | 영향 |
|---|---|---|
| 매일 morning-brief / autopilot_log / SHIP_BLOCKERS / weekly_packet 따로 열어야 함 | 매일 4번 | 평균 5-10분 분산 비용 |
| Slack/Sentry/Brevo/Vercel/Railway 콘솔 산재 | 매일 sporadic | "어디서 봤더라" 검색 비용 |
| carry-over 15건이 어디에 모이는지 불명 (Slack/Brevo/Sentry/변호사/통신판매업/DNS) | 상시 | 망각 → 출시 지연 |
| 자율 처리된 것 vs 결정 필요 vs 외부 액션 구분 어려움 | 매일 | 우선순위 혼란 |
| 모바일에서 응답 불가 — 노트북 켜야 OK/reject 가능 | 매일 | 응답 지연 |

### 2.2 유저 (페르소나 1명)
- **CEO 본인** — 1인 창업자, 모바일 primary, 노트북 secondary
- 매일 아침 06:30 KST 화장실/카페에서 폰으로 PivoxQuant 상태 확인
- 결정 응답에 10초 이상 쓰기 싫음 (OK/Defer/Drop 3-tap)
- 알림 폭격 거부 — 진짜 결정 필요한 것만 push

### 2.3 Evidence
- 메모리 `feedback_no_askuserquestion` (2026-05-28) — AskUserQuestion 짜증, autopilot 자율 + carry-over 보고 패턴 요구
- 메모리 `autopilot_log` — 마라톤 세션 7 commit + 한계 6건 분산 기록
- carry-over 인벤토리 SoT가 SHIP_BLOCKERS.md / legal_question_queue.md / autopilot_log.md 3곳 분산 (현재 실측)

---

## 3. Phase 1 — 알림/결정 출처 인벤토리 (10개)

| # | 출처 | 위치 | 확인 빈도 | 매체 | 우선순위 | 응답 가능? |
|---|---|---|---|---|---|---|
| 1 | morning-brief | `~/.claude/briefings/morning-*.md` | 매일 06:27 | 파일 (수동) | P1 24h | ❌ read-only |
| 2 | autopilot_log | `~/.claude/projects/-Users-seanbae-Desktop---/memory/autopilot_log.md` | 수시 (cron append) | 파일 (수동) | P1-P2 | ❌ read-only |
| 3 | SHIP_BLOCKERS | `Desktop/취준/SHIP_BLOCKERS.md` | 매일 06:00 헤더 갱신 | 파일 (수동) | P0 즉시 | ❌ read-only |
| 4 | weekly_packet | `weekly_packet_*.md` | 매주 일 21:00 | 파일 (수동) | P2 주간 | ❌ read-only |
| 5 | Slack alert | webhook (미박힘) | env 박히면 push | Slack push | P0 (Sentry) / P1 (cron fail) | ⏳ 박힌 후 |
| 6 | 이메일 alert | Brevo (미박힘) | env 박히면 inbox | 이메일 | P1-P2 | ⏳ 박힌 후 |
| 7 | Vercel 콘솔 | vercel.com | sporadic (배포 시) | 웹 | P0 (배포실패) | ✅ 콘솔 |
| 8 | Railway 콘솔 | railway.app | sporadic (배포 시) | 웹 | P0 (배포실패) | ✅ 콘솔 |
| 9 | GitHub 알림 | github.com | sporadic (PR) | 이메일 + 웹 | P1-P2 | ✅ 웹 |
| 10 | 변호사 큐 | `legal_question_queue.md` | 자문 미팅 전 | 파일 (수동) | P0 (Q-S3 BLOCKER) | ❌ read-only |

**관찰**:
- 10개 중 7개가 "파일 (수동)" — 모바일에서 사실상 확인 불가
- 응답 가능 채널이 Vercel/Railway/GitHub 콘솔 3개뿐 — 모두 데스크탑 친화
- Slack/Brevo는 webhook env 박혀야 작동 (carry-over)

---

## 4. Phase 2 — CEO Inbox 모델 (옵션 비교)

| 옵션 | 장점 | 단점 | 비용 | 채택 |
|---|---|---|---|---|
| A. PWA 새 화면 `/inbox` | 통제력 / 디자인 v3 일관 / push 인프라 보유 | 매번 사이트 열어야 | 0원 | ✅ 메인 |
| B. Slack `#pivox-ceo-inbox` | 푸시 강력 / thread reply 응답 | Slack 앱 의존 / webhook 미박힘 | 0원 (webhook free) | ✅ 보조 (env 박힌 후) |
| C. 이메일 daily digest (Brevo) | 가장 단순 | 응답 어려움 / Brevo 미박힘 | 0원 (300/day free) | ⏳ 보조 (Brevo 박힌 후) |
| D. 카카오톡 알림톡 | 한국 mobile primary | API 비용 / 사업자 인증 / 템플릿 심사 | ❌ 비용 발생 | ❌ DROP |

**채택**:
1. **A (PWA `/inbox`)** = primary canvas — 상세/응답/이력
2. **B (Slack push)** = primary trigger — 06:30 KST 1회 push + Sentry/cron-fail 실시간
3. **C (이메일 daily)** = fallback — Slack 못 보는 날 backup

D는 [[feedback_no_extra_cost]] 위배로 영구 제외.

---

## 5. Phase 3 — Inbox 콘텐츠 구조

### 5.1 텍스트 mockup (모바일 PWA `/inbox` 또는 Slack 메시지)

```
═══ PivoxQuant CEO Inbox — 2026-05-29 06:30 KST ═══

🟢 자율 처리 완료 (read-only, 3건)
  [✓] bug-hunter: typo fix services/data/fmp.py:223
       └ PR #501 자동 머지, prod 배포 SUCCESS (commit b63b5244)
  [✓] data-freshness: KIS 24h+ stale 감지
       └ KIS API 재호출 자동 복구, 005930 정상
  [✓] ship_blockers: RELEASE 6 / RISK 11 / POST 15
       └ 변화 없음 (전일 동일)

🟡 검토 후 응답 (decision queue, 2건)  [OK / Defer / Drop]
  [?] Brand-voice: 새 카피 "기록의 코치"
       └ legal_filter 통과 / 이전 "AI 트레이딩 봇" 대체
       └ 적용 시 marketing_copy.md + landing/hero 동시 갱신
       [ OK 적용 ]  [ Defer 24h ]  [ Drop 폐기 ]

  [?] Pricing experiment: Pro ₩9,900 → ₩12,000 A/B 시작?
       └ growth_experiments.md 가설: 가격 탄력성 -0.7 예상
       └ 30일 50/50 split, MRR 영향 ±5% 예상
       [ OK 시작 ]  [ Defer ]  [ Drop ]

🔴 외부 액션 필요 (carry-over, 1건)
  [!] Brevo API key Railway env 추가 (예상 10분)
       └ Brevo 가입 → Settings → API Keys → BREVO_API_KEY 발급
       └ Railway: railway variables --service web set BREVO_API_KEY=...
       └ 가동 후: SendGrid cascade fallback / 이메일 daily digest 활성
       [ ✅ 완료 표시 ]  [ Defer ]

📊 KPI (24h)
  signup: 0 / activation: 0 / churn: 0 / MRR: ₩0
  prod uptime: 99.97% / OAuth 성공률: 100% (3/3)
  pytest: 3443 PASS / vitest: 494 PASS

⏰ 다음 fire (다음 24h)
  04:00 data_integrity / 06:00 ship_blockers
  06:27 morning_brief / 매시 47 api-sentinel
  21:00 weekly_packet (일요일만)

📎 변호사 큐 미해결 (21건)
  P0: Q5 Q6 Q7 Q8 Q13 Q-S1 Q-S3
  무료 자문 1.5h 예약? → 핀테크상담소 신청 카드
  [ 자세히 보기 ]  [ Defer 7d ]
```

### 5.2 카테고리 정의

| 카테고리 | 목적 | 동작 |
|---|---|---|
| 🟢 자율 처리 완료 | "이미 끝났으니 확인만" | read-only, "더 보기" 클릭 시 PR/commit/diff 링크 |
| 🟡 검토 후 응답 | "결정만 하면 자동 진행" | OK/Defer/Drop 3-button → backend 자율 트리거 |
| 🔴 외부 액션 필요 | "CEO만 할 수 있는 것" (env 입력, OAuth 로그인, 변호사 미팅) | ✅ 완료 표시 / Defer / 상세 가이드 |
| 📊 KPI | 24h 핵심 숫자 | read-only |
| ⏰ 다음 fire | 다음 24h cron 일정 | read-only |
| 📎 변호사 큐 | 미해결 법무 P0 carry-over | "자세히" → legal_question_queue.md |

### 5.3 콘텐츠 규칙
- 항목당 최대 3줄 (제목 + 근거 + 액션)
- 카테고리당 항목 5개 초과 시 "+ N more" 접기
- 자율 처리 완료는 24h 후 자동 archive
- 결정 대기는 응답 전까지 매일 누적 표시 (Defer 누르면 24h 숨김)

---

## 6. Phase 4 — 3-button 응답 메커니즘

### 6.1 응답 의미

| 버튼 | 의미 | 동작 |
|---|---|---|
| **OK** | "자율 진행해" | backend `/api/inbox/respond` POST → 해당 agent 자동 실행 (commit / env 변경 / 배포) |
| **Defer** | "내일 다시 봐" | 24h 동안 inbox에서 숨김, 익일 06:27 재출현 |
| **Drop** | "영구 폐기" | inbox에서 제거 + autopilot_log.md "dropped by CEO" 기록 |

### 6.2 응답 path

| 매체 | 응답 방법 | backend 처리 |
|---|---|---|
| PWA `/inbox` | 3 버튼 tap | `POST /api/inbox/respond {id, action: ok/defer/drop}` |
| Slack thread | reply "ok" / "defer" / "drop" | Slack webhook → backend `/api/inbox/slack-respond` (단순 keyword detect) |
| 이메일 reply | 본문 "OK" 첫줄 (대소문 무관) | Brevo inbound (미박힘) → backend `/api/inbox/email-respond` |

### 6.3 자율 진행 예시 (OK 누른 후)

**케이스 A: 카피 변경 OK**
1. backend `/api/inbox/respond {id: copy-001, action: ok}`
2. `services/brand_voice/applier.py` (신규) 호출 → marketing_copy.md + landing/hero 파일 자동 patch
3. git commit "brand: apply '기록의 코치' copy (CEO inbox approval)" + push
4. PR 자동 생성 + auto-merge (GitHub Actions)
5. Vercel auto-deploy
6. 결과 → 익일 morning-brief "자율 처리 완료"에 표시

**케이스 B: Pricing A/B OK**
1. backend `/api/inbox/respond {id: pricing-001, action: ok}`
2. `services/growth/ab_runner.py` (신규) → experiment row insert + flag 활성
3. growth_experiments.md "active" 상태로 기록
4. 30일 후 자동 결과 리포트 → inbox 신규 항목 "결과 검토"

**케이스 C: Brevo env ✅ (외부 액션 완료 표시)**
1. backend `/api/inbox/respond {id: brevo-001, action: done}`
2. carry-over에서 제거 + autopilot_log 기록
3. health check `/api/health/email-cascade` 자동 실행 → SendGrid + Brevo OK 확인 → 결과 inbox

### 6.4 코드 변경 범위 (Phase별, 추정)

| 컴포넌트 | 신규/수정 | 라인 추정 | Phase |
|---|---|---|---|
| `services/inbox/aggregator.py` | 신규 | ~400 | A |
| `services/inbox/responder.py` | 신규 | ~250 | B |
| `services/inbox/models.py` (SQLAlchemy) | 신규 | ~150 | A |
| alembic migration `0XX_inbox_tables.py` | 신규 | ~80 | A |
| backend `routes/inbox.py` | 신규 | ~200 | A+B |
| `services/brand_voice/applier.py` | 신규 | ~180 | B |
| `services/growth/ab_runner.py` | 신규 | ~220 | B |
| `frontend/src/app/inbox/page.tsx` | 신규 | ~350 | B |
| `frontend/src/components/inbox/*` | 신규 (5개) | ~400 합계 | B |
| `services/notifications/slack_inbox.py` | 신규 | ~150 | D |
| `services/notifications/brevo_inbox.py` | 신규 | ~180 | C |

**합계 ~2,560 라인** (Phase A 830 / B 1,400 / C 180 / D 150). 모두 신규 모듈, 기존 코드 침습 최소.

---

## 7. Phase 5 — 모바일 PWA `/inbox` 화면 spec

### 7.1 레이아웃 (텍스트 mockup, 가로 360px 기준)

```
┌────────────────────────────────┐
│ ← Inbox                  ⟳    │  ← 헤더 (sticky, 48px)
│ 2026-05-29 06:30 KST           │
├────────────────────────────────┤
│                                │
│ 🟢 자율 처리 완료     (3)  ▼  │  ← 카테고리 헤더 (Eyebrow 토큰)
│ ┌──────────────────────────┐  │
│ │ bug-hunter: typo fix     │  │  ← 카드 (border 1px, padding 16px)
│ │ services/data/fmp.py:223 │  │
│ │ PR #501 자동 머지 →      │  │
│ └──────────────────────────┘  │
│ ┌──────────────────────────┐  │
│ │ data-freshness: KIS      │  │
│ │ 24h+ stale 자동 복구     │  │
│ └──────────────────────────┘  │
│ + 1 more                       │  ← 접기
│                                │
│ 🟡 결정 대기         (2)  ▼  │
│ ┌──────────────────────────┐  │
│ │ Brand-voice 신규 카피    │  │
│ │ "기록의 코치"            │  │
│ │ legal_filter 통과 ✓      │  │
│ │                          │  │
│ │  [ OK ]  [Defer] [Drop]  │  │  ← 3 버튼 (44px 높이 HIG)
│ └──────────────────────────┘  │
│ ...                            │
│                                │
│ 🔴 외부 액션         (1)  ▼  │
│ ...                            │
│                                │
│ 📊 KPI 24h                     │
│ signup 0 / MRR ₩0              │
│                                │
│ ⏰ 다음 fire                   │
│ 04:00 data_integrity ...       │
└────────────────────────────────┘
```

### 7.2 디자인 토큰 (v3 준수)

| 요소 | 토큰 | 비고 |
|---|---|---|
| 배경 | `--vantablack` `#0A0A0A` | v3 |
| 카드 배경 | `--surface-1` `#121212` | v3 |
| 텍스트 | `--text-primary` `#F5F5F5` | v3 |
| Accent (OK) | `--bronze` `#C99A4B` | v3 |
| 🟢 status | `--up` `#A23030` carmine | v3 (KR 상승) |
| 🔴 status | `--alert` `#C84A4A` | v3 |
| 헤딩 | Playfair Display | v3 (italic 금지 — `feedback_thorough_fixes`) |
| 본문 | Inter | v3 |
| 카테고리 헤더 | Eyebrow 컴포넌트 (uppercase tracking-wider) | v3 |
| 버튼 높이 | 44px | Apple HIG min tap target |
| 카드 간격 | 12px | v3 8pt grid 1.5배 |

### 7.3 인터랙션
- 카드 tap → 상세 sheet bottom-up (높이 70vh)
- 상세 sheet: agent 이름 / 결정 근거 / 영향 범위 / rollback 가능 여부 / 관련 commit
- OK tap → 0.3s confirm modal "자율 진행할까요?" → backend POST → 카드 fade out
- Defer tap → 즉시 카드 fade out (확인 없음, 가벼움)
- Drop tap → confirm modal "영구 폐기 (autopilot_log 기록)" → POST → fade out
- Pull-to-refresh → 카테고리 재로드

### 7.4 모션 (motion-spec skill 준수)
- 카드 fade in/out: 200ms `ease-out`
- Bottom sheet: 280ms `ease-out` (translateY)
- 금지: bounce / spring overshoot (금융 앱 — motion-spec.md)

### 7.5 PWA push
- 매일 06:27 KST 1회 (morning-brief 직후, 결정 대기 ≥1건일 때만)
- 외부 액션 신규 추가 시 즉시 1회
- 폼: "PivoxQuant Inbox · 결정 대기 2건 · 외부 액션 1건"
- 데이터 payload: `{deepLink: "/inbox"}` → tap 시 바로 `/inbox`

---

## 8. Phase 6 — 구현 단계 + 의존성

### 8.1 Phase A — Backend Aggregator (1주, 0원)

**목표**: read-only inbox JSON 생성 + 5개 출처 수집

**작업**:
1. `services/inbox/models.py` — `InboxItem` 테이블 (id, category, title, body, action_payload, status, created_at, deferred_until, dropped_at)
2. alembic migration — prod schema self-heal 가드 포함 ([[project_prod_schema_selfheal]] 룰)
3. `services/inbox/aggregator.py` — 5개 collector:
   - `collect_autopilot_log()` — `autopilot_log.md` 최근 24h tail parse
   - `collect_ship_blockers()` — `SHIP_BLOCKERS.md` 헤더 RELEASE/RISK/POST 카운트
   - `collect_weekly_packet()` — `weekly_packet_*.md` 최신 1개 핵심 3줄
   - `collect_decisions_pending()` — `agent_decisions` 테이블 status=pending
   - `collect_carry_over()` — `legal_question_queue.md` P0 + carry-over.md 미해결
4. cron: 매시간 47분 (api-sentinel과 동시) inbox 재계산 → DB upsert
5. `routes/inbox.py` GET `/api/inbox` — 카테고리별 JSON 반환

**검증**:
- pytest `tests/inbox/test_aggregator.py` ≥10 케이스
- 실 데이터로 `curl /api/inbox` 카테고리 6개 모두 반환

**의존**: 없음 (Phase A 단독 가능)

---

### 8.2 Phase B — Frontend + 3-button 응답 (1주, 0원)

**목표**: PWA `/inbox` 화면 + OK/Defer/Drop 응답 동작

**작업**:
1. `frontend/src/app/inbox/page.tsx` — SSR + SWR 5s polling
2. `frontend/src/components/inbox/` — `CategorySection / InboxCard / ActionButtons / DetailSheet / KPIBlock` 5개
3. backend `POST /api/inbox/respond` — body `{id, action}` 검증 + dispatcher
4. `services/inbox/responder.py` — action별 dispatcher:
   - `dispatch_ok(item)` → `item.action_payload.type` 분기 (`brand_voice` / `pricing_ab` / `auto_pr` / ...)
   - `dispatch_defer(item)` → `deferred_until = now + 24h`
   - `dispatch_drop(item)` → `dropped_at = now` + autopilot_log append
5. `services/brand_voice/applier.py` — 카피 변경 자동 patch + git commit (push은 별도 CEO 세션, `feedback_push_workflow`)
6. `services/growth/ab_runner.py` — A/B experiment row insert + flag

**검증**:
- vitest `inbox/page.test.tsx` ≥6 케이스
- Playwright `e2e/inbox-flow.spec.ts` — OK 누르면 카드 사라지고 24h 후 자율 결과 출현
- legal_filter 통과 (브랜드 카피 적용 path)

**의존**:
- Phase A 완료
- `services/brand_voice` 존재 확인 필요
- PWA push 인프라 (이미 보유, 메모리 [[project_pwa]])

---

### 8.3 Phase C — 이메일 daily digest (Brevo 박힌 후, 0원)

**목표**: Slack 못 보는 날 backup 매체

**전제**: Brevo API key Railway env 박힘 (현재 carry-over)

**작업**:
1. `services/notifications/brevo_inbox.py` — 매일 06:30 KST inbox JSON → HTML 변환 + 발송
2. 정통망법 §50 List-Unsubscribe 헤더 (`project_email_infra.md` 준수)
3. 이메일 본문 OK/Defer/Drop은 **링크 클릭 → PWA `/inbox/respond?id=X&action=ok`** (이메일 reply parse는 Phase D 이후)
4. ⚠️ **변호사 답변 의존**: Q-S1 §50 분리동의 미해결 — 출시 전이라 자기 자신에게만 발송하므로 §50 적용 외 (1인 운영 + 본인 동의). 출시 후 일반 유저 대상 발송 차단.

**검증**:
- 본인 이메일로 1주일 daily digest 수신 → 가독성 확인
- List-Unsubscribe 헤더 grep 통과

**의존**:
- Brevo env 박힘 (CEO 외부 액션, 10분)
- Phase A 완료
- Q-S1 변호사 답변 — 본인 발송은 무관, 일반 발송 차단 로직만 필요

---

### 8.4 Phase D — Slack 통합 (webhook 박힌 후, 0원)

**목표**: 모바일 push 강력 + thread reply 응답

**전제**: Slack webhook URL Railway env 박힘 (현재 carry-over)

**작업**:
1. `services/notifications/slack_inbox.py` — inbox 변화 시 webhook POST (06:30 daily + 외부 액션 신규)
2. Slack 채널 `#pivox-ceo-inbox` 신규 생성 (CEO 작업, 5분)
3. Slack event subscription (thread reply) → backend `/api/inbox/slack-respond`
4. thread reply keyword detect: `ok` / `defer` / `drop` (대소문 무관, 다른 텍스트 섞여도 첫 단어 매칭)
5. ⚠️ Slack Event API는 verification token 필요 — webhook free tier 한도 내 가능 (Slack 무료 플랜)

**검증**:
- 본인 워크스페이스에서 일주일 Slack push 수신 + thread reply OK 응답 → 자율 진행 확인

**의존**:
- Slack webhook env 박힘 (CEO 외부 액션, 10분)
- Slack 워크스페이스 `pivoxquant.slack.com` (이미 보유 가정, 미보유면 무료 생성)
- Phase A + B 완료

---

### 8.5 Phase 의존성 그래프

```
[A] Backend Aggregator
   ↓ (필수)
[B] Frontend + 3-button
   ↓ (선택, 병렬 가능)
   ├─ [C] 이메일 digest (Brevo env 박힌 후)
   └─ [D] Slack 통합 (webhook 박힌 후)
```

**최소 작동 단위**: A + B 만으로 PWA `/inbox` 완전 동작.
C/D는 push 강화일 뿐 필수 아님.

---

## 9. 비기능 요구사항

| 항목 | 요구 |
|---|---|
| 응답 시간 | `/api/inbox` p95 < 200ms (메모리 5개 출처 캐시) |
| 새로고침 | SWR 5s polling (모바일 데이터 절약) |
| 모바일 first | 360px 가로 기준 설계, 데스크탑은 max-width 480px 중앙 |
| 접근성 | 버튼 44px+ / aria-label 모두 / 색 contrast WCAG AA |
| 오프라인 | service worker 캐시 (마지막 inbox 표시), 응답은 online 필요 |
| 보안 | `/api/inbox/respond` JWT + CSRF 토큰 (기존 인증 재사용) |
| 다국어 | 한국어만 (1인 운영 CEO 전용) |
| 분석 | 자체 로그 (GA 미사용, [[legal_pipa_saas_inventory]] 준수) |

---

## 10. Success Metrics

### Primary
- **CEO inbox 일일 활성**: 7일 중 6일 이상 06:30-07:00 KST 사이 `/inbox` 1회 이상 진입
- **결정 응답 시간 중앙값**: OK/Defer/Drop 누르기까지 < 60초 (PWA 또는 Slack)
- **결정 누락률**: 7일 누적 결정 대기 항목 0건 (모두 응답)

### Secondary
- **자율 처리 비율**: 자율 완료 / (자율 완료 + 결정 대기) ≥ 70%
- **carry-over 해소 속도**: 추가 후 평균 7일 이내 ✅ 완료
- **분산 출처 진입 감소**: morning-brief / autopilot_log / SHIP_BLOCKERS 직접 열기 빈도 50% 감소

### Failure signal
- 결정 누락 7일 연속 ≥1건 → inbox 자체가 노이즈 → 카테고리 재설계
- OK 누른 후 자율 진행 실패 ≥2회 → dispatcher 신뢰도 파괴 → rollback to Phase A read-only

---

## 11. Out of Scope (의도적으로 안 함)

| 안 하는 것 | 이유 |
|---|---|
| 카카오톡 알림톡 | 비용 발생 ([[feedback_no_extra_cost]]) + 사업자 인증/템플릿 심사 부담 |
| 일반 유저용 inbox (멀티 CEO) | 1인 운영, 본인만 사용 |
| inbox UI 비주얼 디자인 (Figma) | 본 spec은 텍스트 mockup만 (디자인부 별도 task) |
| 이메일 reply parse (자연어 응답) | Phase D는 링크 클릭만, NLP 복잡도 회피 |
| Push 알림 사운드/햅틱 | PWA 기본 동작만 |
| inbox 항목 우선순위 정렬 알고리즘 | v1은 시간순/카테고리순 고정, ML 정렬은 v2 |
| inbox 검색/필터 | v1 단일 화면, 검색은 v2 |
| 이력 archive 화면 | autopilot_log.md가 SoT, inbox는 24h 윈도우만 |
| 카톡/문자 fallback | 비용 발생, drop |
| Apple Watch / wearable | 1인 운영 우선순위 낮음, v3+ |

---

## 12. Edge Cases

| 케이스 | 처리 |
|---|---|
| inbox 항목 0건 | 카테고리 헤더 숨김 + "오늘은 결정 대기 없음 ☕" 1줄 표시 |
| 자율 진행 실패 (dispatch_ok 예외) | 항목 status="failed" + error 메시지 카드에 표시 + Sentry 보고 |
| Drop 후 후회 | `autopilot_log.md` 기록 → CEO가 수동으로 다시 trigger (UI에서 복구는 v1 미지원) |
| Defer 무한 반복 | 7회 Defer 누적 시 자동 Drop + autopilot_log 기록 ("CEO ignored, auto-dropped") |
| 동일 항목 중복 수집 (aggregator) | `dedup_key` (source + sha256(title)) UNIQUE 인덱스 |
| inbox 응답 중 prod 장애 | DB write retry 3회 + 실패 시 PWA "응답 저장 실패, 재시도" 토스트 |
| 변호사 답변 Q-S3 (월구독 충돌) 답 받기 전 결제 결정 | inbox에 절대 노출 X — 출시 BLOCKER 유지 |
| Slack thread reply에 OK 외 다른 단어 | 첫 단어만 매칭, 모호하면 무시 + Slack ephemeral msg "응답 인식 못함, ok/defer/drop 중 하나로" |
| 이메일 digest 발송 실패 (Brevo 한도 초과) | SendGrid cascade fallback ([[project_email_infra]] 자동) |
| PWA service worker 캐시로 stale inbox 표시 | pull-to-refresh 시 강제 fetch + SW invalidate |

---

## 13. 변호사 답변 의존부 (carry-over)

| 항목 | 변호사 질문 | 영향 |
|---|---|---|
| Phase C 이메일 digest (일반 유저 발송) | Q-S1 §50 분리동의 | 본인 발송은 무관, 일반 발송 차단 로직만 필요 |
| 결정 항목에 "Pricing A/B" 포함 가부 | Q-S3 §101 ② "매월 청구 금지" | 출시 BLOCKER, 답변 전 결제 관련 결정 inbox 노출 금지 |
| 결정 항목 "Brand-voice 카피" | Q-M1/M2/M3 §101 마케팅 카피 | legal_filter 통과 후에도 변호사 최종 OK 필요 항목은 별도 라벨 |

**원칙**: 변호사 답변 추측 금지. 위 3건은 답변 받기 전까지 inbox 카테고리에서 자동 필터링.

---

## 14. Acceptance Criteria

### Phase A
- [ ] Given inbox 항목이 5개 출처에서 수집되어 있을 때, When `GET /api/inbox` 호출, Then 6개 카테고리 JSON 응답 200 < 200ms
- [ ] Given autopilot_log.md에 신규 라인 추가, When 매시 47분 cron 실행, Then InboxItem row 추가 + dedup_key 중복 시 update
- [ ] Given alembic 040 prod 누락 케이스, When 배포, Then self-heal 가드로 inbox 테이블 생성 ([[project_prod_schema_selfheal]] 룰)

### Phase B
- [ ] Given `/inbox` 모바일 360px 방문, When SWR 폴링, Then 6개 카테고리 카드 표시 + 44px+ tap target
- [ ] Given 카드 OK tap, When `/api/inbox/respond` POST, Then 200 응답 + 카드 fade out 200ms + 자율 진행 dispatcher 호출
- [ ] Given Defer tap, When 24h 경과, Then 익일 06:27 inbox에 재출현
- [ ] Given Drop tap, When confirm modal, Then autopilot_log.md "dropped by CEO {id} at {ts}" append

### Phase C
- [ ] Given 06:30 KST 매일, When Brevo 발송, Then 본인 이메일 수신 + List-Unsubscribe 헤더 포함
- [ ] Given 이메일 link 클릭 `/inbox/respond?id=X&action=ok`, When PWA 로드, Then 해당 항목 OK 자동 dispatch

### Phase D
- [ ] Given Slack `#pivox-ceo-inbox` 발송, When 모바일 push 수신, Then 30초 이내 thread reply "ok" 가능
- [ ] Given thread reply "ok", When Slack Event API, Then backend `/api/inbox/slack-respond` 200 + 자율 진행

---

## 15. v2 후보 (출시 후 검토)

- inbox 우선순위 ML 정렬 (CEO 응답 패턴 학습)
- inbox 항목 검색/필터
- archive 화면 (autopilot_log 시각화)
- Drop 복구 UI
- 음성 응답 ("헤이 시리, PivoxQuant inbox OK") — Apple Shortcuts
- inbox API 외부 노출 (zapier 등) — 비용 발생 가능성 검토 후
- 일반 유저용 "User Inbox" — User as CFO Artifact 패턴 연장 ([[product_concept_cfo]])
- inbox WAMR (Weekly Active Monthly Return) — North Star KPI 통합

---

## 16. 의사결정 로그

| 일자 | 결정 | 근거 |
|---|---|---|
| 2026-05-28 | 단일 컨테이너 채택 (분산 → 통합) | CEO 통증: 분산 5-10분/일 |
| 2026-05-28 | PWA primary + Slack 보조 + 이메일 backup | 0원 + mobile-first + 이미 인프라 보유 |
| 2026-05-28 | 카카오톡 알림톡 영구 제외 | 비용 + 인증 부담 |
| 2026-05-28 | 3-button (OK/Defer/Drop)만 유지 | tap 부담 최소 + Snooze는 Defer로 통합 |
| 2026-05-28 | v1 한국어만 | 1인 운영 |
| 2026-05-28 | inbox 항목 24h 윈도우 + autopilot_log SoT | 단순화 + 기존 SoT 재사용 |

---

## 17. 부록 — 출처별 데이터 매핑

| 출처 | aggregator 함수 | 카테고리 매핑 |
|---|---|---|
| autopilot_log.md tail | `collect_autopilot_log()` | "[✓] " prefix → 🟢 자율 완료 / "[?] " → 🟡 결정 / "[!] " → 🔴 외부 |
| SHIP_BLOCKERS.md 헤더 | `collect_ship_blockers()` | RELEASE/RISK/POST 카운트만 → 🟢 (변화 시 상세) |
| weekly_packet (일요일만) | `collect_weekly_packet()` | KPI 블록 → 📊 |
| agent_decisions table | `collect_decisions_pending()` | status=pending → 🟡 |
| legal_question_queue.md | `collect_carry_over()` (legal partition) | P0 카운트 → 📎 변호사 |
| carry-over.md | `collect_carry_over()` (ops partition) | env 박힘 필요 → 🔴 외부 |

---

**EOF — v56-M2 / 615 lines / 한국어**
