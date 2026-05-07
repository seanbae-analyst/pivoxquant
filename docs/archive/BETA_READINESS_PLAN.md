# PivoxQuant 베타 공유 전 기획안 (Beta Readiness Plan)

> **작성일**: 2026-04-15
> **작성자**: Claude + CEO(배상현)
> **목적**: 지인 베타 공유 전 처리해야 할 모든 이슈를 한 문서에 집대성
> **원칙**: 🚨 C(Critical)은 공유 **전 반드시**, ⚠️ H(High)는 3일 내, 💡 M(Medium)은 런칭 후

---

## 0. 현재 배포 상태 (2026-04-15 17:30 KST)

| 항목 | 상태 |
|---|---|
| 도메인 | ✅ `https://pivoxquant.com` 동작 (가비아 DNS → Vercel) |
| 프론트 | ✅ Vercel Ready, Next.js 16 + Turbopack |
| 백엔드 | ✅ Railway Ready, gunicorn gevent |
| DB | ✅ Railway PostgreSQL 연결 |
| API 프록시 | ✅ Vercel → Railway (next.config 하드코딩) |
| CORS | ✅ pivoxquant.com, vercel.app 허용 |
| 베타 게이트 | ✅ `${BETA_PASSWORD}` 비번 작동 |
| OAuth redirect URI | ✅ Google + Kakao 4개씩 등록 |
| 환경변수 19개 | ✅ Railway 주입 |

---

## 1. CEO 실사용자 테스트에서 발견한 버그 (공유 전 수정)

### 🚨 B1. "타임머신 체험하기" 버튼 한국어만
- **위치**: 랜딩 페이지 / 타임머신 CTA
- **증상**: EN 토글 해도 버튼 텍스트가 한국어 그대로
- **원인 추정**: `frontend/messages/en.json`에 해당 키 누락 또는 키 미사용
- **우선순위**: P1

### 🚨 B2. PivoxQuant 로고 클릭 → 홈 이동 안 됨
- **위치**: 상단/좌측 네비게이션 로고
- **증상**: 클릭해도 무반응 또는 현재 페이지 머무름
- **원인 추정**: `<Link href="/">` 래핑 누락 또는 onClick 핸들러 이슈
- **우선순위**: P0 (UX 기본 원칙 위배)
- **담당**: frontend-dev agent (진행 중)

### 🚨 B3. 온보딩 질문 Skip 버튼 동작 안 함
- **위치**: 로그인 직후 온보딩 플로우
- **증상**: Skip 버튼 클릭해도 다음 페이지로 이동 안 됨
- **원인 추정**: router.push() 누락, 백엔드 skip API 미호출
- **우선순위**: P0 (신규 유저 스킵 불가 = 탈퇴 유발)
- **담당**: frontend-dev agent (진행 중)

### 🚨 B4. 로그인 후 온보딩 재노출
- **위치**: 이미 온보딩 완료한 유저의 재로그인
- **증상**: 완료 상태 무시하고 질문 다시 노출
- **원인 추정**: 프론트에서 `user.onboarding_completed` 플래그 체크 누락
- **우선순위**: P0 (재방문 유저 UX 최악)
- **담당**: frontend-dev agent (진행 중)

### 🚨 B5. 모바일 메뉴 버튼 미동작
- **위치**: 모바일 뷰포트 상단/하단 네비
- **증상**: 햄버거 메뉴 클릭해도 드로어 안 열림
- **원인 추정**: Sheet/Drawer state 연결 누락, z-index 충돌
- **우선순위**: P0 (친구들 대부분 폰으로 접속할 것)
- **담당**: frontend-dev agent (진행 중)

### ⚠️ B6. 번역 전반 애매함
- **증상**: EN 문구가 어색하거나 맥락과 안 맞음
- **원인 추정**: 기계 번역 그대로, 문맥 고려 부족
- **우선순위**: P1 (친구 대부분 한국인이라 당장 치명적이진 않음)
- **담당**: 런칭 후 i18n agent 전수 점검

---

## 2. 보안 감사 결과 (NSA Red Team 기준)

