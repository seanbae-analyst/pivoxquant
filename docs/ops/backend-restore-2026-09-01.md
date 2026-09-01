# 백엔드 복구 — 2026-09-01

Railway 계정이 삭제되면서 앱과 prod DB 가 함께 사라진 뒤, 백엔드를
**Render(앱) + Supabase(Postgres)** 조합으로 다시 세운 기록이다.

이 문서는 두 가지를 한다. ① 지금까지 실제로 검증된 것을 남기고 ② CEO 가
Render 에서 눌러야 할 것만 짧게 정리한다.

---

## 1. 인수인계서가 틀렸던 것 — alembic 은 스키마의 SoT 가 아니다

CLAUDE.md 와 이전 인수인계서는 이렇게 적고 있었다:

> alembic 리비전 52개 → **스키마는 100% 재생성 가능**.
> `flask db upgrade` (Procfile 의 release 단계가 이미 이걸 한다).

**빈 DB 에 대고 실행해 보면 실패한다.** 실측 결과:

```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.DuplicateTable)
relation "agent_tasks" already exists
  → migrations/versions/004_add_agent_tables.py
```

원인은 `app.py:414` 다. `create_app()` 이 조건 없이 `db.create_all()` 을
부른다. alembic 의 `migrations/env.py` 는 Flask 앱을 임포트해야 동작하므로,
`flask db upgrade` 는 **자기가 돌기도 전에 create_all 이 전체 스키마를 이미
만들어 놓은 상태**에서 시작한다. 그래서 004 에서 충돌한다.

이건 새로 생긴 버그가 아니라 원래 그렇게 운영돼 왔다. app.py 안의 주석이
이미 실토하고 있다 (`app.py:1024`):

> prod 는 alembic 미실행 (`db.create_all()` + `_do_migrations()` self-heal 패턴)

즉 **스키마의 진짜 SoT 는 ORM 모델**이고, alembic 리비전은 과거 이력일 뿐
빈 DB 를 세우는 경로가 아니다. Procfile / railway.json 의 release 단계가
`flask db upgrade` 실패를 삼키고 넘어가도록(`ALEMBIC_UPGRADE_FAILED ... boot
continues`) 짜여 있는 이유도 이것이다 — 실패가 정상 경로였다.

### 그래서 빈 DB 를 세우는 올바른 순서

1. 앱을 DATABASE_URL 만 걸고 **한 번 부팅** → `create_all()` 이 모델에서 전체
   스키마 생성 (43 테이블)
2. `flask db stamp head` → `alembic_version = 049_reflection_observed_context`
3. 이후 `flask db upgrade` 는 no-op (exit 0). 앞으로 추가되는 마이그레이션은
   정상 적용된다.

2번을 빼먹으면 `alembic_version` 테이블이 아예 없어서 다음 마이그레이션이
001 부터 다시 돌려다 영원히 깨진다. 이번에 그 상태를 실제로 만들어 봤고,
stamp 로 복구했다.

---

## 2. 지금 살아 있는 것 (실측)

| 항목 | 상태 | 증거 |
|---|---|---|
| Supabase 프로젝트 | `pivoxquant` / `yjiztgummaxecriiuumt` / ap-northeast-2 | `ACTIVE_HEALTHY` |
| 스키마 | 43 테이블 생성 완료 | `information_schema.tables` 카운트 |
| alembic | `049_reflection_observed_context` 로 stamp | `flask db upgrade` → no-op, exit 0 |
| 앱 ↔ DB | 연결됨 | `/api/health` → **200**, `{"db":"ok"}` |
| 접속 경로 | session pooler `aws-0-ap-northeast-2.pooler.supabase.com:5432` | 직결 호스트(`db.*.supabase.co`)는 **IPv4 미해석** — pooler 필수 |
| DB 롤 | `pivox_app` (postgres 아님) | Supabase 는 `postgres` 롤 비번 변경을 막는다 (`42501: permission denied to alter role`) |
| 외부 노출 | 차단됨 | anon key 로 `/rest/v1/users`·`positions`·`trade_history`·`broker_connections` → 전부 **401 `42501`** |
| **로그인 이후 E2E** | **통과** | 아래 §2.1 |

DB 는 `postgres` 가 아니라 전용 롤 `pivox_app` 으로 붙는다. Supabase 가
`postgres` 롤 비밀번호 변경을 superuser 로 제한해서 우회한 것인데, 결과적으로
이게 데이터를 지켰다 — 표의 "외부 노출" 행이 그 덕분이다. 앱이 superuser 로
돌지 않는 편이 어차피 낫다.

### 2.1 로그인 이후 표면 — 새 DB 에서 실제로 동작한다

