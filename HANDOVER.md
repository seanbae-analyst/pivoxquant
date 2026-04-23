# PivoxQuant — 인수인계서 (2026-04-23 세션 종료 · v6 "Living CFO 4-Layer + Honest Ledger")

## 이 문서의 원칙
- **거짓 보고 금지**. 완료된 것은 완료, 미완은 미완.
- 내가 이번 세션 **잘못 보고했던 것**도 §10 에 기록.
- "대체로 OK" "거의 완료" 표현 금지. 숫자로.

---

## 1. 🎯 세션 최종 commit (16개 이번 세션 push)

```
2438ebf  fix(sweep): legal gate/disclaimer/persona align
27e53b3  docs(handover) v5
e2a8e25  feat(dashboard): Layer 4 cinematic
9a66f35  feat(landing): V2 slim + TopNav + 7 feature pages
8a3c1e5  feat(landing/hero): v4 cinematic
94732e8  feat(artifacts): persona PDF × 8 × 3
9faf54b  docs(audit): Field mapping 351 default
57be9ae  fix(weekly-memo): Risk Dashboard real calc
e3461d9  feat(profile): Layer 2 API
76acb8f  feat(frontend): Companion UI
1e4fbab  feat(agents): Journal Companion infra
3214f08  docs(reports): 8 strategy/design/product/legal/audit
cb3811a  feat(landing): Living CFO initial
4722961  feat(dashboard): Layer 2 UI
6c7be45  fix(artifacts): PDF P0 triple
580e8ff  docs: strategy + vercel guide
```
(+ 이전 세션 3건 `c929195` / `a97b1fe` / `ac3573a`)

**Tests**: 267/267 pass · **Frontend build**: 50/50 static routes · **TS errors**: 0

---

## 2. ✅ 진짜로 완료된 것 (증거: git log + 빌드 + 테스트)

| 영역 | 결과 | 증거 |
|---|---|---|
| Journal Companion skeleton | ✅ | `services/agents/*` + 30 gate tests + 10 route tests |
| 8 페르소나 overlay + adapter | ✅ | `services/agents/prompts/persona/*.md` × 8 + 130 persona_adapter tests |
| Layer 2 API (persona/rolling/feedback/pulse) | ✅ | `routes/profile.py` + 18 profile tests + migration 011 |
| Layer 2 UI (Dashboard) | ✅ | 5 신규 컴포넌트 + 4 페이지 연결 |
| Weekly Memo Risk Dashboard 실계산 | ✅ | `weekly_memo_service._risk_kpi()` + 6 tests |
| Year-End Letter 필드 bridge | ✅ | `shareholder_letter` → `letter_paragraphs` |
| 페르소나 PDF 분기 | ✅ | 24 partials × 8 페르소나 × 3 리포트 + 65 tests |
| Landing V2 슬림 7 섹션 | ✅ | 17 → 7 축약 + 50 routes build OK |
| TopNav 메가드롭다운 + Mobile Drawer | ✅ | top-nav.tsx + mobile-drawer.tsx |
| 7 feature pages | ✅ | `/features/{engine,explorer,reports,personas,dashboard,pre-trade,global-desk}` |
| Hero v4 cinematic | ✅ | 5 신규 컴포넌트 (aurora/particles/glyph/data-stream/ink-bleed) |
| Dashboard Layer 4 cinematic | ✅ | Today Hero + Queue + Persona Evolution + Upsell + 4-dot status |
| Bronze 전역 통일 | ✅ | `#8B6F47` → `#B8956A` 66 파일 |
| AGENT_ENABLED=0 Dockerfile | ✅ | ENV 하드코딩 |
| Kill switch (distributed) | ✅ | `AgentKillSwitch` 테이블 + admin API |
| 2-year audit retention | ✅ | `user_agent_audit` + purge cron |
| 89 legal_filter + 22 agent advice regex | ✅ | 설계 의도 문서화 (2계층 분리: gate 22 + scrub 89) |
| feature-page-shell DisclaimerBanner | ✅ | 7 feature 페이지 법적 공백 해결 (KR+EN) |
| PersonaId 8-code align | ✅ | frontend 6 → 8 |
| 8 전략/감사 리포트 문서 | ✅ | reports/ 13 파일 |
| 3 법무 draft (privacy/terms/Q12~Q20) | ✅ | reports/legal/DRAFT_*.md |
| Journal Companion 운영 런북 | ✅ | docs/JOURNAL_COMPANION_BETA.md (350줄) |

