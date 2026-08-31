# PivoxQuant — Landing Page Content

**작성일**: 2026-04-20
**용도**: Claude Design 또는 디자이너에게 전달할 랜딩 콘텐츠 명세
**참조**: `DESIGN_BRIEF_FOR_CLAUDE.md` (디자인 시스템)

---

## 섹션 순서 (12개)

1. **Hero**
2. **Trust Bar** (소셜 프루프)
3. **Problem** (왜 PivoxQuant 인가)
4. **Solution** (User as CFO 컨셉)
5. **How It Works** (3단계)
6. **Performance** (S&P 500 백테스트 결과)
7. **Features** (20개 Artifact 카테고리별)
8. **Artifact Preview** (Weekly Memo 샘플 PDF)
9. **Pricing** (3티어)
10. **Comparison** (경쟁사 대비)
11. **FAQ**
12. **Final CTA + Footer**

---

## 1. Hero

### Headline (한국어)
```
당신은 당신 포트폴리오의 CFO
```

### Sub-headline
```
AI가 자는 동안 Weekly Memo, Earnings Pre-Brief, Monthly Finance Report 를
만들어 이메일과 PDF 로 보내드립니다.
```

### Alternative headlines (A/B 테스트용)
- "ChatGPT는 물어야 답한다. PivoxQuant는 자는 동안 만든다."
- "매일 아침, 당신의 전담 애널리스트가 브리핑을 보냅니다."
- "내 포트폴리오의 Bloomberg Terminal — 월 ₩9,900"

### CTA
- Primary: **"무료로 시작하기"** → 회원가입
- Secondary: **"샘플 Weekly Memo 보기"** → PDF 다운로드

### Visual
- 오른쪽에 Weekly Memo PDF 5페이지 mockup (Apple MacBook 프레임 안에)
- 또는 이메일 받은 스크린샷 (iPhone 프레임)

---

## 2. Trust Bar

### 영역
Hero 바로 아래 slim horizontal bar. 흐리게 (gray-500).

### 콘텐츠
```
2026년 Private Beta 중 · 한국+미국 주식 지원 · 브로커 자동 연동 (KIS)
```

### 로고 스트립 (받을 수 있으면)
- 한국투자증권 로고
- Anthropic Claude 로고 ("Powered by Claude")

---

## 3. Problem 섹션

### 헤드라인
```
개인 투자자가 매일 버리는 5시간
```

### 3개 Pain point

**📉 정보 과부하**
> 매일 뉴스 30개, 공시 5개, 실적 콜 2개. 어떤 게 내 포트폴리오에 영향 있는지 모름.

**🔄 중복 체크**
> 네이버 금융 → 토스증권 → Bloomberg → ChatGPT. 같은 정보 4번 찾아보기.

**📊 감정적 결정**
> 급락하면 팔고, 급등하면 사고. 3개월 후 "왜 그랬지?" 기록이 없음.

### 전환 문구
```
CFO는 이런 문제를 겪지 않습니다. 당신이 CFO가 될 차례입니다.
```

---

## 4. Solution 섹션 — "User as CFO"

### 헤드라인
```
AI가 챗봇이 아니라 당신의 전담 CFO가 되는 방식
```

### 3개 원칙 (3-column)

**🤖 Proactive AI**
> 유저가 묻기 전에 AI가 먼저 움직입니다. 매일 06시 Morning Brief,
> 실적 30분 전 Pre-Brief, 매월 Risk Board Deck 이 자동으로 이메일에 도착.

**📄 Artifact 중심**
> ChatGPT 답변은 창을 닫으면 사라집니다. PivoxQuant 는 이메일, PDF,
> 공유 카드 — **실물로 남는 결과물**을 만듭니다.

**🔒 개인화 + 브로커 연동**
> 한국투자증권(KIS)을 연결하면 내 포지션이 자동 동기화.
> 모든 리포트는 **내 포트폴리오 기준**으로 생성됩니다.

### 인용구 (Quote block)
```
"ChatGPT는 유저가 물어야 답한다.
PivoxQuant는 유저가 자는 동안 만든다."
```

---

## 5. How It Works (3단계)

### 헤드라인
```
3분 만에 시작, 5분 만에 첫 리포트
```

