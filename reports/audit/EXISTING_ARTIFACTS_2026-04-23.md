# PivoxQuant Artifact Audit — 2026-04-23

조사 기준 파일:
- `/routes/artifacts.py` (2511줄, 16개 섹션)
- `/services/artifacts/` (15개 서비스 파일 + 22개 템플릿)
- `/models/artifact.py` (ARTIFACT_TYPES 집합)
- `/app.py` scheduler 등록부 (lines 864–1092)
- `/frontend/src/app/(dashboard)/reports/page.tsx` (CATALOG 18개 항목)

---

## A. PDF/HTML 리포트 전수 표 (실제 코드 기반)

> HANDOVER.md "18 리포트"는 reports/page.tsx CATALOG 배열 18개를 말한다.
> 백엔드 ARTIFACT_TYPES는 22개 슬러그를 포함하지만 일부는 legacy alias이다.

| # | 이름 (UI 표시) | 백엔드 타입 슬러그 | 서비스 파일 | HTML 템플릿 | JTBD (1줄) | 데이터 소스 | 트리거 | 이메일 배송 | Tier | 완성도 | UI 진입 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Weekly Memo | `weekly_memo` | `weekly_memo_service.py` | `weekly_memo.html` + `weekly_memo_email.html` | "이번 주 내 포트 성과 + 퀀트 시그널 요약을 McKinsey 스타일 PDF로 받는다" | engine.py, FMP, Alpaca | APScheduler 일요일 08:00 KST | 배송 (SendGrid, PDF 첨부) | Pro+ | 코드+DB+UI 연동, production 배송 중 | `/reports` |
| 2 | Morning Brief Plus | `morning_brief` | `morning_brief_service.py` | `morning_brief_plus.html` | "매일 아침 오늘 장 브리핑 + KPI 카드를 이메일로 받는다" | FMP, 포트, kpi_dashboard_service | APScheduler 매일 06:00 KST | 배송 (SendGrid, HTML 이메일) | Free+ | 코드+DB+UI 연동, production 배송 중 | `/morning-brief` + `/reports` |
| 3 | Brag Card | `brag_card` / `monthly_brag` | `brag_card_service.py` + `monthly_brag_service.py` | `brag_card.html` + `brag_card_email.html` | "월간 수익률을 9:16 카드로 SNS 공유한다" | 포트폴리오 수익 데이터 | APScheduler 매월 1일 09:00 KST | 배송 (SendGrid) + 공개 share 링크 | Free+ | 코드+DB+UI 연동, production 배송 중 | `/reports` + `/api/artifacts/brag-card/share/<token>` |
| 4 | Earnings Pre-Brief | `earnings_prebrief` | `earnings_prebrief_service.py` | `earnings_prebrief.html` + `earnings_prebrief_email.html` | "보유 종목 실적 발표 30분 전 알림 브리핑을 받는다" | FMP earnings calendar, SEC | APScheduler 15분 간격 스캔 | 배송 (SendGrid, PDF 첨부) | Pro+ | 코드+DB+UI 연동, production 배송 중 | `/reports` |
| 5 | Risk Board | `risk_board` | `risk_board_service.py` | `risk_board.html` | "월간 + VIX 급등 시 리스크 보드 미팅 덱을 받는다" | FMP, VIX, 포트폴리오, risk_defense.py | APScheduler 매월 15일 09:30 KST + VIX>25 hourly 감지 | 배송 (SendGrid, PDF 첨부) | Premium | 코드+DB+UI 연동, production 배송 중 | `/reports` |
| 6 | Quarterly Self Report | `quarterly_self_report` | `quarterly_self_report_service.py` | `quarterly_self_report.html` | "분기 종료 후 내 투자 결정 품질을 Self 10-K 형식으로 검토한다" | TradeHistory, SelfAuditService 내장 | APScheduler 1/7, 4/7, 7/7, 10/7 10:00 KST | 배송 (SendGrid, PDF 첨부) | Premium | 코드+DB+UI 연동, production 배송 중 | `/reports` |
| 7 | Self Audit | `self_audit` | `self_audit_service.py` | `self_audit.html` | "내 매매 결정의 품질(감정 편향, 손절 실패율)을 4p PDF로 수령한다" | TradeHistory | DEPRECATED — Quarterly Self Report에 흡수됨; `/api/artifacts/self-audit/*` 엔드포인트는 유지 | 배송 코드 있음 (SendGrid) | Premium | 코드만 있음 (스케줄러 비활성화) | `/reports` (on-demand로만) |
| 8 | DD Checklist | `dd_checklist` | `dd_checklist_service.py` | `dd_checklist.html` | "포지션 진입 T+3일 후 DD 체크리스트 이메일을 받는다" | positions, PositionDDCheck 모델 | APScheduler 매일 08:05 KST | 배송 (SendGrid, HTML 이메일) | Pro+ | 코드+DB+UI 연동, production 배송 중 | `/reports` |
| 9 | Dividend Income | `dividend_income` | `dividend_income_service.py` | `dividend_income.html` | "월간 배당금 수령 명세서 3p PDF를 받는다" | FMP 배당 데이터, 포트폴리오 | APScheduler 매월 1일 10:00 KST | 배송 (SendGrid, PDF 첨부) | Premium | 코드+DB+UI 연동, production 배송 중 | `/reports` |
| 10 | Insider Mirror | `insider_mirror` | `insider_mirror_service.py` | `insider_mirror.html` | "보유 종목 임원 내부자 거래를 주간 3p PDF로 받는다" | SEC Form 4, DART (DART_API_KEY 미설정 시 US만) | APScheduler 매주 월요일 09:00 KST | 배송 (SendGrid, PDF 첨부) | Premium | 코드+DB+UI 연동, production 배송 중 | `/reports` |
| 11 | S&P 500 Backtest | `sp500_backtest` (프론트 only) | 없음 (백엔드 artifact 없음) | `sp500_backtest.html` (템플릿만 존재) | "내 포트폴리오 vs S&P 500 백테스트 결과를 본다" | backtester.py (별도 /api/backtest/<ticker>) | 없음 (백엔드 artifact 서비스 미구현) | 없음 | Pro (UI 표시) | 코드만 있음 (HTML 템플릿 + sample_data.py만; artifact 서비스 없음) | `/reports` (sample PDF만 노출) |
| 12 | Portfolio Segment | `portfolio_segment` | `portfolio_segment_service.py` | `portfolio_segment.html` | "분기별 포트폴리오 섹터/스타일 세그먼트 분석 4p PDF를 받는다" | FMP, 포트폴리오 | APScheduler 1/7, 4/7, 7/7, 10/7 10:00 KST | 배송 (SendGrid, PDF 첨부) | Premium | 코드+DB+UI 연동, production 배송 중 | `/reports` |
| 13 | Capital Allocation | `capital_allocation` | `capital_allocation_service.py` | `capital_allocation.html` | "신규 자금 투입 시 What-If 자본 배분 시나리오 PDF를 생성한다" | 포트폴리오, FMP | 온디맨드 POST + 분기 이메일 리마인더 (1/14, 4/14, 7/14, 10/14 09:00 KST) | 리마인더 이메일 배송 (actual PDF는 온디맨드) | Premium | 코드+DB+UI 연동, production 배송 중 | `/reports` |
| 14 | Credit Rating | `credit_rating` | `credit_rating_service.py` | `credit_rating.html` | "포트폴리오의 자체 신용등급 평가 이메일을 월간으로 받는다" | 포트폴리오, 리스크 지표 | APScheduler 매월 15일 09:00 KST | 배송 (SendGrid, HTML 이메일) | Pro+ | 코드+DB+UI 연동, production 배송 중 | `/reports` |
| 15 | Burn Rate | `burn_rate` | `burn_rate_service.py` | `burn_rate.html` | "이전 달 거래 비용 + 예상 세금을 번레이트 PDF로 받는다" | TradeHistory, 거래비용 | APScheduler 매월 1일 09:00 KST | 배송 (SendGrid, PDF 첨부) | Pro+ | 코드+DB+UI 연동, production 배송 중 | `/reports` |
| 16 | Monthly Finance | `monthly_finance` | `monthly_finance_service.py` | `monthly_finance.html` | "월간 현금 런웨이 + 비용/세금 종합 6p PDF를 받는다" | 포트폴리오, TradeHistory, FMP | APScheduler 매월 1일 11:00 KST | 배송 (SendGrid, PDF 첨부) | Premium | 코드+DB+UI 연동, production 배송 중 | `/reports` |
| 17 | KPI Dashboard | `kpi_dashboard` | `kpi_dashboard_service.py` | `kpi_dashboard.html` | "5개 핵심 KPI를 일간 이메일 상단에 포함해 받는다" | 포트폴리오, FMP | DISABLED — Morning Brief에 통합됨; admin trigger 전용 엔드포인트만 남음 | Morning Brief 이메일 상단에 포함 | Premium (UI 표시) | 코드만 있음 (스케줄러 비활성화) | `/reports` (Morning Brief로 대체) |
| 18 | Year-End Letter | `year_end_letter` | `year_end_letter_service.py` | `year_end_letter.html` | "연말 Buffett 톤 6p 투자 서한 PDF를 받는다" | TradeHistory, 포트폴리오 | APScheduler 12/31 10:00 KST | 배송 (SendGrid, PDF 첨부) | Premium | 코드+DB+UI 연동, production 배송 중 | `/reports` |

