# PivoxQuant — Launch Pre-Flight Checklist

> 출시 직전 CEO 단독 + 외부 액션 종합 체크리스트.
> 본 세션 (2026-05-15) 자율 wave가 끝낸 모든 fix + 남은 CEO 의존 모두 정리.
> 작성: v43 autonomous wave 최종 (24 PR 머지, OPEN PR 0).

---

## 🟥 P0 (출시 차단 — CEO 직접 액션)

### 1. **Email infrastructure** (15분, 0원)
**Why blocker**: PDF cron 매주 일요일 발송 시작 → SENDGRID_API_KEY 없으면 silent drop / inbox 없으면 reply bounce / `support@`/`hello@` 4곳 표시 → 표시의무 위반 risk.

**Steps**: `docs/ops/email-setup.md` 따라 진행:
- [ ] Cloudflare 무료 계정 + pivoxquant.com 추가
- [ ] 가비아 → Cloudflare NS 위임 (propagation 1-6h)
- [ ] Cloudflare Email Routing 활성 (support@/reports@/hello@/catch-all → seanbae1521@gmail.com)
- [ ] SendGrid 도메인 인증 (DKIM CNAME × 3)
- [ ] Railway env에 SENDGRID_API_KEY 추가
- [ ] 테스트 발송 1통 → Gmail inbox 도착 confirm