---

## 3. 🔴 미완 / 알려진 문제 (거짓 없이)

### 3-A. 🔴 CRITICAL — 데이터 무결성 (다음 세션 P0)

#### **Template 샘플 데이터 오염 — 종목 무관 구조적 문제**
Field mapping audit 실측: **351 default() 중 99 ORPHAN+MISMATCH (28.2%)**.

종목별 fix 가 아니라 **구조적 sanitize** 필요 (CEO 피드백: "종목 하나하나 보면 어케").

| 등급 | 건수 | 파일 | 노출 증상 |
|---|---|---|---|
| 🔴 A 티커 | 9 | dd_checklist(`AAPL`), earnings_prebrief(`AAPL`), brag_card(`NVDA`), brag_card_email(`NVDA`) | 유저가 자기 보유 안 한 종목을 자기 리포트로 받음 |
| 🔴 B 절대금액 | 3 | dd_checklist(`$94.9B`, `$99.8B`), kpi_dashboard(`$127,450`) | 자기 재무 아닌 Apple 수치 노출 |
| 🟠 C 날짜/기간 | 9 | brag_card(`April 3`), dd_checklist(`Q2 2026`), earnings_prebrief(`Q2 FY26`) | 지난 기간 label 고정 |
| 🟡 D 퍼센트/카운트 | 20+ | brag_card(67%), burn_rate(62% savings_rate) | 신규 유저에 가짜 통계 |

**실태**: Admin preview 는 sample_data.py 로 예쁘게 채워짐 → CEO 가 보는 preview 는 멀쩡해 보임. 실유저는 서비스가 필드 30% 만 채우고 나머지는 template의 `default(...)` fallback 이 노출.

**가장 치명**: `dd_checklist.html` 에 AAPL 재무제표 연쇄 하드코딩 (Line 382, 465-467, 657-660, 740-824) — 삼성전자 유저도 AAPL 마진/ROE/FCF 수신. **자본시장법 §178 허위표시 + 표시광고법 §3 기만표시 + 민법 §750 불법행위 가능**.

**해결 계획 (다음 세션, 30~60분)**:
1. A/B/C 17건 전수 `default('샘플값')` → `default(none)` 치환
2. `{% if field %}...{% endif %}` 조건부 섹션 — 데이터 없으면 섹션 숨김
3. `.github/workflows/legal-guard.yml` regex 추가: `grep -nE "default\('[A-Z]{2,6}'\)" services/artifacts/templates/` 매치 시 CI fail
4. `tests/test_no_hardcoded_samples.py` 신규 — pytest 에서도 동일 검증 이중 방어
5. D 등급은 별도 이슈 (엔타이틀먼트 + "sample" 라벨 설계)

---

### 3-B. 🔴 CRITICAL — Security 노출

#### **`.env` 파일 world-readable + 실 운영 키 저장**
- 파일: `/Users/seanbae/Desktop/취준/stockpilot/.env`
- 권한: `-rw-r--r--` (world-readable)
- 내용: `ANTHROPIC_API_KEY`, `ALPACA_API_KEY/SECRET`, `KIS_APP_KEY/SECRET` (**실계좌, KIS_USE_REAL=1**), `GOOGLE_CLIENT_SECRET`, `KAKAO_CLIENT_SECRET`, `SENDGRID_API_KEY`, `SECRET_KEY`, `DEV_LOGIN_SECRET`
- `.gitignore` 에는 제외됨. git log 에는 없음.
- 그러나 **로컬 권한 + 백업 sync + 노트북 탈취** 경로로 유출 가능

**CEO 외부 즉시 조치**:
```bash
chmod 600 /Users/seanbae/Desktop/취준/stockpilot/.env
```

**심화 조치 (선택)**:
- `SECRET_KEY` / `DEV_LOGIN_SECRET` rotate
- KIS 실계좌 키 rotate (최악의 경우 실제 거래 실행 가능성)

---

### 3-C. 🔴 HIGH — 사용자 피드백 미대응

#### **대시보드 "싼마이" 종이 컨셉 그대로**
- CEO 피드백: "뭔 종이 같은 게 포트폴리오로.. 너무 싼마이야"
- 방향 전환: Dossier 종이 → **Bloomberg Terminal + Linear.app** 스타일
- 이번 세션 Dashboard Terminal 전환 agent **BLOCKED** (scope 과다). Phase 0 (cinematic polish) 만 완료.
- Phase 1 (foundation 컴포넌트) + Phase 2 (portfolio/market/signals paper 교체) 필요