### 주석

- **실제 배송 중인 항목**: 1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 13, 14, 15, 16, 18 — 15종
- **코드만 있음 (스케줄러 비활성화 또는 서비스 미구현)**: 7 (Self Audit — deprecated), 11 (sp500_backtest — artifact 서비스 없음), 17 (KPI Dashboard — Morning Brief 통합)
- **WeasyPrint 의존**: `requirements.txt`에 `weasyprint>=62.0` 포함. 로컬 native libs(pango, cairo) 필요. Railway 서버 환경에서 작동 여부는 이 조사로 확인 불가.
- **SendGrid API Key**: `.env` line 13에 `SENDGRID_API_KEY=SG.GL_x...` 실제 키 존재.

---

## B. Artifact 기능 매트릭스 (PDF 외 산출물 포함)

| 유형 | 이름 | 핵심 파일 | 완성도 | 유저 접근 경로 |
|---|---|---|---|---|
| PNG 이미지 | Brag Card (9:16 소셜 카드) | `brag_card_service.py`, `brag_card.html` | 코드+DB+UI 연동 | `/api/artifacts/brag-card/share/<token>` (공개, 비인증) |
| 공유 URL | Portfolio Share Link | `routes/share.py`, `models/portfolio_share.py` | 코드+DB+UI 연동 | POST `/api/shares` → GET `/api/shares/<token>` |
| AI 텍스트 | SWOT Analysis | `routes/ai.py:43` | 코드만 있음 | POST `/api/ai/swot` |
| AI 텍스트 | Competitor Analysis | `routes/ai.py:57` | 코드만 있음 | POST `/api/ai/competitor` |
| AI 텍스트 | Sector Trend | `routes/ai.py:81` | 코드만 있음 | POST `/api/ai/sector-trend` |
| AI 텍스트 | AI Chat | `routes/ai.py:104` | 코드만 있음 | POST `/api/ai/chat` |
| AI 텍스트 | Coaching | `routes/ai.py:175` | 코드만 있음 | POST `/api/ai/coaching` |
| AI 텍스트 | Earnings Call Tone | `routes/ai.py:216` | 코드만 있음 | GET/POST `/api/ai/earnings-tone/<ticker>` |
| AI 텍스트 | Risk Summary | `routes/ai.py:330` | 코드만 있음 | POST `/api/ai/risk-summary` |
| HTML 이메일 | Morning Brief Plus | `services/morning_brief_service.py` | 코드+DB+UI 연동, 배송 중 | 이메일 인박스 + GET `/api/morning-brief/today` |
| HTML 이메일 | DD Checklist 이메일 | `dd_checklist_service.py` | 코드+DB+UI 연동, 배송 중 | 이메일 인박스 |
| HTML 이메일 | Credit Rating 이메일 | `credit_rating_service.py` | 코드+DB+UI 연동, 배송 중 | 이메일 인박스 |
| 공개 계산기 | Counterfactual (What-if) | `routes/counterfactual.py` | 코드만 있음 (viral 의도, no-auth) | GET `/api/simulate/counterfactual?ticker=&amount=&from=` |
| 이메일 알림 | Price Alert | `services/alert_service.py`, `routes/alerts.py` | 코드+DB+UI 연동 | 이메일 + GET `/api/alerts` |
| 웹 푸시 | Push Notification | `routes/push.py`, `services/push_service.py` | 코드만 있음 (구독 모델만) | 브라우저 푸시 |

