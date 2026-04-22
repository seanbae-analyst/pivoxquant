# PivoxQuant — 인수인계서 (2026-04-21 세션 종료 v3)

## 🎯 이 세션 핵심 작업
- **랜딩 페이지 AIDA funnel 재구성** + 전체 영어 + 공백 middle-ground
- **PDF Goldman IC v2 (weekly_memo)** — 6p, 각 페이지 다른 에디토리얼 레이아웃, hand-crafted SVG 차트
- **브랜드 시스템 v2** — wordmark + monogram + submark (3 variants)
- **폰트 임베딩 근본 수정** — base64 WOFF2, 17/17 all embedded
- **Agent 시스템 확장** — 5개 신규 agent + UI/UX Pro Max skill 설치
- **Investor Archetype 섹션** 랜딩 신규 추가 (20 questions · 8 archetypes)
- **버튼·링크 전수 감사** — 20개 중 8곳 fix, dead link 0

---

## ✅ 이번 세션 완료 (상세)

### Landing Page (`frontend/src/components/landing/landing-page.tsx`)
**최종 섹션 순서 (AIDA funnel)**:
1. Hero
2. Proof of Discipline (S&P 백테스트 수치)
3. **Sample Reports** ← up-moved, 실물 PDF 먼저 보여줌
4. Features Bento (6 카드)
5. **Feature Explorer** — 17 artifact 클릭 drawer 설명
6. How It Works (3-step onboarding)
7. **Archetype** (신규) — 20 문항 + 8 투자자 유형
8. **The Engine** (신규) — 58 quant + 7 risk + Claude, 31개 모델 drawer
9. Dashboard Preview
10. Pricing (₩0 / ₩9,900 / ₩19,900 KRW 전환)
11. Pull-quote
12. Final CTA
13. Data Pipeline (파트너 스트립, Footer 바로 위)
14. Footer

**공백**: 여러 차례 조정 후 최종 middle-ground 상태 (py-28 md:py-40 lg:py-48 base)

**Hero**: Cinematic + Hero Highlight 합성, silver-matte 타이포, Bronze spotlight, PDF mockup stack, stat strip

**법적 grep**: 금지어 0건 (방어 부정만)
**한글 grep**: 0건
**버튼·링크 감사**: 20개 href 전수 검사, 8곳 수정, dead link 0
**Build**: TypeScript PASS, HTTP 200

### PDF 시스템

#### Brand Marks v2 — `_brand_mark.html` 전면 재작성
3 variants, SVG-drawn (font-independent):
- **wordmark** — NYT masthead 스타일 + 이탈릭 Bronze Q + fleuron + tagline + 2-rule
- **monogram** — P·Q IC-seal (twin concentric rings, Source-serif P + Bronze Q with tail)
- **submark** — 14pt 미니멀 서클 엠블럼

Usage: `{% with brand_kind='monogram', brand_size=48 %}{% include '_brand_mark.html' %}{% endwith %}`

#### weekly_memo.html Goldman v2 — 6 페이지, 각 페이지 다른 레이아웃
- **P1 COVER**: wordmark 340pt + 3-line poetic italic headline + KPI 4개
- **P2 SPREAD**: 68/32 magazine grid, drop cap, inline hand-crafted equity curve with Bronze callout/anomaly arrow, 4 marginalia blocks
- **P3 LADDER**: sparkline table (normalized per row, Bronze end-dot) + 5×5 correlation heatmap
- **P4 RISK**: 2×2 small-multiples quadrant (VaR / ES / Drawdown / Tail ratio) + methodology sidebar
- **P5 EDITORIAL**: full-bleed 38pt italic pull quote + "What to watch"
- **P6 COLOPHON**: data sources + disclaimer + monogram 64pt + doc-ref

File size: 869KB, 6 pages, 법적 grep 0.

#### Wave 1 (PDF 템플릿 기반)
- `_chart_macros.html` (8 SVG 매크로)
- `_report_css.html` 에 pq-* 컴포넌트 + 토큰
- `_disclaimer.html` §4 verbatim + LICENSE_NUMBER 변수화
- `legal_filter.py` 42 → **74 패턴** (리밸런싱/최적화/Should/Must/Suggest/Optimize 추가)
- **BUY 위반 7건 중립화** (self_audit, quarterly_self_report, year_end_letter, monthly_finance, insider_mirror)
- pytest 73 PASS

#### 폰트 임베딩 근본 수정
- 35 WOFF2 로컬 번들 (`services/artifacts/assets/fonts/`)
- Source Serif 4 / Source Sans 3 / JetBrains Mono / Noto Sans KR / Noto Serif KR / Pretendard
- `_embedded_fonts.html` base64 data URL embed
- 17/17 all embedded (125 font objects)

