# PivoxQuant — 세션 컨텍스트

> **2026-09-01 전면 재작성.** 이전 판은 자기 자신과 모순돼 있었고(같은 파일이
> "135 rules"와 "141 rules"를 동시에 적고 있었다), 이미 삭제된 것들을 살아있다고
> 기술했다. 그 결과 이 파일을 읽은 세션이 잘못된 판단을 반복했다.
>
> **이 파일의 규칙: 잰 것만 적는다. 재는 방법을 같이 적는다.**
> 숫자를 갱신할 땐 아래 §검증 명령을 실제로 돌리고 그 출력을 적을 것.
> 모르면 "확인 불가"라고 적는다. 추정을 사실처럼 적지 않는다.
> 상세 이력은 `HANDOVER.md` 와 `docs/ops/backend-restore-2026-09-01.md`.

---

## 이 파일을 믿기 전에

수치는 **측정 시각과 함께** 적혀 있다. 오래됐으면 다시 재라.

```bash
# 부팅 — URL rule / blueprint 수
RUN_SCHEDULER=0 POPULATE_CACHE_ON_BOOT=0 ./venv/bin/python -c "
from app import create_app
a=create_app(); print('rules', len(list(a.url_map.iter_rules())), '| bp', len(a.blueprints))"

# 백엔드 테스트
./venv/bin/python -m pytest -q | tail -2

# 프론트
cd frontend && npx vitest run && npx tsc --noEmit && npm run lint && npm run build
```

---

## 제품

**기록(記錄) 중심 개인 투자 회고 도구.** 유저가 이미 들고 있는 포트폴리오를 읽고,
사기 전에 멈춰 이유를 적게 하고, 그 기록을 나중에 거울처럼 되비춘다.
루프는 하나다 — **멈춤 → 기록 → 거울.**
미국 + 한국 주식. 1인 창업자(배상현). 클로즈드 베타, 무료.

### 핵심 3축 (측정 2026-09-01)

| 화면 | 하는 일 | 시세 필요? |
|---|---|---|
| `/pre-trade` **멈춤** | 사기 전 7문항 기록. 쿨다운은 현재 **0초** (`DEFAULT_COOLDOWN_SECONDS=0`, CEO가 제거) — 지금의 마찰은 시간이 아니라 질문 자체다 | ❌ |
| `/journal` **기록** | 기록 + behavior mirror 5종 (보유기간/회전율/집중도/물타기/손익처분) | ❌ |
| `/mirror` **거울** (홈) | 선언 페르소나 vs 관찰 페르소나(30일 9차원)의 **간극** + 드리프트 | ❌ |

**셋 다 시세를 한 번도 안 부른다.** `services/behavior/*.py` 전부 시세 서비스를
import 하지 않으며, `averaging_down_mirror.py` 가 자기 docstring 에
*"no network, no live price / FX call"* 이라고 적어 뒀다. 의도된 설계다.

시세는 **오직 `/portfolio` 의 평가액(NAV·미실현손익·섹터비중)** 때문에 존재한다.
이 사실이 데이터 라이선스 문제의 출구다 — 평가액을 유저 본인 계좌에서 받으면
FMP 재배포 문제와 R7 이 함께 닫힌다.

### 나머지 화면
`/portfolio` (보유·NAV·거래내역) · `/profile` (페르소나·펄스·데이터 내보내기/삭제)
· `/settings` · `/support/contact` · `/support/inbox`

---

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

## 🔴 지금 막혀 있는 것 — 하나뿐이다

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

---

## 기술 스택

- **Backend**: Flask + SQLAlchemy + PostgreSQL(Supabase) / SQLite(local)
- **Frontend**: Next.js 16 + TypeScript + Tailwind 4 + SWR + motion/react
- **AI**: **없음 — 코드까지 삭제됨.** 2026-09-01 지원 챗봇 제거로
  `ANTHROPIC_API_KEY` 의 마지막 실사용처가 사라졌고, 같은 날 죽은 코드를
  **트리에서도 걷어냈다**: `services/ai/`(9개 공개 메서드 + 3개 모델 클래스),
  `services/ai_budget.py`, `container.ai` 싱글턴, `fetcher.score_news_sentiment`
  (+`_score_news_with_ai`/`_score_news_keywords`), `cache_service` 의
  `ai_result_cache_*`/`earnings_tone_*`. 전부 **호출처 0곳**임을 확인 후 삭제했고,
  삭제 전후 URL rule 120 / blueprint 23 이 동일하다. 런타임에 Claude API 를 한 번도
  부르지 않는다. 되살릴 거면 **소비자부터** 만들 것 (원본은 `git show cee3d291:services/ai/service.py`).
  ⚠️ `anthropic_usage_log` 테이블 + migration 042 + `scripts/nightly/
  anthropic_cost_estimate.py` 는 **남겼다** — `pipa_purge` 가 참조한다.