### 🚨 C1. CSP `'unsafe-eval'` 프로덕션 활성화 (OWASP A03)
- **파일**: `frontend/middleware.ts:86`
- **증거**: `script-src 'self' 'unsafe-inline' 'unsafe-eval'` — isDev 분기 없음
- **공격 시나리오**: 라이브러리 취약점 하나만 터져도 `eval` 기반 RCE → 세션 탈취
- **수정**:
  - `isDev`면 `'unsafe-eval'` 허용, 프로덕션은 제거
  - 인라인 스크립트는 nonce 재도입 (`script-src 'self' 'nonce-${nonce}'`)
  - Next.js 16 nonce propagation 이슈 재검증
- **우선순위**: 공유 전 CRITICAL

### 🚨 C2. 베타 비밀번호 쿠키 평문 저장
- **파일**: `frontend/src/app/api/beta-auth/route.ts:42`
- **증거**: `response.cookies.set(COOKIE_NAME, correct, …)` — 쿠키 값 자체가 평문 비밀번호 (구버전)
- **공격 시나리오**: 지인 PC 쿠키 1건 유출 → 비번 전체 노출, 30일 보존 → 로테이션 불가
- **수정**:
  - HMAC 서명 토큰 (`sign(BETA_SECRET, userAgent+timestamp)`)
  - 또는 짧은 만료(1일) + 로테이션 가능한 토큰
- **우선순위**: 공유 전 CRITICAL

### 🚨 C3. 베타 비번 비교 타이밍 공격 취약
- **파일**: `frontend/src/app/api/beta-auth/route.ts:34`
- **증거**: `if (password !== correct)` 단순 비교
- **공격 시나리오**: 수백만 회 시도로 문자 단위 길이/매칭 추정 (짧은 비번이라 실전성 낮으나 방어막 0)
- **수정**: `crypto.timingSafeEqual(Buffer.from(password), Buffer.from(correct))` + 길이 미스매치 가드
- **우선순위**: 공유 전 CRITICAL

### 🚨 C4. OAuth `state` 파라미터 누락 (CSRF, OWASP A01)
- **파일**: `routes/auth.py:107-114` (Google), `routes/auth.py:174` (Kakao)
- **증거**: Google은 `nonce`만, Kakao는 아무 것도 없음
- **공격 시나리오**: 공격자가 자기 OAuth 코드 삽입한 링크를 피해자에게 클릭시킴 → **피해자 계정에 공격자 소셜 계정 링킹** (Account Linking Takeover)
- **수정**:
  - `state` 세션 저장 후 callback에서 대조
  - Google/Kakao 둘 다 적용
- **주의**: `auth.py`는 수정 금지 파일 아님 — 수정 가능
- **우선순위**: 공유 전 CRITICAL

### ⚠️ H1. `FLASK_ENV=production` 미설정 시 쿠키 Secure 꺼짐
- **파일**: `security.py:158-165`
- **증거**: `_IS_PRODUCTION=(FLASK_ENV=="production")` 조건에서만 `SESSION_COOKIE_SECURE=True`
- **확인 필요**: Railway Variables에 `FLASK_ENV=production` 있는지
- **수정**: 없으면 추가. `PREFERRED_URL_SCHEME=https`도 같이
- **우선순위**: 30초 체크 — 지금 바로

### ⚠️ H2. CORS 화이트리스트에 www 누락 가능성
- **파일**: `security.py:36`
- **증거**: Railway `CORS_ORIGINS=https://pivoxquant.vercel.app,https://pivoxquant.com` — `www.pivoxquant.com` 없음
- **공격/영향**: Vercel이 apex→www 리다이렉트 후 API 호출 → CORS 실패 → 로그인 불가
- **수정**: Railway env에 `https://www.pivoxquant.com` 추가
- **우선순위**: 공유 전 권장

### ⚠️ H3. Rate limit in-memory + gunicorn 2 workers
- **파일**: `security.py:57`
- **증거**: `memory://` 기본. 워커별 독립 카운터
- **공격**: 로그인 5/min → 실제 10/min, 브루트포스 방어 약화
- **수정**:
  - Redis 사이드카 or
  - 베타 기간만 `--workers 1` (지금 `Procfile`은 2)
- **우선순위**: 공유 권장 (베타 기간은 workers=1로)