---

## C. Ritual(의식) 기능 — 정시 배송 현황

| ID | 스케줄 | 산출물 | 배송 시각 (KST) | 배송 채널 | 유저 설정 가능? |
|---|---|---|---|---|---|
| refresh | 3분 간격 | 포트 시그널 캐시 갱신 | 상시 | 없음 (내부) | 불가 |
| morning_brief_daily | 매일 | Morning Brief Plus 이메일 | 06:00 | SendGrid | 불가 |
| weekly_memo_sunday | 매주 일요일 | Weekly Memo PDF 이메일 | 08:00 | SendGrid + PDF | 불가 |
| brag_card_monthly | 매월 1일 | Brag Card PNG 이메일 | 09:00 | SendGrid | 불가 |
| earnings_prebrief_scan | 15분 간격 | Earnings Pre-Brief (조건부) | 실적 발표 ~30분 전 | SendGrid + PDF | 불가 |
| quarterly_self_report | 분기 (1/7, 4/7, 7/7, 10/7) | Quarterly Self Report PDF | 10:00 | SendGrid + PDF | 불가 |
| year_end_letter_annual | 12/31 | Year-End Letter PDF | 10:00 | SendGrid + PDF | 불가 |
| dd_checklist_daily | 매일 | DD Checklist 이메일 (T+3 조건부) | 08:05 | SendGrid | 불가 |
| burn_rate_monthly | 매월 1일 | Burn Rate PDF | 09:00 | SendGrid + PDF | 불가 |
| credit_rating_monthly | 매월 15일 | Credit Rating 이메일 | 09:00 | SendGrid | 불가 |
| dividend_income_monthly | 매월 1일 | Dividend Income PDF | 10:00 | SendGrid + PDF | 불가 |
| monthly_finance_monthly | 매월 1일 | Monthly Finance PDF | 11:00 | SendGrid + PDF | 불가 |
| risk_board_monthly | 매월 15일 | Risk Board PDF | 09:30 | SendGrid + PDF | 불가 |
| vix_spike_monitor | 매시 30분 | Risk Board PDF (VIX>25 조건부) | 조건부 | SendGrid + PDF | 불가 |
| portfolio_segment_quarterly | 분기 (1/7, 4/7, 7/7, 10/7) | Portfolio Segment PDF | 10:00 | SendGrid + PDF | 불가 |
| capital_allocation_quarterly_reminder | 분기 (1/14, 4/14, 7/14, 10/14) | 리마인더 이메일만 | 09:00 | SendGrid | 불가 |
| insider_mirror_weekly | 매주 월요일 | Insider Mirror PDF | 09:00 | SendGrid + PDF | 불가 |
| fx_rate_refresh | 1분 간격 | FX rate 캐시 | 상시 | 없음 (내부) | 불가 |
| GitHub Actions: api-health | 7,23,37,53분 | Railway /api/health 체크 | 상시 | GitHub Actions 로그 | 불가 |
| GitHub Actions: ci | push/PR | Python + Node 테스트 | 커밋 트리거 | GitHub Actions | 불가 |

