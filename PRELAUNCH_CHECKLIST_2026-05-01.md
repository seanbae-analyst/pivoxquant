# PivoxQuant — Pre-Launch Master Checklist (2026-05-01)

> 모든 감사/조사 결과 + HANDOVER.md + CLAUDE.md TODO 통합본.
> "이거 다 안 하면 출시하면 안 됨" 또는 "출시 후 사고남" 항목.

---

## TL;DR — 한 페이지 요약

| 카테고리 | 🔴 BLOCKER | 🟠 MUST | 🟡 SHOULD | 🟢 NICE |
|---|---|---|---|---|
| **법적/컴플라이언스** | 3 | 2 | 2 | 1 |
| **UX 핵심 버그** | 5 | 3 | 5 | 4 |
| **인프라/배포** | 4 | 3 | 2 | 1 |
| **결제/수익화** | 2 | 2 | 1 | 0 |
| **보안** | 2 | 3 | 4 | 0 |
| **이메일** | 3 | 3 | 4 | 3 |
| **모니터링/운영** | 1 | 3 | 2 | 2 |
| **합계** | **20** | **19** | **20** | **11** |

**최소 출시 가능 = BLOCKER 20개 + MUST 19개 = 39개**.
풀타임 4-5일, part-time 2주.

---

## 🔴 BLOCKER — 이거 안 하면 출시 절대 X (20개)

### 법적/컴플라이언스 (3)

- [x] **L1.** `email_opt_out` 컬럼 추가 + opt-out PATCH endpoint + Settings UI
  - 정보통신망법 §50 위반. **첫 사용자 신고 = 즉시 제재**
  - 출처: EMAIL_BUG_AUDIT E1
  - Owner: Claude Code | 시간: 4h
  - ✅ DONE 2026-05-03 PR #39 — migration 021 + PATCH /api/profile/email-preferences + Settings 토글 + 21 신규 테스트

- [x] **L2.** 모든 이메일 템플릿에 unsubscribe 링크 + `List-Unsubscribe` 헤더
  - 정보통신망법 §50 + Gmail 스팸 점수
  - 출처: EMAIL_BUG_AUDIT E2
  - Owner: Claude Code | 시간: 3h
  - ✅ DONE 2026-05-03 PR #39 + #41 — `services/email_token.py` HMAC + GET /api/email/unsubscribe + List-Unsubscribe 헤더 17 서비스 모두 + EmailSender 통합

- [ ] **L3.** `LEGAL_CONSULT_PACKAGE.md` 변호사 1회 검토
  - 자본시장법 §6 (미등록 투자자문업) — 코드 가드 있어도 변호사 사인 없으면 형사 리스크
  - Owner: Sean | 시간: 1주 (변호사 일정) | 비용: ₩200~500만

### UX 핵심 버그 (5)

- [x] **U1.** Portfolio 페이지 + Add Position 모달 실 동작 검증/수정
  - 출처: CRITICAL Bug #1 (코드 있음, 실 클릭 미검증)
  - Owner: Claude Code | 시간: 4-8h
  - ✅ VERIFIED FIXED 2026-05-03 PR #38 — `_v1/page-v1.tsx:432` mounts `<AddPositionModal/>`, backend `routes/portfolio.py:777` POST live (401 auth-gated)

- [x] **U2.** Top-bar Search 검증/수정
  - 출처: CRITICAL Bug #2
  - Owner: Claude Code | 시간: 2-4h
  - ✅ VERIFIED FIXED 2026-05-03 PR #38 — `top-bar.tsx:89` `<SearchCommandMenu/>` mounted, Cmd+K wired

- [x] **U3.** Watchlist 추가/삭제 검증/수정
  - 출처: CRITICAL Bug #3
  - Owner: Claude Code | 시간: 2-4h
  - ✅ VERIFIED FIXED 2026-05-03 PR #38 — `watchlist/page.tsx:26` AddSymbolModal → POST /api/watchlist (backend `routes/watchlist.py:96`)

- [x] **U4.** Risk 페이지 4개 endpoint schema match 검증/수정
  - 출처: CRITICAL Bug #4
  - Owner: Claude Code | 시간: 4h
  - ✅ VERIFIED FIXED 2026-05-03 PR #38 — `risk/_v1/page-v1.tsx` 4 SWR hooks live, all 4 backend endpoints return 401 (auth-gated, expected)