- **Broker**: KIS 한국투자증권 (read-only — `services/kis/service.py` 의
  `KIS_READ_ONLY` 가드 3곳). Alpaca 는 데이터 fallback stub 만
  `ALPACA_ENABLED` 게이트(기본 OFF)로 잔존
- **Data**: FMP + KIS. ⚠️ **FMP 약관 §2.2.2 — 별도 Data Display Agreement 없이는
  유저에게 표시 금지.** *"complimentary or paid"* 를 명시하므로 **무료 서비스도
  해당된다.** R7(KIS 시세 재배포)의 미장 버전이며 **미해결**
- **Auth**: Google + Kakao OAuth (이메일+비번 없음)
- **Payment**: Stripe (게이트로 비활성)
- **Design**: v3 락-인 — Vantablack + Bronze + Playfair + KR 컨벤션

---

## 구조

### 백엔드 (2026-09-01 실측: blueprint 23 / URL rule 120)

```
app.py              # create_app() factory  ⚠️ L414 에서 db.create_all() 무조건 실행
config.py · extensions.py · security.py · run.py (5050)
models/ · migrations/   # alembic 리비전 전량 보존 — 삭제 금지
routes/   alerts · auth(+auth_alias) · behavior · billing · consents · data_status
          · dev_auth · email_preferences · feedback · health · inbox
          · market · mirror_home · notifications · portfolio · pre_trade
          · profile · push · realtime · sendgrid_webhook · support · trades
          (조건부·부팅 시 미등록: command_center=opt-in. 위 23 카운트에 없다.
           sim_onboard 은 2026-09-01 CAUS 와 함께 삭제 — 함정 §7)
services/ behavior · broker · customer · data · email · inbox · kis
          · legal · marketing · mock_data · observability · portfolio
          · pre_trade · profile · scheduler · support · tax · trading
```

**`routes/market.py` 는 2026-09-01 에 18 → 4 라우트로 줄었다**
(`/search` · `/market/fx` · `/market/indices` · `/public/market-snapshot`).
나머지 14개는 8-31 prune 으로 사라진 화면의 잔재였고 **FMP 를 가장 많이 쓰던
것들**이다. 되살리지 마라.

**퀀트 코드는 없다.** `services/quant/` 는 2026-08-31 통째로 삭제됐다.
autotrade 는 2026-05-05 물리 삭제 (투자일임업 회피).

### 프론트엔드 (2026-09-01 실측: `page.tsx` 보유 디렉터리)

```
frontend/src/app/(dashboard)/
  mirror · portfolio · pre-trade · journal · profile
  settings(+/profile) · support/contact · support/inbox(+/[id])
```
nav(`terminal-sidebar.tsx` / `bottom-nav.tsx`)에 있는 것 = 유저가 갈 수 있는 곳.
`/home` 은 삭제 → `/mirror` 로 308.

⚠️ **프론트가 어떤 API 를 쓰는지 볼 땐 경로 문자열로 grep 하지 마라.**
컴포넌트는 `endpoints.ts` 의 **심볼**(`API.market.fx` 등)로 호출한다. 경로 리터럴
매칭은 실사용처를 전부 놓친다 — 2026-09-01 에 이걸로 틀린 결론을 냈다.
심볼을 먼저 찾고 그 심볼의 소비자를 추적할 것.

---

## ⚠️ 함정 — 여기서 사람들이 틀린다

### 1. 빈 DB 를 alembic 으로 세우려 하지 마라

이전 문서는 *"alembic 리비전 52개로 스키마 100% 재현 가능"* 이라고 했다.
**틀렸다.** 빈 DB 에 `flask db upgrade` 를 걸면 **004 에서 DuplicateTable 로
죽는다** (실측). `app.py:414` 의 `db.create_all()` 이 조건 없이 돌고, alembic 의
`migrations/env.py` 는 Flask 앱을 import 해야 동작하기 때문이다 — alembic 이
시작하기도 전에 create_all 이 전부 만들어 놓는다.

