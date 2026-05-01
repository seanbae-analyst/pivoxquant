# 다음 세션 TODO — 2026-05-01 종료 시점

## 이번 세션 종료 시 상태 (요약)

**11 commits 누적** (`f743568 → d6feb11`). main HEAD `d6feb11`. pytest 1305/0 fail.

### 이번 세션 해결 완료
1. ✅ earnings_prebrief 종목당 1개 이메일 → digest mode (1유저 1통)
2. ✅ dd_checklist 양식 전면 리디자인
3. ✅ 13 PDF cover title 시적 → data-driven 헤드라인
4. ✅ 종목명 우선 표시 (티커 작게) — 17 PDF + 3 email
5. ✅ 법적고지 페이지 진짜 맨 아래 (`@page` running disclaimer)
6. ✅ 페이지 짤림 fix (`page-break-inside: avoid` on cards/tables/headings)
7. ✅ 오른쪽 치우침 fix (`.pq-pdf-page` width/padding 제거)
8. ✅ Naver Search API 401 해결 (secret 재발급)
9. ✅ Pretendard 폰트 production 5 variants 등록

---

## 🔴 P0 — 다음 세션 즉시 (CEO 액션)

### 1. earnings_prebrief digest 실 동작 검증 (배포 후)
```bash
# 다음 cron 시점 (15분 간격) 형님 메일함 확인
# 보유 종목 N개 같은 주 실적 → 1통의 digest 이메일이 와야 함
# Subject 형식: "[Pre-Brief] 오늘 N개 종목 실적 발표"
```

만약 안 오면:
- Railway logs 확인: `railway logs --deployment | grep "scan_digest"`
- 매칭 종목 있는지 확인 (in_window > 0)
- SendGrid 로그 확인

### 2. v10 PDF 17개 시각 검증 (CEO 직접)
```bash
open /tmp/pq_weasy/v10_*.pdf
```
체크포인트:
- 가운데 정렬 OK인지 (오른쪽 치우침 없음)
- 디스클레이머 매 페이지 진짜 맨 아래 있는지
- 페이지 넘어갈 때 컨텐츠 짤림 없는지
- Cover headline 데이터 driven으로 보이는지
- 종목명 우선 / 티커 작게 표시되는지

### 3. CEO 외부 액션 (출시 차단)
- [ ] Anthropic API credit 충전 (5분, console.anthropic.com)
- [ ] GitHub Actions billing 한도 $5 (5분, github.com/settings/billing)
- [ ] 변호사 자문 일정 (50~80만원, §101 면제 + 父 명의 사업자 리스크)
- [ ] 사업자등록 (본인 명의 권장, 변호사 자문 후)

---

## 🟠 P1 — 다음 세션 작업

### 4. 추가 PDF/이메일 디테일 다듬기 (피드백 받아서)
v10 PDF 보고 구체적 피드백 줘 — 어느 부분이 더 구린지:
- 색상? (Bronze accent / Vantablack 톤)
- 폰트 사이즈? (현재 Source Serif 28-34px headline)
- 간격? (KPI row, table, section title 사이)
- 정보 부족? (어떤 정보 더 필요한지)
- 레이아웃? (1열 / 2열 / 카드 그리드)

### 5. earnings_prebrief digest 단위 테스트 추가
새 메서드 5개 (`render_digest_email_html`, `_send_digest_email`,
`_already_sent_digest`, `_persist_digest_marker`, `run_scan_digest`)에
대한 단위 테스트 — 회귀 방지. 약 20-30 lines.

### 6. Naver API key 환경 검증
- [ ] Production 배포 후 `/api/lookup/005930.KS` 호출 → 한글 뉴스 나오는지
- [ ] daily-legal-scan, weekly-security-scan에서 401 사라졌는지

### 7. OAuth redirect URI 등록 (사업자등록 후)
- [ ] Google Cloud Console: `https://pivoxquant.com/api/auth/google/callback`
- [ ] Kakao Developers: `https://pivoxquant.com/api/auth/kakao/callback`

---

## 🟡 P2 — 다음 다음 세션