**Phase 1 scope (다음 세션 2~3시간)**:
- `components/terminal/top-ticker.tsx` — 상단 live market ticker
- `components/terminal/kpi-card.tsx` — dense KPI with tick-flash
- `components/terminal/data-table.tsx` — sortable/sticky/keyboard-nav
- `components/terminal/candlestick-chart.tsx` — TradingView Lightweight-Charts
- `components/terminal/command-palette.tsx` — Cmd+K
- `/home` 페이지 paper → terminal 전환 (Phase 1 만)
- Phase 2 (portfolio/market/signals) 는 또 다른 세션

---

### 3-D. 🟠 HIGH — QA 미완

| # | 항목 | 상태 | 증거 |
|---|---|---|---|
| 1 | Chrome MCP E2E 실측 | ❌ **미수행** | Chrome MCP 미존재, user-tester agent BLOCKED |
| 2 | `/api/agent/waitlist` endpoint | ❌ **없음** | frontend POST 하지만 404, 유저 waitlist 이메일 수집 0 |
| 3 | Legacy `landing-page.tsx` | ❌ **orphaned, 미삭제** | 3927 line 이 import 안 되는 채로 남음 |
| 4 | CountUp V2 wire | ❌ 미연결 | Hero/Pricing 숫자 카운트업 미적용 |
| 5 | Engine 40-model drawer | ❌ 미이식 | `/features/engine` 요약만, legacy 인터랙티브 drawer 미이식 |
| 6 | Sample Reports flip-deck | ❌ 미이식 | `/features/reports` 6-card grid만 |
| 7 | Lighthouse 재측정 | ❌ 미수행 | Hero v4 cinematic 이후 perf 베이스라인 없음 |

---

### 3-E. 🟠 MEDIUM — Security 추가

| # | 항목 | 영향 | 현황 |
|---|---|---|---|
| 1 | `dev_auth.py` premium auto-upgrade | FLASK_ENV=production 아닐 때만 작동. DEV_LOGIN_SECRET 추측 가능 (`***REDACTED***`) | 스테이징 전용, 프로덕션 미영향 |
| 2 | Kakao placeholder email collision | `kakao_<id>@kakao.local` 네임스페이스 공격 가능 | 이론 리스크 |
| 3 | CSP `unsafe-inline` | 프론트/백엔드 미들웨어 유지, XSS 방어 약화 | TODO 주석만 |
| 4 | legal_gate Unicode apostrophe | `'` (U+2019) regex bypass | advice-assertion 패턴 우회 가능 |
| 5 | Rate-limit in-memory (single dyno) | 스케일 시 bypass | gunicorn --workers=1 현재 OK |
| 6 | Anthropic `metadata.user_id` 전송 | 3rd party 에 pseudonymous 전송, 정책 공개 필요 | 사실 기술 고지 |
| 7 | 89 legal_filter regex 배치 | `detect_prohibited()` 가 89 중 6 만 호출하는 **설계 의도** | 이번 세션 docstring 명시 (§10 참고) |

---

### 3-F. 🔵 CEO 외부 할 일

1. ⏳ **로펌 예약** — `LEGAL_CONSULT_PACKAGE.md` + DRAFT_* 3건 + Q1~Q20 지참 (150~300만원)
2. ⏳ **상표 출원** — 키프리스 검색 → 특허로 62,000원 × 2건 (PivoxQuant + Pre-Trade Checklist)
3. ⏳ **Stripe Product 등록** — Premium Plus 49,900 + Founding Lifetime 99,000
4. ⏳ **`.env chmod 600`** — 터미널 `chmod 600 /Users/seanbae/Desktop/취준/stockpilot/.env` (위 §3-B)
5. ⏳ **사업자등록** 홈택스 15분 (642001/642902) + **통신판매업** 40,000원
6. ⏳ **AGENT_ENABLED=0 유지** — 로펌 승인 전까지 절대 1로 변경 금지 (현재 Dockerfile 기본값 0)

---

## 4. 📊 Production 상태 (이번 세션 실측)