**스키마의 SoT 는 ORM 모델**이고 alembic 은 이력이다. 빈 DB 순서:

```bash
# ① 앱을 DATABASE_URL 만 걸고 1회 부팅 (create_all 이 스키마 생성)
# ② 반드시 stamp — 빼먹으면 alembic_version 이 없어 이후 마이그레이션이
#    001 부터 다시 돌다 영구히 깨진다
./venv/bin/python -m flask db stamp head
```

### 2. `.env` 가 `override=True` 다

`app.py:13` 이 `load_dotenv(..., override=True)`. **셸 환경변수를 `.env` 가
덮어쓴다.** `RUN_SCHEDULER=0` 을 앞에 붙여도 `.env` 에 `=1` 이 있으면 스케줄러가
뜬다. 로컬에서 prod 환경을 재현하려면 `.env` 를 잠시 치워야 한다.

### 3. 로컬 dev 서버는 demo fixture 를 서빙할 수 있다

`.env.local`(gitignore)의 `NEXT_PUBLIC_DEMO_MODE=1` 이면 백엔드가 아니라
canned fixture 를 본다. `=0` 으로 띄울 것.

### 4. Template Hardcoding Guard 는 현재 **방어선 0개**다

문서는 오래 "이중 방어"라고 적혀 있었지만 둘 다 동작하지 않는다 —
CI 스캔 대상 `services/artifacts/templates/` 는 8-31 prune 으로 **없어졌고**
(→ 대상 0개로 공허하게 green), `tests/test_no_hardcoded_samples.py` 는 **파일이
존재하지 않는다.** 지킬 템플릿이 사라졌으니 정합이지만, **그 green 을
"하드코딩 없음"의 증거로 읽으면 안 된다.**

살아있는 legal 방어선은 이쪽이다 (2026-09-01 실측 **228 passed**):
```bash
./venv/bin/python -m pytest tests/test_disclaimer_sot.py \
  tests/test_forbidden_terms_sync.py tests/test_legal_deep_scan_local.py \
  tests/test_legal_filter.py tests/test_legal_filter_forbidden_parity.py \
  tests/test_legal_scrub_decorator.py tests/test_pivoxaudit_secret_leak.py
```
⚠️ 이 green 이 실제로 무엇을 보장하는지는 **함정 §10** 을 먼저 읽어라 —
2026-09-01 까지 이 스위트는 green 이면서도 `scrub_response` 의 최상위 문자열
구멍을 못 잡고 있었다 (테스트가 dict 페이로드만 덮었다).

### 5. 로컬 grep 은 `ugrep`, 파이썬은 3.12 다

`grep` 은 BSD 도 GNU 도 아닌 **ugrep**(`-P` 지원). 옛 "macOS BSD grep 은 -P
미지원" 경고는 이 머신에선 성립하지 않는다. 다만 CI 는 GNU grep 이므로
`-Pzo` 동작이 같다고 가정하지 말고 **판단은 pytest 를 SoT 로** 삼는다.

**로컬 venv 는 Python 3.12, 프로덕션은 3.11**(`runtime.txt`, `Dockerfile`).
이 머신에 3.11 이 없어 **프로덕션 파이썬으로는 아무것도 검증하지 못한다.**
호환성은 이력이 보증할 뿐 측정된 게 아니다. Docker 도 없어 이미지 빌드는
미검증 — Render 첫 빌드가 둘을 동시에 검증하는 지점이다.

### 6. 로컬 pre-commit legal-guard 는 **추가된 줄만** 스캔한다

기존 코드의 금지어는 안 걸리고 새로 추가한 줄만 걸린다. 의도된 경우 그 줄에
`// legal-ok` 를 단다. `# noqa: legal` 도 훅은 받지만 **ruff 가 자기 지시어로
오해해 경고**를 내므로 전자를 쓸 것.

---

### 7. CAUS 는 **삭제됐다** (2026-09-01) — 되살리지 마라

Continuous Autonomous User Simulation(브라우저 sim 유저 1명/일). **CEO 결정으로
retire.** 시나리오가 겨냥하던 URL 10개 중 9개가 8-31 prune 으로 사라져서 매일 도는
QA 가 **없는 제품을 검사**하고 있었고, 산출물은 오탐 아니면 `SKIPPED` 뿐이었다.