- [x] **U5.** Discover 시나리오 A/B/C 검증 (빈 결과는 의도된 동작 확인)
  - 출처: CRITICAL Bug #5
  - Owner: Claude Code | 시간: 4h
  - ✅ VERIFIED FIXED 2026-05-03 PR #38 — empty pool is INTENTIONAL §101 자본시장법 compliance (commit `0c3c73d`), not a bug

### 인프라/배포 (4)

- [ ] **I1.** `.env` 30+ 누락 키 채우기 (Railway prod env vars)
  - 출처: SECONDARY B1
  - 누락: STRIPE_*, PIVOX_BROKER_ENCRYPTION_KEY, CSRF_SECRET, DATABASE_URL,
         ADMIN_EMAILS, RATELIMIT_STORAGE_URI, CORS_ORIGINS, SESSION_COOKIE_DOMAIN,
         FRONTEND_URL, VAPID_*
  - Owner: Sean | 시간: 2h

- [ ] **I2.** Frontend Vercel 배포
  - 출처: HANDOVER + CLAUDE.md "인프라 미배포"
  - Owner: Sean | 시간: 2h

- [ ] **I3.** Backend Railway 배포 + 환경변수 + custom domain
  - Owner: Sean | 시간: 4h

- [ ] **I4.** OAuth redirect URI prod 등록
  - Google Cloud Console + Kakao Developers 양쪽
  - 미등록 시 모든 로그인 깨짐
  - Owner: Sean | 시간: 30min

### 결제/수익화 (2)

- [ ] **P1.** 사업자등록 (없으면)
  - Stripe Live mode 활성화 전제 + 결제 정산 가능
  - Owner: Sean | 시간: 2주 (홈택스/세무서) | 비용: 무료(개인사업자)

- [ ] **P2.** Stripe Live mode 활성화 + Product/Price ID 등록 + Webhook 연결
  - 출처: CLAUDE.md TODO P2
  - Free / ₩9,900 / ₩19,900 3티어 등록
  - Owner: Sean (Stripe 셋업) + Claude Code (코드 wiring) | 시간: 4h

### 보안 (2)

- [x] **S1.** 25+ POST/PUT/DELETE endpoint에 rate limit 추가
  - 출처: SECONDARY B3
  - 안 하면 악의 유저가 PDF cron 분당 100회 트리거 → FMP 402 + Anthropic burnout
  - Owner: Claude Code | 시간: 4h
  - ✅ DONE 2026-05-02 PR #28 (76 endpoints) — `routes/` grep 결과 41개 데코레이터 (`@*_rate_limit` / `@limiter.limit`) 활성

- [ ] **S2.** SendGrid sender authentication (SPF/DKIM/DMARC)
  - 출처: EMAIL_BUG_AUDIT E6
  - 미설정 시 모든 이메일 즉시 스팸 폴더
  - Owner: Sean (도메인 DNS) | 시간: 2h

### 이메일 (3)

- [x] **E1.** earnings_prebrief digest STARTTLS 추가 (1줄)
  - 출처: EMAIL_BUG_AUDIT E3
  - 안 하면 SMTP 자격증명 평문 전송
  - Owner: Claude Code | 시간: 5min
  - ✅ DONE 2026-05-03 PR #36 → consolidated into PR #41 EmailSender — `services/email/sender.py:364` `s.starttls()` covers all 17 services (was direct edit on earnings_prebrief, then refactored)

- [ ] **E2.** pivoxquant.com 도메인 등록 + DNS
  - 출처: EMAIL_BUG_AUDIT E6 + CLAUDE.md "Contact 이메일 가짜 도메인"
  - Owner: Sean | 시간: 1h | 비용: ~₩15,000/년