Render 가 서기 전에 5단계를 미리 검증했다. 로컬 백엔드를 Supabase 에 붙이고
dev-login 으로 세션을 만든 뒤 실제 엔드포인트를 때렸다.

| 엔드포인트 | 결과 |
|---|---|
| `/api/auth/dev-login` | 200 (유저가 새 DB 에 생성됨) |
| `/api/auth/oauth-finalize` (생년월일 게이트) | 200 |
| `/api/mirror-home` — **거울, PRIMARY** | 200 |
| `/api/portfolio` · `/api/portfolio/positions` | 200 (`fx_rate: 1368.52` 라이브) |
| `/api/behavior/holding-mirror` · `concentration-mirror` | 200 |
| `/api/pre-trade/list` · `/api/pre-trade/start` — **멈춤, PRIMARY** | 200, **행 INSERT 확인** |
| `/api/notifications` · `/api/profile` | 200 |

두 가지가 부수적으로 증명됐다:

- **스키마가 alembic head 와 실제로 일치한다.** `pre_trade_reflections` 에
  `observed_context_json` 이 있다 — 마이그레이션 **049 가 추가한 그 컬럼**이다.
  create_all 산출물이 head 와 같은 모양이라는 직접 증거다.
- **앱 레벨 암호화가 새 DB 에서 동작한다.** 기록된 `rationale` 이 평문이 아니라
  `pqenc:1:...` 로 저장됐다.

검증에 쓴 QA 유저와 행은 **전부 삭제했다** (`users=0`,
`pre_trade_reflections=0`). DB 는 출시 기준 백지 상태다.

⚠️ 처음 프로브에서 `/api/journal` 이 404 였는데 **결함이 아니다** — 그런
엔드포인트는 없고 `/journal` 페이지는 behavior mirror 들로 조립된다. 마찬가지로
`intended_side` 가 NULL 로 들어간 것도 파라미터명이 `action` 이 아니라 `side`
이기 때문이었다 (`routes/pre_trade.py:66`). 둘 다 프로브 쪽 오류다.

---

## 3. CEO 가 할 것 — Render

레포에 `render.yaml` (Blueprint) 를 넣어 뒀다. 설정을 손으로 채울 일은 없다.

1. render.com 가입 → GitHub 레포 연결
2. **New → Blueprint** → 이 레포 선택. Render 가 `render.yaml` 을 읽는다
3. `sync: false` 로 표시된 변수들을 Render 가 하나씩 물어본다 →
   **`.secrets/RENDER_PASTE_VALUES.txt`** 에 붙여넣을 값과 출처를 정리해 뒀다
   (이 파일은 gitignore 되어 커밋되지 않는다)
4. 첫 배포 → URL 발급되면 `RAILWAY_BACKEND_URL` 에 그 URL 을 넣고 재배포
   (이름은 Railway 지만 Railway 전용이 아니다 — `routes/auth.py` 의 로그아웃
   Origin 허용목록이 이 값을 읽는다)
5. **Google OAuth — 2026-09-01 에 복구 + 게시 완료.** 아래 §3.1 참조.

   원래 이 자리에는 "OAuth 콘솔은 손댈 필요 없다" 라고 적었었다. redirect URI 는 백엔드가
   아니라 **프론트 origin** 으로 만들어진다 — `routes/auth.py:1025` 가
   `_resolve_frontend_url()` 로 origin 을 잡고 `{origin}/api/auth/google/callback`
   을 쓴다. 그 origin 은 `_ALLOWED_OAUTH_ORIGINS` 화이트리스트로 제한되고
   Render 도메인은 거기 없다. 프론트 도메인이 그대로이므로 기존 등록값
   `https://www.pivoxquant.com/api/auth/{google,kakao}/callback` 이 계속 맞다.

### 3.1 Google OAuth — 삭제돼 있었고, 복구했다

콘솔을 직접 열어 보고 나서야 안 사실이다. **redirect URI 를 새로 등록할 필요가
없다는 판단 자체는 맞았지만**(`routes/auth.py:1025` 가 `_resolve_frontend_url()`
= 프론트 origin 으로 URI 를 만들고, 그 origin 은 `_ALLOWED_OAUTH_ORIGINS` 로
제한되며 Render 도메인은 거기 없다), **정작 클라이언트가 사라져 있었다.**

- OAuth 클라이언트 `StockPilot Web` 이 **2026-09-01 에 삭제**돼 있었다. Railway
  계정을 지운 것과 같은 날이다. 30일 복원 창이 남아 있어 **복원**했다
  (새로 만드는 것보다 낫다 — 클라이언트 ID 와 등록된 URI 가 그대로 살아난다).
- 복원 후 확인한 redirect URI: `https://pivoxquant.com/api/auth/google/callback`
  과 `https://www.pivoxquant.com/api/auth/google/callback`. 둘 다 정확하다.