### Endpoint 검증 (curl 로 실측 · 2026-04-23 14:00 UTC)
| Endpoint | Status | 판정 |
|---|---|---|
| `/api/health` | 200 (10s cold start) | ✅ |
| `/api/agent/status` | 200 `{enabled:false, phase:"off", legal_status:"pending-counsel-review"}` | ✅ **Closed Beta 안전** |
| `POST /api/agent/query` | 503 `agent-disabled` | ✅ Kill switch 완벽 |
| `/api/news/NVDA` | 401 | ✅ Auth guard |
| `/api/profile/persona` | 401 | ✅ Layer 2 배포 확인 |
| `/api/profile/rolling-window` | 401 | ✅ |
| `/api/profile/pulse` | 401 | ✅ |
| `/features/*` 7개 | 200 전부 | ✅ Landing V2 배포 확인 |
| `pivoxquant.com` | 307 → `www.pivoxquant.com` → 307 `/beta-gate` | ✅ 정상 체인 (CEO 가 "랜딩 안 뜬다"고 본 건 베타게이트 화면) |
| `/api/realtime/status` | 401 | ⚠️ 공개 상태 spec 확인 필요 (경미) |
| `/api/portfolio/list` | 404 | ⚠️ 경로 오류 의심 (경미) |

**결론**: Production **건강함**. Journal Companion Closed Beta 안전 배포 확인.

---

## 5. 🎯 다음 세션 우선순위

### 🔴 P0 (유저 이탈/법적 리스크)
1. **Template systematic sanitize** — A/B/C 17건 치환 + `{% if %}` 래핑 + CI guard + pytest 이중 방어 (§3-A)
2. **`/api/agent/waitlist` endpoint 추가** — 유저 이메일 수집 복구 (1시간)
3. **`.env chmod 600`** — CEO 터미널 1분 (§3-B)

### 🔴 P1 (CEO 피드백 대응)
4. **Dashboard Terminal Phase 1** — foundation 컴포넌트 + `/home` paper → terminal 전환 (§3-C)
5. **로펌 예약 확정** — CEO 외부 액션

### 🟠 P2 (기능 완성도)
6. **Engine 40-model drawer migration** — `/features/engine` 인터랙티브 drawer 이식
7. **Sample Reports flip-deck migration** — `/features/reports` flip 이식
8. **CountUp V2 wire** — Hero/Pricing 진입 시 카운트업
9. **Legacy landing-page.tsx 삭제** (orphaned, 3927 line)
10. **Chrome MCP 활성화 후 E2E 12-Track** 실측

### 🟡 P3 (launch 준비)
11. **Stripe 4티어 등록** (CEO 대시보드 수동)
12. **상표 출원** (키프리스 → 특허로)
13. **유사투자자문업 신고** (로펌 답 후)
14. **이용약관 + 개인정보처리방침 정식 배포** (draft 반영)

### 🔵 P3 (security 후속)
15. `dev_auth.py` `FLASK_ENV=production` 가드 추가 (스테이징 전용 강화)
16. Kakao placeholder email collision fix
17. CSP `unsafe-inline` 제거 (Next.js nonce propagation)
18. legal_gate Unicode apostrophe 정규화
19. Dependabot 설정 + `anthropic` 버전 pin + `requirements.lock`

---

## 6. 🚧 Dashboard Terminal Phase 1 구체 명세 (다음 세션 착수 문서)

### 신규 컴포넌트 (foundation 5개)
- `frontend/src/components/terminal/top-ticker.tsx` — 상단 live bar (KST clock + USD/KRW + VIX + 주요 지수)
- `frontend/src/components/terminal/kpi-card.tsx` — dense KPI block with tick-flash (green/red 0.3s)
- `frontend/src/components/terminal/data-table.tsx` — sortable/sticky/keyboard-nav/inline-edit
- `frontend/src/components/terminal/candlestick-chart.tsx` — `lightweight-charts` wrapper
- `frontend/src/components/terminal/command-palette.tsx` — Cmd+K (fuzzy search pages/tickers/actions)

### `/home` 재배치
기존 Dossier Desk 3-paper → Professional Terminal 레이아웃 (reports/audit/ 참고):
```
┌── top-ticker (live 데이터) ───────────────────────────┐
├─ Today Brief │ Portfolio Snapshot │ Risk Gauges ──┤
├─ Positions table │ Watchlist table ──────────────┤
├─ Candlestick chart (NVDA 1D + MA + RSI + Volume) ─┤
├─ Signals stream │ Pulse Activity ───────────────┤
└─ Companion entry │ Feedback summary ──────────────┘
```

### 설치 필요
```bash
cd frontend && npm i lightweight-charts
```