**Verify**: `curl https://web-production-7b484b.up.railway.app/api/health | jq .env.missing_recommended` → 감소 확인 (PR #400 launch_prep).

---

### 2. **변호사 의견서** (출시 차단 — 별 비용)
**Why blocker**: 유료결제 활성화 + AI surface 양방향 채널 회피 + 통신판매업 신고 + §101 면제 트랙 4요건 등 15개 회색지대 항목.

**Status**: `legal_question_queue.md` Q1-Q15 대기. 예상 비용 300-500만원 (금융규제 전문 변호사).

**Steps**:
- [ ] 변호사 미팅 예약 (Kim & Chang 또는 Lee & Ko 금융규제 팀)
- [ ] Q1-Q15 일괄 의견서 요청 (출시 전 한 번에)
- [ ] 의견서 받고 terms-ko.md / privacy-ko.md 수정 (variable)
- [ ] 유료결제 활성화 결정 (Stripe Connect 활성)
- [ ] AI surface 양방향 channel 분류 확정 (companion / ai-chat / pre-trade)

---

### 3. **Stripe 결제 활성화** (변호사 의견 후)
**Why blocker**: 현재 `/api/billing/create-checkout` → 503 `BUSINESS_REGISTRATION_PENDING`. PR #397이 user-facing 메시지 graceful 처리 완료.

**Status**: 사업자등록 완료 (2026-05-08, 459-01-03808). 통신판매업 신고 미완. Stripe Connect 미활성.

**Steps**:
- [ ] 통신판매업 신고 (각 시군구청 또는 인터넷 신청)
- [ ] Stripe Korea 계정 활성화 (사업자등록증 업로드)
- [ ] Pro / Premium Price ID 생성 (각각 ₩9,900 / ₩19,900)
- [ ] Railway env: STRIPE_SECRET_KEY + STRIPE_WEBHOOK_SECRET + STRIPE_PRICE_PRO + STRIPE_PRICE_PREMIUM
- [ ] Stripe webhook URL: `https://pivoxquant.com/api/billing/webhook` 등록
- [ ] routes/billing.py `_business_registration_complete()` 조건 확인 + 활성 분기
- [ ] 테스트 결제 (test mode → live mode)

---

## 🟧 P1 (출시 권고 — 출시 후 1주 내 fix 가능)

### 4. **외부 데이터 소스 점검**

#### 4a. FMP API ($29/mo Premium)
**Issue**: Wave 5에서 chart + news 전체 `source: "none"` 확인. Key 만료 또는 plan 초과 의심.

**Steps**:
- [ ] FMP 콘솔 (financialmodelingprep.com) 로그인 → 사용량 확인
- [ ] Key 만료/도용 여부 확인
- [ ] 필요 시 Renewal 결제
- [ ] Railway env FMP_API_KEY 갱신

**메모리 admit**: FMP $29 Starter plan은 caret-prefixed 인덱스 (^GSPC, ^IXIC, ^KS11) 등 일부 심볼 402 — 영구 한계. 우회는 ETF proxy로 진행 중 (PR #380 disclosure).

#### 4b. Anthropic 크레딧
**Issue**: AI SWOT + coaching 503. Memory: "2026-05-09 v28 root cause = Anthropic 크레딧 소진".

**Steps**:
- [ ] console.anthropic.com → Billing → 잔액 확인
- [ ] $50-100 충전 (출시 후 사용량 모니터링하며 점진 증액)
- [ ] Anthropic API key가 Max plan과 다른 key인지 확인 (Max는 사용자용, API는 서버용 분리)
- [ ] Railway env ANTHROPIC_API_KEY 갱신

---

### 5. **모바일 + responsive 최종 점검**
**Status**: 본 세션 Wave 5에서 일부 fix (IndicesDetailPaper overflow PR #395, mobile watchlist PR #397). verify-ux agent가 viewport resize 미지원 → 실 viewport 검증 INCOMPLETE.

**Steps**:
- [ ] 실 iPhone (375px) / Android (360px) / iPad (768px) 3 viewport에서 모든 dashboard 페이지 직접 클릭
- [ ] Hamburger menu / Bottom nav 동작 확인
- [ ] Form input (signup / pre-trade / settings) 키보드 가림 처리
- [ ] PWA install banner (manifest.json 확인)
- [ ] Touch target 44×44px (WCAG)
- [ ] 발견된 launch-blocker는 직접 fix 또는 본 가이드 update

---

### 6. **/detail/AAPL AAPL=$30 dirty row**
**Status**: 코드 가드는 PR #379 (`_avg_cost_implausible`) wired, 기존 row는 unchanged (migration 034 정책 — "auto-mutation = data fabrication").

**Steps**:
- [ ] Railway PG console (`railway connect Postgres`) 접속
- [ ] `SELECT id, user_id, ticker, avg_cost FROM positions WHERE ticker = 'AAPL' AND avg_cost < 50;`
- [ ] CEO 본인 데모 계정의 dirty row만 → 실제 avg_cost로 update OR delete
- [ ] **다른 user에는 절대 손대지 말 것** (migration 034 정책)

---

### 7. **CAUS Phase 4 첫 실 작동 monitoring**
**Status**: PR #393 자동 fix loop active. 첫 강화 Day 3 tick = 2026-05-19 03:00 KST.

**Steps**:
- [ ] 2026-05-19 09:00 KST 이후 `cat ~/projects/pivoxquant/docs/qa/auto-sim-reports/2026-05-19.md`
- [ ] CAUS가 P0 발견했다면 `~/projects/pivoxquant/docs/qa/auto-fix-log/2026-05-19.md` 확인
- [ ] auto-created PR 있으면 review + merge (label `caus-auto-fix`)
- [ ] state 모니터: `python scripts/caus_auto_fix.py --state-dump`

---

## 🟨 P2 (출시 후 정리 가능)

### 8. **Bug #2 KOSPI 7,699 값 contested**
- 코드 주석: "KIS 7,981 is real, +31% MoM AI chip rally 확정"
- bug-hunt-live.md: "sparkline_30d [2,293-2,640] contradicts 7,981"
- STALE chip (#381) + range_52w null (#385)로 signal 명시화는 완료
- [ ] 변호사 의견 받을 때 같이 — "KIS Open API 신뢰성" 별도 자문 가능

### 9. **Settings notification toggle localStorage-only (GAP-E)**
- Wave 4 P1 #1
- 백엔드 `notification_pref` 테이블 + `/api/notifications/prefs` PUT endpoint 필요
- [ ] 알embic migration 035 + 새 route + 프론트 mutate switch
- 비용: 코드 작업만, 0원

### 10. **historical /alerts INFO body raw ticker**
- Wave 4 P1 #2 (코드 fix됨, DB 과거 rows 영향)
- Migration 034 정책 충돌 — auto-mutation 금지
- [ ] CEO 결정 후 manual SQL backfill 또는 row 자연 만료 대기

### 11. **/pre-trade duplicate input IDs**
- Wave 4 P2 #5 (코드 grep = 1 render, prod = 2 DOM elements)
- Next.js SSR/CSR hydration 의심
- [ ] 직접 브라우저 dev tools로 React rendering 확인
- [ ] 또는 React `useId()` 도입으로 defensive 처리

### 12. **KR watchlist 버튼 ~2초 지연**
- Wave 4 LOW #6
- SWR cache key normalization
- [ ] mutate 경로 추적 + ticker norm 일관화

---

## 🟦 P3 (Nice-to-have)

### 13. **Bundle size analysis + code split**
- [ ] `npm run build` → `.next/analyze` 가능하면 큰 chunk 확인
- [ ] dynamic import 추가 후보 검토

### 14. **Sentry error rate baseline**
- [ ] 출시 후 7일 Sentry 에러율 baseline 측정
- [ ] 일일 에러율 > 10 spike alert 설정

### 15. **performance 측정**
- [ ] Lighthouse score (mobile)
- [ ] Core Web Vitals (LCP / FID / CLS)
- [ ] /api/* p95 latency baseline

### 16. **i18n EN/KO 완성도**
- 현재 412 keys both sides 정확 일치 (verify-data Wave 1)
- 출시 후 신규 카피 추가 시 동기화 routine 유지

---

## 자동화 자율 작동 일정 (CEO 부재 시에도 작동)

| 시각 | 작업 | 비용 |
|---|---|---|
| 매일 03:00 KST | CAUS sim daily (Playwright, 7 scenario rotation) | 0원 (cron + local claude) |
| 매주 일 09:00 KST | finance_weekly_check (SSL pin 적용됨) | 0원 |
| 매주 일 08:00 KST | weekly_memo cron (SendGrid set 시) | $0 (SendGrid free 100/day) |
| 매월 1일 09:00 KST | monthly_brag + brag_card (Playwright Chromium) | $0 |
| 매일 08:00 KST | KPI dashboard email (Pro+ tier) | $0 (SendGrid) |

---

## 본 세션 마감 시점 main HEAD: `ab62e4c` (PR #400)

| 영역 | 상태 |
|---|---|
| backend pytest | 2080+ PASS (PR #400 +10 신규) |
| frontend vitest | 313/313 PASS |
| tsc | 0 errors |
| alembic single head | `034_flag_implausible_avg_cost` |
| 24 PR 누적 이 세션 | #377/#379 cleanup + 신규 22 |
| CAUS Phase 4 자동 fix | active, 2026-05-19 03:00 KST 첫 실 작동 |
| OPEN PR | 0건 |

---

## 본 가이드 작성 근거

- 본 세션 5개 bug-hunter wave + 2 verify-ux + 1 verify-security + 1 verify-data 결과 종합
- HANDOVER.md v43 final cycle 누적
- memory rules: feedback_no_extra_cost / feedback_no_false_reports / feedback_thorough_fixes / feedback_official_data_only / legal_compliance / project_biz_plan
- 본 checklist는 출시 전 살아있는 문서 — CEO가 진행 상황을 본 파일에 체크 표시하며 진행
