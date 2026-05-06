# PivoxQuant — Master Fix Plan (2026-05-01)

> 3개 감사 보고서(CRITICAL · SECONDARY · EMAIL)에서 발견한 **38개 이슈를
> 9개 phase로 묶어** Claude Code가 순차 처리할 수 있게 정리한 단일 작업 계획.

## 참조 파일 (이 폴더에 함께 있음)
- `CRITICAL_BUG_VERIFICATION_2026-05-01.md` — UX critical 5건 (Bug #1~#5)
- `SECONDARY_BUG_SWEEP_2026-05-01.md` — 코드 품질/보안/성능 20건 (B1~B20)
- `EMAIL_BUG_AUDIT_2026-05-01.md` — 이메일 시스템 13건 (E1~E13)

---

## 사용 방법 (Sean)

터미널에서:

```bash
cd /Users/seanbae/Desktop/취준/pivoxquant
claude
```

Claude Code 켜진 후 **이 한 덩어리를 통째로** 붙여넣기:

````
MASTER_FIX_PLAN_2026-05-01.md 파일을 읽고, "## 작업 지시 (Claude Code 전용)"
섹션의 9개 Phase를 순서대로 처리하라.

원칙:
- 각 Phase = 별도 git branch + 1개 이상 commit
- Phase N 완료 후 반드시 사용자(Sean)에게 정직 보고하고 승인 대기
- 사용자가 "다음" 또는 "go" 답하면 Phase N+1 시작
- "스킵" 또는 "skip"이면 다음 Phase
- 작업 중 발견된 새 이슈는 NEW_FINDINGS.md에 누적
- 절대 main에 직접 push 금지. PR 형태 권장

지금 Phase 0 (Pre-flight)부터 시작해.
````

---

## 작업 지시 (Claude Code 전용)

### Phase 0 — Pre-flight (5분)

**목적**: 작업 시작 전 환경/repo 상태 점검.

```bash
cd /Users/seanbae/Desktop/취준/pivoxquant

# git 손상 검사 (B15)
git fsck --full 2>&1 | tee /tmp/pq_gitfsck.log

# working tree clean 확인
git status

# 현재 main HEAD
git log --oneline -3

# 테스트 baseline
pytest -q 2>&1 | tail -10

# 환경변수 누락 점검 (B1)
diff <(grep -oE "^[A-Z_]+=" .env | sort -u) \
     <(grep -oE "^[A-Z_]+=" .env.example | sort -u) > /tmp/pq_env_diff.txt

# alembic 헤드 다중 점검 (B12)
alembic heads 2>&1
```

**산출물**: 위 5개 결과를 정리해 사용자에게 보고. 다음 항목 명시:
- `git fsck` errors/warnings
- pytest 결과 (1305 baseline 유지 여부)
- alembic heads 개수 (1 = 정상, >1 = 문제)
- `.env` 누락 키 개수
- working tree 상태

**STOP. 사용자 응답 대기.**

---

### Phase 1 — 5분짜리 Quick Wins 일괄 (15분)

**목적**: 위험-비용 비율 압도적인 수정 4개를 한 commit으로.

브랜치: `fix/quick-wins-2026-05-01`

| # | 위치 | 변경 |
|---|---|---|
| E3 | `services/artifacts/earnings_prebrief_service.py:1630` | `with smtplib.SMTP(...) as s:` 다음 줄에 `s.starttls()` + login + port (다른 17개 서비스 패턴 그대로) |
| E5 | `services/artifacts/templates/earnings_prebrief_email.html:108` | `pdf_url` 없으면 `<a>` 자체 숨김 (`{% if pdf_url %}<a ...>...</a>{% endif %}`) |
| E8 | `services/artifacts/weekly_memo_service.py:1545` | `f"Week {iso[1]}, {iso[0]} Investor Memo"` 패턴으로 연도 포함 |
| B3 trigger 1개 | `routes/agent.py:190` POST /query | `_rate_limit_ok` 데코레이터화 또는 명시적 호출 검증 |

**검증**:
```bash
pytest tests/test_earnings_prebrief_service.py -v
pytest tests/test_weekly_memo_service.py -v
```

**Commit 메시지**: `fix(quick-wins): STARTTLS digest + email link guards + week year + agent rate-limit`

**STOP. diff 보고 + 사용자 승인 대기.**

---

### Phase 2 — Email 컴플라이언스 P0 (E1 + E2) (반나절)

**목적**: 정보통신망법 §50 대응. 글로벌 수신거부 + unsubscribe 링크.

브랜치: `fix/email-compliance-p0`

#### E1: `email_opt_out` 컬럼 추가

1. `migrations/versions/021_email_opt_out.py` 생성:
   - idempotent ALTER TABLE (기존 008/009 패턴 참고)
   - `op.add_column("users", sa.Column("email_opt_out", sa.Boolean, nullable=False, server_default=sa.false()))`
   - downgrade 도 작성

2. `models/user.py` line 43 다음에 추가:
   ```python
   email_opt_out = db.Column(db.Boolean, default=False,
                              nullable=False, server_default="0")
   ```

3. `routes/profile.py` (또는 새 `routes/email_preferences.py`)에:
   ```
   PATCH /api/profile/email-preferences
   Request: {email_opt_out?: bool, email_opt_out_earnings?: bool}
   Response: {ok: true, preferences: {...}}
   @api_auth, @csrf protect
   ```

4. `frontend/src/app/(dashboard)/settings/page.tsx`에 토글 2개:
   - "모든 마케팅 이메일 받지 않기"
   - "실적 발표 알림만 받지 않기"
   - PATCH 호출 + sonner toast

5. `tests/test_email_opt_out.py` 신규:
   - 컬럼 존재 검증
   - PATCH 정상 동작
   - opt-out=true 후 send_email() False 반환 (실 DB 검증)
   - 기존 `tests/test_weekly_memo_service.py:194`의 가짜 테스트 수정 (실 DB로)

#### E2: Unsubscribe 링크 + List-Unsubscribe 헤더

1. `services/email_token.py` 신규:
   - `itsdangerous.URLSafeTimedSerializer(SECRET_KEY)`
   - `make_unsubscribe_token(user_id) -> str` (max_age=365일)
   - `verify_unsubscribe_token(token) -> user_id | None`

2. `routes/profile.py`에 추가:
   ```
   GET /api/email/unsubscribe?token=...&type=all|earnings
   - 토큰 검증
   - 해당 user의 opt-out 플래그 set
   - HTML 응답: "수신거부 완료" 페이지
   ```

3. 5개 모든 템플릿 푸터에 링크 추가:
   ```jinja
   <a href="{{ unsubscribe_url }}" style="color:#8a8a8a;font-size:9pt;">
     이 메일 더 받지 않기 / Unsubscribe
   </a>
   ```

4. 19개 서비스의 send_email에 `unsubscribe_url` 컨텍스트 + List-Unsubscribe 헤더:
   ```python
   from sendgrid.helpers.mail import Header
   token = make_unsubscribe_token(user.id)
   url = f"{FRONTEND_URL}/api/email/unsubscribe?token={token}&type=all"
   mail.add_header(Header("List-Unsubscribe", f"<{url}>"))
   mail.add_header(Header("List-Unsubscribe-Post", "List-Unsubscribe=One-Click"))
   ```

   ⚠️ 19개 동일 코드 → Phase 8에서 EmailSender 추출. 지금은 일단 복붙.

**검증**:
- `pytest tests/test_email_opt_out.py -v`
- `pytest -q tests/test_*_service.py` (기존 17개 통과)
- 실 발송 테스트: `python3 -c "from services.artifacts.weekly_memo_service import WeeklyMemoService; ..."` 으로 unsubscribe 토큰 포함 HTML dump

**Commit 메시지**: `feat(email): global opt_out column + unsubscribe link + List-Unsubscribe header`

**STOP. 사용자 승인 대기.**

---

### Phase 3 — Rate Limit 일괄 (B3) (반나절)

**목적**: 25개+ POST/PUT/DELETE 엔드포인트에 rate limit 추가.

브랜치: `fix/rate-limits-coverage`

대상 엔드포인트 (SECONDARY_BUG_SWEEP_2026-05-01.md B3 참조):
- `routes/alerts.py`: `/read-all`, `/<id>/read`, `/<id>` DELETE, `/read`, `/clear`, `/admin/check`
- `routes/artifacts.py`: 13개 `*/trigger`, `*/preview`, `*/submit`, `/privacy`
- `routes/agent_admin.py`: `/kill`, `/revive`, `/purge-expired` (admin이지만 추가 보호층)

**전략**:
1. `security.py`에 새 데코레이터 추가:
   ```python
   artifact_rate_limit = limiter.limit("5/minute")  # /trigger 류
   alert_action_rate_limit = limiter.limit("30/minute")  # /read 류
   ```
2. 엔드포인트에 `@artifact_rate_limit` 또는 `@alert_action_rate_limit` 추가
3. 429 응답이 정상 작동하는지 smoke test

**검증**:
```bash
# 429 동작 확인 (개념 코드)
for i in {1..10}; do curl -X POST localhost:5050/api/artifacts/weekly-memo/trigger; done
# 5번까지 200, 이후 429 기대
```

**Commit 메시지**: `fix(security): rate-limit 25 mutating endpoints (artifacts/alerts/agent)`

**STOP. 사용자 승인 대기.**

---

### Phase 4 — UX Critical 5개 검증 + 수정 (1~2일)

**목적**: CLAUDE.md(2026-04-14)의 CRITICAL 5건 실 클릭 검증 + 깨진 부분만 수정.

각 버그 별도 브랜치. 상세 사양은 `CRITICAL_BUG_VERIFICATION_2026-05-01.md`의 Prompt #1~#5 그대로 사용.

추천 순서 (의존성 기반):
1. `fix/critical-bug-2-search` — Top-bar 검색 + Cmd+K
2. `fix/critical-bug-3-watchlist` — Watchlist add (Discover의 prerequisite)
3. `fix/critical-bug-1-portfolio` — Portfolio + Add Position
4. `fix/critical-bug-4-risk` — Risk 페이지 7-Layer 연동
5. `fix/critical-bug-5-discover` — Discover (의도된 빈 결과 vs 실 버그 구분)

각 버그마다:
- Claude in Chrome MCP로 실 클릭 검증 (없으면 코드 검토 + pytest로만)
- 실패한 단계만 정확히 수정
- 작동 코드는 절대 건드리지 마
- pytest + 신규 smoke test

**STOP. 5개 끝나면 사용자 승인 대기.**

---

### Phase 5 — N+1 쿼리 Batch Load (B4 + B6) (3시간)

**목적**: 5곳의 N+1 패턴을 batch load로.

브랜치: `perf/n-plus-one-batch-load`

대상:
- `routes/ai.py:96, 127, 402-403`
- `routes/alerts.py:177-178`
- `routes/quant.py:161-162, 337-338`

**참조 패턴** (`routes/portfolio.py:50-54` 이미 적용):
```python
tickers = [p.ticker for p in positions]
cache_map = {
    c.ticker: c
    for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
} if tickers else {}
# 루프 안에서: cache_map.get(p.ticker)
```

추가로 B6: `routes/ai.py:96, 127`의 `SignalCache.query.all()` 전체 스캔 → 사용자 스코프 한정.

**검증**:
- pytest 전체
- `pytest --benchmark` 가능하면 before/after 비교

**Commit**: `perf(routes): batch-load SignalCache to remove N+1 (5 sites)`

**STOP. 사용자 승인 대기.**

---

### Phase 6 — 무테스트 라우트 14개 Smoke Test (B5) (반나절)

**목적**: 14개 무테스트 라우트에 최소 smoke test (auth=401 + happy path).

브랜치: `test/smoke-coverage-14-routes`

대상 (`SECONDARY_BUG_SWEEP_2026-05-01.md` B5):
```
ai, broker_oauth, daytrade — prod 트래픽
admin_fmp, admin_preview, command_center, counterfactual — admin/도구
autotrade(disabled), dev_auth, health, pre_trade, push, quant_composer, simulate
```

각 라우트당 ~30 lines. 패턴:
```python
def test_route_requires_auth(client):
    r = client.get("/api/...")
    assert r.status_code == 401

def test_route_happy_path(client, auth_user):
    r = client.get("/api/...")
    assert r.status_code in (200, 503)  # 503 OK if upstream dependency
```

**Commit**: `test: add smoke coverage for 14 untested route modules`

**STOP. pytest 결과 보고 후 승인 대기.**

---

### Phase 7 — Email Refactor (E9~E13) (1일)

**목적**: 17개 서비스의 send_email 코드 ~1,200줄 중복 → 공통 `EmailSender`로.

브랜치: `refactor/email-sender-common`

1. `services/email/sender.py` 생성:
   ```python
   class EmailSender:
       def send(
           self, user, subject, html_body, *,
           pdf_bytes=None,
           from_env_var="WEEKLY_MEMO_FROM_EMAIL",
           opt_out_attrs=("email_opt_out",),
           reply_to="support@pivoxquant.com",
           display_name="PivoxQuant Research",
       ) -> bool:
           # opt-out 체크 (E1, 다중 가능)
           # from_email 해석 + Display Name (E13)
           # SendGrid 우선 → SMTP STARTTLS fallback (E3)
           # List-Unsubscribe 헤더 (E2)
           # Reply-To (E7)
   ```

2. 17개 서비스의 send_email 메서드를 `EmailSender().send(...)` 호출로 교체

3. `_currency_prefix(ticker)` 헬퍼 (E4) 별도 추출 → 17곳 일괄 적용

4. `_disclaimer.html` include 강제 (E10): `brag_card_email.html`의 인라인 disclaimer를 `{% include '_disclaimer.html' %}`로 교체. dark-mode 대응 CSS variant는 `_disclaimer.html` 내부에 `@media`로

5. `dd_checklist_email.html` fallback disclaimer 제거 → include 강제 (E11)

6. 4개 템플릿에 `<html lang="ko">` 추가 (E12)

**검증**: 17개 서비스 테스트 전부 통과 + 신규 EmailSender 단위 테스트

**Commit**: `refactor(email): consolidate 17 send_email duplicates into EmailSender`

**STOP. 사용자 승인 대기.**

---

### Phase 8 — 잡다한 P2 일괄 (1일)

**목적**: 모아두면 의미 없지만 모이면 의미 있는 것들.

브랜치: `chore/p2-cleanup`

| # | 작업 |
|---|---|
| B7 | CSP `unsafe-inline` 제거 — Next.js 16 nonce 패턴 (`frontend/middleware.ts:140`, `security.py:411`) |
| B8 | `except Exception: pass` 30+ 위치 → `logger.exception(...)` 일괄 변환. 단 `engine.py`/`quant_models.py`/`risk_defense.py` 수정 금지 → 별도 `LEGACY_SILENT_EXCEPTIONS.md` 노트 |
| B9 | `routes/counterfactual.py:486, 738` fx-historical TODO — `fx_service.get_rate_at(date)` 추가 (시계열 cache + FMP/exchangerate-api fallback) |
| B11 | `tests/test_quant.py:954, 962` skipif 영구 skip 의도 확인. `routes/quant.py` 존재하므로 skip 조건 stale → 제거 또는 의도 명시 |
| B13 | 미사용 shadcn 9개 + hooks 8개 + types 13개 일괄 삭제 (CLAUDE.md 인지 항목) |
| B14 | ESLint 17 errors 카탈로그 + 수정 |
| B19 | KR ticker `.KS`/`.KQ` suffix 자동 추가 일관성 — `name_resolver` + `data_fetcher`에서 단일 진입점 검증 |
| B20 | `frontend/src/lib/realtime.tsx` SSE EventSource 재연결 — exponential backoff |
| E14 | 4개 템플릿에 preview text 추가 |
| E16 | digest dedup KST/UTC 명시 (도메인 메서드) |

**Commit**: 항목당 1 commit. prefix는 적절히.

**STOP. 사용자 승인 대기.**

---

### Phase 9 — 사용자 액션 체크리스트 (CEO만 가능)

**목적**: 코드 변경 X. `NEEDS_CONFIG.md`에 정리만.

`NEEDS_CONFIG.md` 신규 작성:

```markdown
# PivoxQuant — 출시 전 사용자(CEO) 액션 체크리스트

## 🔴 P0 — 출시 차단

- [ ] B1: `.env`에 30+ 누락 키 채우기
  - 누락 목록: (Phase 0의 /tmp/pq_env_diff.txt 그대로)
  - prod는 Railway/Vercel 환경변수에 직접 설정
  - 특히: STRIPE_*, PIVOX_BROKER_ENCRYPTION_KEY, CSRF_SECRET,
         DATABASE_URL, ADMIN_EMAILS, RATELIMIT_STORAGE_URI
- [ ] B2: Anthropic API credit 충전 (최소 $50 권장)
- [ ] B6 / E6: pivoxquant.com 도메인 등록 + SendGrid sender
        authentication (SPF/DKIM/DMARC) 설정
- [ ] OAuth redirect URI 등록 (HANDOVER.md P0):
  - Google Cloud Console: http://localhost:3000/api/auth/google/callback
  - Kakao Developers: http://localhost:3000/api/auth/kakao/callback
  - prod 도메인도 동시 등록

## 🟠 P1 — 출시 직전

- [ ] Stripe Test mode → Live mode 전환 + 사업자등록 후 정산
- [ ] FMP plan 업그레이드 검토 (Starter $29 → Standard $99) — 무료 100명 시점
- [ ] `LEGAL_CONSULT_PACKAGE.md` 변호사 1회 검토 (₩200~500만원)
- [ ] HANDOVER.md v19 세션 정리

## 🟡 P2 — 베타 후

- [ ] B12 alembic heads 다중 검증
- [ ] B15 `git fsck` 손상 commit 복구 (필요 시)
```

**Commit**: `docs: launch checklist for CEO actions (NEEDS_CONFIG.md)`

**STOP. 전체 작업 완료 보고. PR 9개 + NEEDS_CONFIG.md 1개.**

---

## 정직 보고 템플릿 (각 Phase 후)

```
## Phase N 완료 보고

### 변경 파일
- (git diff --stat)

### 작동 검증
- pytest: M/N pass (이전 N/N → 변경 사유)
- 신규 테스트: K개 추가
- 실 클릭 검증 (있으면): ✓/✗

### 발견된 새 이슈 (NEW_FINDINGS.md에 추가)
- ...

### 누락한 부분
- ...

### 다음 Phase 준비 상태
- ✓ 진행 가능 / ⚠ 의존성 이슈 (사유)
```

---

## 전체 일정 요약

| Phase | 시간 | 위험도 |
|---|---|---|
| 0. Pre-flight | 5분 | 0 |
| 1. Quick wins (E3+E5+E8+B3 일부) | 15분 | 0 |
| 2. Email 컴플라이언스 (E1+E2) | 반나절 | 중 (DB 마이그레이션) |
| 3. Rate limit (B3 전체) | 반나절 | 낮음 |
| 4. UX Critical 5개 | 1~2일 | 중 (실 클릭 의존) |
| 5. N+1 batch load | 3시간 | 낮음 |
| 6. 무테스트 라우트 smoke | 반나절 | 0 |
| 7. Email refactor | 1일 | 중 (대규모 리팩토링) |
| 8. P2 cleanup | 1일 | 낮음 |
| 9. NEEDS_CONFIG.md (CEO) | 30분 | 0 |

**총 추정**: 4~5일 fulltime, 또는 2주 part-time.

**최소 출시 가능 셋**: Phase 0 → 1 → 2 → 3 → 4 (3일).
**나머지 Phase 5~9는 베타/출시 후 점진 처리 가능.**

---

## 안전망

각 Phase 시작 전 자동:
```bash
git status        # clean 확인
git checkout main && git pull
git checkout -b <phase-branch-name>
```

Phase 끝나면:
```bash
pytest -q         # 회귀 검증
git diff main --stat
git log --oneline main..HEAD
```

문제 발생 시:
```bash
git checkout main
git branch -D <phase-branch-name>  # 폐기 후 재시작
```
