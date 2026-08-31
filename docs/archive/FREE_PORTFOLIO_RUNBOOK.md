# 무료 포트폴리오 모드 — 운영 런북

> PivoxQuant 를 **월 $0 · 무유지보수**로 링크드인 포트폴리오 데모로 유지하기 위한 가이드.
> 검증일 2026-06-20. 데모는 **백엔드 없이 클라이언트 canned 데이터(`frontend/src/lib/demo.ts`)만으로** 완전 동작함이 실측 확인됨.

## TL;DR
데모는 백엔드(Railway)를 **런타임에도 빌드에도 안 쓴다.** 그러니 **Railway 서비스를 내리면 월 비용이 사라지고**, 데모는 Vercel 무료(Hobby) 위에서 그대로 돌아간다. 백엔드 **코드는 레포에 남긴다**(풀스택 깊이를 보여주는 포트폴리오의 본체 — 리크루터가 읽을 수 있음).

## 백엔드 독립 — 증거 (2026-06-20 실측)
로컬 백엔드(`:5050`)를 죽인 상태에서:
- `/portfolio`(가장 무거운 페이지: positions·summary·fx·equity·trades·persona·pulse 훅) → **완전 렌더**, **실패 네트워크 요청 0, 콘솔 에러 0.**
- `/detail/005930`(삼성전자, 커스텀 fetch + KR 경로) → **완전 렌더**(시총 503조·4-pillar).
- 메커니즘: `installDemoFetch()`가 `globalThis.fetch`를 패치해 모든 `/api/*`를 canned 로 가로챔. 페이지는 `"use client"` + SWR 라 서버 fetch 없음.
- 빌드도 Railway 독립: 정적 prerender 실패 페이지(sample-reports / onboarding-broker / paper-trading)는 **빌드때 백엔드를 안 친다**(각각 하드코딩 `generateStaticParams` / `"use client"` / 순수 정적). 그 실패는 아래 "알려진 빌드 flake"(Next16 레이스, Railway 무관)일 뿐.

## 비용 — 끄기 전/후
| 항목 | 지금 | Railway 종료 후 |
|---|---|---|
| **Railway** (Flask 백엔드 + Postgres) | 과금 | **$0** ← 핵심 절감 |
| Vercel (FE) | Hobby = 무료 | 무료 |
| 도메인 `pivoxquant.com` | ~₩15–20k/년 | 선택 (아래) |
| Anthropic / FMP / KIS / SendGrid / Stripe | 백엔드만 사용 | **$0** (백엔드 off → 호출 0) |

## CEO 액션 (대시보드 — 내가 못 하는 부분)
1. **Railway**: 백엔드 서비스(`web-production-7b484b`)와 Postgres 플러그인을 **Pause 또는 Delete**. → 과금 중단. (GitHub auto-deploy 연결도 끊어두면 깔끔.)
2. **Vercel**: 프로젝트가 **Hobby(무료) 플랜**인지 확인(현재 OIDC 토큰상 `hobby`). 데모에 필요한 env 는 `NEXT_PUBLIC_DEMO_MODE=1` + `NEXT_PUBLIC_MIRROR_HOME=true`(+ V2 플래그)뿐. `NEXT_PUBLIC_API_URL`은 **절대 호출되지 않으므로** 둬도 무방(지워도 됨).
3. **도메인**: `pivoxquant.com` 유지(~₩20k/년, 깔끔한 URL — **추천**) vs 무료 `*.vercel.app`로 전환. 링크드인엔 커스텀 도메인이 인상이 좋다.
4. **기타 유료 구독**(FMP 데이터 플랜 등)이 살아있으면 해지 — 백엔드 전용이라 off 후 미사용.

## 무유지보수인 이유
- 데이터가 **정적 canned**(`lib/demo.ts`) — DB·cron·스케줄러·외부 API **0**. 갱신할 게 없음.
- Vercel 이 정적/서버리스로 자동 서빙 + push 시 자동 재빌드. 서버 관리 대상 없음.
- 한 번 잘 배포해두면 **동결된 포트폴리오 피스**로 그냥 살아있음.

## 알려진 빌드 flake (Railway 무관 — 당황 금지)
로컬 `next build`가 비결정적으로 실패(`Expected workStore to be initialized`)할 수 있음 — Next 16.2.6 Turbopack 병렬 prerender × 루트 layout `cookies()/headers()` 레이스. **Vercel 빌드는 같은 커밋을 통과**(라이브 200). Vercel 배포가 어쩌다 실패하면 **재배포(Redeploy) 한 번**이면 됨 — Railway 와 무관. (상세: 메모리 `local-prod-build-and-vitest-flakes`.)

## 절대 지우지 말 것
`pivoxquant/` 백엔드(`services/`·`routes/`·`models/`·`migrations/`)와 `frontend/` 전체 소스. 데모는 안 쓰지만 **풀스택 역량의 증거**이자 포트폴리오의 본체다. "안 돌린다"와 "지운다"는 다르다 — **끄되, 남긴다.**