#### P1 버그 fix
- `brag_card.pdf` disclaimer strip 추가
- `earnings_prebrief.pdf` "$42300.0M" → "$42,300M"
- `burn_rate.pdf` Times 폰트 (폰트 fix 로 자동 해소)

### Agent 시스템 (`.claude/agents/`)
- `pdf-report-designer.md`
- `email-deliverability.md`
- `stripe-billing.md`
- `regulatory-monitor.md`
- `artifact-qa.md`

### Skill
- `.claude/skills/ui-ux-pro-max/` — 67 UI styles DB, 161 색 팔레트, 57 폰트 페어링, 25 차트 타입

### 코드 정리
- **한글 dead code 244줄 제거** (구 `steps`, `pricingPlans`, `footerLinks` 상수 + `{false && ...}` 레거시 Hero)
- Turbopack Unicode bug fix (`next.config.ts` turbopack.root)

### 파일 복사
- `Pivoxquant report/` — 17 PDF 최신본 (weekly_memo 는 Goldman v2 로 갱신됨)
- `frontend/public/samples/` — 6 PDF 노출 (랜딩 Sample Reports 섹션용)

---

## 🔴 다음 세션 최우선 P0 (이번 세션 완료 못함)

### 1. **S&P 500 Backtest PDF** 생성 (Goldman v2 디자인)
**이번 세션 dispatch 했으나 Agent B 타임아웃 → 전혀 생성 안 됨.**

필요 작업:
- `services/artifacts/templates/sp500_backtest.html` 신규 (weekly_memo.html Goldman v2 구조 복제)
- 6 페이지 구조:
  - P1 COVER: wordmark + "Ten years, one rule, measured in the open." (62pt serif italic) + KPI 4 (CAGR 15.2% / Sharpe 0.94 / Alpha +9.66% / 2022 Bear +2.1%)
  - P2 SPREAD: 10-year equity curve (hand-crafted SVG, 2022 Bronze callout band) + 2-paragraph prose drop-cap
  - P3 ANNUAL LADDER: 10-row table (year / strategy / S&P / alpha / DD / Sharpe) + sparklines
  - P4 RISK DASHBOARD: 2×2 small-multiples (rolling 12M Sharpe / Underwater / Histogram / Corr)
  - P5 EDITORIAL: Pull-quote + "What this backtest does NOT show"
  - P6 COLOPHON: Data sources + disclaimer + monogram + doc-ref
- 숫자 데이터는 `docs/BACKTEST_RESULTS.md` 에서 추출 (또는 Jinja 내부 `{% set %}` literal)
- 렌더 후 `frontend/public/samples/sp500_backtest.pdf` 로 복사
- 랜딩의 "View S&P 500 backtest" / "View full backtest" 링크를 `/samples/sp500_backtest.pdf` 로 업데이트

### 2. **나머지 16 PDF 템플릿 Goldman v2 확장**
weekly_memo 를 1st flagship 으로 완성. 다음 우선순위:
- risk_board.pdf (플래그십 2)
- year_end_letter.pdf (플래그십 3)
- quarterly_self_report.pdf
- earnings_prebrief.pdf
- monthly_finance.pdf
- ... 나머지 11개

각 템플릿마다 weekly_memo.html 과 동일한 6p 에디토리얼 구조 적용.
**단, 각 아티팩트 성격에 맞게 페이지 레이아웃 tune** (risk_board 는 heatmap 중심, year_end_letter 는 letter 포맷).

### 3. **Dashboard 실제 상태 업데이트** (프론트 50% 완성 상태)
CLAUDE.md P0 목록 (2026-04-14 직접 테스트):
- **Portfolio 페이지 404** — 신규 구현 + Add Position / 매수/매도 모달
- **Search Stock 검색바** — 클릭/입력 불가
- **Watchlist 추가 불가**
- **Risk 페이지 빈** — 7-Layer Risk Defense 프론트 연동
- **Discover 데이터 안 나옴** — FMP 402 연관
- **알림 벨 / 프로필 아이콘** — 드롭다운 미구현
- **Connect Alpaca 버튼** — 동작 안 함
- **코스피/코스닥 Market 페이지 미노출**

### 4. **CEO 외부 작업 (미완료)**
- [ ] 사업자 등록 (홈택스, 15분)
- [ ] 통신판매업 신고
- [ ] 유사투자자문업 신고 (금감원) → 완료 후 Railway env `SIMILAR_ADVISORY_LICENSE_NUMBER`
- [ ] Naver Developers API 키 (Search API)
- [ ] DART API 키 (선택)
- [ ] Google OAuth redirect URI 등록
- [ ] Kakao Developers redirect URI 등록
- [ ] Gmail 앱비번 (myaccount.google.com/apppasswords)
- [ ] Stripe Product 2개 (Pro ₩9,900 / Premium ₩19,900) + `STRIPE_PRICE_PRO/PREMIUM/WEBHOOK_SECRET`
- [ ] 변호사 검토 (300-700만원)

