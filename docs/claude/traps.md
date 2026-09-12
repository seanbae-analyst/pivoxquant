# ⚠️ 함정 — 여기서 사람들이 틀린다 (전문)

> CLAUDE.md 에서 옮겨 온 원문 (2026-09-11). CLAUDE.md 에는 같은 번호로 한 줄 요약만 남겼다.
> 코드 주석의 "CLAUDE.md §7 / §10 / 함정 §N" 은 이 문서의 같은 번호를 가리킨다.

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

### 8. `services/access_guard.py` 는 **없다** (2026-09-02 삭제)

`is_user_allowed_ticker()` / `access_denied_response()` — §101 회피용 화이트리스트
가드였고, 프로덕션 호출처가 0곳이었다(2026-09-01 전수 grep).

이 절은 오래 "죽은 코드지만 일부러 남겼다"고 적었지만, 가드와
`tests/test_access_guard.py` 는 `c1f61809`(2026-09-02)에서 **함께 삭제됐다**.
확인: `git cat-file -e origin/main:services/access_guard.py` 실패,
`git log --diff-filter=D -- services/access_guard.py` → `c1f61809`
(2026-09-12 재확인). **§101 화이트리스트 가드가 존재한다고 가정하지 마라.**
되살릴 거면 `git show c1f61809^:services/access_guard.py` 에서 복원하고,
§101 게이트가 필요한 route 에 실제로 붙여라.

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
396줄이 거기 있다), CLAUDE.md 의 §제품 전제 절은 **후자**를 가리킨다. 둘 다 맞지만
**같은 곳이 아니다.** `legal_question_queue.md` / `DECISIONS.md` /
`business_registration.md` 는 전자에만 있다. 파일이 "없다"고 결론내기 전에
**두 경로를 다 확인**할 것 (2026-09-01 에 이걸로 버그를 오진할 뻔했다).

### 12. `endpoints.ts` 상수가 **404 를 가리킬 수 있다** — 심볼로 확인해라

2026-09-01 실측: `frontend/src/lib/endpoints.ts` 의 `/api` 경로 79개 중 **13개가
백엔드 url_map 에 없었다.** 전부 검증한 결과 라이브 버그는 **0건**이었지만,
왜 0건인지가 중요하다:

| 경로 | 상태 |
|---|---|
| `broker.*` (5) | **의도적 dormant** — `BROKER_LINKING_AVAILABLE=false` + SWR 키가 `false && ...` 라 요청 자체가 안 나감. 사유 주석까지 있음(KIS 제휴 불가·토스 약관 §5②) |
| `admin.artifacts*` (2) | `/admin` 페이지가 401/403/404 를 "blank 렌더" 로 설계 |
| `watchlist.*`(4)·`discover`·`portfolio.analytics`·`backtest` | **호출처 0 — 삭제함** |

즉 살아있는 게이트/그레이스풀 처리가 있는 것과, 그냥 아무도 안 부르는 것을
구분해야 한다. **삭제 전에 반드시 심볼(`API.x.y`)로 소비자를 세라** — 경로
문자열 grep 은 놓친다(CLAUDE.md 구조 절의 경고와 같은 이유).

⚠️ 검증 스크립트를 쓸 거면 **템플릿 리터럴 보간**(`${id}`)을 먼저 와일드카드로
치환할 것. 안 하면 `/api/support/admin/inquiries` 가 `/api/support/admin/` 로
잘려서 **멀쩡한 라우트를 "없음"으로 오판**한다 (이번에 실제로 그랬다).

### 13. 부팅 마이그레이션이 **아무도 안 읽는 테이블**을 만들고 있었다

`app.py::_do_migrations` (718줄, 부팅마다 실행) 가 **ORM 모델이 없는 테이블 7개**를
매번 `CREATE TABLE IF NOT EXISTS` 하고 있었다 — 2026-09-01 제거:

- `growth_*` 4개 (Growth OS) — 주석이 지목한 `growth_routes.py` 없음
- `agent_*` 3개 (자율 워커) — 주석이 지목한 `agent_worker/` 디렉터리 없음

실측: 7개 테이블명이 **app.py 와 alembic 이력 밖 어디에도 없고**, `/api/growth`
· `/api/agent` URL rule 0개. 읽지도 쓰지도 않는 테이블을 부팅마다 보장하고 있었다.

⚠️ **기존 DB 는 영향 없다** — 생성 코드를 지워도 테이블이 드롭되지는 않으므로
Supabase 의 43 테이블은 그대로다. 새 DB 만 이 7개를 안 받는다. alembic 리비전
(`004_add_agent_tables` 등)은 **건드리지 않았다** (리비전 삭제 금지 원칙).

교훈: `_do_migrations` 안의 DDL 은 **모델이 없으면 아무도 안 본다.** 새 테이블을
여기 추가할 거면 소비자(모델·라우트·서비스)부터 만들고, 소비자가 사라질 땐 DDL 도
같이 지워라. 그러지 않으면 부팅마다 유령 스키마가 늘어난다.

### 14. 베타 비번 리터럴은 **스윕 리포트를 통해 반복 재유입**된다

2026-09-02 실측: `tests/test_pivoxaudit_secret_leak.py` 가 빨갛게 떴는데 원인이
**야간 daily-sweep 이 03:00 에 쓴 `BUG_SWEEP_2026-09-02.md:63`** 이었다. 스윕이
`/api/beta-auth` 를 curl 로 찌른 뒤 **명령줄을 그대로** 리포트에 붙여서 비번
리터럴이 파일로 떨어졌다.

**처음이 아니다** — `git log -S` 에 최소 두 번의 선례가 있다
(`416425bb` — HANDOVER 평문 self-heal, "v32 PR #224 동일 패턴" 이라고 적혀 있다;
`53c063fe` "obfuscate BETA_PW literal"). 커밋 제목 자체에 리터럴이 들어 있으니
**여기에 그대로 인용하지 마라** — 이 문단을 쓰면서 실제로 한 번 밟았고, 가드가
바로 잡았다. 확인할 땐 `git log --all -S` 로 직접 조회할 것. 즉 **가드는 매번 잡지만 소스가 계속
재생산**한다.

알아둘 것:
- 가드는 **git 추적 여부와 무관하게 파일시스템을 스캔**한다. `BUG_SWEEP_*.md`
  는 gitignore 라 커밋될 일이 없는데도 테스트는 실패한다 — 의도된 설계다
  (커밋되기 *전에* 잡는 게 목적).
- 허용 파일은 딱 둘: `tests/test_pivoxaudit_secret_leak.py` ·
  `.github/workflows/legal-guard.yml`.
- 그래서 **pytest 가 이 한 건으로 빨갛게 뜨면 코드 회귀가 아니라 리포트 오염을
  먼저 의심하라.** 조치는 리포트의 리터럴만 마스킹하는 것 — 리포트 자체를
  지우면 그날 스윕이 찾은 P0 도 같이 날아간다.

근본 해결: **② 로 결정됐다 (2026-09-04 CEO, 무료 공개).** 베타 게이트·비번·env 를
전부 폐기했으므로 이 리터럴이 새로 생길 이유가 없다. 남은 것은 옛 리포트 오염뿐 —
마스킹으로 처리한다.
