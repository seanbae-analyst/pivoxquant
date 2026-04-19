# PivoxQuant — 인수인계서 (Handover)

> **작성일**: 2026-04-19 (대규모 작업 세션 종료)
> **목적**: 다음 세션이 이 문서만 읽고 즉시 컨텍스트 복원 + 남은 블로커 해결

---

## Deployment Status (2026-04-19 17:25 KST 기준)

| 서비스 | 커밋 | 상태 | 비고 |
|--------|------|------|------|
| Railway backend | `9f2250d` | ACTIVE | `RAILWAY_BACKEND_HOST.up.railway.app` |
| Vercel frontend | `9f2250d` (main) | READY | `pivoxquant.com` (307 apex→canonical) |
| PostgreSQL | migration `009` | OK | Alembic heads = 1개 |

**`/api/health` 실측 응답** (방금 호출):
```json
{"db":"ok","status":"ok","timestamp":"2026-04-19T08:24:13.930806Z","version":"2026-04-19"}
```

- 로컬 `git status`: HANDOVER.md 수정만, origin/main 동기화됨 (ahead=0, behind=0)
- 루트 커밋 `9f2250d` (OAuth redirect_uri 동적 host 감지) — 로컬/Railway/Vercel 전부 동일

---

## 0. 30초 컨텍스트 복원

- **상태**: 백엔드/프론트 배포 완료. Active 상태. 하지만 **OAuth 로그인 `state_mismatch` 에러로 실사용 불가**.
- **URL**:
  - 베타: `https://pivoxquant.com` (비번 `***REDACTED***`)
  - 백엔드: `https://RAILWAY_BACKEND_HOST.up.railway.app`
  - `.vercel.app`은 쓰지 마라 — 쿠키 도메인 안 맞음
- **헬스체크**: `/api/health` → 200 OK, `{"db":"ok","status":"ok"}`
- **최신 커밋**: `9f2250d` (OAuth redirect_uri 동적 host 감지)

---

## 다음 세션 시작 시 10분 안에 해야 할 것

```bash
# 1. 로컬 동기화 (HANDOVER.md만 수정된 상태여야 함)
cd /Users/seanbae/Desktop/취준/stockpilot
git pull origin main

# 2. 백엔드 살아있는지 확인
curl https://RAILWAY_BACKEND_HOST.up.railway.app/api/health
# 기대: {"db":"ok","status":"ok",...}

# 3. Railway 콘솔 → Variables 탭 → SECRET_KEY 존재 확인
#    없으면 OAuth state_mismatch 원인 1순위 — 값 생성:
#    python3 -c "import secrets; print(secrets.token_hex(32))"
#    동시에 CSRF_SECRET, FLASK_ENV=production, CORS_ORIGINS 확인

# 4. 시크릿 브라우저 창 열기:
#    https://pivoxquant.com/login → 베타 비번 ***REDACTED*** 입력
#    → DevTools Network 탭 열기 → Kakao 로그인 클릭
#    → /api/auth/kakao 요청 Set-Cookie 헤더 확인 (session 쿠키 Domain=.pivoxquant.com 인지)
#    → Kakao 콜백 후 /login?error=state_mismatch 재현

# 5. Railway → Deploy Logs → 최근 10분 확인
#    "Kakao OAuth state mismatch" warning 로그 나왔는지 확인
#    그 위아래 "Kakao OAuth start" 로그와 같은 request-id인지
```

위 5단계 끝나면 원인 지점 좁혀짐 → §1 디버깅 플로우로.

---

## 1. 🔴 다음 세션 최우선 블로커 (OAuth 로그인 불가)

### 현재 증상
1. `https://pivoxquant.com/login` 에서 카카오/구글 로그인 버튼 클릭
2. Kakao/Google 인증 성공
3. 콜백 후 → `https://www.pivoxquant.com/login?error=state_mismatch` 리다이렉트
4. **로그인 실패**

### 지금까지 시도한 것 (다 실패)
- ✅ `PIVOX_BROKER_ENCRYPTION_KEY` Railway 설정
- ✅ `BETA_PASSWORD=***REDACTED***` 변경
- ✅ `DEV_LOGIN_SECRET` 삭제
- ✅ `WEEKLY_MEMO_FROM_EMAIL` 등 3종 `seanbae1521@gmail.com` 설정
- ✅ `SESSION_COOKIE_DOMAIN=.pivoxquant.com` 추가 ← **이걸 추가해도 state_mismatch**
- ✅ `FRONTEND_URL=https://pivoxquant.com` 설정
- ✅ OAuth redirect_uri를 Referer 기반 동적 결정 (커밋 `9f2250d`)

