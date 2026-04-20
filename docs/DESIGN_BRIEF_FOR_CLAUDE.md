# PivoxQuant — Design Brief for Claude Design AI

---

## 📋 사용법

Claude Design (또는 유사 AI 디자인 도구) 에 UI/컴포넌트 디자인 명령 내릴 때,
아래 문장을 **그대로 복사해서** 프롬프트 상단에 붙여넣으세요.

---

## 🏢 회사 소개 (Company Context)

**PivoxQuant** is an AI + Quant-powered personal investment advisor platform
built for Korean individual investors trading in US + Korean stock markets.

- **Core concept**: "User as CFO" — users feel like their own portfolio's
  Chief Financial Officer, not a chatbot user.
- **Differentiator**: We generate Artifacts (PDF reports, emails, shareable
  cards) while users sleep — not a ChatGPT clone that responds to questions.
- **Founder**: 배상현 (Sean Bae), solo founder, Seoul.
- **Launch status**: Private beta (April 2026), ~50 beta testers target.
- **Tagline**: "ChatGPT는 유저가 물어야 답한다. PivoxQuant는 유저가 자는 동안 만든다."
  (ChatGPT waits for questions. PivoxQuant works while you sleep.)

## 💰 Pricing

- **Free** (바이럴 미끼): 3 positions max, Monthly Brag Card
- **Pro ₩9,900/month**: Daily briefings + Weekly Memo + Earnings Pre-Brief +
  AI analysis suite (SWOT/Competitor/etc) + DD Checklist + Burn Rate +
  Credit Rating
- **Premium ₩19,900/month**: Pro + Risk Board Deck + Portfolio Segment +
  Dividend Income + Monthly Finance + Quarterly Self Report + Year-End
  Investor Letter + Capital Allocation Calculator + Insider Transaction
  Mirror

---

## 👥 Target User Persona

- **Primary**: 30~50대 한국 개인투자자, 본업 있음, 투자에 주 5시간 이하 투입
- 미국 + 한국 주식 둘 다 보유 (KIS 연동 or 수동 입력)
- 월 거래 1~20건 (홀드형, 데이트레이더 아님)
- 주 관심: 본인 포트폴리오 **리스크 관리** + **과거 결정 품질 검증** + **자동화된 리포트**
- 경쟁 서비스 대체 사용 경험: ChatGPT Plus, 토스증권, Seeking Alpha, SimplyWall.St

---

## 🎨 Design Direction

### Brand Personality
- **Professional** — 금융 서비스 신뢰성 (은행·회계법인 레벨)
- **Trustworthy** — 과장 없고 데이터 중심
- **Calm** — Bloomberg Terminal 의 정적·집중도
- **Modern** — Linear / Vercel / Stripe 수준의 현대적 minimalism
- **Distinctly Korean** — 한국어 타이포그래피 + 한국 금융 문체 자연스러움

### Visual Style

**모델 비교 한 줄**:
> Bloomberg Terminal × Apple Human Interface Guidelines × Linear × Stripe Dashboard

**참고 레퍼런스**:
- Linear (linear.app) — clean, monospace 숫자, generous whitespace
- Stripe Dashboard (dashboard.stripe.com) — 데이터 밀도 + 시각적 계층
- Apple HIG — 타이포그래피 hierarchy
- Bloomberg Terminal — 정보 밀도 + 금융적 신뢰감

### Color Palette (현재 시스템)

**Light theme (primary)**:
- Background: `#fafafa` (off-white), cards `#ffffff`
- Text primary: `#0f172a` (slate-900)
- Text muted: `#64748b` (slate-500)
- Border: `#e2e8f0` (slate-200)
- Accent (sparingly): 금융 서비스답게 **Navy/Deep Blue** `#1e3a8a`
- Positive (수익): `#16a34a` (green-600)
- Negative (손실): `#dc2626` (red-600)
- Warning: `#f59e0b` (amber-500)
- Warm Gold (highlights): `#E2B96F`