### ⚠️ H4. Open Redirect via `//evil.com`
- **파일**: `routes/auth.py:161`
- **증거**: 가드가 `startswith("/")` + `"://" not in` → `//evil.com`은 통과
- **공격 시나리오**: `/api/auth/google/callback?next=//evil.com` → 로그인 후 피싱 사이트로
- **수정**: `redirect_url.startswith("//")` 차단, 화이트리스트 경로만 허용
- **우선순위**: 공유 전 권장

### ⚠️ H5. `data_fetcher.py` .env 직접 파싱
- **파일**: `data_fetcher.py:292`
- **증거**: 런타임에 `.env` 파일 라인별로 읽어서 `ANTHROPIC_API_KEY=` 추출
- **영향**: 컨테이너에 `.env` 없으면 무동작, 로컬에서 Railway env와 혼선
- **수정**: `os.environ.get()` 단일화, `.env` 파싱 코드 삭제
- **우선순위**: 권장

### 💡 M1. HANDOVER.md에 베타 비번 6회 하드코딩
- **파일**: `HANDOVER.md:14,70,102,159,210,361`
- **영향**: 리포 public 전환 시 즉시 유출
- **수정**: 런칭 전 비번 환경변수 참조로 치환, 리포 private 유지

### 💡 M2. CSRF 토큰 httpOnly=false
- **파일**: `security.py:293`
- **영향**: Double-submit 패턴상 불가피. XSS 1건이면 CSRF 우회
- **수정**: C1과 함께 XSS 억제가 핵심

### 💡 M3. `X-XSS-Protection` 헤더 사용 중단
- **파일**: `security.py:266`
- **수정**: 제거 또는 `0`

### 💡 M4. OAuth `oauth_nonce` callback 검증 미확인
- **파일**: `auth.py:113`
- **확인**: Authlib `parse_id_token(nonce=)` 호출 여부

### 💡 M5. `session.clear()` 뒤 `_last_active` 재설정 누락
- **영향**: 첫 요청에서 inactivity 계산 오작동 가능

---

## 3. 엔지니어링 코드 품질 감사 (진행 중)

- Google Staff Engineer 기준 리뷰
- 완료 시 P0/P1/P2 분류된 리포트 추가 예정
- **예상 항목**: 에러 핸들링, 타입 안전성, dead code, naive datetime, SWR key 충돌

> ⏳ Agent 결과 나오면 이 섹션 업데이트

---

## 4. 라이브 E2E QA 결과 (실행 불가)

### ❌ 상태: 자동화 실패
- Claude Code 세션에서 브라우저 MCP / curl 권한 거부
- "재현하지 못한 테스트는 통과가 아니다" 원칙으로 미실행

### 대체 방안
- CEO 수동 테스트 (10분)
- 또는 형이 브라우저 MCP 권한 허용하면 자동 재시도

### 수동 테스트 체크리스트 (CEO 기준)
- [ ] `https://pivoxquant.com` 접속 → 베타 게이트
- [ ] `${BETA_PASSWORD}` 입력 → 홈 진입
- [ ] Google 로그인 버튼 → Google OAuth 이동
- [ ] Kakao 로그인 버튼 → Kakao OAuth 이동
- [ ] 홈 대시보드 (Market, Signals, Portfolio) 데이터 로딩
- [ ] `/simulator/what-if?ticker=AAPL&start_date=2020-01-01&amount=1000` 동작
- [ ] 모바일 뷰포트에서 레이아웃
- [ ] 브라우저 콘솔 빨간 에러 없음

---

## 5. 기타 알려진 이슈

### 무관한 빌드 경고 (무시해도 됨)
- `npm warn deprecated node-domexception@1.0.0` — transitive deprecation
- `⚠ Using edge runtime on a page currently disables static generation` — middleware 정보성 경고

### 이전 세션에서 인계된 미해결 (HANDOVER 기반)
- Morning Brief cron 2회 실행 가능성 (DB UniqueConstraint로 보호됨)
- naive datetime 혼재 (routes에서 aware vs naive 비교 0건이라 현 상태 안전)
- Alembic migration 003 자동 실행 없음 (`db.create_all()` + `_run_migrations`로 보완)

---

## 6. 수정 우선순위 / 실행 순서 (공유 D-Day 기준)

