# PivoxQuant UI 리디자인 제안서

> 작성일: 2026-04-10  
> 작성: 디자인부  
> 목적: 상현님의 A/B/C 방향 결정을 위한 실제 코드 기반 분석 + 3가지 옵션 제시

---

## 1. 현재 UI 문제점 진단

코드 전수 검토 결과. 추측 없이 실제 코드에서 발견된 문제들입니다.

### 1-1. 가장 심각한 문제: 다크/라이트 혼재

현재 앱은 단일 테마처럼 보이지만 실제로는 **세 개의 다른 색상 세계**가 공존합니다.

| 화면 | 배경색 | 텍스트 계열 | 분위기 |
|------|--------|------------|--------|
| 로그인 페이지 | `#0a0a0a` 계열 다크 (zinc-900) | white/zinc | 다크 핀테크 |
| 랜딩 페이지 | `#ffffff` 라이트 | slate-900 | Cohere 라이트 SaaS |
| 대시보드 (로그인 후) | `#f8fafc` 연회색 | slate-900 | 기업용 라이트 |

로그인 화면에서 `landing-dark` 클래스를 쓰는데 해당 클래스의 `--ld-bg`가 `#ffffff`로 오버라이드되어 있어, 실제로는 로그인 페이지만 다크이고 나머지는 라이트입니다. 사용자가 로그인 → 대시보드 진입 시 시각적 충격이 발생합니다.

**코드 근거:**
- `login/page.tsx` L74: `className="landing-dark"` → 진짜 다크 (zinc 계열)
- `globals.css` L372: `.landing-dark { --ld-bg: #ffffff; }` → 랜딩은 라이트로 오버라이드
- `dashboard/layout.tsx` L138: `bg-slate-50` → 대시보드는 연회색

### 1-2. 색상 토큰 파괴 — one-off 하드코딩

```
summary-cards.tsx:  text-[#0a1929]  ← 토큰 없는 임의 near-black
summary-cards.tsx:  border-l-[#003a70]  ← 토큰 없는 네이비
notification-bell.tsx:  bg-[#0d0d12]  ← 다크 모드 흔적 (라이트 앱에 다크 드롭다운)
```

`#0d0d12` 다크 드롭다운이 흰 배경 앱 안에 살아있습니다. 이 세 값은 `design-system.md`에도 "Not Tokenized"로 명시되어 있습니다.

### 1-3. 성공/하락 색상이 글로벌 표준 미달

현재: `--success: #10b981` (에메랄드), `--destructive: #dc2626` (레드)  
글로벌 표준: Bloomberg `#00C853` (진한 초록), `#FF1744` (진한 빨강)

현재 에메랄드는 금융 "수익" 색이라기보다 브랜드 색처럼 읽힙니다. Primary 버튼(`bg-primary = #059669`)과 수익 표시(`text-success = #10b981`)가 거의 같은 초록이라 **브랜드 컬러와 금융 데이터 컬러의 구분이 없습니다.**

### 1-4. 숫자 폰트 부분 적용 — 레이아웃 시프트 위험

`summary-cards.tsx`의 포트폴리오 총액은 일반 bold 텍스트. `market-ticker.tsx`는 `font-mono`. `position-card.tsx`는 `font-bold`(가변폭). 시세가 변경될 때 자릿수가 바뀌면 레이아웃이 밀립니다. Tabular figures 미적용.

### 1-5. 내비게이션 — 정보 과잉, 우선순위 없음

대시보드 상단 nav에 직접 링크 3개 + 드롭다운 3개(AI/Analysis/Tools) + 우측 링크 3개 = 총 9개 진입점이 12px 폰트로 나열됩니다. Bloomberg Terminal도 탭을 그룹핑하지, 이렇게 펼쳐두지 않습니다. 특히 "Analysis" 드롭다운 안에 7개, "Tools" 드롭다운 안에 10개가 들어있습니다.

### 1-6. 포지션 카드 — 정보 밀도 vs. 스캔 속도 미최적화