### Step 1 — 로그인 + 브로커 연결
```
Google/Kakao 로그인 → KIS 연결 (선택)
(또는 "수동 입력" 으로 건너뛰기 가능)
```

### Step 2 — 포지션 자동 Import
```
브로커 API 로 보유 종목 + 평단가 + 수량 자동 동기화
(또는 직접 추가)
```

### Step 3 — AI 가 자동으로 리포트 생성
```
매일 Morning Brief + 주간 Memo + 월간 Risk Board Deck
= 하루 평균 5시간 절약
```

### Visual
단계별 스크린샷 3개 좌→우 flow. 각 스크린샷 아래 설명.

---

## 6. Performance (S&P 500 백테스트) — ⭐ 코어 마케팅

### 헤드라인
```
PivoxQuant 퀀트 모델은 5년간 S&P 500 을 이겼습니다.
```

### 핵심 숫자 3개 (대형 그래픽)

```
📈  +21.19%        📈  0.94              🛡️  -19.6%
    CAGR              Sharpe                 Max Drawdown
    (SPY +12.55%)    (SPY 0.50)             (SPY -24.5%)
```

### 서브 카피
```
2021-12 ~ 2026-04 (4년 4개월) 백테스트 결과.
Multi-Model 전략 기준. Strategy A/B 도 SPY 를 전부 아웃퍼폼.
```

### 차트 (Hero 이미지)
**equity_curves.png** (`tests/backtest_results/equity_curves.png`)
- Strategy A / B / C + SPY 라인 비교
- 1200x600 PNG

### Highlight Box (주목할 것)
```
🔥 2022 베어 마켓에서 S&P 500이 -18.6% 폭락할 때
    PivoxQuant 세 전략 모두 +2% 이상 수익 기록.
```

### 면책 (작게, 하단)
```
과거 성과는 미래 수익을 보장하지 않습니다.
백테스트는 survivorship bias, 거래비용 단순화 등 한계가 있습니다.
상세 방법론은 [백테스트 리포트] 참조.
```

### CTA
**"전체 백테스트 리포트 보기"** → `docs/BACKTEST_RESULTS.md` 링크

---

## 7. Features (20개 Artifact)

### 헤드라인
```
매월 받는 40+ Artifact — 당신만을 위한 보고서
```

### 카테고리별 (4-column grid)

**📅 매일 (Daily)**
- Morning Brief Plus (매일 06:00 이메일)
  - 포지션 변동 + KPI 5개 + 레드플래그 + 실적 일정

**📊 매주 (Weekly)**
- Weekly Investor Memo (일요일 PDF 5p)
- Insider Transaction Mirror (월요일 PDF 3p, Premium)

**📈 매월 (Monthly)**
- Monthly Finance Report (월초 PDF 6p, Premium)
- Risk Board Meeting Deck (월 15일 PDF 8p, Premium)
- Burn Rate Report (월초 PDF 2p)
- Credit Rating Self-Assessment (월 15일 1p)
- Dividend Income Statement (월초 PDF 3p, Premium)

**📅 매분기 (Quarterly)**
- Quarterly Self Report (분기 +7일 PDF 15p, Premium)
- Portfolio Segment Report (분기 PDF 4p, Premium)

**🎯 매년 (Annual)**
- Year-End Investor Letter (12월 31일 PDF 6p, Premium)

**⚡ 이벤트 기반**
- Earnings Pre-Brief (실적 30분 전 PDF + Push)
- DD Checklist (매수 후 T+3 이메일)
- VIX Spike Risk Alert (VIX>25 즉시, Premium)

**🧮 On-demand**
- Capital Allocation Calculator (What-if, Premium)
- Monthly Brag Card (공유 가능 PNG, Free 포함)
- AI 분석 Suite (SWOT/Competitor/Sector/Coaching 8종)

### 각 Artifact 카드 형식
```
[아이콘]
제목
한 줄 설명 (20자 이내)
[샘플 보기] → 썸네일 Modal
```

---

## 8. Artifact Preview (실물 보여주기)

### 헤드라인
```
실제 Weekly Investor Memo — 5 페이지
```

### Mockup
PDF 5페이지 Carousel 또는 flipbook:
- P1 표지
- P2 포트폴리오 요약
- P3 섹터별 분석
- P4 리스크 지표
- P5 다음 주 Watch Items

