# PivoxQuant — 인수인계서 (2026-04-23 세션 종료 · v5 "Living CFO 4-Layer")

## 🎯 세션 최종 성과 (13 commits pushed this session)

**Commit chain**: `3214f08 → e2a8e25` (13 new commits)

---

## 확정된 제품 정체성

### One-Liner
> **"2년 쓰면 너보다 너를 더 잘 아는 개인 CFO"**

### 4-Layer 아키텍처
```
Layer 4  Personal Journal Companion  — 유저 전담 AI (Closed Beta, AGENT_ENABLED=0)
Layer 3  Artifact                    — 페르소나별 PDF/이메일 (8 페르소나 × 3 리포트 분기)
Layer 2  Learning                    — Drift · Pulse · Feedback (UI + API 완성)
Layer 1  Identity                    — InvestmentProfile (온보딩 20문항)
```

---

## 📦 이번 세션 13 commits

| Hash | 영역 | 요지 |
|---|---|---|
| `6c7be45` | artifacts | PDF P0 triple — Year-End letter + fonts 10MB + Bronze drift |
| `4722961` | dashboard | Layer 2 UI (PersonaCard + RollingWindow + Pulse + SectionFeedback + StatusBar) |
| `cb3811a` | landing | Living CFO Hero v4 (v2 초판) + 3-Layer + 8 personas + 4티어 pricing |
| `3214f08` | reports | 8 strategy/design/product/legal/audit 심층 문서 |
| `1e4fbab` | agents | Journal Companion skeleton + persona overlays + audit + kill switch |
| `76acb8f` | frontend | Companion UI (/companion + ChatPanel + teaser + bottom-nav) |
| `e3461d9` | profile | Layer 2 API — persona/rolling-window/feedback/pulse |
| `57be9ae` | weekly-memo | Risk Dashboard 실계산 (하드코딩 VaR/ES/MDD/TailRatio 해제) |
| `9faf54b` | audit | Field mapping 351 default() — 99 ORPHAN+MISMATCH |
| `94732e8` | artifacts | Persona PDF × 8 × 3 리포트 (24 partials + 3 서비스) |
| `8a3c1e5` | hero | v4 cinematic (aurora + particles + glyph + data stream + ink bleed) |
| `9a66f35` | landing | V2 슬림 7-섹션 + TopNav 메가드롭다운 + MobileDrawer + 7 feature pages |
| `e2a8e25` | dashboard | Layer 4 cinematic (Today Hero + Queue + Persona Evolution + Upsell + 4-dot) |

---

## 🧪 테스트 상태
- **267/267 tests pass** (backend)
  - Companion gate 30 + Persona adapter 130 + Agent route 10 + Profile Layer 2 18 + Weekly Risk 6 + Persona PDF 65 + Regression 0 fail
- **Frontend build**: 50/50 static routes, 0 TS errors, 0 lint warnings
- **Railway + Vercel 자동 배포** 완료

---

## 🆕 신규 인프라 (이번 세션)

### Backend
```
services/agents/             Journal Companion (Closed Beta)
├─ __init__.py
├─ journal_companion.py      stateless orchestrator
├─ legal_gate.py             20 advice regex + 89 shared filter
├─ persona_adapter.py        compose system + persona overlay
├─ data_bridge.py            pseudonymized DB → AgentContext
├─ audit_logger.py           2-year regulatory retention
└─ prompts/
   ├─ companion_system.md    HARD rules + T1~T6 templates
   └─ persona/*.md           8 persona tone overlays

services/profile/            Layer 2 analytics
├─ persona_analytics.py      8-centroid cosine classifier
└─ rolling_metrics.py        pandas rolling 30/60/90d

services/artifacts/
├─ persona_resolver.py       8 persona code mapping
└─ templates/partials/       24 partials (8 persona × 3 section) + macros

models/
├─ user_agent_audit.py       UserAgentAudit + AgentKillSwitch
├─ companion_waitlist.py     email hash + consent
├─ artifact_feedback.py      🔥😐😴 votes
└─ weekly_pulse.py           mood/confidence/topics

migrations/
├─ 010_user_agent_audit.py
└─ 011_layer2_profile_tables.py

routes/
├─ agent.py                  POST /api/agent/query + GET /status
├─ agent_admin.py            kill/revive/audit/stats/purge
└─ profile.py                Layer 2 extensions
```