현재 카드는 7개 섹션(헤더 / 시세&PnL / 매수추천 / 데이터그리드 / 스코어 / TP-SL / 액션버튼)이 세로로 쌓입니다. 포지션 5개만 있어도 스크롤이 길어집니다. Bloomberg 방식이라면 테이블 행으로, Robinhood 방식이라면 카드를 훨씬 압축해 가장 중요한 3가지(시세, PnL, 시그널)만 즉시 보이게 합니다.

### 1-7. 터미널 모드 vs 대시보드 모드 분리 문제

로그인한 사용자는 `Terminal` 컴포넌트를 렌더하는데(`page.tsx` L26), 이 Terminal은 별도 레이아웃으로 `(dashboard)/layout.tsx`의 nav를 사용하지 않습니다. 즉 **로그인 후 보이는 메인화면과 `/market` 같은 하위 페이지가 완전히 다른 레이아웃**입니다. 사용자가 혼란스럽습니다.

---

## 2. 리디자인 방향 — 3가지 옵션

---

### Option A: 미니멀 클린 (토스증권 스타일)

**컨셉:** "필요한 것만, 딱 그것만." 복잡한 쿼트 도구지만 UI는 보험 앱처럼 단순하게. 비전문가도 5초 안에 파악.

#### 색상 팔레트

```
Background:  #FFFFFF (순백)
Surface:     #F7F8FA (토스 그레이)
Card:        #FFFFFF, border: 1px solid #EAECF0
Text-1:      #191F28 (거의 검정)
Text-2:      #6B7684 (미디엄 그레이)
Text-3:      #B0B8C1 (연회색)
Primary:     #3182F6 (토스 블루 — 브랜드 색)
Success:     #00B367 (초록 — 수익 전용)
Danger:      #F04452 (레드 — 손실 전용)
Warning:     #F5A623 (앰버)
```

*주의: Primary(브랜드)와 Success(수익)를 완전히 다른 색으로 분리하는 것이 핵심입니다.*

#### 카드 스타일

```
border-radius: 16px
border: 1px solid #EAECF0
padding: 20px
box-shadow: none (flat)
hover: border-color: #D1D5DB, shadow: 0 2px 8px rgba(0,0,0,0.06)
```

섹션 구분선 대신 **여백**으로만 구분. 불필요한 divider 제거.

#### 네비게이션 패턴

- 상단 바 높이 56px (현재 48px) — 여유 있게
- 탭 5개로 압축: **Portfolio / Market / AI / Tools / Me**
- AI 드롭다운, Analysis 드롭다운, Tools 드롭다운 → "Tools" 단일 드롭다운으로 통합
- 현재 9개 진입점을 5개로 감소
- 모바일: 하단 탭 5개, 아이콘 + 라벨

#### 포지션 뷰 변경

카드 그리드 → **리스트 + 미니 카드 혼합**
- 기본: 각 포지션이 compact list row (60px 높이)
- 탭/클릭 시: 슬라이드다운으로 상세 정보 펼침
- 즉시 보이는 정보: 종목명 / 현재가 / PnL% / 시그널 배지 (4개)

#### 핵심 변경 포인트

1. 로그인 → 대시보드 일관성: 모두 라이트 모드 단일화
2. 포트폴리오 총액 헤더: 텍스트 크기 48px → 56px (더 크게, 더 단순하게)
3. Quant Score 게이지: 숫자만, 바 제거 (바가 의미를 희석시킴)
4. 매수/매도 버튼: 현재 5개 버튼 → Primary CTA 1개 (가장 중요한 액션만)

**적합한 대상:** 금융 초보자, 모바일 중심 사용자, 심플함을 원하는 사람

---

### Option B: 프로 트레이딩 (Bloomberg/TradingView 스타일)

**컨셉:** "정보가 곧 무기다." 다크 배경에 최대 정보 밀도. 트레이더가 1초 안에 시장 전체를 스캔하는 화면.

#### 색상 팔레트

```
Background:  #0A0A0A (최심부 블랙)
Surface-1:   #131313 (패널 배경)
Surface-2:   #1A1A1A (카드 배경)
Surface-3:   #242424 (hover)
Border:      rgba(255,255,255,0.07)
Text-1:      #FFFFFF
Text-2:      #A0A0A0
Text-3:      #555555
Accent:      #2962FF (Bloomberg 블루)
Success:     #00C853 (Bloomberg 그린)
Danger:      #FF1744 (Bloomberg 레드)
Warning:     #FFD600
```