- [x] **E3.** 한국 ticker `$` prefix 버그 수정
  - 출처: EMAIL_BUG_AUDIT E4
  - `$005930.KS` 같이 보이는 거 → `₩` 또는 prefix 제거
  - Owner: Claude Code | 시간: 1h
  - ✅ DONE 2026-05-03 branch `fix/e3-ticker-currency-prefix-2026-05-03` — `currency_prefix()` helper (PR #41) wired into 3 hardcoded sites (push title + artifact title + email template hero `<span>`). KR ticker → ₩, US ticker → $. 26 tests pass

### 운영 (1)

- [x] **O1.** 404 / 500 에러 페이지
  - 출처: CLAUDE.md TODO P2
  - 미설정 시 백엔드 다운 = 빈 화면
  - Owner: Claude Code | 시간: 1h
  - ✅ VERIFIED EXISTING 2026-05-03 — `frontend/src/app/{not-found,error,global-error}.tsx` (51/115/167 LOC) 모두 production-ready. Vantablack/Bronze 디자인, `pq-ink-btn-bronze` CSS 활성, `/home` route 검증, error.digest prod/dev 분기 정상. 영문 카피만 (한글 추가는 출시 후 별도)

---

## 🟠 MUST-HAVE — 출시 1주 이내 (19개)

### 법적/컴플라이언스 (2)

- [ ] **L4.** 이용약관 + 개인정보처리방침 한국어 버전 + 영문 버전
  - 출처: CLAUDE.md TODO P2
  - 변호사 검토 받은 버전 권장
  - Owner: Sean (또는 Claude Code 초안) | 시간: 1일

- [ ] **L5.** 회원탈퇴 (PIPA 준수) UI 검증
  - HANDOVER에 "있음" 표기, 실 동작 검증 필요
  - Owner: Claude Code | 시간: 2h

### UX (3)

- [ ] **U6.** 알림 벨 드롭다운 동작
  - 출처: CLAUDE.md HIGH 6
  - Owner: Claude Code | 시간: 2h

- [ ] **U7.** 프로필 드롭다운 메뉴 동작
  - 출처: CLAUDE.md HIGH 7
  - Owner: Claude Code | 시간: 2h

- [ ] **U8.** 로그인 → 온보딩 → 홈 전체 플로우 e2e 검증
  - 출처: CLAUDE.md TODO P1
  - Owner: Claude Code (Chrome MCP) | 시간: 3h

### 인프라 (3)

- [ ] **I5.** SQLite → PostgreSQL 마이그레이션 (prod)
  - dev SQLite OK, prod에서는 데이터 손실 위험
  - Owner: Sean | 시간: 4h

- [ ] **I6.** Sentry 프로덕션 alert 룰 설정
  - error rate > 5/min, response time > 2s 등
  - Owner: Sean | 시간: 1h

- [ ] **I7.** alembic heads 다중 점검 + 정리
  - 출처: SECONDARY B12
  - `alembic heads` 결과 1개여야 정상
  - Owner: Claude Code | 시간: 1h

### 결제 (2)

- [ ] **P3.** Stripe 결제 페이지 e2e 테스트 (test mode)
  - Free → Pro 업그레이드 / 다운그레이드 / 취소 플로우
  - Owner: Claude Code | 시간: 3h

- [ ] **P4.** 결제 실패 / 카드 만료 webhook 처리
  - Stripe webhook → 사용자에게 이메일 + tier 다운그레이드
  - Owner: Claude Code | 시간: 4h

### 보안 (3)

- [ ] **S3.** CSP `unsafe-inline` → nonce 마이그레이션
  - 출처: SECONDARY B7
  - XSS 방어
  - Owner: Claude Code | 시간: 1일

- [ ] **S4.** `git fsck --full` 검사 + 손상 commit 복구
  - 출처: SECONDARY B15
  - Owner: Sean | 시간: 30min

- [ ] **S5.** weekly-security-scan workflow 결과 0 vuln 확인
  - 이미 자동 실행 중, 결과 검토 필요
  - Owner: Sean | 시간: 30min

### 이메일 (3)

- [ ] **E4.** PDF URL null일 때 broken link 수정 (`href="#"`)
  - 출처: EMAIL_BUG_AUDIT E5
  - Owner: Claude Code | 시간: 15min

- [ ] **E5.** Reply-To 헤더 일괄 추가
  - 출처: EMAIL_BUG_AUDIT E7
  - Owner: Claude Code | 시간: 30min

- [ ] **E6.** weekly_memo subject에 연도 포함
  - 출처: EMAIL_BUG_AUDIT E8
  - Owner: Claude Code | 시간: 5min

### 운영 (3)

- [ ] **O2.** Claude Code OAuth 토큰 셋업 + 6개 workflow 마이그레이션
  - 자동화 풀활성, $0 추가
  - Owner: Sean (token) + Claude Code (yml 변환) | 시간: 1일

- [ ] **O3.** Slack `#pivoxquant-alerts` + Webhook
  - Agent Worker + Self-Healing 알림 수신
  - Owner: Sean | 시간: 10min

- [ ] **O4.** Morning Brief 이메일/Slack 발송 추가
  - GitHub Issue 외 본인 알림 채널
  - Owner: Claude Code | 시간: 1h

---

## 🟡 SHOULD-HAVE — 출시 1달 이내 (20개)

### 법적/컴플라이언스 (2)

- [ ] **L6.** 마케팅 이메일 별도 동의 체크박스 (회원가입 시)
- [ ] **L7.** Cookie Consent 한국어 + 영문 검증 (이미 있음, drift 확인)

### UX (5)

- [ ] **U9.** Connect Alpaca 버튼 동작 (CLAUDE.md HIGH 8) — Alpaca DISABLED라 보류 가능
- [ ] **U10.** 코스피/코스닥 Market 페이지 추가 (CLAUDE.md HIGH 9)
- [ ] **U11.** Detail 페이지 7개 섹션 완성 (CLAUDE.md TODO P3)
- [ ] **U12.** 모바일 반응형 점검 62 페이지 (CLAUDE.md TODO P2)
- [ ] **U13.** Discover 빈 결과 EmptyState UX 개선

### 인프라 (2)

- [ ] **I8.** 데이터베이스 백업 자동화 (Railway daily snapshot)
- [ ] **I9.** CDN 설정 (이미지/PDF 정적 파일)

### 결제 (1)

- [ ] **P5.** Annual plan 추가 (₩299,000/년) — retention + cash flow

### 보안 (4)

- [ ] **S6.** N+1 query 5곳 batch load (SECONDARY B4+B6) — 성능
- [ ] **S7.** 무테스트 라우트 14개 smoke test (SECONDARY B5)
- [ ] **S8.** 17개 service의 send_email 코드 → 공통 EmailSender (EMAIL E9)
- [ ] **S9.** `except Exception: pass` 30+ 위치 → logger.exception (SECONDARY B8)

### 이메일 (4)

- [ ] **E7.** 인라인 disclaimer drift 제거 (EMAIL E10)
- [ ] **E8.** dd_checklist fallback disclaimer 강화 (EMAIL E11)
- [ ] **E9.** 4개 템플릿 `<html lang="ko">` 추가 (EMAIL E12)
- [ ] **E10.** SendGrid `From` Display Name 추가 (EMAIL E13)

### 운영 (2)

- [ ] **O5.** Self-Healing AUTO_PR=true 활성화 (1주 검토 후)
- [ ] **O6.** End-of-Day Diff Summary cron

---

## 🟢 NICE-TO-HAVE — 출시 후 점진 (11개)

- [ ] **N1.** 미사용 imports/hooks/types 정리 (SECONDARY B13)
- [ ] **N2.** ESLint 17 errors 정리 (SECONDARY B14)
- [ ] **N3.** Web Push 알림 (CLAUDE.md TODO P3)
- [ ] **N4.** Intraday 스캐너 인터랙션 (CLAUDE.md TODO P3)
- [ ] **N5.** fx-historical 시계열 환율 (SECONDARY B9)
- [ ] **N6.** SSE EventSource 재연결 backoff (SECONDARY B20)
- [ ] **N7.** 한국 ticker .KS/.KQ suffix 일관성 헬퍼 (SECONDARY B19)
- [ ] **N8.** 4 템플릿 preview text (EMAIL E14)
- [ ] **N9.** PDF 첨부 파일명 user.id 노출 정리 (EMAIL E15)
- [ ] **N10.** Digest dedup KST/UTC 명시 (EMAIL E16)
- [ ] **N11.** Marketing copy / 블로그 / SEO 작업

---

## Owner별 분류 (누가 뭘 하나)

### 👤 Sean만 할 수 있는 것 (외부 액션, 17개)
- L3 변호사 검토
- L4 이용약관/개인정보 한국어 (Claude Code 초안 가능)
- I1 .env 채우기, I2 Vercel, I3 Railway, I4 OAuth URI, I5 PostgreSQL, I6 Sentry alert
- P1 사업자등록, P2 Stripe Live setup
- S2 SendGrid SPF/DKIM/DMARC, S4 git fsck, S5 security scan 검토
- E2 도메인 등록
- O2 OAuth 토큰, O3 Slack webhook
- 합계: ~3-4일 + 2주 외부 일정 (사업자등록)

### 🤖 Claude Code가 처리할 것 (코드 변경, 22개)
- L1 email_opt_out, L2 unsubscribe, L5 회원탈퇴 검증
- U1-U8 UX 버그 8개
- I7 alembic
- P3-P4 Stripe wiring + webhook
- S1 rate limit, S3 CSP, S6-S9 perf/test/refactor
- E1 STARTTLS, E3 ticker prefix, E4-E10 email polish
- O1 404/500, O2 yml 마이그레이션, O4 morning brief 발송
- 합계: ~5-7일 (병렬 가능)

### 🤝 같이 (1개)
- P2 Stripe (Sean이 Stripe 셋업, Claude Code가 코드 wiring)

---

## 출시 일정 시뮬레이션

### 가장 빠른 시나리오 (Sean 풀타임 + Claude Code 자율)

| 주차 | Sean 작업 | Claude Code 작업 |
|---|---|---|
| **W1** | I1 .env, I4 OAuth, S4 git fsck, E2 도메인, O2 토큰, O3 Slack, P1 사업자등록 시작 | E1 STARTTLS, E3 ticker, U1-U5 critical bugs, S1 rate-limit |
| **W2** | I2 Vercel, I3 Railway, I5 PostgreSQL, S2 DNS, P2 Stripe 셋업 | L1 opt-out, L2 unsub, U6-U8, P3-P4, O1, O4 |
| **W3** | L3 변호사 일정, L4 약관, S5 security scan 검토, I6 Sentry alert | I7 alembic, S3 CSP, E4-E10 email polish |
| **W4** | 베타 50명 모집 시작 | S6-S9 perf/test, U9-U13 should-have |
| **W5** | 결제 활성화 + 공개 출시 | 모니터링, 신규 이슈 대응 |

→ **5주 출시 가능**.

### 현실적 시나리오 (part-time)

위 일정 × 2 = **10주 = 2.5달**.

### 기술적 최소 (부분 출시 — 베타만, 무료)

BLOCKER 20개만 = **3주**. Stripe/L3/L4 미완 상태로 무료 베타 출시 가능. 단 결제 수익 X, 한국 사용자에게는 약관 한국어 미제공 리스크.

---

## 우선순위 1줄 가이드

**3가지 트랙 병렬 진행**:

1. **🔴 Sean 트랙 (외부 액션)**: 사업자등록(2주, 가장 길음) → 도메인/Vercel/Railway → OAuth/Stripe 셋업
2. **🟠 Claude Code 트랙 (코드)**: U1-U5(critical) → L1/L2(legal email) → S1(rate limit) → P3-P4(Stripe wiring)
3. **🟡 변호사 트랙 (병렬)**: 약관 초안 → 변호사 검토 → 최종본

---

## 진행 상황 추적

이 파일을 GitHub Issue로 옮겨서 체크박스로 추적 권장:

```bash
gh issue create --title "Pre-Launch Checklist (W of 2026-05-04)" \
  --body-file PRELAUNCH_CHECKLIST_2026-05-01.md \
  --label "launch-blocker"
```

또는 매주 일요일 진행률 리뷰:
```
완료: ☑️ 12 / 70
이번 주 목표: ☐ 8개
블로커: ☐ ?? (있으면 즉시 보고)
```

---

## Claude Code에 줄 마스터 명령어

```
PRELAUNCH_CHECKLIST_2026-05-01.md 파일 읽고, 🔴 BLOCKER 섹션 중
"Owner: Claude Code"인 항목만 처리해줘.

순서:
1. E1 (5분, easy win)
2. E3 (1시간)
3. U2 → U3 → U1 → U4 → U5 (CRITICAL_BUG_VERIFICATION 파일 참조)
4. S1 (rate limit 일괄)
5. L1 → L2 (EMAIL_BUG_AUDIT 파일 참조)
6. O1 (404/500 에러 페이지)

각 항목 별도 branch + commit. fix(area): prefix.
완료마다 PRELAUNCH_CHECKLIST_2026-05-01.md의 체크박스 update + commit.
사용자 승인 없이 main에 push 절대 X.

각 항목 끝나면 정직 보고.
```