### 원인 추정 (다음 세션 디버깅 시작점)

**state_mismatch 의미**:
1. Flask가 OAuth 시작 시 `session["oauth_state_kakao"] = random_state` 저장
2. Kakao에서 돌아와 `request.args["state"]` 와 비교
3. 둘이 다르면 `state_mismatch`

**가능한 원인**:
1. **apex → www 리다이렉트 중 session 쿠키 유실**
   - Kakao redirect_uri가 `pivoxquant.com` 이면 307 → www로 리다이렉트 → 그 과정에 쿠키 도메인 불일치로 session 비워짐
   - **fix 후보**: Vercel에서 apex primary 설정 + www → apex 308 redirect
2. **Flask SECRET_KEY가 매 배포마다 바뀜**
   - Railway에 `SECRET_KEY` 환경변수 **확인 필요** — 없으면 매 부팅마다 random → session 해독 불가
   - 없으면: `python3 -c "import secrets; print(secrets.token_hex(32))"` 값 설정
3. **gunicorn gevent 멀티워커 session 동기화**
   - 현재 `--workers 1` 이지만 gevent에서 세션 직렬화 이슈 가능성
4. **Cookie `Secure=True` + `SameSite=Lax` + cross-site redirect 문제**
   - Kakao → pivoxquant.com 은 cross-site → SameSite=Lax 에서 세션 쿠키 안 전송되는 엣지 케이스

### 권장 디버깅 순서
1. Railway Variables에 `SECRET_KEY` 존재 확인 (없으면 32바이트 hex 값 설정)
2. `routes/auth.py` 의 `kakao_callback` 에서 state 비교 전후 로깅 추가해서 **실제로 어떤 state가 들어오고 session에 뭐가 있는지** 확인
3. Vercel Domain 설정에서 `pivoxquant.com` Primary + `www.pivoxquant.com` → apex 308 redirect
4. OAuth 시작 시 state를 `session` 대신 **signed cookie** 또는 **encrypted state token** 으로 교체 검토 (stateless)

### 📍 routes/auth.py OAuth 실제 상태 (검증 완료 2026-04-19)

Kakao 흐름 (파일: `routes/auth.py`):

| Step | 함수 | Line | 핵심 동작 |
|------|------|------|-----------|
| 1 | `kakao_login()` | 251–263 | `state = generate_token()` → `session["oauth_state_kakao"] = state` (260) + `session["oauth_origin"] = origin` (261) |
| 2 | `kakao_callback()` | 266–276 | `expected = session.pop("oauth_state_kakao", None)` (272) → `received = request.args.get("state")` (273) → 둘이 다르면 `state_mismatch` 리다이렉트 (274–276) |

Google 흐름도 동일 구조 (line 173–187 시작, 190–202 state 검증).

**세션 키**:
- `oauth_state_kakao` (line 260 set, 272 pop)
- `oauth_state_google` (line 182 set, 198 pop)
- `oauth_origin` (line 185/261 set, 195/269 pop) — 콜백 redirect 타겟

**state 비교 로직 현재** (auth.py:200-202, 274-276):
```python
if not expected_state or expected_state != received_state:
    logger.warning("Kakao OAuth state mismatch — possible CSRF attack")
    return redirect(f"{origin}/login?error=state_mismatch")
```

→ 현재 warning만 찍음. **expected_state / received_state 값 자체는 로그에 안 찍힘** → 어느 쪽이 비어있는지 불명.

### 🛠 로깅 추가 위치 (다음 세션 즉시 반영 가능)

**Kakao `kakao_callback`, routes/auth.py line 273 직후** (state 비교 직전):
```python
# 현재:
#     expected_state = session.pop("oauth_state_kakao", None)
#     received_state = request.args.get("state")
# 추가:
logger.info(
    "Kakao callback state check: expected=%s received=%s session_keys=%s has_sid=%s",
    (expected_state or "NONE")[:8],
    (received_state or "NONE")[:8],
    list(session.keys()),
    bool(request.cookies.get("session")),
)
```