#### 카드 스타일

```
border-radius: 4px (날카로운 — Bloomberg 느낌)
border: 1px solid rgba(255,255,255,0.07)
padding: 12px 16px (컴팩트)
box-shadow: none
hover: background: #1E1E1E
```

모든 숫자 Tabular figures (font-variant-numeric: tabular-nums). 폰트 IBM Plex Mono (이미 설치됨) 시세 데이터 전용.

#### 네비게이션 패턴

- 좌측 수직 사이드바 48px 폭 (아이콘만)
- 아이콘 호버 시 라벨 툴팁 표시
- 상단 bar 없음 → 사이드바가 주 네비게이션
- 콘텐츠 영역 최대화 (Bloomberg 방식)
- 모바일: 하단 탭 (사이드바는 tablet/desktop만)

#### 포지션 뷰 변경

카드 그리드 완전 제거 → **데이터 테이블**
- 각 행: 종목 / 현재가 / PnL$ / PnL% / 시그널 / 스코어 / 시장가치
- 테이블 행 높이 36px
- 헤더 고정, 컬럼 정렬 가능
- 클릭 시 우측 패널(현재 Terminal의 RightPanel과 유사)에 상세 표시

#### 핵심 변경 포인트

1. 전체 앱 다크 테마 통일 (로그인 페이지의 다크 스타일을 앱 전체로 확장)
2. 시장 데이터 영역 확대: 현재 7px 마켓 티커 → 24px 전광판급 행으로 확장
3. 차트 중심 레이아웃: 대시보드의 50% 이상을 차트/데이터 테이블이 차지
4. 컬러 코딩 강화: 모든 시그널(BUY/SELL/HOLD) 셀 배경 컬러 (Bloomberg 터미널 방식)
5. 알림 시스템: 우측 상단 실시간 토스트 (Bloomberg의 플래시 뉴스)

**적합한 대상:** 적극적 트레이더, 데이터 헤비 유저, Bloomberg/TradingView 경험자

---

### Option C: 모던 핀테크 (Robinhood/Webull 스타일)

**컨셉:** "다크하지만 따뜻하다." 완전 다크가 아닌 딥 네이비 계열. 차트와 그래픽이 주인공. Robinhood의 감성 + Webull의 데이터.

#### 색상 팔레트

```
Background:  #0F0F14 (딥 다크 네이비)
Surface-1:   #16161D (카드)
Surface-2:   #1E1E28 (hover, 강조 영역)
Border:      rgba(255,255,255,0.06)
Text-1:      #F2F2F7 (약간 쿨한 화이트)
Text-2:      #8E8EA0 (미디엄 라벤더 그레이)
Text-3:      #52525F
Accent:      #7C3AED (바이올렛 — Robinhood 스타일)
Success:     #22C55E (밝은 초록)
Danger:      #EF4444 (부드러운 레드)
Warning:     #EAB308
Gradient-up: linear-gradient(135deg, #22C55E 0%, #16A34A 100%)
Gradient-dn: linear-gradient(135deg, #EF4444 0%, #DC2626 100%)
```

#### 카드 스타일

```
border-radius: 20px (둥글게 — Robinhood 느낌)
border: 1px solid rgba(255,255,255,0.06)
padding: 20px
background: #16161D
box-shadow: 0 4px 24px rgba(0,0,0,0.3)
hover: transform: translateY(-2px), shadow 강화
```

#### 네비게이션 패턴

- 상단 바 높이 56px, 배경 `#0F0F14`에 glass blur 효과
- 탭 아이콘 + 텍스트 (Robinhood 스타일)
- 5개 핵심 탭: Portfolio / Market / Trade / AI / More
- "More" 탭에 분석 도구 전부 모음
- 탭 활성 시: 배경 `#7C3AED/15`, 텍스트 바이올렛 (현재 에메랄드 대신)
- 모바일: 하단 탭 5개, iOS/Android 네이티브 앱 느낌

