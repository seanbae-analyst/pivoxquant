# 지금 상태 — 2026-09-01 실측 스냅숏

> CLAUDE.md 에서 옮겨 온 원문 (2026-09-11). CLAUDE.md 는 매 세션 통째로 컨텍스트에 실리므로 이력·수치 스냅숏은 여기 둔다.
> ⚠️ **2026-09-01 기준이다.** 2026-09-11 에 `https://www.pivoxquant.com/api/health` 가 200 을 냈다 — 아래
> "남은 것: Render 배포" · "로그인 이후가 전부 동작하지 않는다" 는 그 뒤에 바뀌었을 수 있으니 **다시 재고 믿어라.**

## 지금 상태 (2026-09-01 실측)

### 🟡 백엔드 — DB 완료 / 앱 호스팅만 남음

**Supabase Postgres 가동 중.** 프로젝트 `pivoxquant` / `yjiztgummaxecriiuumt` /
ap-northeast-2. 43 테이블 + alembic `049` stamp.
`/api/health` **200 `{"db":"ok"}`**, 로그인 이후 API E2E 통과 (dev-login → 생년월일
게이트 → mirror-home · portfolio · pre-trade 행 INSERT · behavior mirror 전부 200).

- **접속은 session pooler 경유 필수** — `aws-0-ap-northeast-2.pooler.supabase.com:5432`.
  직결 호스트 `db.*.supabase.co` 는 **IPv4 로 해석되지 않는다.**
- **DB 롤은 `postgres` 가 아니라 전용 `pivox_app`.** Supabase 가 postgres 롤
  비번 변경을 막아 우회한 것인데, 결과적으로 이게 데이터를 지켰다 — Supabase 는
  public 스키마를 PostgREST 로 자동 공개하는데 `anon` 에 grant 가 새지 않아
  `/rest/v1/users` 가 **401 `42501`** 을 낸다 (실제 엔드포인트 타격으로 확인).

**남은 것: Render 배포 하나.** `render.yaml` Blueprint 준비 완료.
→ 런북: `docs/ops/backend-restore-2026-09-01.md`

### ✅ 프론트엔드 — prod 라이브
Vercel `www.pivoxquant.com` **200**. 단 `/api` 프록시가 죽은 Railway 를 가리켜
**로그인 이후가 전부 동작하지 않는다.** Render URL 나오면 재연결.
(`vercel` CLI 인증됨. SoT 는 `next.config.ts:9-10` 이 읽는
`RAILWAY_BACKEND_URL` / `NEXT_PUBLIC_API_URL`.)

### 🔴 결제 — 게이트로 비활성
Stripe 통합 완료. `BUSINESS_REGISTRATION` 미완 + 변호사 의견서 대기로 prod 는
503 `BUSINESS_REGISTRATION_PENDING`. 사업자등록 459-01-03808 발급됨.

### 측정값

| 항목 | 값 | 측정 |
|---|---|---|
| 부팅 URL rules | **120** | 2026-09-01 |
| blueprints | **23** | 2026-09-01 |
| pytest | **2007 passed / 0 failed** (18 skip, 1 xfail) | 2026-09-01 (죽은코드 + CAUS 정리 후) |
| vitest | **353 / 353** | 2026-09-01 |
| next build | **36 routes** | 2026-09-01 |
| alembic | 52 revisions, head `049_reflection_observed_context` | 2026-09-01 |

> pytest 가 **2175 → 2007 (-168)** 로 줄어든 것은 회귀가 아니다. 2026-09-01 정리로
> **테스트 대상 자체가 사라져서** 함께 지운 수다:
> - AI 삭제 −36 — 테스트 7파일(31) + `TestLogUsageWrapper`(4) + `TestDiscoverFreshTtlBump`(1)
> - CAUS 삭제 −132 — `test_caus_{scenarios,daily_sweep,auto_fix}` + `test_sim_onboard`
>
> skip 18 / xfail 1 / fail 0 은 정리 전후 동일하고, URL rule 120 · blueprint 23 ·
> vitest 353 · next 36 routes 도 전부 그대로다. 스케줄러 job 만 31 → **30** (CAUS).
> ⚠️ `tests/test_scheduler_cron_jobs.py::EXPECTED_JOB_COUNT` 는 **하드코딩된 수**다 —
> cron job 을 더하거나 뺄 때 같이 고쳐야 한다 (이번에 안 고쳐서 3건 실패했었다).

---

## 🔴 지금 막혀 있는 것 — 하나뿐이다 (2026-09-01)

**Render 배포.** 다른 모든 것이 이것 하나를 기다린다.

1. Render → New Blueprint → 이 레포 (`render.yaml` 을 읽는다)
2. 시크릿 **15칸** 붙여넣기 → **값은 `.secrets/RENDER_PASTE_VALUES.txt`** (gitignore)
   - ✅ **15칸 전부 채워져 있다** (2026-09-01 재실측: 파일의 15개 키 이름이
     `render.yaml` 의 `sync: false` 15개와 정확히 일치, 빈 값 0개).
   - ⚠️ **`BREVO_API_KEY` 는 필요 없다.** 이 파일이 한때 "Brevo 하나만 없다"고
     적었는데 **틀렸다** — HEAD 커밋 `cee3d291` 이 이미 뒤집었다. 전송 캐스케이드는
     SendGrid → Brevo → SMTP 이고 SendGrid·SMTP 자격증명은 `.env` 에 있다. Brevo 는
     **Railway 가 outbound SMTP 를 막아서**(OSError 101) 들어왔던 우회로일 뿐,
     Render 에도 해당한다는 근거는 없다.
   - 교훈은 그대로다: **키를 찾기 전에 `.env` 부터 열어라.** (2026-09-01 에
     "키 4개를 콘솔에서 모아와라"고 안내했다가 틀린 적이 있는데, `.env` 를 안 열어본
     실수였다. FMP·KIS×2 는 그때도 이미 `.env` 에 있었다 — `SHIP_BLOCKERS.md` B5 는
     아직 이 stale 한 4개 목록을 들고 있으니 그쪽을 믿지 말 것.)
3. URL 발급 → `RAILWAY_BACKEND_URL` 채우고 재배포 → Vercel 재연결 → E2E

**OAuth 콘솔은 손댈 필요 없다** (2026-09-01 확인·조치 완료). Google 클라이언트는
그날 삭제돼 있던 것을 **복원**했고 redirect URI 2개(`pivoxquant.com`,
`www.pivoxquant.com`)가 정확하며, 게시 상태를 **테스트 중 → 프로덕션**으로 올렸다
(민감 범위 0개라 Google 심사 불필요). Kakao 앱도 정상, Redirect URI 맞다.
`.env` 의 client id 들이 콘솔 값과 일치함을 교차 확인했다.