### D-Day-2 (공유 2일 전) — CRITICAL 수정
1. **B2, B3, B4, B5** — UX 4대 버그 (frontend-dev agent 진행 중)
2. **C1** — CSP unsafe-eval 프로덕션 제거
3. **C2** — 베타 쿠키 HMAC 서명 토큰화
4. **C3** — timingSafeEqual 적용
5. **C4** — OAuth state 파라미터 추가 (Google + Kakao)
6. **H1** — `FLASK_ENV=production` Railway Variables 확인 (30초)
7. **H2** — CORS_ORIGINS에 www 추가 (30초)

### D-Day-1 (공유 1일 전) — HIGH 점검
8. **H3** — Procfile `--workers 1` 임시 변경
9. **H4** — Open redirect 가드 강화
10. **H5** — data_fetcher.py .env 파싱 제거
11. **B1** — 타임머신 번역 키 추가
12. **수동 E2E 10분**

### D-Day (공유 당일)
13. **공유 메시지 카톡 발송 (친한 친구 3~5명 우선)**
14. **피드백 수집 채널** 준비 (스프레드시트 또는 구글폼)

### 공유 후 (D+1 ~ D+7)
15. **B6** — 번역 전수 점검
16. **M1~M5** — Medium 이슈 정리
17. **Redis** — Rate limiter 분산화
18. **Sentry** — 에러 모니터링 연결

---

## 7. Agent 위임 현황

| Agent | 작업 | 상태 |
|---|---|---|
| frontend-dev #1 | B2(로고) + B3(Skip) 수정 | ⏳ 진행 중 |
| frontend-dev #2 | B4(온보딩재질문) + B5(모바일메뉴) 수정 | ⏳ 진행 중 |
| engineering | 전체 코드 품질 감사 | ⏳ 진행 중 |
| security | 보안 감사 | ✅ 완료 (위 §2) |
| qa | 라이브 E2E 테스트 | ❌ 권한 거부 |

각 agent 완료 시 이 문서 업데이트.

---

## 8. 베타 공유 체크리스트

### 공유 메시지 (카톡/DM)
```
🧪 PivoxQuant 베타 테스트 도와줄래?

미국 + 한국 주식 분석하는 퀀트 기반 AI 투자 보조 서비스.

🔗 https://pivoxquant.com
🔑 비밀번호: ***REDACTED***

5분만 써보고 뭐 이상한 거 있었냐 알려주면 도움 됨.
스샷 막 보내줘 🙏
```

### 공유 전 마지막 체크
- [ ] 이 문서 §6 D-Day-2 전부 완료
- [ ] 수동 E2E 10분 통과
- [ ] Railway Variables 확인 (`FLASK_ENV`, `CORS_ORIGINS` www 추가)
- [ ] `HANDOVER.md` 가 public 리포에 안 올라가있는지 확인
- [ ] Sentry 연결 권장 (에러 추적)

### 공유 후 24시간 모니터링
- Railway logs에서 5xx 에러 없는지
- Vercel analytics에서 페이지 로드 시간
- 친구들 피드백 수집 → 트리아지

---

## 9. 파일 레퍼런스

수정이 필요한 주요 파일:
- `/Users/seanbae/Desktop/취준/stockpilot/frontend/middleware.ts` (C1)
- `/Users/seanbae/Desktop/취준/stockpilot/frontend/src/app/api/beta-auth/route.ts` (C2, C3)
- `/Users/seanbae/Desktop/취준/stockpilot/routes/auth.py` (C4, H4)
- `/Users/seanbae/Desktop/취준/stockpilot/security.py` (H3, M3)
- `/Users/seanbae/Desktop/취준/stockpilot/data_fetcher.py` (H5)
- `/Users/seanbae/Desktop/취준/stockpilot/Procfile` (H3)
- `/Users/seanbae/Desktop/취준/stockpilot/frontend/messages/en.json` (B1)
- `frontend/src/components/layout/top-bar.tsx` (B2, B5)
- `frontend/src/app/(auth)/onboarding/` (B3, B4)

수정 금지:
- `engine.py`, `quant_models.py`, `autotrader.py`, `risk_defense.py`

---

**종합 판단**: 현재 상태로 지인 공유 **불가**. CRITICAL 4건(C1-C4) + UX 4건(B2-B5) 처리 후 공유 권장. 예상 소요 2~4시간.