### Frontend
```
src/app/(dashboard)/companion/page.tsx   Closed Beta 진입
src/app/features/                        7 신규 feature pages
├─ engine, explorer, reports, personas, dashboard, pre-trade, global-desk

src/components/companion/                Layer 4 chat UI
├─ chat-panel.tsx
└─ disclaimer-band.tsx

src/components/landing/                  V2 + Hero v4
├─ top-nav.tsx              sticky mega-dropdown
├─ mobile-drawer.tsx        accordion slide-in
├─ landing-v2.tsx           슬림 7-섹션
├─ marquee-logos.tsx
├─ personas-preview.tsx     4-of-8
├─ feature-page-shell.tsx
├─ hero-aurora.tsx          bronze radial
├─ hero-particles.tsx       canvas drift
├─ hero-typography.tsx      glyph reveal
├─ hero-data-stream.tsx     paper flow
├─ cta-ink-bleed.tsx        SVG ink
├─ companion-teaser.tsx
└─ (legacy landing-page.tsx — orphaned)

src/components/home/                     Layer 4 + cinematic
├─ today-hero.tsx
├─ artifact-queue.tsx
└─ persona-glyph.tsx

src/components/dashboard/                Layer 2 + 4
├─ persona-card.tsx
├─ rolling-window.tsx
├─ weekly-pulse.tsx
├─ living-cfo-status.tsx   4-dot
├─ persona-evolution.tsx
└─ upsell-plus.tsx

src/lib/cfo/
├─ hooks.ts                 Layer 2 hooks
└─ useCompanion.ts          Layer 4 hooks
```

### 문서
```
reports/strategy/COMPETITIVE_ANALYSIS_2026-04-23.md      26 경쟁사 + Only-We + 3 Silver Bullet
reports/strategy/CFO_FEATURE_DEEP_DIVE_2026-04-23.md     30 CFO 기능 + TOP 7 Wave 2
reports/strategy/RADICAL_NEVER_DONE_2026-04-23.md        18 radical + Signature "Pre-Trade Checklist"
reports/design/PDF_REDESIGN_SPEC_2026-04-23.md           Goldman IC 타이포 + Exhibit + 우선 3종
reports/product/PDF_CONTENT_AUDIT_2026-04-23.md          7축 점수 + 456 default + 3 P0 content bugs
reports/product/PERSONA_SPEC_2026-04-23.md               8 페르소나 × 9 항목 (1008줄)
reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md           HIGH-risk 재설계 + PIPA + 10 꼼수
reports/legal/DRAFT_PRIVACY_POLICY_COMPANION_2026-04-23.md
reports/legal/DRAFT_TERMS_AI_CLAUSE_2026-04-23.md
reports/legal/LEGAL_CONSULT_DELTA_2026-04-23.md          Q12~Q20
reports/audit/EXISTING_ARTIFACTS_2026-04-23.md           15/18 PDF production
reports/audit/MODEL_INVENTORY_2026-04-23.md              40 클래스 (CLAUDE.md 58 오류 정정)
reports/audit/FIELD_MAPPING_AUDIT_2026-04-23.md          351 default, 99 ORPHAN+MISMATCH
reports/lighthouse/*                                      perf baselines
docs/JOURNAL_COMPANION_BETA.md                           운영 런북 350줄
```

---

## 💰 Pricing 최종안 (이번 세션 확정)

| Tier | 월 | 연간(월환산) | 핵심 |
|---|---|---|---|
| Free | 0 | - | 1종목 맛보기 |
| Pro | 14,900 | 11,900 | 15종 PDF + Morning Brief |
| Premium | 29,900 | 22,900 | + Portfolio Journal + IPS + Decision Ledger |
| **Premium Plus (CFO Suite)** | **49,900** | 39,900 | + Pre-Trade Checklist + Second Opinion + **Journal Companion** + 양도세 추정기 |
| Founding Lifetime | 99,000 일시불 | — | **선착순 200석** |

기존 9,900/19,900에서 인상 + 49,900 신설. 기존 Pro 가입자 6개월 Grandfathering.

---

## 🛡 법적 방어선 (v5 기준)

| 항목 | 상태 |
|---|---|
| DisclaimerBanner | ✅ 13/13 페이지 |
| legal_filter.py | ✅ 89 regex |
| Journal Companion legal_gate | ✅ 20 advice regex 추가 (30 gate test pass) |
| POSITIVE/NEGATIVE/NEUTRAL 라벨 | ✅ |
| KIS read-only / Alpaca paper | ✅ |
| AGENT_ENABLED=0 | ✅ Dockerfile ENV 기본값 |
| Journal Companion 스펙 | ✅ SAFE_FEATURE_SPECS §6 + Q7~Q11 + 꼼수 10개 |
| 개인정보처리방침 draft | ✅ Companion 섹션 (로펌 대기) |
| 이용약관 AI 면책 draft | ✅ (로펌 대기) |
| 로펌 Q 자료 | ✅ Q1~Q20 총 20개 |
| 유사투자자문업 신고 | ⏳ 로펌 Q9 답변 대기 |
| 상표 출원 | ⏳ 미출원 (62,000원 × 2건) |

---

## ❌ 이번 세션 **완료하지 못한 것** (정직)

