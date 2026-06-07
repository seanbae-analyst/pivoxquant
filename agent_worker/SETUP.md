# PivoxQuant Agent Worker — 수동 셋업 가이드

Phase 1 autonomous agent worker를 프로덕션(Railway)에 올리기 위한 수동 작업 체크리스트. 순서대로 실행하세요.

> ⚠️ **2026-05-03 업데이트** — Claude Max OAuth 마이그레이션 영향 알림
>
> CI 워크플로우(morning-triage / self-healing)는 2026-05-03에 `CLAUDE_CODE_OAUTH_TOKEN`(Claude Max 구독 자격) 기반으로 전환됨 (`docs/CLAUDE_CODE_OAUTH_SETUP.md` 참조). 그러나 **agent_worker는 Slack ↔ Claude 브릿지로 Anthropic Messages API를 직접 호출**하며 Messages API는 OAuth 토큰을 거부함. 따라서 agent_worker는 여전히 `ANTHROPIC_API_KEY`(per-token 과금)가 필요.
>
> **현재 정책 (Phase 2 deferred)**: `ANTHROPIC_API_KEY`가 없으면 worker는 첫 Claude 호출 시 `RuntimeError("ANTHROPIC_API_KEY not set")`를 던지고 종료 (`agent_worker/claude_client.py:21`). 즉 **`ANTHROPIC_API_KEY`를 비워두면 worker가 자동으로 dormant 상태**가 됨 — 별도 토글 환경변수 불필요.
>
> **PivoxQuant 출시 직후엔 worker를 켜지 않을 계획.** 웹 앱이 primary surface, Slack 통합은 Phase 2로 미룸. 켜고 싶을 때:
> 1. Anthropic console에서 API key 발급 + credit 충전
> 2. Railway worker 서비스 변수에 `ANTHROPIC_API_KEY` 추가
> 3. 자동 재시작 → worker가 정상 기동

---

## 1. Slack 워크스페이스 + 알림 채널 생성

1. https://slack.com/get-started 에서 워크스페이스 생성 (이미 있으면 스킵).
2. 채널 이름 `#pivoxquant-alerts` 생성. Private 권장.
3. 본인만 멤버로 두세요. 에스컬레이션 알림이 여기로 옵니다.

`[SCREENSHOT: slack 채널 생성 화면]`

---

## 2. Slack Incoming Webhook URL 발급

1. https://api.slack.com/apps → **Create New App** → **From scratch** → 앱 이름 `PivoxQuant Agent`, 워크스페이스 선택.
2. 왼쪽 메뉴 **Incoming Webhooks** → 토글 **On**.
3. 하단 **Add New Webhook to Workspace** → `#pivoxquant-alerts` 선택 → **Allow**.
4. 생성된 **Webhook URL** 복사 (형식: `https://hooks.slack.com/services/TXXX/BXXX/xxxxx`).

`[SCREENSHOT: slack webhook url 생성 화면]`

> 이 URL은 누구든 이 URL을 아는 사람이 채널에 메시지를 보낼 수 있으므로 **비밀로 취급**하세요.

---

## 3. Railway에 Worker 서비스 추가

1. Railway 대시보드 → 기존 `pivoxquant` 프로젝트 열기.
2. **+ New** → **GitHub Repo** → 같은 repo(`seanbae-analyst/pivoxquant`) 선택.
3. 서비스 이름을 `pivoxquant-agent-worker` 로 변경.
4. **Settings → Service → Start Command** 를 다음으로 설정:
   ```
   python -m agent_worker.worker
   ```
   (`agent_worker/Procfile`을 사용해도 되지만 Railway는 루트 Procfile만 읽음 — Start Command 덮어쓰기가 확실합니다.)
5. **Settings → Networking** 에서 public domain은 만들지 마세요. Worker는 외부 노출 불필요.
6. 같은 프로젝트 내이므로 기존 Postgres DB의 `DATABASE_URL` 변수를 공유 참조로 연결:
   - **Variables → Add Variable Reference → Postgres → DATABASE_URL**

`[SCREENSHOT: railway worker 서비스 생성 + DATABASE_URL 참조 화면]`

---

## 4. 환경변수 설정 (Worker 서비스 전용)

Railway worker 서비스 **Variables** 탭에 다음을 추가:

| 키 | 값 | 설명 |
|---|---|---|
| `SLACK_WEBHOOK_URL` | (2단계에서 복사한 URL) | 에스컬레이션 알림 |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Claude Haiku 호출용 |
| `DATABASE_URL` | (Postgres 참조) | Web 서비스와 공유 |
| `TARGET_URL` | `https://pivoxquant.com` | 헬스체크 대상 |
| `DEV_LOGIN_SECRET` | (Web 서비스와 동일 값) | 헬스체크 로그인용 |
| `ADMIN_EMAILS` | `seanbae1521@gmail.com` | 쉼표 구분. 관리자 화면 접근 제한 |
| `AGENT_DAILY_BUDGET_USD` | `5.00` | 일일 Claude 비용 상한 |
| `AGENT_KILL_SWITCH` | `false` | 즉시 종료하려면 `true` |

> Web 서비스에도 `ADMIN_EMAILS` 와 `DATABASE_URL` 이 있어야 Admin 페이지가 동작합니다.

---

## 5. DB 마이그레이션 실행