지운 것: `scripts/caus_daily_sweep.py` · `caus_auto_fix.py` · `caus_scenarios/`(12)
· `check_caus_today.sh` · `routes/sim_onboard.py` · 스케줄러 `ops_caus_daily_sweep`
등록 · 테스트 4종(`test_caus_*` 3 + `test_sim_onboard`) · `SIM_ONBOARD_SECRET`
배선 전부 · `docs/qa/auto-sim-reports/`(43) · `docs/specs/continuous-user-sim-spec.md`
· **`playwright` 의존성**(삭제 후 import 0곳).

⚠️ **`users.is_simulated` 는 남겼다** — 지우지 마라. migration 032 + 모델 컬럼 +
이메일/푸시의 `is_simulated` 가드가 **합성 유저에게 실제 메일·푸시가 나가는 걸
막는다.** `scripts/qa/virtual_user_sweep.py` 가 아직 sim 유저를 만들기 때문에 이
가드는 여전히 살아있는 방어선이다 (`services/email/sender.py:269`,
`services/email/{sendgrid,brevo}_provider.py`, `services/push_service.py:59`,
`services/customer/inactive_nudge.py:125`).

검증: 삭제 전후 URL rule 120 · blueprint 23 동일. `SIM_ONBOARD_SECRET=x` 를 세팅하고
부팅해도 120/23 그대로 — blueprint 가 실제로 사라졌다는 뜻이다.

### 8. `services/access_guard.py` 는 **호출처 0곳**이다 (의도적으로 남김)

`is_user_allowed_ticker()` / `access_denied_response()` — §101 회피용 화이트리스트
가드인데 **프로덕션 호출처가 없다.** `tests/test_access_guard.py` 만 부른다
(2026-09-01 전수 grep 확인). 이걸 걸던 endpoint 들이 prune 으로 사라졌기 때문.

**죽은 코드지만 2026-09-01 정리에서 일부러 남겼다** — 법무 성격의 가드를 agent
판단으로 지우는 건 범위를 넘는다. 되살릴 거면 §101 게이트가 필요한 route 에
붙이고, 영영 안 쓸 거면 테스트와 함께 지울 것. **"테스트가 green 이니 가드가
동작 중"으로 읽지 말 것** — 가드는 아무것도 안 지키고 있다.
### 9. Docker 빌드 컨텍스트 — `.dockerignore` 를 지워도 되는 파일로 착각하지 마라

`render.yaml` 이 `runtime: docker` 로 빌드하고 `Dockerfile` 끝이 `COPY . .` 다.
2026-09-01 까지 **`.dockerignore` 가 없었다** — 빌드 컨텍스트 전체가 이미지에
들어갔다는 뜻이다. 로컬 기준 ~1.7 GB(`node_modules` 815M · `.next` 587M ·
`venv` 179M · `.git` 157M)가 불필요하게 실렸고, 더 중요한 건 **로컬에서
`docker build .` 를 하면 `.env` 와 `.secrets/` 가 이미지 레이어에 구워진다**는
점이었다. (Render 는 레포를 clone 하므로 gitignore 된 그 둘은 원래 없었다 —
로컬 빌드만의 문제였지만 실재하는 유출 경로였다.)

⚠️ **`.dockerignore` 에서 `docs/` · `frontend/` · `tests/` · `scripts/` 를 빼지 마라.**
크게 보여도 **런타임에 읽힌다** — 인프로세스 APScheduler(`RUN_SCHEDULER=1`)가
`scripts/nightly/*` 크론 30개를 돌리고, 그중 legal scan 은 `frontend/` 소스에서
금지어를 훑고, `marketing_daily_dispatch` 는 `docs/marketing/content-bank.json`
+ `week1-cards/*.png` 를 읽고, ship-blocker 잡은 루트 `SHIP_BLOCKERS.md` 를 읽는다.
지우면 **조용히** 깨진다 (크론은 best-effort 로 예외를 삼킨다).


### 9-2. CSP `connect-src` 는 **Render** 를 가리킨다 (2026-09-01 교체)

`frontend/middleware.ts` 의 CSP 백엔드 호스트가 `https://*.railway.app` 이었다.
Railway 계정은 삭제됐고 백엔드는 Render 로 간다 → `https://*.onrender.com` 으로
바꿨다.