- `GOOGLE_CLIENT_ID` =
  `1029651476294-icjlnngdi9438i9qka064g9mq0h1r0o1.apps.googleusercontent.com`
  (GCP 프로젝트 `PivoxQuant` / `stockpilot-492803`).
  ⚠️ 같은 계정의 다른 프로젝트 `stockpilot`(491804) 에도 `StockPilot` 이라는
  클라이언트가 있는데 **그건 nuscale-analyzer 용**이다(콜백이
  `ynpyhxeflkihmnmfexre.supabase.co`). 헷갈리지 말 것.

**그리고 게시 상태가 "테스트 중" 이었다.** 그대로 뒀으면 백엔드가 떠도 테스트
사용자로 등록한 사람만 로그인됐다 — 무료 베타의 조용한 킬러다. 막고 있던 건
브랜딩의 링크 2개뿐이라 채우고 게시했다:

- 앱 이름 `StockPilot` → **`PivoxQuant`** (동의 화면에 옛 제품명이 뜨고 있었다)
- 홈페이지 / 개인정보처리방침 / 서비스 약관 링크 = `https://www.pivoxquant.com`
  `/privacy` `/terms` (셋 다 200 확인)
- **게시 상태 = 프로덕션.** 민감·제한 범위가 0개고 로고도 없어서 Google 심사
  대상이 아니었다 — 즉시 반영됐다.

⚠️ **Kakao 도 같은 날 삭제됐을 수 있다.** Google 이 그랬으니 카카오 개발자
콘솔의 앱도 상태를 확인할 것.

### 요금

`render.yaml` 은 `plan: free` 로 두었다. 무료 티어는 15분 무트래픽 시
슬립되고 콜드스타트가 1분쯤 걸린다. 유저가 없는 클로즈드 베타에서는 견딜
만하지만 **크론이 죽는다** — `RUN_SCHEDULER` 가 인프로세스 APScheduler 라
서비스가 자면 52주 알림도, 집중도 알림도, 이메일 큐 드레인도 발사되지 않는다.
알림을 진짜로 켜는 순간 `plan: 0.5c-512mb` (상시 가동) 한 줄로 바꾼다. Render 는 옛 마케팅
이름(`starter`)이 아니라 인스턴스 사이즈를 받는다 — 2026-09-01 공식 스펙 확인.

---

## 4. 이번에 같이 고친 것

`routes/__init__.py` 의 `DEV_LOGIN_SECRET` 가드가 **Railway 마커만** 보고
있었다 (`RAILWAY_ENVIRONMENT` / `RAILWAY_PUBLIC_DOMAIN`). Render 로 옮기면 그
마커가 없으니 이중 방어의 한 겹이 조용히 사라지고 `FLASK_ENV` 단일 체크로
되돌아간다 — 2026-06-10 W2-P3 이 고쳤던 바로 그 상태다. 마커 목록에
`RENDER` / `RENDER_SERVICE_ID` / `FLY_APP_NAME` 을 추가했다.

같은 Railway 결합이 두 군데 더 있지만 **둘 다 `FLASK_ENV=production` 으로
덮이므로 Render 에서 정상 동작한다**. 고치지 않고 남겨 둔다:

- `services/crypto_service.py:90` — `RAILWAY_ENVIRONMENT_NAME` 은 prod 판정
  휴리스틱 5개 중 하나일 뿐이고 `FLASK_ENV` 가 먼저 잡는다
- `routes/auth.py:864` — `RAILWAY_BACKEND_URL` 을 읽지만 값만 넣어 주면 되는
  일반 env 다 (위 3번 4단계)

---

## 5. 아직 안 된 것

- **Vercel 재연결** — 프론트의 `RAILWAY_BACKEND_URL` / `NEXT_PUBLIC_API_URL`
  이 아직 죽은 Railway 를 가리킨다. Render URL 이 나오면
  `vercel env` + `vercel redeploy`. 이 값이 `/api` 프록시의 SoT다
  (`next.config.ts:9-10`)
- **Dockerfile 실빌드 검증** — 이 머신에 Docker 가 없어 여전히 정적 감사만
  된 상태다. Render 의 첫 빌드가 실질 검증이다. 실패하면
  `git show c982e273^:Dockerfile` 로 옛 버전 대조
- **브라우저 E2E** — API 레벨은 §2.1 에서 통과했다. 남은 건 프론트가 실제로
  렌더하는지이고, 그건 Render URL 로 Vercel 을 재연결한 뒤에 가능하다
- **시크릿 재발급** — `.secrets/RENDER_PASTE_VALUES.txt` 의 "CEO 가 가져와야
  하는 값" 목록