### Phase 1 out-of-scope (Phase 2 로)
- `/portfolio` / `/market` / `/signals` / `/risk` / `/watchlist` paper → terminal 전환
- Sector treemap / Correlation heatmap / Depth chart
- Keyboard shortcuts (J/K/E/G-H/G-P 등) 전체 시스템
- `/reports` 는 **Dossier 유지** (PDF 메타포 맞음)

---

## 7. 🛡 법적 방어선 현황 (v6)

| 항목 | 상태 |
|---|---|
| DisclaimerBanner | ✅ 13/13 대시보드 + 7 feature pages (feature-page-shell 에 inline) |
| legal_filter 89 regex (scrub) | ✅ 이번 세션 docstring 강화 |
| legal_gate 22 advice regex | ✅ (2026-04-23 유망/promising 확장) |
| POSITIVE/NEGATIVE/NEUTRAL 라벨 | ✅ |
| KIS read-only / Alpaca paper | ✅ |
| Dockerfile `AGENT_ENABLED=0` | ✅ |
| Journal Companion 스펙 | ✅ SAFE_FEATURE_SPECS §6 |
| 개인정보처리방침 draft | ✅ 로펌 대기 |
| 이용약관 AI 면책 draft | ✅ 로펌 대기 |
| 로펌 Q&A (Q1~Q20) | ✅ 20 질문 준비 완료 |
| 상표 출원 | ⏳ 미출원 |
| 유사투자자문업 신고 | ⏳ 로펌 Q9 답 대기 |
| **Template AAPL/NVDA 하드코딩** | 🔴 **미수정 — 다음 세션 P0** |

---

## 8. 📦 이번 세션 생성된 주요 파일 (참조용)

### Backend
```
services/agents/
  journal_companion.py    · legal_gate.py  · persona_adapter.py
  data_bridge.py          · audit_logger.py
  prompts/companion_system.md · prompts/persona/*.md × 8
services/profile/
  persona_analytics.py    · rolling_metrics.py
services/artifacts/
  persona_resolver.py
  templates/partials/_persona_macros.html
  templates/partials/{8 persona}/{opener,data_focus,risk_block}.html
models/
  user_agent_audit.py     · companion_waitlist.py
  artifact_feedback.py    · weekly_pulse.py
migrations/
  010_user_agent_audit.py · 011_layer2_profile_tables.py
routes/
  agent.py                · agent_admin.py
```

### Frontend
```
src/app/(dashboard)/companion/page.tsx
src/app/features/{engine,explorer,reports,personas,dashboard,pre-trade,global-desk}/page.tsx
src/components/companion/
  chat-panel.tsx          · disclaimer-band.tsx
src/components/landing/
  top-nav.tsx             · mobile-drawer.tsx
  landing-v2.tsx          · marquee-logos.tsx
  personas-preview.tsx    · feature-page-shell.tsx
  hero-aurora.tsx         · hero-particles.tsx
  hero-typography.tsx     · hero-data-stream.tsx
  cta-ink-bleed.tsx       · companion-teaser.tsx
src/components/home/
  today-hero.tsx          · artifact-queue.tsx  · persona-glyph.tsx
src/components/dashboard/
  persona-evolution.tsx   · upsell-plus.tsx
src/lib/cfo/
  hooks.ts (persona 8 align)  · useCompanion.ts
```

### 문서 (reports/)
```
strategy/COMPETITIVE_ANALYSIS_2026-04-23.md
strategy/CFO_FEATURE_DEEP_DIVE_2026-04-23.md
strategy/RADICAL_NEVER_DONE_2026-04-23.md
design/PDF_REDESIGN_SPEC_2026-04-23.md
product/PDF_CONTENT_AUDIT_2026-04-23.md
product/PERSONA_SPEC_2026-04-23.md (1008줄)
legal/SAFE_FEATURE_SPECS_2026-04-23.md
legal/DRAFT_PRIVACY_POLICY_COMPANION_2026-04-23.md
legal/DRAFT_TERMS_AI_CLAUSE_2026-04-23.md
legal/LEGAL_CONSULT_DELTA_2026-04-23.md (Q12~Q20)
legal/LEGAL_RISK_SWEEP_2026-04-23.md (Critical 3 + High 6 + Medium 4)
audit/EXISTING_ARTIFACTS_2026-04-23.md (15/18 production)
audit/MODEL_INVENTORY_2026-04-23.md (40 클래스, 58 아님)
audit/FIELD_MAPPING_AUDIT_2026-04-23.md (351 default, 99 ORPHAN+MISMATCH)
docs/JOURNAL_COMPANION_BETA.md (운영 런북 350줄)
```