지금 당장은 아무것도 안 깨졌었다 — `lib/endpoints.ts` 가 `API_BASE = ""` 라
모든 호출(포트폴리오 SSE 포함)이 same-origin 이고 Next rewrites 가 /api 를
프록시하므로 `'self'` 로 이미 커버된다. **이 항목은 백엔드 오리진에 직접
붙는 순간에만 의미가 있다.** 문제는 그때 죽은 플랫폼이 적혀 있으면 **조용히**
실패한다는 것 — CSP 위반은 콘솔에만 뜨고 네트워크 에러로도 안 잡힌다.

⚠️ `RAILWAY_BACKEND_URL` **환경변수 이름은 일부러 안 바꿨다.** `render.yaml` ·
`frontend/next.config.ts` · `routes/auth.py` · **Vercel 대시보드**가 동시에
이 이름에 걸려 있어서, 넷 중 하나만 바꾸면 `/api` 프록시가 죽는다. 이름은
틀렸지만 값은 Render URL 이 들어간다. 바꾸려면 **네 곳을 한 번에** 바꿔라.

### 10. 법적 스크럽은 **구현이 하나**다 — 두 번째 복사본을 만들지 마라

2026-09-01 정리 중 발견. `services/legal_filter.scrub_response()` 와
`routes/decorators._deep_scrub()` 가 **같은 딥 스크럽 로직을 각자 구현**하고
있었고, 이미 갈라져 있었다:

| | legal_filter.scrub_response (구) | decorators._deep_scrub (구) |
|---|---|---|
| 최상위 문자열 | **스크럽 안 함** ← 취약점 | 스크럽함 |
| 입력 dict | **제자리 변형** ← 캐시 오염 | 새 객체 반환 |
| 테스트 | 있음 | 없음 |
| 프로덕션 사용 | **0곳** | 라우트 12곳 |

즉 **테스트된 쪽은 안 쓰이고, 쓰이는 쪽은 테스트가 없었다.** 그리고 테스트된
쪽에는 실제 구멍이 있었다 — `scrub_response("you should buy now")` 가 문구를
**그대로 반환**했다. `__all__` 에 노출돼 있어 누가 bare string 을 반환하는
엔드포인트에 쓰면 자본시장법 경계가 통째로 우회됐을 것이다.

지금은 `scrub_response()` **하나**이고 `_deep_scrub` 은 얇은 별칭이다(로그
context 만 다름). 회귀 테스트 4종 추가:
`test_bare_top_level_string_is_scrubbed` · `test_does_not_mutate_caller_payload`
· `test_decorator_helper_shares_one_implementation` (+기존 nested).

**교훈: 법적으로 중요한 규칙은 구현이 둘이면 반드시 갈라진다.** 라우트 쪽에
"편의 헬퍼"를 새로 만들지 말고 `services/legal_filter` 를 불러라.

### 11. 메모리 디렉터리가 **두 개**다 — 어느 쪽인지 확인하고 써라

```
~/.claude/projects/-Users-seanbae-Desktop---/            ← 123 files, 장기 메모리
~/.claude/projects/-Users-seanbae-Desktop----pivoxquant/ ←  20 files, 이 세션 auto-memory
```

`scripts/legal/lawyer_packet_build.py` 는 **전자**를 읽고(`legal_question_queue.md`
396줄이 거기 있다), 이 파일의 §제품 전제 절은 **후자**를 가리킨다. 둘 다 맞지만
**같은 곳이 아니다.** `legal_question_queue.md` / `DECISIONS.md` /
`business_registration.md` 는 전자에만 있다. 파일이 "없다"고 결론내기 전에
**두 경로를 다 확인**할 것 (2026-09-01 에 이걸로 버그를 오진할 뻔했다).

## 중요 원칙

- 🔴 **최신 정보 파악** — **코드/수치** = grep·Read 실측 (기억 인용 금지) /
  **시장·경쟁·규제** = WebSearch + 출처 날짜 확인 / **결정**(가격·법·수익모델) =
  메모리 `DECISIONS.md`.
- 🔴 **주장 범위 = 측정 범위.** 한 파일 재고 "전체가 그렇다"고 하지 마라.
  "~뿐이다 / 없다" 를 말할 프로브엔 `head` 를 걸지 마라. 결과를 말할 때 **무엇을
  쟀는지 같이** 적어라. (2026-09-01 에 이 규칙을 어겨 여러 번 틀렸다.)