Railway Web 서비스의 **Deploy**가 자동으로 `flask db upgrade`를 실행합니다 (루트 `Procfile`의 `release:` 라인). 수동으로 돌려야 하면:

```bash
# Railway CLI (로컬에서 서비스 shell 접속)
railway run --service pivoxquant-web flask db upgrade
```

마이그레이션 ID: `004_agent_tables` 가 적용되었는지 확인:

```bash
railway run --service pivoxquant-web flask db current
# → 004_agent_tables (head)
```

`[SCREENSHOT: flask db current 결과]`

---

## 6. Flask app.py 에 Admin Blueprint 등록

`app.py` (또는 `create_app()` 내부)에 다음 한 줄 추가:

```python
# app.py — Blueprint 등록 구간
from agent_worker.admin_routes import admin_agent_bp
app.register_blueprint(admin_agent_bp)
```

- 등록 위치: 기존 `auth_bp`, `portfolio_bp` 같은 Blueprint 등록 구간 바로 아래.
- URL prefix는 Blueprint 자체에 `/admin/agent` 로 설정되어 있어 별도 인자 불필요.
- 등록 후 로컬에서 `http://localhost:5050/admin/agent/` 가 열리는지 확인 (관리자 이메일 로그인 필요).

커밋 후 `git push` → Railway 자동 재배포 → `https://api.pivoxquant.com/admin/agent/` (또는 Web 서비스 도메인) 으로 접근 가능.

---

## 7. 로컬 테스트 방법

### 7-1. 로컬에서 단발 헬스체크 실행

```bash
cd /Users/seanbae/Desktop/취준/pivoxquant

# .env 로드 후 (또는 export)
export DATABASE_URL="postgresql://..."
export TARGET_URL="https://pivoxquant.com"
export DEV_LOGIN_SECRET="..."
export SLACK_WEBHOOK_URL="https://hooks.slack.com/..."

python -c "from agent_worker.scenarios import daily_healthcheck; print(daily_healthcheck.run())"
```

성공 시: Slack `#pivoxquant-alerts` 에 `✅ Daily healthcheck passed` 메시지.
실패 시: `❌ Healthcheck failed — …` 메시지 + `agent_tasks` 테이블에 `investigate` 태스크 1건 삽입.

### 7-2. 로컬에서 worker 루프 실행

```bash
python -m agent_worker.worker
```

- 시작 시 Slack `🟢 PivoxQuant agent worker started` 알림.
- 30초마다 `agent_tasks` 중 `status='pending'` 1건 pickup (Phase 1은 로깅만).
- `Ctrl+C` 종료 시 `🔴 PivoxQuant agent worker stopped` 알림.

---

## 8. 첫 헬스체크 수동 트리거

프로덕션에서 스케줄(08:00 KST) 기다리지 않고 즉시 한 번 돌려보려면:

### 방법 A — Railway shell

```bash
railway run --service pivoxquant-agent-worker python -c \
  "from agent_worker.scenarios import daily_healthcheck; print(daily_healthcheck.run())"
```

### 방법 B — 로컬에서 프로덕션 DB 찌르기

7-1과 동일하되 `DATABASE_URL` 을 Railway Postgres 값으로 설정.

결과 확인:

```sql
SELECT id, type, status, risk_score, result->>'forbidden_terms_hit' AS forbidden
FROM agent_tasks
WHERE type = 'healthcheck_result'
ORDER BY id DESC LIMIT 5;
```

---

## 9. Kill Switch 사용법

문제가 감지되거나 예산이 나가는 것 같으면 즉시 중지:

### 옵션 1 — Railway 환경변수

Worker 서비스 Variables:
```
AGENT_KILL_SWITCH=true
```
→ Railway가 재시작할 때 즉시 exit + Slack `🛑 KILL_SWITCH=true — shutting down` 알림.
→ 복구: 값을 `false` 로 바꾸고 재배포.

### 옵션 2 — 오늘 예산만 중지 (worker는 계속 실행)

관리자 화면 `/admin/agent/` 하단의 **오늘 중지** 버튼 클릭, 또는:

```bash
curl -X POST https://pivoxquant.com/admin/agent/halt -b "session=..."
```

→ 오늘 날짜의 `agent_budget.halted = TRUE`. Worker는 살아있지만 Claude 호출을 중단.
→ 복구: `DELETE FROM agent_budget WHERE date = CURRENT_DATE;` 또는 다음날 자동 리셋.

### 옵션 3 — 서비스 자체 정지

Railway 대시보드 → 서비스 → **Settings → Danger → Remove Service** 또는 **Pause**.

---

## 체크리스트

- [ ] Slack 채널 생성
- [ ] Webhook URL 발급 및 환경변수 입력
- [ ] Railway worker 서비스 생성 + Start Command 설정
- [ ] DATABASE_URL 공유 참조
- [ ] 모든 환경변수 입력 완료
- [ ] `flask db upgrade` 로 `004_agent_tables` 적용 확인
- [ ] `app.py` 에 `admin_agent_bp` 등록 + 배포
- [ ] 로컬에서 헬스체크 1회 성공 (Slack ✅ 수신)
- [ ] `/admin/agent/` 접속 가능
- [ ] KILL_SWITCH 테스트 (true → 재시작 → Slack 확인 → false 복구)

모든 체크 끝나면 Phase 1 완료. Phase 2에서 investigator agent와 approval workflow를 연결합니다.
