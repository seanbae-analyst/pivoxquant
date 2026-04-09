# StockPilot Frontend — Session Handoff

## 현재 상태 (2026-04-07)

### 아키텍처
- **Next.js 16** App Router + TypeScript + Tailwind
- **SWR** for data fetching (hooks in `src/lib/hooks.ts`)
- **API endpoints** centralized in `src/lib/endpoints.ts` (no magic strings)
- **Auth** via `src/lib/auth.tsx` (AuthContext + Flask session cookies)

### 라우트 구조
```
/ .............. Landing page (비로그인시)
/login ......... 로그인/회원가입
/onboarding .... 투자성향 온보딩 (신규 유저)
/home .......... 포트폴리오 대시보드 (메인 페이지)
/dashboard ..... → /home 리다이렉트
/market ........ 시장 오버뷰 (Overview/Intraday/Scanner 탭)
/detail/[ticker] 종목 상세 분석
/autotrade ..... 오토트레이딩
/alerts ........ 알림
/trades ........ 매매 기록
/watchlist ..... 관심종목
/morning ....... Morning Brief
/glossary ...... 용어 사전
```

### 네비게이션
- **상단 탭** (사이드바 제거됨): Portfolio / Market / Trading / Alerts / Trades
- **모바일**: 하단 탭 (md:hidden)

### 디자인 현황 — ⚠️ UI 리디자인 필요
현재 디자인은 기본 shadcn + 수동 색상 조합이라 **프로 수준이 아님**.
다음 세션에서 **Tremor (무료)** 또는 **Figma 템플릿 구매**로 디자인 시스템 교체 예정.

현재 color scheme (`globals.css`):
- Background: #f5f5f7 (연한 그레이)
- Card: #ffffff
- Primary: #1b4dff (블루)
- Success: #00b386 / Destructive: #e5334b
- Font: IBM Plex Sans + IBM Plex Mono

### 핵심 파일
- `src/app/globals.css` — 전체 색상/테마 변수
- `src/app/layout.tsx` — 루트 레이아웃 (폰트 설정)
- `src/app/(dashboard)/layout.tsx` — 대시보드 레이아웃 (헤더+네비+마켓티커)
- `src/app/(dashboard)/home/page.tsx` — 메인 포트폴리오 대시보드
- `src/lib/endpoints.ts` — API URL 상수
- `src/lib/hooks.ts` — SWR 데이터 페칭 훅
- `src/lib/types.ts` — TypeScript 타입 정의

### 백엔드 연동
- 프록시: `next.config.ts`에서 `/api/*` → `http://localhost:5050/api/*`
- 백엔드: Flask (app.py = create_app factory, 189줄)
- DB: SQLite (stockpilot.db)
- 백엔드 기동: `python3 run.py` (port 5050)

### 중요 원칙
- **백엔드 코드 건들지 말 것** — UI 작업은 `frontend/src/` 안에서만
- **endpoints.ts의 URL 변경 금지** — 백엔드 라우트와 1:1 매핑
- **hooks.ts의 SWR 키 변경 금지** — 캐시 무효화 문제 발생
- **types.ts는 추가만 가능** — 기존 타입 필드 삭제/이름변경 금지 (백엔드 응답과 매핑)
- **디자인 변경 시 컴포넌트 파일만 수정** — lib/ 폴더의 로직 파일은 건들지 않기

### TODO (다음 세션)
1. [ ] Tremor 또는 프리미엄 템플릿으로 디자인 시스템 교체
2. [ ] 대시보드 UI 완전 재디자인
3. [ ] 투자성향 온보딩 기능 구현 (백엔드 + 프론트)
4. [ ] 테스트 추가 (pytest + Jest)

@AGENTS.md