#### 포지션 뷰 변경

카드 → **스와이프 가능한 미니멀 카드 리스트**
- 각 카드: 260px 높이 압축 (현재보다 40% 감소)
- 보이는 정보: 종목명/티커 / 차트 sparkline(72h) / 현재가 / PnL% / 시그널
- 우측 스와이프: 빠른 매도 액션
- 좌측 스와이프: 빠른 분석 이동
- Sparkline이 카드의 감성을 높임 (Robinhood의 핵심 UX)

#### 핵심 변경 포인트

1. 포트폴리오 총액 화면 상단에 그래프 + 금액 → 시각적 임팩트 극대화
2. Sparkline 차트를 포지션 카드 안에 삽입 (현재 없음)
3. 색상: 에메랄드 브랜드 → 바이올렛으로 교체 (차별화)
4. PnL이 양수이면 카드 좌측 테두리 초록 glow, 음수이면 레드 glow (감성적 피드백)
5. 온보딩 후 첫 대시보드: 축하 애니메이션 (Robinhood의 confetti)

**적합한 대상:** 25-35세 MZ 투자자, 시각적 경험을 중시하는 사용자, 모바일 우선 트레이더

---

## 3. 옵션 비교 매트릭스

| 기준 | A. 미니멀 클린 | B. 프로 트레이딩 | C. 모던 핀테크 |
|------|---------------|----------------|--------------|
| 개발 난이도 | 낮음 (라이트 테마 유지) | 높음 (전체 다크 전환) | 중간 (신규 토큰 추가) |
| 정보 밀도 | 낮음 | 최고 | 중간 |
| 감성/브랜딩 | 신뢰/안전 | 전문/파워 | 세련/프리미엄 |
| 모바일 최적 | 최고 | 낮음 | 높음 |
| 경쟁 차별화 | 낮음 (토스와 유사) | 중간 | 높음 |
| 기존 코드 수정량 | globals.css만 | 전체 컴포넌트 | globals.css + 카드 컴포넌트 |
| 타깃 유저 | 대중 | 파워유저 | MZ 투자자 |
| 완성까지 예상 시간 | 1-2일 | 4-5일 | 2-3일 |

---

## 4. 공통 필수 수정 사항 (어떤 옵션이든)

어떤 방향을 선택하든 반드시 고쳐야 할 것들:

1. **색상 토큰 정리** — `summary-cards.tsx`의 `#0a1929`, `#003a70`, `notification-bell.tsx`의 `#0d0d12` 제거. 모두 CSS 변수로 교체.
2. **Tabular figures 전역 적용** — 시세/PnL/수량 숫자에 `font-variant-numeric: tabular-nums` 강제. `globals.css`에 `.tabular { font-variant-numeric: tabular-nums; }` 추가.
3. **브랜드 컬러 vs 금융 컬러 분리** — Primary 버튼 색과 수익(Success) 색을 다른 색으로 분리.
4. **로그인 ↔ 대시보드 색상 일치** — 로그인 페이지가 다크라면 대시보드도 다크, 라이트라면 둘 다 라이트.
5. **네비게이션 9개 → 5개 압축** — AI/Analysis/Tools를 의미 있게 통합.

---

## 5. 권장 사항

**상현님 상황 (1인 창업, 빠른 출시, 트레이더 대상)을 고려한 권장: Option C**

이유:
- 기존 다크 스타일(로그인 페이지)과 자연스럽게 연결
- 개발량이 B보다 적으면서 차별화는 A보다 큼
- 현재 에메랄드 → 바이올렛 교체로 토스증권과 완전히 달라짐
- Sparkline은 Recharts(이미 설치됨)로 구현 가능
- 퀀트/AI 기반 플랫폼의 "프리미엄" 이미지와 어울림

단, A옵션이 더 빠른 출시가 필요한 경우 적합합니다.

---

*상현님이 A/B/C 중 선택하시면 해당 옵션의 globals.css 토큰 교체 + 핵심 컴포넌트(summary-cards, position-card, dashboard layout) 리디자인을 진행합니다.*
