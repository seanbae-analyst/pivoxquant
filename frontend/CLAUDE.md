# PivoxQuant Frontend — Session Handoff

> ⚠️ 2026-05-24 현행화. 이 파일은 오랫동안 "2026-04-12 FRONTEND RESET — 모든
> 페이지 삭제, 처음부터 재구축 중" 상태로 STALE 했다. 실제로는 71개 page.tsx +
> 197개 컴포넌트가 완성·배포되어 prod 라이브 중이다. 옛 "TODO: 랜딩/로그인/
> 대시보드 만들기" 목록은 전부 완료되어 삭제했다.

## 현재 상태 (2026-05-24 실측)
- **prod 라이브** — Vercel `pivoxquant.com` (베타 게이트 307), Next.js 16.
- **71개 page.tsx / 197개 컴포넌트 / vitest 454 통과 / tsc clean.**
- V2 디자인 플래그 9개(login/signup/home/portfolio/signals/reports/risk/settings/
  profile) 모두 prod true. 각 페이지의 `_v1/` 는 dynamic-import 롤백 보험 — 함부로
  삭제 금지(Vercel env 9개 모두 true 확인 후에만 제거 가능).

## 아키텍처
- **Next.js 16** App Router + TypeScript + Tailwind 4 + SWR + motion/react
- **SWR** 데이터 페칭 (`src/lib/hooks.ts`, 24개 훅)
- **API endpoints** `src/lib/endpoints.ts` 에 중앙화 (백엔드 1:1 매핑)
- **Auth** `src/lib/auth.tsx` (AuthContext + Flask 세션 쿠키)
- **프록시**: `next.config.ts` → `/api/*` → `http://localhost:5050/api/*`

## 디자인 시스템 — v3 락-인 (Vantablack + Bronze + Playfair + KR 컨벤션)
> 상세: 메모리 `project_design_v3.md`. 옛 Supanova "Warm Gold #E2B96F" 는 폐기.
- **Base**: Vantablack (#050505) + Bronze accent (`--pq-bronze` 184,149,106)
- **Heading**: Playfair Display (editorial) / **Body**: Pretendard / **Numbers**: IBM Plex Mono
- **가격 방향 (KR 컨벤션)**: 상승 = carmine `--up #D18888` / 하락 = indigo `--down #7AA0C8`.
  `lib/format.ts` 의 `pctColor()` / `PRICE_COLOR_HEX` 가 SoT. 평가 토큰
  `--pq-positive`(bronze) / `--pq-negative`(carmine) 은 **시그널 평가 라벨 전용**이며
  가격 방향에 쓰면 안 됨(2026-05-24 반전 버그 fix). 토큰 drift 는 `design-token-drift` skill 가드.
- **BANNED**: Inter, violet/purple AI gradient, neon glow, raw hex(토큰만)
- **italic**: 전역 제거됨 (CEO 2026-06-15 "이탤릭 이상한거 다 빼라" — 옛 "전역 sweep 금지" 결정 폐기).
  모든 장식 italic(Playfair 헤딩·워드마크·히어로 강조·캡션 + globals.css 편집 규칙) upright 전환.
  className `italic` 0건 / inline `fontStyle:"italic"` 0건 — `not-italic`·next/font italic cut·PDF `em` 규칙만 보존.
  **신규 컴포넌트도 italic 금지.** 상세 메모리 `project_design_v3.md`.

## 중요 원칙
- **백엔드 코드 / endpoints.ts URL / hooks.ts SWR 키 변경 금지** (백엔드 1:1 매핑)
- **types.ts 추가만 가능** — 기존 필드 삭제/이름변경 금지
- 기존 기능 100% 보존 (메모리 `feedback_feature_preservation`) — 리디자인 시 빠지는 기능 없게

@AGENTS.md