1. **Dashboard "Terminal" 전면 전환** — agent BLOCKED. 방향 전환 (Bloomberg Terminal + Linear.app 수준) 설계안 작성까지. Phase 1 (foundation) 대기. **종이 Dossier 레이아웃 유지 중** (CEO "싼마이" 지적분).
2. **E2E 프로덕션 실측** — Chrome MCP 미존재로 실제 클릭 테스트 불가. 빌드/type check 만 증명.
3. **dd_checklist AAPL 하드코딩 fix** — Field mapping audit 발견. 다른 종목 유저도 AAPL 재무제표 수신 (법적 사실 오류). 별도 fix 필요.
4. **Field mapping 52% quick win** — 3 shared vars (issue_number/doc_ref/hero_headline) mixin 미구현. 81 ORPHAN 중 42개 한 번에 해소 가능한데 미진행.
5. **Legacy landing-page.tsx 삭제** — orphaned 상태 유지. UAT 후 삭제.
6. **CountUp 애니메이션 V2 wire** — Hero/Pricing 숫자 카운트업 미연결.
7. **Engine 40-model drawer migration** — `/features/engine` 에 인터랙티브 drawer 없음 (요약만).
8. **Sample Reports flip-deck migration** — `/features/reports` 에 6-card grid 만.
9. **Internal Beta dogfood** — Journal Companion AGENT_ENABLED=1 staging 7일 돌려본 적 없음.
10. **Railway production smoke test** — env 3개(AV/KIS/Naver) 활성 후 실제 P/E/뉴스 응답 확인 못 함 (Chrome MCP 없음).

---

## 🔴 CEO(너) 외부 할 일

1. **로펌 예약** — `LEGAL_CONSULT_PACKAGE.md` + `reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md` §6 + DRAFT_* 3건 + 20 질문 지참. 150~300만원
2. **상표 출원** — 키프리스 "PivoxQuant" 유사 검색 → 특허로 온라인 62,000원 × 2건 (PivoxQuant + Pre-Trade Checklist)
3. **Stripe Product 등록** — Premium Plus 49,900 + Founding Lifetime 99,000 (Stripe Dashboard 수동)
4. **사업자등록** 홈택스 15분 (642001/642902) + 통신판매업 40,000원
5. **프로덕션 육안 확인** — `https://pivoxquant.com` 최근 배포된 버전 직접 스크롤/클릭해서 피드백
6. **AGENT_ENABLED=0 유지** — 로펌 승인 전까지 절대 1로 변경 금지

---

## 🎯 다음 세션 우선순위

### 🔴 P0 (유저 이탈 리스크)
1. **dd_checklist AAPL 하드코딩 fix** — 법적 사실 오류
2. **Field mapping 52% quick win** (3 vars shared mixin) — 42 ORPHAN 한 번에 해소

### 🟠 P1 (CEO 피드백 반영)
3. **Dashboard "Terminal" 전면 전환 Phase 1** — foundation 컴포넌트 (top-ticker, kpi-card, data-table, command-palette, candlestick-chart) + `/home` 재배치
4. **Legacy landing-page.tsx 삭제** (UAT 후)
5. **CountUp 애니메이션 V2 wire**
6. **Engine 40-model interactive drawer migration**

### 🟡 P2 (Phase 2 작업)
7. **Dashboard Terminal Phase 2** — portfolio/market/signals/risk paper 컴포넌트 교체
8. **Sample Reports flip-deck** migration
9. **Internal Beta dogfood** — Journal Companion staging
10. **Chrome MCP 활성화 후 E2E 12-Track 실측**

### 🔵 P3 (로펌 승인 후)
11. 유사투자자문업 신고
12. Journal Companion Closed Beta 20명 초대
13. 개인정보처리방침 + 이용약관 정식 배포

---

## 📊 최종 상태

- **세션 13 commits 배포** (`3214f08 → e2a8e25`)
- **Tests**: 267/267 pass (backend), 0 TS errors (frontend)
- **Routes**: 50/50 static (프론트) + 90+ backend endpoints
- **Prod**: https://pivoxquant.com (베타 `***REDACTED***`)
- **GitHub**: https://github.com/seanbae-analyst/pivoxquant
- **AGENT_ENABLED**: 0 (Closed Beta 안전)
- **자동 운영**: GitHub Actions Tier A 유지 (15분 health / legal-guard / canary)

---

## 🎯 다음 세션 시작 프롬프트

```
HANDOVER.md v5 읽고 이어서.

컨셉: Living CFO 4-Layer. 이번 세션 13 commits / 267 tests.

P0:
1. dd_checklist AAPL 하드코딩 fix (Field mapping audit 치명)
2. Field mapping 52% quick win (3 shared vars mixin)

P1:
3. Dashboard Terminal Phase 1 (foundation 컴포넌트 + /home 재배치)
4. CountUp wire + Legacy landing 삭제 + Engine drawer migration

CEO 외부:
- 로펌 예약
- 상표 출원
- Stripe Product 등록
- AGENT_ENABLED=0 유지
```

---

**작성**: 2026-04-23 (v5 세션 종료)
**최신 commit**: `e2a8e25`
**프로덕션**: https://pivoxquant.com
**GitHub**: https://github.com/seanbae-analyst/pivoxquant/commits/main