### CTA
**"샘플 PDF 다운로드"** → 익명화된 샘플 파일

---

## 9. Pricing (3티어)

### 헤드라인
```
월 ₩9,900 — ChatGPT Plus 보다 저렴하게 전담 애널리스트
```

### 3 티어 카드

| | **Free** | **Pro** | **Premium** |
|---|---|---|---|
| 가격 | ₩0 | **₩9,900/월** | **₩19,900/월** |
| 포지션 | 3개 | 무제한 | 무제한 |
| Monthly Brag Card | ✅ | ✅ | ✅ |
| Morning Brief Plus (매일) | — | ✅ | ✅ |
| Weekly Investor Memo | — | ✅ | ✅ |
| Earnings Pre-Brief | — | ✅ | ✅ |
| AI 분석 8종 | — | ✅ | ✅ |
| Burn Rate / Credit Rating | — | ✅ | ✅ |
| DD Checklist | — | ✅ | ✅ |
| Monthly Finance Report | — | — | ✅ |
| Risk Board Meeting Deck | — | — | ✅ |
| Quarterly Self Report | — | — | ✅ |
| Year-End Investor Letter | — | — | ✅ |
| Capital Allocation Calculator | — | — | ✅ |
| Insider Transaction Mirror | — | — | ✅ |
| Portfolio Segment Report | — | — | ✅ |
| Dividend Income Statement | — | — | ✅ |

### 뱃지
- Pro 카드에 "가장 많이 선택" 태그
- Premium 카드에 "Best value" 태그

### CTA
각 카드에 **"시작하기"** 버튼

---

## 10. Comparison (경쟁사 대비)

### 헤드라인
```
월 구독료 비교
```

### 테이블

| 서비스 | 월 가격 | 한국어 | PDF Artifact | 개인화 | 브로커 연동 |
|--------|---------|--------|-------------|--------|------------|
| ChatGPT Plus | ₩27,000 | 부분 | ❌ | ❌ | ❌ |
| Seeking Alpha Premium | ₩36,000 | ❌ | ❌ | ❌ | ❌ |
| SimplyWall.St | ₩16,000 | ❌ | 제한적 | 부분 | ❌ |
| Atom Finance | ₩43,000 | ❌ | ❌ | 부분 | ❌ |
| Koyfin Plus | ₩56,000 | ❌ | 부분 | 부분 | ❌ |
| **PivoxQuant Pro** | **₩9,900** | ✅ | ✅ 20+ | ✅ | ✅ |

### Highlight
```
한국어 + PDF Artifact + 브로커 연동 — 동급 유일.
```

---

## 11. FAQ (7개 Q&A)

**Q1. 투자자문업 인가 받았나요?**
> 아니요. PivoxQuant 는 **정보 제공 서비스**이며 투자자문업이 아닙니다.
> 모든 Artifact 는 이용자 본인의 포트폴리오 데이터를 집계·정리한 것이며,
> 매수/매도를 권유하지 않습니다. 투자 결정은 이용자 본인의 판단입니다.

**Q2. 실제로 S&P 500 을 이기나요?**
> 백테스트 결과 5년간 아웃퍼폼했지만 **과거 성과는 미래 수익을 보장하지 않습니다**.
> 실전에서는 거래비용, 세금, 슬리피지로 실제 수익이 달라질 수 있습니다.

**Q3. 브로커 API 키를 저장하면 안전한가요?**
> 모든 API 키는 AES-256-GCM 암호화로 저장됩니다.
> 주문 기능은 **read-only** 이며 매매 실행 권한은 없습니다 (법적 안전).

**Q4. 한국 주식 + 미국 주식 모두 지원하나요?**
> 네. KOSPI / KOSDAQ + NYSE / NASDAQ 모두 지원. 환율 자동 변환.

**Q5. Pro 구독하면 언제 첫 Artifact 받나요?**
> 가입 후 24시간 이내 Morning Brief 첫 이메일 수신.
> 주간 Memo 는 첫 일요일에 발송.

**Q6. 환불 가능한가요?**
> 결제 후 14일 이내 환불 가능 (이용약관 제4조).