**Dark theme (optional)**: `#050505` Vantablack base + Warm Gold accents

### Typography

- **Headings**: Source Serif 4 (serif, 금융 리포트 느낌) OR Geist Sans
- **Body**: Geist Sans (UI) + Pretendard (한국어 최적)
- **Numbers/Data**: JetBrains Mono (monospace, 가격/KPI 정렬)
- **Korean**: Pretendard 900~400 weight range

### Layout Principles

- **Dashboard** = 정보 밀도 높게 (Bloomberg처럼)
- **Reports/PDF** = 여백 넉넉하게 (McKinsey deck 처럼)
- **Mobile** = stack vertically, never compromise readability
- **12-column grid**, 1440px max-width, generous gutters

---

## 🚫 BANNED (절대 쓰지 말 것)

이건 과거에 유저가 싫어했던 스타일:
- ❌ **Purple/pink gradient** (AI 앱 진부한 클리셰)
- ❌ **Neon glow effects** (유치함)
- ❌ **3-equal-column hero sections** (보편적 웹디자인)
- ❌ **"AI Assistant" / "AI Coach" labeling** (법적 위험 + 브랜드와 안 맞음)
- ❌ **Emoji overuse** in product copy (전문성 저해)
- ❌ **Generic stock photo** of "business person with chart"
- ❌ **Pie chart + bar chart 혼용 대시보드** (데이터 시각화 약함)

---

## ✅ REQUIRED (필수)

- ✅ 한국어 + 영어 **병기 가능** 레이아웃 (한국어 기본, 토글)
- ✅ 법적 면책 **모든 분석 페이지** 하단에 필수 (`DisclaimerBanner`)
- ✅ POSITIVE / NEGATIVE / NEUTRAL signal 라벨 (BUY/SELL 절대 금지 — 자본시장법)
- ✅ Cookie Consent Banner
- ✅ 숫자는 항상 monospace + thousand separator
- ✅ 환율 변환 표시 (USD → KRW 자동)
- ✅ Accessibility: AAA contrast ratio where possible
- ✅ Dark mode support (optional but preferred)

---

## 🎯 Key Pages to Design

### 1. Landing Page (미로그인)
- Hero: "당신은 당신 포트폴리오의 CFO" + 서브카피
- 특징 3개: 자동 발송 Artifact / S&P 500 outperformance / 브로커 연동
- S&P 500 벤치마크 결과 차트 (equity curve, 우리가 이긴 그림)
- Sample Artifact 미리보기 (Weekly Memo PDF 1p 일부)
- 가격표 (Free / Pro / Premium)
- FAQ + 법적 면책

### 2. Onboarding Broker Connect (`/onboarding/broker`)
- 2개 카드 나란히: KIS / 수동 입력 (2026-04-20 단순화)
- 각 카드: 아이콘, 제목, 한 줄 설명, 연결 상태 배지, CTA
- Step 0 of 21 progress bar

### 3. Dashboard Home (`/home`)
- Top: KPI 5-card (Portfolio Value + YTD, Sharpe, Max DD, Turnover, Cash %)
- Middle: Today's insight (Morning Brief 요약)
- Bottom: Positions list (회사명 크게, 티커 작게)

### 4. Portfolio (`/portfolio`)
- Grouped by: 전체 / POSITIVE / NEGATIVE / NEUTRAL
- Sortable: 티커 / 손익 / 평가금액 / 점수
- Each card: 회사명 primary, 티커 secondary, 현재가, 평단가, 수량, 평가금액, PnL, 점수 gauge

### 5. Reports Archive (`/reports`)
- 모든 Artifact 타입 (13종) Grid 또는 타임라인
- 각 Artifact: 썸네일 + 제목 + 날짜 + 다운로드 버튼
- 필터: Pro (Morning Brief/Weekly Memo/Earnings Pre-Brief/DD Checklist/Burn Rate/Credit Rating) vs Premium (Self Audit/Risk Board/Portfolio Segment/Dividend/Monthly Finance/Year-End/Quarterly Self/Capital Allocation/Insider Mirror)

