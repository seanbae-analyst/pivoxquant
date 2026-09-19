# 지금 상태 — 2026-09-12 실측 스냅숏

> CLAUDE.md 에서 옮겨 온 파일 (2026-09-11). CLAUDE.md 는 매 세션 통째로 컨텍스트에 실리므로 이력·수치 스냅숏은 여기 둔다.
> 아래 09-12 절이 현재 상태, 그 밑 09-01 절은 **이력**이다(백엔드 재구축 당시 기록 — 지금은 해소됨).
> 수치는 측정 시각과 함께 적는다. 오래됐으면 다시 재라.

## 변경 2026-09-19 — 만 14세 확인: 생년월일 입력 → 자가선언 체크 (CEO "굳이 14세 이거 필요함?" → "그렇게 해")

- **왜**: PIPA §22⑥ 은 14세 미만을 걸러낼 장치를 요구하지, 생년월일 수집을 요구하지 않는다. 생년월일은 이 게이트 말고 어디서도 안 쓰였다(grep 실측). 자가선언 체크는 동의 스택에 이미 있었다.
- **어떻게**: `users.age_confirmed_at`(053 + `_do_migrations` 가드) 신설. `/api/auth/oauth-finalize` 필수 동의 4종(`terms/non_advisory/cross_border/age`), 본문의 `birthdate` 는 무시. 게이트 403 코드 `AGE_CONFIRMATION_REQUIRED`, `/me` 는 `age_confirmation_required`(+ `birthdate_required` 별칭, 2026-10-19 이후 제거). 기존 가입자는 `birthdate` 가 있으면 확인된 것으로 간주 — 재입력 없음. `users.birthdate` 컬럼과 값은 **남겨 둔다**(삭제는 CEO 결정).
- **방침**: `privacy-ko.md` §1.1·§3 에서 생년월일 삭제, §11 자가선언으로 정정, 변경 이력 1행. 자문 큐 **Q9(자가선언 충분성)** 는 그대로 열려 있다.
- **실측** (2026-09-19, 로컬 SQLite 부팅 + dev-login): `age` 누락 → 400 `consents_required`, `birthdate` 섞인 본문 → 200 + DB `birthdate NULL / age_confirmed_at 기록`, 재전송 → 200 멱등.

## 지금 상태 (2026-09-12 실측, HEAD `b6c451b3`)

### ✅ 백엔드 — Render 라이브 (free 플랜)

`https://pivoxquant-api.onrender.com/api/health` → **200** `db:ok · missing_required:0 · missing_recommended:1 (SENDGRID_WEBHOOK_PUBLIC_KEY) · version v37+` (2026-09-12 21:51 KST, curl).
- **콜드스타트 43.9초** (같은 curl, `time_total`). free 플랜은 유휴 시 spin-down 하고, 스케줄러가 인프로세스(`RUN_SCHEDULER`)라 **잠들면 크론(52주·집중도 알림, 메일 큐)도 같이 멈춘다.** 09-12 에 `#572`→`#575` 로 스케줄러를 껐다 켰다.
- DB Supabase Postgres, session pooler 경유, 롤 `pivox_app` (규칙은 CLAUDE.md "지금 상태").

### ✅ 프론트엔드 — Vercel 라이브
`https://www.pivoxquant.com/api/health` → **200**, 0.69초 (2026-09-12 21:51 KST). 프록시가 Render 를 가리킨다 (B6, 09-04 완료).
🟡 **인증 이후 화면의 브라우저 실렌더는 아무도 못 봤다** — agent 브라우저가 조직 정책으로 pivoxquant.com 을 못 연다. `SHIP_BLOCKERS.md` B7. CEO 가 직접 로그인해 `/mirror` · `/portfolio` · `/pre-trade` · `/journal` · `/settings` 를 한 바퀴 돌면 닫힌다.

### 🔴 결제 — 게이트로 비활성 (변동 없음)
prod 503 `BUSINESS_REGISTRATION_PENDING`. 무료 베타라 켤 이유가 없다.

### 측정값

| 항목 | 값 | 측정 |
|---|---|---|
| 부팅 URL rules | **121** | 2026-09-12 (`RUN_SCHEDULER=0 POPULATE_CACHE_ON_BOOT=0` 부팅 프로브) |
| blueprints | **23** | 2026-09-12 |
| pytest | **2222 passed / 0 failed** (18 skip, 1 xfail, 604s; 09-11 야간 2194 대비 +28) | 2026-09-12 (`./venv/bin/python -m pytest -q`) |
| vitest | **379 / 379** (52 files; 09-11 야간 380 대비 −1, 어느 테스트가 빠졌는지는 미확인) | 2026-09-12 (`npx vitest run`) |
| alembic | 53 revisions, head `050_onboarding_v3_declared` | 2026-09-12 (`ls migrations/versions/*.py`) |
| 야간 게이트 (참고) | pytest 2194/0 · vitest 380/380 · tsc·eslint·build 0 · 계약 74/74 | 2026-09-11 03:00, HEAD `a6cf9d99` — 오늘 13 PR 이전 값 |

### 오늘 남은 결함 (스윕 재현 완료, 미수정)
`BUG_SWEEP_2026-09-12.md` P2 2건: ① `terms-ko.md`/`privacy-ko.md` 렌더에서 `unbreakKoreanBold` 정규식이 `**` 리터럴을 남긴다(면책 문구 파손) ② 인증 라우트마다 `/api/alerts` 401 콘솔 에러(SWR 키 무게이트). P1 4건은 이월.

### 막혀 있는 것 (2026-09-12)
코드가 아니다. **R1 변호사 의견서**(미팅 미예약) · **R8 FMP Data Display Agreement**(09-10 문의 접수, 회신 대기) · **B7 CEO 브라우저 로그인 1회**. 상세는 `SHIP_BLOCKERS.md`.

---

# 이력 — 2026-09-01 실측 스냅숏 (백엔드 재구축 당시)

> ⚠️ 아래는 **2026-09-01 기준 기록**이다. "남은 것: Render 배포" 는 09-04 에 끝났고, "로그인 이후가 전부 동작하지 않는다" 도 B6 로 해소됐다. 함정·교훈(pooler · `pivox_app` 롤 · `.env` 먼저 열기)만 여전히 유효하다.

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