**Q7. 해지하면 데이터는 어떻게 되나요?**
> 탈퇴 즉시 모든 개인 데이터 삭제 (PIPA §21).
> 브로커 API 키도 즉시 폐기.

---

## 12. Final CTA + Footer

### Final CTA 섹션
```
[대형 버튼]

"무료로 시작하기"

14일 환불 보장 · 신용카드 등록 불필요 · 언제든 해지
```

### Footer

**컬럼 1 — Product**
- 기능
- 가격
- 백테스트 결과
- 샘플 리포트

**컬럼 2 — Company**
- 소개
- 블로그 (나중)
- 연락처

**컬럼 3 — Legal**
- 이용약관
- 개인정보처리방침
- 쿠키 정책
- 면책 고지

**컬럼 4 — Social**
- Twitter / X (나중)
- LinkedIn (나중)
- Discord (나중)

**하단 Copyright**
```
© 2026 PivoxQuant · 대표: 배상현 · 사업자등록번호: XXX-XX-XXXXX
· 통신판매업신고: XXX · 이메일: support@pivoxquant.com
```

**법적 면책 (footer 최하단, 작게)**
```
PivoxQuant 는 자본시장법상 투자자문업 인가를 받지 않았습니다.
본 서비스는 정보 제공 목적이며, 투자 결정 및 그 결과에 대한
책임은 이용자 본인에게 있습니다. 과거 성과는 미래 수익을
보장하지 않습니다.
```

---

## 🎨 디자인 가이드

### 컬러 (DESIGN_BRIEF_FOR_CLAUDE.md 참조)
- Background: `#fafafa` / `#ffffff`
- Text: `#0f172a` / `#64748b`
- Accent: Navy `#1e3a8a` + Warm Gold `#E2B96F`
- Positive: `#16a34a`
- Negative: `#dc2626`

### 폰트
- Heading: Source Serif 4
- Body: Geist Sans + Pretendard (한국어)
- Numbers: JetBrains Mono

### 애니메이션
- Scroll reveal: 섹션 viewport 진입 시 fade-up
- Hero graphic: subtle parallax
- Easing: `cubic-bezier(0.16, 1, 0.3, 1)`

### 반응형
- Desktop: 1440px max-width, 12 column
- Tablet: 768px, 8 column
- Mobile: 375px, stack vertical
- 모든 CTA 는 모바일에서 full-width pill

---

## 📎 에셋 파일 경로

Claude Design 에게 참조 주고 싶을 때:

1. **Equity curve 차트**: `tests/backtest_results/equity_curves.png`
2. **Drawdown 차트**: `tests/backtest_results/drawdown.png`
3. **Monthly heatmap**: `tests/backtest_results/monthly_heatmap_A.png`
4. **백테스트 상세**: `docs/BACKTEST_RESULTS.md`
5. **디자인 시스템 브리프**: `docs/DESIGN_BRIEF_FOR_CLAUDE.md`
6. **기존 랜딩 코드**: `frontend/src/components/landing/landing-page.tsx`
7. **디자인 토큰**: `frontend/src/app/globals.css`
8. **제품 컨셉 메모리**: `docs/PRODUCT_PLAN.md` (있으면)

---

## 🚀 Claude Design 에 넘길 프롬프트 템플릿

```
I'm designing the landing page for PivoxQuant — an AI-powered personal
investment advisor for Korean retail investors (US + KR stocks).

Concept: "User as CFO" — AI generates PDF reports, emails, shareable cards
automatically while users sleep.

Read full landing content: /Users/seanbae/Desktop/취준/pivoxquant/docs/LANDING_PAGE_CONTENT.md
Read design system: /Users/seanbae/Desktop/취준/pivoxquant/docs/DESIGN_BRIEF_FOR_CLAUDE.md

The landing has 12 sections — please design section-by-section:

Start with: Hero section
- Headline: "당신은 당신 포트폴리오의 CFO"
- CTA: primary "무료로 시작하기", secondary "샘플 Weekly Memo 보기"
- Visual: MacBook mockup showing a Weekly Memo PDF

Style: Bloomberg Terminal × Apple HIG × Linear. Navy + Warm Gold accents
on light theme. Serif headlines + monospace numbers.

Generate Next.js + TailwindCSS 4 + Motion components ready to paste.
```