---

## D. Accumulation(축적) 기능

### 현재 축적되는 것

| 데이터 | 테이블 | 필드 | 메모/코멘트 기능 |
|---|---|---|---|
| 포지션 | `positions` | `thesis`, `thesis_status`, `thesis_reason`, `thesis_last_checked` | Thesis Tracker 있음 (500자 텍스트) |
| 매매 이력 | `trade_history` | ticker, action, shares, price, pnl, pnl_pct, traded_at | 코멘트 필드 없음 |
| 아티팩트 | `artifacts` | type, title, data_json, pdf_path, sent_at, opened_at | 유저 메모 없음 |
| 알림 기록 | `alerts` (모델) | 알림 발생 기록 | 없음 |
| 매매 DD | `position_dd_check` | 포지션별 DD 체크리스트 완료 여부 | 없음 |
| Morning Brief | `morning_briefs` (모델) | 일간 브리프 HTML 저장 | 없음 |

### 현재 축적되지 않는 것 (갭)

- TradeHistory에 유저 코멘트/태그/감정 메모 없음 — 매매 일지(Journal) 기능 없음
- Artifact에 유저 노트/별점 없음 — 아티팩트를 "읽었다" 기록(opened_at)만 있음
- 학습 진행도 없음 — 퀀트 모델 이해도, 오답노트 등 없음
- 투자 성장 추적 없음 — 분기별 수익률 개선 추세 DB 저장 없음 (Quarterly Self Report가 PDF로 출력하지만 structured time-series 없음)