### 8. Stripe 결제 연결 (사업자등록 후)
- [ ] Stripe 계정 사업자 인증
- [ ] 4종 키 발급 + Railway env (`STRIPE_PUBLIC_KEY` / `_SECRET_KEY` / `_WEBHOOK_SECRET` / `_PRICE_ID_*`)
- [ ] 3-tier Product 생성 (Free / Pro 9,900 / Premium 19,900)
- [ ] Test → Live mode 검증

### 9. 이용약관 / 개인정보처리방침 한국어 작성
- [ ] `frontend/src/app/terms/page.tsx` 한국어 verbatim (변호사 검토)
- [ ] `frontend/src/app/privacy/page.tsx` PIPA 준수 (CISO/책임자 정보)

### 10. SendGrid Sender 이름 변경
- [ ] "StockPilot" → "PivoxQuant" (sendgrid.com Sender Authentication)

### 11. 사업자 대표 이메일 활성화
- [ ] `contact@pivoxquant.com` 가비아 또는 Google Workspace
- [ ] 4곳에 흩어진 가짜 도메인 통일

### 12. 모바일 반응형 검증 (62 페이지)
- [ ] iPhone Safari + Android Chrome
- [ ] Watchlist / Portfolio modal / 알림벨 / 프로필 드롭다운 클릭

---

## 🟢 P3 — 출시 후

### 13. 알려진 미완 기능 (HANDOVER 참조)
- [ ] OAuth 실 로그인 검증 (BUG-OAUTH-001 잔존 가능)
- [ ] Frontend ESLint 17 errors (set-state-in-effect 패턴)
- [ ] Detail 페이지 7개 섹션 완성
- [ ] 코스피/코스닥 데이터 Market 페이지에 추가

### 14. 운영 모니터링
- [ ] Sentry 알림 채널 (Slack/이메일)
- [ ] Anthropic 잔액 자동 알림
- [ ] Beta 비밀번호 rotation 정책
- [ ] 도메인 SSL 자동 갱신 확인

---

## 🟢 v10 PDF 시각 검증 항목 (CEO)

**전부 확인 후 OK 사인**:
- [ ] weekly_memo (Free, 일요일 발송) — Sunday 09:00 KST
- [ ] dd_checklist (Pro, 매일 08:05 KST) — 리디자인 확인
- [ ] earnings_prebrief — digest mode (다음 매칭 시점)
- [ ] brag_card (Free, 매월 1일 09:00 KST) — viral
- [ ] burn_rate (Pro, 매월 1일 09:00 KST)
- [ ] dividend_income (Pro, 매월)
- [ ] portfolio_segment (Pro, 분기)
- [ ] insider_mirror (Pro, 매주 월요일 09:00 KST)
- [ ] credit_rating (Premium, 매월 15일)
- [ ] kpi_dashboard (Premium, Morning Brief 흡수)
- [ ] monthly_finance (Premium, 매월 1일 11:00 KST)
- [ ] capital_allocation (Premium, on-demand)
- [ ] risk_board (Premium, 매월 15일 + VIX spike)
- [ ] self_audit (Quarterly Self Report 흡수)
- [ ] sp500_backtest (admin-debug)
- [ ] quarterly_self_report (Premium, 분기 +7일)
- [ ] year_end_letter (Premium, 12/31 10:00 KST)

---

## 다음 세션 시작 프롬프트 추천

```
HANDOVER v17 + docs/NEXT_SESSION_TODO.md 읽고 이어서.

이번 라운드 11 commits 정리됨:
- earnings_prebrief digest mode (1유저 1통)
- dd_checklist 전면 리디자인
- 17 PDF cover headline data-driven
- @page running disclaimer
- 페이지 짤림 / 오른쪽 치우침 fix
- Naver API 정상화
- Pretendard production 적용

다음 우선순위:
1. v10 PDF 17개 시각 검증 (CEO)
2. earnings_prebrief digest 실 동작 확인 (다음 cron 시점)
3. CEO 외부 액션 (Anthropic / GitHub billing / 변호사 / 사업자등록)
4. 추가 PDF 디테일 피드백 받기
```

---

**END OF DOCUMENT** — 2026-05-01