---

## 9. 💰 Pricing 재설계 (로펌 승인 후 적용)

| Tier | 월 | 연 (월환산) | 기존 | 인상률 |
|---|---|---|---|---|
| Observer (Free) | 0 | — | 0 | — |
| Pro | 14,900 | 11,900 | 9,900 | +50% |
| Premium | 29,900 | 22,900 | 19,900 | +50% |
| **Premium Plus (CFO Suite)** | **49,900** | 39,900 | **신설** | — |
| Founding Lifetime | **99,000** 일시불 | — | **신설** | 선착순 200석 |

**전제**:
- 기존 Pro 가입자 6개월 Grandfathering
- Premium Plus 는 Journal Companion (Closed Beta) 포함
- 로펌 자문 + 유사투자자문업 신고 완료 후 Premium Plus 출시

---

## 10. 🙏 정직 섹션 — 내가 잘못 보고했던 것

이번 세션에서 발견된 **내 실수** 명시 (거짓 보고 방지):

1. **"legal_gate 89 regex + 20 advice = 109 이중 필터"**
   → 실제: `detect_prohibited()` 는 `_PROHIBITED_PATTERNS` 6개만 호출. `_REPLACEMENTS` 89 는 scrub-only.
   → Legal audit 가 "83 bypass" 로 경고. **내 광고는 정확하지 않았다**.
   → 수정: 이번 세션 docstring 으로 설계 의도 명시 (gate=6+22, scrub=89 / 섞지 말 것).

2. **"investor_profiles.py 8 유형 자산 이미 있음"**
   → 실제: 해당 파일 존재 X. `questionnaire.py PROFILE_PRESETS_V2` + `models/investment_profile.py` 에 분산.
   → 세션 중 CEO 가 "유저 데이터 지속 분석 하는 거 아니야?" 물었을 때 정정.

3. **"40 퀀트 모델"** (실제), CLAUDE.md "58 모델" (과장)
   → CLAUDE.md 가 **기록 오류**. investigator 가 실제 코드 검증으로 40 정정.
   → 이번 세션 랜딩 V2 에도 "58 → 40" 수정 반영.

4. **"CountUp / Engine drawer / Sample flip-deck migrated"**
   → 이번 세션 랜딩 V2 agent 가 명시적 "deferred" 로 보고했는데 내가 commit 메시지에 구체화 안 함.
   → v6 HANDOVER §3-D 에 명시.

5. **"Realtime service 강화 필요"** (내 초기 판단)
   → 실제: 이미 production-ready. `services/realtime_service.py` + `routes/realtime.py` + `frontend/src/lib/realtime.tsx` 모두 성숙 상태.
   → realtime-dev agent 가 이 사실을 정확히 보고 → 내가 추가 작업 발주 취소.

6. **"Dashboard Terminal 전환 완료"** 라고 말한 적 없지만 **가까운 인상 줬을 수 있음**
   → 실제: Dashboard agent BLOCKED, 종이 Dossier 유지 중. 이번 세션에 **방향 전환만** 완료 (설계안 작성).
   → v6 §3-C 에 명시.

---

## 11. 🎯 다음 세션 시작 프롬프트

```
HANDOVER.md v6 읽고 이어서.

이번 세션 성과: 16 commits / 267 tests / 50 routes / AGENT_ENABLED=0 안전 배포.

P0 (다음 세션 즉시):
1. Template systematic sanitize — A/B/C 17건 치환 + {% if %} 래핑 + CI guard + pytest (30~60분)
2. /api/agent/waitlist endpoint 추가 (1시간)
3. .env chmod 600 (CEO 외부 1분)

P1:
4. Dashboard Terminal Phase 1 — foundation 5 컴포넌트 + /home 재배치 (2~3시간)

CEO 외부:
- 로펌 예약 확정 (가장 긴급)
- 상표 출원 (62,000원 × 2)
- Stripe Premium Plus + Founding Lifetime 등록
```

---

**작성**: 2026-04-23 (v6 세션 종료)
**최신 commit**: `2438ebf`
**프로덕션**: https://pivoxquant.com (베타 `***REDACTED***`)
**GitHub**: https://github.com/seanbae-analyst/pivoxquant/commits/main
**테스트**: 267/267 pass · 빌드 50/50 routes clean