**Kakao `kakao_login`, routes/auth.py line 263 직전** (authorize_redirect 호출 직전):
```python
logger.info(
    "Kakao login issued state=%s origin=%s session_id=%s cookie_domain=%s",
    state[:8], origin, session.sid if hasattr(session, "sid") else "n/a",
    os.environ.get("SESSION_COOKIE_DOMAIN", "unset"),
)
```

Google은 `google_login` line 187 직전 / `google_callback` line 199 직후에 동일한 패턴 적용.

**판정 규칙**:
- `expected=NONE received=<값>` → 세션 쿠키가 콜백 요청에 안 실려 옴 (cookie domain / SameSite 문제)
- `expected=<값A> received=<값B>` (둘 다 값 있음, 다름) → 서로 다른 세션 (apex↔www, worker간, SECRET_KEY 회전) 간섭
- `expected=<값> received=NONE` → 카카오가 state 파라미터 안 돌려보냄 (거의 없음)

---

## 2. 🎯 다음 세션 TODO

### 🔴 P0 — OAuth 로그인 수리 (CRITICAL)
- [ ] `SECRET_KEY` Railway 환경변수 존재 확인 + 영구 값 고정
- [ ] `routes/auth.py` state 검증 로깅 보강 + 디버깅
- [ ] Vercel apex/www 리다이렉트 정리
- [ ] OAuth state를 session-based → token-based로 전환 검토
- [ ] 이메일 회원가입 경로도 함께 동작 확인 (`/api/auth/register`)

### 🟠 P1 — 홈페이지(랜딩) 전면 개편 (CEO 요청)
- [ ] 현재 `frontend/src/components/landing/landing-page.tsx` 리뷰
- [ ] CFO 컨셉 강화 — "ChatGPT는 물어야 답한다, PivoxQuant는 자는 동안 만든다"
- [ ] Hero + 3 features + pricing + social proof 재구성
- [ ] 실제 리포트 샘플 이미지 삽입 (Weekly Memo PDF 1페이지 미리보기)
- [ ] 모바일 반응형 체크
- [ ] CTA 버튼 A/B 테스트 준비

### 🟡 P2 — 인프라 정리
- [ ] Gmail SMTP 세팅 (이메일 실발송)
  - 앱 비밀번호 생성: https://myaccount.google.com/apppasswords
  - Railway 환경변수: `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER=seanbae1521@gmail.com`, `SMTP_PASS=<앱비번>`
- [ ] Kakao/Google 콘솔에서 `.vercel.app` redirect URI 삭제 (보안)
- [ ] `pivoxquant.com` DNS 설정 최종 검증 (apex → www 루프 없는지)
- [ ] Dockerfile `playwright install chromium` 실제 성공 여부 확인 (Brag Card PNG 렌더 테스트)

### 🟢 P3 — 기능 확장
- [ ] Kiwoom OAuth Week 2 구현 (KIS 패턴 복사)
- [ ] 베타 테스터 5~10명 모집 (친구/지인)
- [ ] 법무 리뷰 (투자자문업 관련) — 이용약관 / 개인정보처리방침 초안
- [ ] Stripe 결제 연동 활성화 (Product ID 매핑)
- [ ] 마이데이터 사업자 검토 (장기)

---

## 3. 📊 오늘(2026-04-19) 세션 달성

### ✅ 구현 완료 (30개 커밋 푸시 — 전부 2026-04-19 작성/푸시)
1. **CFO 제품 컨셉 확정** (`product_concept_cfo.md`)
2. **MVP 3종 Artifact 구현**
   - Weekly Investor Memo (일요일 08:00 KST PDF 이메일) — 15 test PASS
   - Monthly Brag Card (매월 1일 09:00 KST PNG 9:16) — 14 test PASS
   - Earnings Pre-Brief (실적 30분 전 PDF + 푸시) — 10 test PASS
3. **KIS OAuth Week 1** — AES-256-GCM 암호화 저장, 4 엔드포인트, 16 test PASS
4. **대체 데이터 3종** — pyKRX / SEC EDGAR / FRED (외국인 수급 / 13F / 매크로)
5. **/reports 아카이브 페이지** — Spotify Wrapped 감성
6. **CFO 컨셉 리브랜딩**
   - 랜딩/가격/features 카피 전면 재작성
   - 티어 구조: Free / Pro ₩9,900 / Premium ₩19,900 / Elite ₩29,900