### 5. **기타 마감 항목**
- Landing Lighthouse 점수 측정 (FCP < 1.8s / LCP < 2.5s 목표)
- Mobile 반응형 375px / 768px / 1440px 각각 스크린샷 체크
- weekly_memo 외 나머지 16 PDF 도 Goldman v2 확장 후 baseline QA 재실행
- Chrome headless ↔ WeasyPrint 렌더 pixel-parity 검증 (Railway 배포 시 필수)
- `frontend/public/samples/` 에 17개 전부 노출 (현재 6개만)

---

## 📁 주요 파일 위치

### Landing (redesign 완료)
- `frontend/src/components/landing/landing-page.tsx` — 메인
- `frontend/src/components/landing/hero.tsx` — Hero
- `frontend/src/components/landing/hero-spotlight.tsx`
- `frontend/src/components/landing/film-grain.tsx`
- `frontend/src/components/landing/pdf-stack-mockup.tsx`
- `frontend/src/components/landing/stat-strip.tsx`
- `frontend/src/app/globals.css` L672-702 — `--pq-*` 토큰 + `.pq-silver-matte`
- `frontend/public/hero/*.svg` — PDF mockup assets
- `frontend/public/samples/*.pdf` — 6 PDF 노출
- `frontend/next.config.ts` — `turbopack.root: __dirname`

### PDF 템플릿 (Goldman v2 진행 중)
- `services/artifacts/templates/weekly_memo.html` ← ✅ v2 완료
- `services/artifacts/templates/_brand_mark.html` — 3 variants
- `services/artifacts/templates/_report_css.html`
- `services/artifacts/templates/_disclaimer.html`
- `services/artifacts/templates/_chart_macros.html` (weekly_memo v2 에선 안 씀, 인라인 SVG)
- `services/artifacts/templates/_embedded_fonts.html` — base64 폰트
- `services/artifacts/templates/_report_masthead.html`
- `services/artifacts/assets/fonts/*.woff2` — 35 파일, 7.6MB
- `services/artifacts/sample_data.py` — weekly_memo 에 11개 신규 필드 추가
- `services/legal_filter.py` — 74 패턴
- `scripts/render_artifact_samples.py` — Chrome headless 폴백

### 에이전트 / 스킬
- `.claude/agents/pdf-report-designer.md`
- `.claude/agents/email-deliverability.md`
- `.claude/agents/stripe-billing.md`
- `.claude/agents/regulatory-monitor.md`
- `.claude/agents/artifact-qa.md`
- `.claude/skills/ui-ux-pro-max/`

### 출력 폴더
- `samples/pdf/*.pdf` — 17 PDF 최신본
- `/Users/seanbae/Desktop/취준/Pivoxquant report/` — CEO 전달용

---

## 📊 최종 상태 서머리

### ✅ 완료
- OAuth 로그인 (Kakao + Google) — stateless HMAC
- KIS 단일 브로커 (한국 + 미국)
- 17 Premium Artifact 생성 파이프라인 + 자동 발송
- 3티어 (Free / Pro ₩9,900 / Premium ₩19,900)
- legal_filter 74 패턴
- **랜딩 페이지 AIDA funnel 재구성 + 영어** ← NEW
- **Brand System v2 (wordmark + monogram + submark)** ← NEW
- **weekly_memo Goldman IC v2 (6p, hand-crafted SVG, editorial layout)** ← NEW
- **Investor Archetype 섹션 랜딩 추가** ← NEW
- **The Engine 섹션 (31 모델 클릭 설명)** ← NEW
- **Feature Explorer (17 artifact 드로어)** ← NEW
- **폰트 임베딩 근본 수정 (17/17)** ← NEW
- **버튼·링크 전수 감사, dead link 0** ← NEW
- **한글 dead code 244줄 제거** ← NEW
- Agent 5개 신규 + UI/UX Pro Max skill 설치

### ⏳ CEO 외부 작업 대기
- 사업자/통신판매/유사투자자문 등록
- API 키 (Naver, DART, Gmail SMTP)
- Stripe 연결
- 변호사 검토
- OAuth redirect URI 등록

### 🔄 다음 세션 TODO (우선순위)
1. **S&P 500 Backtest PDF 생성** (Goldman v2, 6p) — 이번 세션 timeout
2. **나머지 16 PDF 템플릿 Goldman v2 확장** (플래그십 risk_board / year_end_letter 먼저)
3. **Dashboard 실동작 P0** (Portfolio 404 / Search / Watchlist / Risk / Discover)
4. Lighthouse 점수 측정 + Mobile 반응형 QA
5. `frontend/public/samples/` 에 17 PDF 전부 노출