- **API endpoint URL 변경 금지** — `frontend/src/lib/endpoints.ts` 와 1:1
- **routes/ · models/ · services/ 구조 유지**
- **시그널 라벨: POSITIVE / NEGATIVE / NEUTRAL** — BUY·SELL·HOLD 절대 금지 (자본시장법)
- **"AI Assistant"** — "AI Coach" · "투자 코치" 금지
- **추천·조언 언어 금지** — recommendation / advice / 추천 / 조언
- **DisclaimerBanner** — `(dashboard)/layout.tsx` 가 경로별 1회 마운트.
  페이지 안에서 중복 마운트 금지
- **없는 기능을 파는 카피 금지** — 삭제된 표면을 가리키는 링크·문구를 만들지 마라

### 법적 컴플라이언스
KIS 주문 disabled (read-only) · 한글+영문 면책 고지 · Cookie Consent ·
회원탈퇴(PIPA) · 가입 시 Terms checkbox 필수

---

## 알림 (2026-09-01 기준)

설정 → 알림 매트릭스는 **실제로 발신되는 2종만** 노출한다:
`price_52w`(52주 고/저) · `concentration`(섹터 30% 초과). 둘 다 `app.py` 의
`_scheduled_price_alerts` 크론이 발신하고 `_BELL_KIND_TO_EVENT_ID` 로 토글이
걸린다. SoT = `models/user.py::NOTIFICATION_EVENT_IDS`.
옛 7종은 **발신자가 없어 삭제**됐다 — 되살리려면 **발신자부터** 만들 것.

---

## 개발

```bash
git config core.hooksPath .githooks        # clone 직후 1회
./venv/bin/python run.py                   # 백엔드 :5050
cd frontend && npm run dev                 # 프론트 :3000
```
canonical 트리 = `~/Desktop/취준/pivoxquant` (여기서 작업·커밋·푸시).
`~/dev/pivoxquant` 는 2026-05-17 에 멈춘 버려진 사본.

**테스트 계정**: Google `seanbae1521@gmail.com` / KIS 계좌 read-only

---

## 출시 블로커

`SHIP_BLOCKERS.md` 가 SoT (2026-09-01 실측 재작성).

**무료 베타에는 법적 블로커가 사실상 없다** — 통신판매업 신고·Stripe 는 유상
거래 전제고, §101 유사투자자문업은 대가를 받을 때 성립한다. 지금 막는 건 법무가
아니라 **Render 배포**다. (agent 판단이지 법률 자문이 아니다. 변호사 의견서
질문 목록에 "무료 운영은 §101 밖인가"를 넣을 것.)

---

## 제품 전제 — 불리한 근거를 먼저 본다

메모리: `~/.claude/projects/-Users-seanbae-Desktop----pivoxquant/memory/`
(`MEMORY.md` 가 인덱스). 조사는 `research_habit_premise.md` /
`research_substitute_threat.md` / `research_toss_openapi.md`.

- **"질문을 던진다"는 차별화가 아니다** — ChatGPT Study Mode(2025-07-29)가 전 플랜
  무료로 제공한다.
- **"자동 수집"도 해자가 아니다** — 키움 자동일지, MyData 금투-003, 도미노가 이미
  커버한다.
- **비-아첨 해자는 2026-09-01 기준 사실상 소멸했다.** 8-30 메모는 "12~18개월
  시한부"로 봤지만, [lechmazur/sycophancy](https://github.com/lechmazur/sycophancy/)
  (2026-08-05 갱신) 실측은 GPT-5.6 Terra **0.0%** / Claude Fable 5 **0.5%**(결단
  커버리지 77.3%)다. 프론티어 모델이 이미 아첨하지 않으면서 판단을 내린다.
- **수요 신호가 나쁘다** — 한국 매매일지 앱 카테고리에 승자가 없다. 동일 컨셉
  '살래말래'가 출시 9개월에 평가 5개.

**남은 진짜 자산은 "일어나지 않은 거래"다.** 증권사도 MyData 도 체결만 알지
*사려다 말았는지*를 모르고, ChatGPT 는 유저가 매번 다시 붙여넣지 않는 한 모른다 —
그리고 안 산 거래를 붙여넣는 사람은 없다. 이걸 계산하는 게
`services/pre_trade/friction_outcome.py` 이고,
`scripts/friction_outcome_report.py` 로 바로 돌려볼 수 있다.

**다음 세션이 답해야 할 질문은 코드가 아니다** — *"한국 개인투자자가 기록을
하긴 하는가."* 직접 통계가 존재하지 않아 조사로는 못 푼다. 무료 베타의 목적을
수익이 아니라 **이 질문의 답을 얻는 것**에 두는 게 맞다.