7. **폰트 통일** — Source Serif 4 + Geist Sans + JetBrains Mono
8. **디자인 시스템** — `frontend/design-principles-cfo.md`, report-* 토큰
9. **Purple/pink gradient 전수 청소** — 26 파일
10. **성능 hardening** — N+1 쿼리 fix, SignalCache TTL 60s
11. **보안 hardening**
    - DEV_LOGIN_SECRET 하드코딩 제거
    - Sentry/logger 헤더 마스킹
    - 베타 게이트 stale cookie 자동 무효화 + 토큰 v2
    - CORS 3 origin 명시적 설정
12. **datetime 마이그레이션** — `utcnow()` → `now(timezone.utc)` (99 치환, 274 warn → 1)
13. **데드 코드 1,633줄 제거** — 8 훅, 5 UI 컴포넌트, investor_profiles.py
14. **OG 메타 태그 보강** — 15 bytes → 18KB, 16개 크롤러 UA bypass
15. **Alembic 9 마이그레이션 체인 검증** — heads 1개 (`009_earnings_prebrief`)

### ✅ 배포 완료
- Railway backend `ACTIVE` (https://RAILWAY_BACKEND_HOST.up.railway.app)
- Vercel frontend (https://pivoxquant.com)
- PostgreSQL 마이그레이션 004~009 적용됨
- /api/health → 200 OK
- Render 계정 정리 완료 (과거 2026-04-02 잔존)

---

## 3.1 📜 커밋 이력 (2026-04-19 전수, 최신 → 과거)

| SHA | 제목 | 범주 |
|-----|------|------|
| `9f2250d` | fix(auth): OAuth redirect_uri를 요청 origin 기반으로 동적 결정 | 🔴 auth |
| `8c15e2c` | fix(migration): advisory lock을 별도 AUTOCOMMIT 커넥션으로 격리 | 🟠 migration |
| `dc1c750` | fix(migration): PostgreSQL BOOLEAN DEFAULT integer 거부 대응 | 🟠 migration |
| `f922e76` | fix(deploy): Debian trixie 패키지명 교체 (libgdk-pixbuf2.0-0 deprecated) | 🟠 deploy |
| `1871080` | fix(deploy): Railway 빌드 실패 복구 — NIXPACKS→DOCKERFILE 전환 + weasyprint deps | 🟠 deploy |
| `e43bdc0` | chore(deps): datetime.utcnow() → datetime.now(timezone.utc) 전면 마이그레이션 | 🟢 deps |
| `d2e2584` | chore(deps): shadcn devDependencies 이동 | 🟢 deps |
| `43401e4` | refactor(dead-code): 미사용 루트 모듈 + 타입 제거 | 🟢 refactor |
| `e619207` | refactor(dead-code): 미사용 훅 8개 + UI 컴포넌트 5개 제거 | 🟢 refactor |
| `9d9071d` | docs(deploy): DOMAIN_SETUP.md + MASTER_KEY legacy 제거 | 🟢 docs |
| `a7fb386` | chore(security): CORS origins 필수 기본값 보강 | 🔵 security |
| `d97924e` | feat(seo): OG 메타 태그 보강 + 크롤러 UA 베타 게이트 bypass | 🟡 seo |
| `e7be4f7` | refactor(types): replace any with unknown in locale resolver | 🟢 refactor |
| `212182c` | fix(tests): pre-existing pytest 4건 회복 | 🟢 test |
| `b27a0f1` | docs(todo): TODO 주석 통합 docs/TODO.md + 데드코드 리스트 docs/DEAD_CODE.md | 🟢 docs |
| `3683615` | chore(cleanup): 데드 파일 + __pycache__ + .DS_Store 제거 + .gitignore 보강 | 🟢 cleanup |
| `81e3464` | chore(docker): playwright chromium 자동 설치 + SW cache 정책 | 🟠 deploy |
| `bd01b5d` | chore(env): CORS/FLASK_ENV/FRONTEND_URL 등 critical 변수 .env.example 보강 | 🔵 env |
| `79646b2` | fix(frontend): bottom-nav i18n + aria-label + button Warm Gold | 🟣 frontend |
| `7a3c13c` | fix(api): 통합 artifacts endpoints + /api/health 추가 | 🟠 api |
| `3282217` | style(fonts): Source Serif 4 + JetBrains Mono 도입, 3개 토큰 통일 | 🟣 design |
| `106f50a` | docs: 운영 문서 + 런치 패키지 + HANDOVER 갱신 + 레거시 아카이브 | 🟢 docs |
| `8e57c42` | feat(frontend): My Reports 아카이브 + Growth 페이지 + 네비 통합 | 🟣 feat |
| `50e3a6e` | style(frontend): gradient purple/pink 청소 + React Hooks 규칙 fix | 🟣 design |
| `db4b677` | feat(frontend): CFO 컨셉 리브랜딩 — 카피 + 디자인 토큰 + 가격 정책 | 🟣 feat |
| `c6644c2` | feat(platform): 성능/보안 하드닝 + agent_worker + Thesis Tracker 통합 | 🔵 perf+security |
| `6688768` | feat(artifacts): Weekly Memo + Brag Card + Earnings Pre-Brief 파이프라인 | ⭐ core-feat |
| `41bdf51` | feat(alt-data): pyKRX + SEC EDGAR + FRED 대체 데이터 파이프라인 | ⭐ core-feat |
| `d66b2c1` | feat(broker): KIS/키움 OAuth 연동 + AES 암호화 저장 + referral 마이그레이션 | ⭐ core-feat |
| `1da4928` | fix(beta-gate): stale cookie 자동 삭제 + 토큰 v2 버저닝 | 🔴 auth |

총 30건. 시간대: 13:04 KST (`1da4928`) ~ 17:02 KST (`9f2250d`) — 약 4시간 연속 세션.
- 🔴 auth: 2 (베타 게이트 쿠키, OAuth redirect_uri)
- ⭐ core-feat: 3 (MVP artifact 파이프라인, 대체 데이터, KIS OAuth)
- 🟠 migration/deploy/api: 7 (Railway 빌드 복구 + BOOLEAN + advisory lock + artifacts endpoint 등)
- 🟣 frontend/design/feat: 6
- 🟢 cleanup/refactor/docs/deps/test: 9
- 🔵 security/perf/env: 3

---

### 🔥 해결한 빌드 블로커
1. `libgdk-pixbuf2.0-0` → `libgdk-pixbuf-2.0-0` (Debian trixie 패키지명 변경)
2. PostgreSQL `BOOLEAN DEFAULT 0` → `DEFAULT false` 자동 변환
3. Advisory lock을 별도 AUTOCOMMIT 커넥션으로 격리 (InFailedSqlTransaction 해결)
4. Dockerfile 사용하게 railway.json 수정 (NIXPACKS → DOCKERFILE)
5. 베타 게이트 stale cookie 자동 삭제 (쿠키 잔존 문제)

---

## 4. 🔑 Railway 환경변수 현황 (2026-04-19 기준)

### ✅ 설정됨
```
PIVOX_BROKER_ENCRYPTION_KEY  (32 bytes base64, 절대 rotate 금지)
BETA_PASSWORD                 = ***REDACTED***
SESSION_COOKIE_DOMAIN         = .pivoxquant.com
FRONTEND_URL                  = https://pivoxquant.com
WEEKLY_MEMO_FROM_EMAIL        = seanbae1521@gmail.com
BRAG_CARD_FROM_EMAIL          = seanbae1521@gmail.com
EARNINGS_PREBRIEF_FROM_EMAIL  = seanbae1521@gmail.com
DATABASE_URL                  (Railway Postgres 자동)
```

### ❓ 확인 필요 (다음 세션)
- [ ] `SECRET_KEY` — session 암호화 키. 없으면 state_mismatch 원인 가능
- [ ] `CSRF_SECRET` — CSRF 토큰
- [ ] `FLASK_ENV` = `production`
- [ ] `CORS_ORIGINS` — `https://pivoxquant.com,https://www.pivoxquant.com,https://pivoxquant.vercel.app`
- [ ] `ANTHROPIC_API_KEY`, `FMP_API_KEY`, `ALPACA_*`, `KIS_*`, `GOOGLE_CLIENT_*`, `KAKAO_CLIENT_*` (있어야 기능 동작)
- [ ] `RUN_SCHEDULER=1` (Weekly Memo/Brag Card 자동 발송)

### ❌ 반드시 없어야 함
- `DEV_LOGIN_SECRET` (삭제 완료)
- `MASTER_KEY` (legacy, 있으면 제거)

---

## 5. 📂 주요 파일 레퍼런스

### 백엔드 (절대 수정 금지)
- `engine.py`, `quant_models.py`, `autotrader.py`, `risk_defense.py`
- `portfolio_models.py`, `signal_models.py`, `ai_models.py`, `risk_models.py`
- `services/kis_service.py`, `services/fmp_service.py` (호출만)
- `services/ai_service.py` (호출만)

### OAuth 관련 (다음 세션 디버깅 대상)
- `routes/auth.py` — Google/Kakao OAuth 핸들러
  - `_resolve_frontend_url()` (신규 추가) — line ~25
  - `google_login()` / `google_callback()` — line ~118
  - `kakao_login()` / `kakao_callback()` — line ~186
- `security.py` — CORS, session, CSRF 설정
- `config.py` — SECRET_KEY, session 설정

### 새 Artifact 서비스
- `services/artifacts/weekly_memo_service.py`
- `services/artifacts/brag_card_service.py`
- `services/artifacts/earnings_prebrief_service.py`
- `services/artifacts/templates/*.html`
- `routes/artifacts.py` — 통합 + 타입별 엔드포인트

### KIS OAuth
- `services/crypto_service.py` — AES-256-GCM
- `services/broker/user_kis_service.py`
- `routes/broker_oauth.py`

### 대체 데이터
- `services/data/pykrx_service.py`
- `services/data/sec_edgar_service.py`
- `services/data/fred_service.py`
- `routes/alt_data.py`

### 프론트 랜딩 (다음 세션 개편 대상)
- `frontend/src/components/landing/landing-page.tsx` ← CEO가 재작성하고 싶어함
- `frontend/src/app/pricing/page.tsx`
- `frontend/src/app/features/*/page.tsx`
- `frontend/design-principles-cfo.md` — 디자인 원칙

### 신규 리포트 아카이브
- `frontend/src/app/(dashboard)/reports/page.tsx`
- `frontend/src/components/reports/artifact-card.tsx`
- `frontend/src/components/reports/preview-modal.tsx`

---

## 6. 💰 예산 현황

- 기존 사용: ₩266,696 + 오늘 Claude 토큰 사용량 추정 ₩30~50K
- 잔여: ~₩650K
- Railway: ~$6/월 (Postgres 포함)
- Vercel: Hobby (무료)
- 도메인: ₩19,800/년
- **예상 런칭 비용**: 법무 자문 중심 (부티크 로펌 ₩100만 이내)

---

## 7. 🚫 절대 하지 말아야 할 것

- `engine.py`, `quant_models.py`, `autotrader.py`, `risk_defense.py` 수정
- `PIVOX_BROKER_ENCRYPTION_KEY` rotate (기존 암호화 자격증명 영구 손실)
- `DEV_LOGIN_SECRET` 프로덕션에 재설정
- `SECRET_KEY` 변경 (모든 기존 세션 무효화)
- 베타 비번 `***REDACTED***` 공개 저장소 commit
- `.env` 파일 git에 commit
- Vercel 도메인 설정에서 apex/www redirect 루프 만들기
- `BUY/SELL/HOLD` 라벨 사용 (POSITIVE/NEGATIVE/NEUTRAL만)
- "AI Coach", "투자 코치" 카피 사용 ("AI Assistant"도 이제 금지)
- "추천", "조언", "매수 시점", "예상 수익률 X%" 표현

---

## 8. 📅 자동 발송 예정 (정상 작동 확인 필요)

| 리포트 | 첫 발송 | 대상 |
|---|---|---|
| Morning Brief | 내일 06:30 KST | Pro+ 유저 |
| Weekly Investor Memo | 이번 주 일요일 08:00 KST | Pro+ 유저 |
| Monthly Brag Card | 5월 1일 09:00 KST | Free+ 유저 |
| Earnings Pre-Brief | 포지션 종목 실적 30분 전 (15분 스캔) | 해당 포지션 보유자 |

**주의**: `RUN_SCHEDULER=1` Railway 환경변수 없으면 스케줄러 작동 안 함.

---

## 9. 🗣️ CEO 다음 세션 시작 프롬프트 (추천)

```
HANDOVER.md 읽고 이어서 시작.

현재 상태:
- 배포 완료, 백엔드/프론트 Active
- /api/health 200 OK
- 하지만 Kakao/Google OAuth 로그인 state_mismatch 에러
- 베타 비번 ***REDACTED***로 사이트 진입은 됨
- 로그인만 안 됨

우선 진행:
1. OAuth state_mismatch 디버깅 (SECRET_KEY 확인부터)
2. 랜딩 페이지 CFO 컨셉 대폭 재작성
3. 이메일 회원가입 경로라도 먼저 열어서 유저 테스트 가능하게

홈페이지 개편 방향:
- CFO가 된 느낌 강화
- 실제 Weekly Memo PDF 샘플 이미지 노출
- 현재 디자인 문제점 먼저 리뷰 후 개편 시작
```

---

## 10. 📞 긴급 연락처 / 자원

- **Railway**: https://railway.app → pivoxquant 프로젝트
- **Vercel**: https://vercel.com → pivoxquant 프로젝트
- **GitHub**: https://github.com/seanbae-analyst/pivoxquant
- **Kakao Developers**: https://developers.kakao.com/console/app
- **Google Cloud Console**: https://console.cloud.google.com
- **KIS Developers**: https://apiportal.koreainvestment.com
- **도메인(가비아)**: pivoxquant.com

---

## 10.5 🧪 로컬 작업 환경 복원 체크

다음 세션 시작 시 로컬이 정상 상태인지 검증하는 명령 모음 + 기대 출력.

```bash
cd /Users/seanbae/Desktop/취준/stockpilot

# 1. 작업 트리 상태
git status
# 기대: "On branch main" + "nothing to commit, working tree clean"
#       (HANDOVER.md가 오늘 커밋에 포함되면 modified 줄 없어야 정상)

# 2. 최근 커밋 5개 (다음 세션 시작 시 루트 커밋이 9f2250d 이상인지)
git log --oneline -5
# 기대 첫 줄: 9f2250d fix(auth): OAuth redirect_uri를 요청 origin 기반으로 동적 결정
#            (또는 이 커밋 이후 새 커밋이 있으면 더 최신)

# 3. 백엔드 테스트 스모크 (Flask/SQLAlchemy 레벨 검증)
python3 -m pytest tests/ -x --tb=short 2>&1 | tail -5
# 기대: "== X passed in Ys =="
#       실패 시 첫 5줄이 원인 — 보통 .env 미설정 또는 pyKRX 네트워크 타임아웃

# 4. 프론트 빌드 (타입 체크 + bundle 검증)
cd frontend && npx next build 2>&1 | tail -5
# 기대 마지막 줄: "✓ Compiled successfully" + 라우트 수 테이블
#       실패 시 TypeScript 에러 또는 missing env (NEXT_PUBLIC_API_URL)
```

실패 케이스별 대응:
| 증상 | 원인 | 복구 |
|------|------|------|
| `git status` dirty | 지난 세션 미커밋 | `git diff` 리뷰 → 커밋 또는 stash |
| `git log` HEAD가 9f2250d 아님 | 새 커밋 추가됨 or 로컬 밀림 | `git pull origin main` |
| pytest 네트워크 실패 | pyKRX/FRED/SEC 호출 | `tests/` 내 해당 테스트만 `-k "not network"` |
| next build 실패 | node_modules 구버전 | `rm -rf frontend/node_modules && npm i` |

---

## 11. 🎯 오늘 Key Takeaway

**"AI가 챗봇이 아니라 비서/애널리스트로 동작하는 플랫폼"** 컨셉 확립.
MVP 3종이 이번 주부터 자동 발송될 예정 (스케줄러 작동 전제).

가장 큰 남은 장벽은 **OAuth 로그인**. 이게 해결돼야 실유저 받을 수 있음.

---

**작성**: Claude (2026-04-19 세션 마감, 17:25 KST)
**커버 범위**: 30개 커밋 (13:04 KST `1da4928` → 17:02 KST `9f2250d`)
**다음 세션**: 이 문서 + 터미널에 `curl https://RAILWAY_BACKEND_HOST.up.railway.app/api/health` 먼저 상태 확인 후 시작
