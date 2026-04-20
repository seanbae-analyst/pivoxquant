# PivoxQuant — 인수인계서 (2026-04-20 세션 종료)

**세션**: ~16시간 연속 작업
**커밋**: 28+ (`dc7585a` ~ `4a18adb`)
**배포**: Railway + Vercel 자동 반영 (최신 `4a18adb`)
**상태**: 백엔드 Active / 프론트 Active / `/api/health` 200 OK

---

## 🎯 이 세션 Key Achievements

### 1. 🔐 법적 5축 전수 청소
- **브랜드** "Advisor/어드바이저" → "Research Tool" rename (8개 파일)
- **데이터 소스** 100% 합법화 (yfinance/pyKRX/Naver모바일/Google News/Yahoo RSS 제거)
- **legal_filter** 런타임 scrubber: 12 → 42 regex 패턴
- **AI 엔드포인트** `scrub_and_jsonify` 강제
- **/risk 페이지** triggerAction 전수 중립화
- **회원가입** 법적 동의 4개 체크박스 + **결제** 3개 체크박스
- **privacy.md** 8개 수탁자 위탁 매트릭스 + PIPA §28의8 국외이전
- **terms.md** 유사투자자문 등록번호 placeholder

### 2. 🏦 KIS 단일 브로커 (마이데이터 회피)
- Kiwoom / Alpaca **유저 브로커 연결** 완전 제거
- KIS **해외주식 잔고** 조회 추가 → 한국 + 미국 단일 연결
- Alpaca Market Data는 **공용 시세** 전용 (유저 연결 아님)

### 3. 📊 Premium Artifact 17개 전부 구현
**Pro (7)**: Morning Brief Plus / Weekly Memo / Earnings Pre-Brief / AI Suite 8종 / DD Checklist / Burn Rate / Credit Rating  
**Premium (10)**: Monthly Finance / Risk Board Deck / Quarterly Self Report / Year-End Letter / Capital Allocation / Insider Mirror / Portfolio Segment / Dividend Income / Self Audit (흡수) / Monthly Brag Card

### 4. ⭐ S&P 500 백테스트 (마케팅 코어)
- CAGR 15~21% / Sharpe 0.94 / Alpha +9.66%
- **2022 베어장 +2% 이상 수익** — 킬러 훅
- `docs/BACKTEST_RESULTS.md` + 4개 PNG 차트

### 5. 🎨 CEO Admin Preview 페이지 신규
- **URL**: https://pivoxquant.com/admin/preview
- 17개 Artifact HTML/PDF/Email 브라우저 확인
- `ADMIN_EMAILS=seanbae1521@gmail.com` 제한

### 6. 📄 법적 문서 초안
- `frontend/public/terms.md`
- `frontend/public/privacy.md`
- `services/artifacts/templates/_disclaimer.html`

---

## 🚀 CEO "외부작업" 한 번에 처리 체크리스트

### 🔴 유료 런칭 전 필수

#### A. 정부/규제 등록
- [ ] 사업자 등록 (홈택스, 15분, 무료)
- [ ] 통신판매업 신고 (홈택스 간이신고)
- [ ] 유사투자자문업 신고 (금감원)
  - 완료 후: Railway env `SIMILAR_ADVISORY_LICENSE_NUMBER=<번호>` 설정
  - → 모든 Artifact 에 자동 삽입 (이미 구현)