### 6. Risk (`/risk`)
- 상단 4 MetricCard: Sharpe / Max DD / 연환산 변동성 / 방어 레이어 X/7
- VaR 95%/99% 섹션
- 7-Layer Risk Defense 상태 grid
- Top 포지션 리스크 기여도

### 7. Settings (`/settings`)
- Profile / Connections (KIS) / Subscription / Notifications
- 기존 탭 구조 유지

### 8. PDF Report Templates (WeasyPrint render)
- Weekly Investor Memo (5p A4)
- Earnings Pre-Brief (3p A4)
- Monthly Finance Report (6p A4)
- Risk Board Meeting Deck (8p A4 landscape)
- Quarterly Self Report (15p A4)
- Year-End Investor Letter (6p A4)

---

## 🛠 Technical Constraints

- **Next.js 16 App Router** (already set up, don't change routing structure)
- **TypeScript strict** mode
- **Tailwind CSS 4** (not 3) — don't use @apply heavily
- **shadcn/ui** components library (already have 15+ components)
- **SWR** for data fetching (don't replace with React Query)
- **Motion/React** (Framer Motion replacement) — 전체 apply
- **Easing**: always `cubic-bezier(0.16, 1, 0.3, 1)` for transitions
- Server Components by default, Client Components only when needed
- 62 backend API endpoints already wired (don't break `/lib/endpoints.ts`)

---

## 📎 Files to Read for Context

Claude Design 에게 이 파일들 참조하라고 알려주세요:

1. `/Users/seanbae/Desktop/취준/pivoxquant/frontend/design-principles-cfo.md` — 현재 디자인 원칙
2. `/Users/seanbae/Desktop/취준/pivoxquant/frontend/src/app/globals.css` — 기존 CSS 변수
3. `/Users/seanbae/Desktop/취준/pivoxquant/frontend/src/messages/ko.json` — 한국어 카피 톤
4. `/Users/seanbae/Desktop/취준/pivoxquant/docs/BACKTEST_RESULTS.md` — 성능 데이터
5. `/Users/seanbae/Desktop/취준/pivoxquant/tests/backtest_results/equity_curves.png` — 차트 레퍼런스

---

## 🎬 프롬프트 예시 (Claude Design에 붙여넣기)

```
I'm working on PivoxQuant, an AI + Quant-powered personal investment advisor
for Korean individual investors trading US + Korean stocks. The product
positions users as their own portfolio's CFO (not a chatbot).

Design style: Bloomberg Terminal × Apple HIG × Linear × Stripe Dashboard.
Professional, trustworthy, calm, modern, distinctly Korean.

Color palette (light theme primary):
- Background #fafafa, cards #ffffff
- Text #0f172a primary, #64748b muted
- Accent Navy #1e3a8a (sparingly)
- Positive #16a34a, Negative #dc2626
- Warm Gold #E2B96F highlights

Typography: Source Serif 4 (headings) + Geist Sans (UI) + Pretendard (Korean)
+ JetBrains Mono (numbers).

BANNED: purple/pink gradients, neon glow, emoji overuse, "AI Assistant" labels.
REQUIRED: monospace numbers, legal disclaimer footers, POSITIVE/NEGATIVE/NEUTRAL
(never BUY/SELL), Korean/English toggle support.

Now design: [여기에 구체적인 요청 — "the Weekly Investor Memo PDF 5-page
layout" or "the Dashboard Home with KPI cards and positions list" 등]

Read full context at:
/Users/seanbae/Desktop/취준/pivoxquant/docs/DESIGN_BRIEF_FOR_CLAUDE.md
```

---

**Last updated**: 2026-04-20
**작성자**: Claude (PivoxQuant 디자인팀)