---

## E. CEO 질문에 대한 결론

### "이미 Premium에 18개 PDF 있는 거 아님?"

**사실:** `reports/page.tsx` CATALOG 배열에 18개 항목이 있다.
그 중 실제 production 배송 중인 것은 15종, 코드만 있는 것은 3종(#7 Self Audit deprecated, #11 sp500_backtest 서비스 미구현, #17 KPI Dashboard disabled).

### Strategy 권고 "Weekly CFO PDF"와 기존 18종 겹침 여부

**결론: 실질적으로 겹친다.**

| Strategy 권고 기능 | 기존 artifact 대응 | 겹침 수준 |
|---|---|---|
| Weekly CFO 포트폴리오 리뷰 | Weekly Memo (#1, Pro+, 매주 일요일) | 강겹침 — 주간 PDF 이미 존재 |
| 월간 성과 요약 | Monthly Finance Report (#16, Premium) + Brag Card (#3) | 강겹침 |
| 분기 리뷰 | Quarterly Self Report (#6, Premium) | 강겹침 |
| KPI 대시보드 | KPI Dashboard (#17, Morning Brief 통합) | 중겹침 (이메일 내 포함) |
| 리스크 리포트 | Risk Board (#5, Premium) | 강겹침 |
| 실적 알림 | Earnings Pre-Brief (#4, Pro+) | 강겹침 |

### "Weekly CFO PDF"가 새로 필요한가?

Strategy 권고의 "Weekly CFO PDF"는 독립적 신규 산출물이 아니다.
Weekly Memo(#1)가 이미 McKinsey 스타일 PDF를 주간 배송한다.
차이는 **네이밍과 포지셔닝**뿐이다.
"CEO로서의 나" 프레이밍을 Weekly Memo에 덧씌우면 구현 공수 0에 가깝다.

### 재포장 전략 (제안 범위는 전달만 — 결정은 Strategy 부서)

1. **번들링**: Weekly Memo + Risk Board + Monthly Finance를 "CFO Pack"으로 묶어 Premium 핵심 USP로 제시
2. **네이밍**: Weekly Memo → "Your Weekly CFO Brief" (백엔드 코드 수정 없이 UI 텍스트만 변경)
3. **선별**: 18종 중 유저에게 실제 보이는 카탈로그를 5-7종으로 축소하고 나머지는 "숨겨진 인텔리전스"로 자동 배송
4. **시사점**: 구현 공수 측면에서 Weekly CFO PDF는 사실상 기존 Weekly Memo의 재브랜딩이므로 공수 0.

---

## 상품감 점수

**현재 상품감: 6.5 / 10**

근거:
- (+) 18종 아티팩트 전부 HTML 템플릿 완성, 서비스 코드 완성, 대부분 스케줄러 등록
- (+) SendGrid API Key 실제 설정됨, WeasyPrint 요구사항에 포함됨
- (+) `/reports` 페이지 카탈로그 UI 존재, 다운로드 라우트 완비
- (+) Share 링크(Brag Card) + 공개 Counterfactual 바이럴 루프 설계됨
- (-) WeasyPrint 실제 Railway 환경에서 PDF 렌더링 작동 여부 미검증
- (-) 18종 중 3종은 스케줄러 비활성화 또는 서비스 미구현 (sp500_backtest 특히 UI에서 링크하는데 artifact 백엔드 없음)
- (-) 프론트 `/reports` 페이지의 `minTier` 값이 백엔드 `require_tier`와 일치하지 않는 항목 다수 (예: weekly_memo는 UI에서 free, 백엔드는 pro)
- (-) 유저 설정 없음 — 배송 시각, 배송 여부, 원하는 아티팩트 종류 선택 불가

---

*조사 완료: 2026-04-23*
*증거 파일: `/routes/artifacts.py`, `/app.py:528-1092`, `/models/artifact.py`, `/services/artifacts/` 전체, `/frontend/src/app/(dashboard)/reports/page.tsx`*