#### B. API 키 발급 (3개)
- [ ] **Naver Developers** (필수 — 없으면 한국 뉴스 안 뜸)
  - https://developers.naver.com/apps/#/register
  - Search API 체크
  - Railway env: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`
- [ ] DART API (선택 — Insider Mirror 한국)
  - https://opendart.fss.or.kr → `DART_API_KEY`
- [ ] Anthropic Commercial ZDR (선택, 프리미엄)

#### C. Railway 환경변수 확인 필수
```
SECRET_KEY, CSRF_SECRET, FLASK_ENV=production ✅
CORS_ORIGINS, SESSION_COOKIE_DOMAIN ✅
KIS_APP_KEY, KIS_APP_SECRET, KIS_USE_REAL=1 ✅
ALPACA_API_KEY, ALPACA_SECRET_KEY ✅ (시세용)
FMP_API_KEY ✅
ADMIN_EMAILS=seanbae1521@gmail.com ✅
DEV_PREMIUM_EMAILS=seanbae1521@gmail.com ✅
RUN_SCHEDULER=1 ⚠️ 확인 필수 (없으면 자동 발송 X)
NAVER_CLIENT_ID, NAVER_CLIENT_SECRET ❌ 발급 후 설정
SIMILAR_ADVISORY_LICENSE_NUMBER ❌ 등록 후 설정
DART_API_KEY ❌ 선택
```

#### D. 결제 (Stripe)
- [ ] Stripe Product 2개: Pro ₩9,900 / Premium ₩19,900
- [ ] Railway env: `STRIPE_PRICE_PRO`, `STRIPE_PRICE_PREMIUM`, `STRIPE_WEBHOOK_SECRET`
- [ ] Stripe DPA 자동 체결 확인

#### E. 이메일 발송 (Gmail SMTP)
- [ ] Google 앱비번 발급 (myaccount.google.com/apppasswords)
- [ ] Railway env: `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER`, `SMTP_PASS`
- [ ] 본인 계정으로 Weekly Memo 실수신 테스트

#### F. 변호사 검토 (300~700만원 예산)
- 금융규제 전문 — 법무법인 세종/광장/태평양 핀테크팀 추천
- 검토 대상:
  - terms.md + privacy.md 최종본
  - Capital Allocation "What-if" 자문업 경계
  - Year-End Letter 공유 기능 시 §57
  - AI Coaching 명명 자문업 경계

---

## ⚠️ 다음 세션 최우선 P0 (미완료 2개)

### 1. risk_defense 엔진 메시지 scrub decorator
- `routes/decorators.py` 신규 `legal_scrub_response` 
- `routes/quant.py` 의 risk/defense 엔드포인트 적용
- 이번 세션 BLOCKED (권한 미확정) → 다음 세션 재시도

### 2. PDF 템플릿 Goldman Sachs CFO 수준 리디자인
- 공통 `_base_report.css` + `_report_base.html`
- 17개 템플릿 전체 재작성 (Vantablack + Ivory, Source Serif 4)
- 샘플 PDF 생성 (`samples/*.pdf`)
- 이번 세션 불완전 → 다음 세션 재시도

---

## 📁 주요 파일 위치

### 법무
- `services/legal_filter.py` (42 patterns)
- `services/artifacts/templates/_disclaimer.html`
- `frontend/public/terms.md` + `privacy.md`

### Admin Preview (신규)
- `/admin/preview` — CEO 전용
- `routes/admin_preview.py`
- `services/artifacts/sample_data.py`
- `frontend/src/app/admin/preview/page.tsx`

### 백테스트
- `docs/BACKTEST_RESULTS.md`
- `scripts/run_benchmark_backtest.py`
- `tests/backtest_results/*.png`

### Artifact 서비스 (17개)
`services/artifacts/*_service.py` 파일들

### 디자인 가이드
- `docs/DESIGN_BRIEF_FOR_CLAUDE.md`
- `docs/LANDING_PAGE_CONTENT.md`

### 메모리 (세션 간 지식)
- `/Users/seanbae/.claude/projects/-Users-seanbae-Desktop---/memory/`
  - `legal_full_audit_final.md` — 52개 항목 감사
  - `tier_structure_3tier.md` — 최종 티어 구조
  - `product_concept_cfo.md` — User as CFO 컨셉
  - `project_oauth_resolved.md` — OAuth 이슈 해결 기록
  - `competitive_analysis_20_artifacts.md` — 경쟁력 분석
  - `strategy_paid_tier_cfo_ideas.md` — 10개 Artifact 아이디어
  - `project_spec_legal_safe.md` — 법적 안전 재설계 스펙

---

## 🎯 CEO 다음 세션 시작 프롬프트

```
HANDOVER.md 읽고 이어서 시작.

외부 작업 완료 상태:
- 사업자 등록: [완료/미완료]
- 통신판매업 신고: [완료/미완료]
- 유사투자자문업 신고: [완료/미완료]
- Naver API 키: [발급/미발급]
- SMTP 설정: [완료/미완료]
- 변호사 검토 의뢰: [완료/미완료]

우선 진행:
1. 미완 P0 (risk_defense scrub + PDF Goldman 디자인)
2. 프론트 Claude Design 적용
3. 베타 테스터 모집
```

---

## 📊 최종 서비스 상태

### ✅ 완료
- OAuth 로그인 (Kakao + Google)
- KIS 단일 브로커 연동 (한국 + 미국)
- 17개 Premium Artifact 생성 + 자동 발송 스케줄
- 3티어 (Free / Pro ₩9,900 / Premium ₩19,900)
- legal_filter 런타임 보호
- S&P 500 백테스트 + 마케팅 자료
- Admin Preview 페이지
- 법적 동의 UI + 이용약관/개인정보방침 초안

### ⏳ 대기 (CEO 외부작업)
- 사업자/통신판매/유사투자자문 등록
- API 키 발급 (Naver, DART)
- Railway env 설정
- Stripe 결제
- 변호사 검토
- SMTP 실제 발송

### 🔄 다음 세션
- risk_defense scrub decorator
- PDF Goldman CFO 디자인
- Frontend Claude Design 코드 적용

---

**작성**: 2026-04-20 (세션 종료)
**다음 세션**: 외부 작업 완료 후 이어서