---

## 🛠 다음 세션에서 반드시 쓸 도구·레퍼런스

### 1. UI/UX Pro Max Skill (설치 완료)
- **경로**: `.claude/skills/ui-ux-pro-max/`
- **출처**: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- **DB 파일**: `data/colors.csv` (161 팔레트) / `landing.csv` / `charts.csv` (25 타입) / `google-fonts.csv` (57 페어링) / `icons.csv` / `design.csv`
- **활용**: 새 섹션/컴포넌트 디자인 때마다 매 결정 전에 CSV 조회 → 검증된 패턴 인용
- **주요 결정 포인트**:
  - 색 조합 → `colors.csv`
  - 레이아웃 → `landing.csv`
  - 차트 타입 선택 → `charts.csv`
  - 타이포 페어링 → `google-fonts.csv`

### 2. 21st.dev Components
- **URL**: https://21st.dev/community/components
- **활용**: 신규 컴포넌트 필요 시 여기서 Prompt/Install 복사 → Vantablack 리스킨 → 통합
- **접근 방법**: Chrome MCP 연결되면 직접 브라우징, 아니면 `https://21st.dev/r/{creator}/{slug}` 로 registry JSON curl
- **검증된 사용처**:
  - Hero → `easemize/cinematic-landing-hero` + `aceternity/hero-highlight` (이번 세션 통합 성공)
- **다음 세션 후보**:
  - Dashboard sidebar
  - Data table (Portfolio 페이지)
  - Command menu (Search)
  - Modal (Add Position)

### 3. 기존 PDF 템플릿 v2 레퍼런스 (완성본)
- **weekly_memo.html** — Goldman IC v2 6-page 편집 레이아웃의 **기준 모델**
- **_brand_mark.html** — wordmark / monogram / submark 3 variants
- **_report_css.html** — pq-* 컴포넌트 시스템
- 모든 신규 PDF 템플릿은 **weekly_memo.html 구조를 복제 후 콘텐츠만 교체**

### 4. 사용해야 할 Agent들
- **frontend-dev** — UI 구현 전담
- **pdf-report-designer** — 17 PDF 템플릿 전담 (Iron Rules 내장)
- **audit** — 완료물 품질 검수
- **email-deliverability** / **stripe-billing** / **regulatory-monitor** / **artifact-qa** — 특화 agent

### 5. 리소스 관리 (이번 세션 학습)
- **동시 Agent 2개 이하** — 3개+ 는 컴퓨터 꺼짐 리스크
- **Agent timeout 피하려면** 스코프를 작게 잘라서 dispatch
- **Chrome MCP 불안정** — 연결 끊기면 WebFetch / curl 으로 대체
- **Turbopack 한글 경로 bug** — `next.config.ts` 의 `turbopack: { root: __dirname }` 필수

---

## 🎯 다음 세션 시작 프롬프트

```
HANDOVER.md 읽고 이어서.

**반드시 쓸 것**:
1. UI/UX Pro Max skill — .claude/skills/ui-ux-pro-max/ 의 CSV DB 조회해서 디자인 결정 검증
2. 21st.dev/community/components — 신규 컴포넌트 필요 시 여기서 prompt/code 가져와 리스킨
3. weekly_memo.html — Goldman v2 레이아웃 기준 (모든 신규 PDF 이 구조 복제)

**최우선 작업**:
1. S&P 500 Backtest PDF 생성 (Goldman v2 6p)
   → public/samples/sp500_backtest.pdf 로 복사
   → 랜딩 "View Full Backtest" 링크 연결
   
2. 그다음 risk_board.pdf Goldman v2 전면 재작업 (ui-ux-pro-max charts.csv 참조)

3. 그다음 year_end_letter.pdf Goldman v2

4. Dashboard P0 (Portfolio 404 / Search / Watchlist)
   → 21st.dev 에서 Data Table + Command Menu + Modal 컴포넌트 가져와 Vantablack 리스킨

**리소스 규칙**:
- 동시 Agent 2개 이하
- 각 agent 스코프 작게 (timeout 방지)

**외부 작업 체크**:
- [ ] 사업자 등록
- [ ] 유사투자자문업 신고
- [ ] Naver API 키
- [ ] Stripe 연결
- [ ] Gmail SMTP
```

---

**작성**: 2026-04-21 (세션 종료 v3)
**이전 버전**: 2026-04-20 v2 / 2026-04-21 v1 / 2026-04-21 v2 아카이브
**다음 세션**: S&P Backtest PDF 부터 시작
