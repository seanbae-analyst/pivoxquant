# Cron 워크플로 감사 — 2026-08-30

> **범위**: `.github/workflows/*.yml.disabled` 18개 (schedule 트리거 16 + push-to-main 트리거 2).
> **목적**: 조사 + 판정만. **이 감사에서 워크플로 파일은 수정하지 않았고 `.disabled` 이름도 바꾸지 않았다.**
> **전제 (실측 확인)**:
> - Railway 백엔드 소멸 — `https://web-production-7b484b.up.railway.app/api/health` → **HTTP 404**
> - Vercel 프론트 생존 — `https://www.pivoxquant.com/` → **200**, `https://pivoxquant.com/` → **307**, `/pricing` → **307** (베타 게이트)
> - GitHub Actions 정상 동작 — PR 게이트 10개 2026-08-30T04:15Z 실행 전부 success
> - 레포 visibility: **PRIVATE** (`seanbae-analyst/pivoxquant`)

---

## 0. 실측 인벤토리 (판정의 근거)

### 등록된 secret (`gh secret list`) — 4개뿐

| Secret | 등록일 |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | 2026-05-03 |
| `RAILWAY_BACKEND_URL` | 2026-05-07 |
| `SENDGRID_API_KEY` | 2026-04-09 |
| `WEEKLY_MEMO_TRIGGER_SECRET` | 2026-04-30 |

### 등록된 repo variable (`gh variable list`)

| Variable | 값 |
|---|---|
| `AUTOFIX_ENABLED` | `1` |
| `NIGHTLY_AUTO_DEV` | `1` (킬 스위치 **꺼짐** = 자율 개발 활성) |

### 워크플로가 요구하지만 **등록되지 않은** secret — 7개

`SLACK_WEBHOOK_URL` · `DEV_LOGIN_SECRET` · `DATABASE_URL` · `GPG_PASSPHRASE` · `DB_SCAN_URL` · `DB_SCAN_TOKEN` · `RAILWAY_TOKEN`

### 스크립트 / 테스트 경로 실재 확인

| 경로 | 상태 |
|---|---|
| `scripts/agent_ops/analyze_health.py` | EXISTS |
| `scripts/agent_ops/propose_upgrades.py` | EXISTS |
| `scripts/nightly/ticker_health.py` | EXISTS |
| `scripts/nightly/aggregate_and_report.py` | EXISTS |
| `scripts/nightly/critical_endpoints.py` | EXISTS |
| `scripts/nightly/indices_consistency.py` | EXISTS |
| `scripts/legal_monitor/monitor.py` | EXISTS |
| `scripts/morning_brief/build_brief.py` | EXISTS |
| `scripts/triage/morning_triage.py` | EXISTS |
| `scripts/self_healing/propose_fix.py` | EXISTS |
| `scripts/self_healing/scan_railway_logs.py` | EXISTS |
| `scripts/self_healing/fixtures/railway_sample.log` | EXISTS (2026-04-24 고정 fixture) |
| `tests/test_no_hardcoded_samples.py` | EXISTS |
| `tests/test_agent_waitlist.py` | EXISTS |
| **`tests/test_alpaca_kill_switch.py`** | **MISSING** — commit `6bea95f8` (Alpaca 통합 제거, 2026-05-27) 에서 삭제 |

**로컬 재현 (venv, exit 0)**: `pytest tests/test_no_hardcoded_samples.py tests/test_agent_waitlist.py -q` → **25 passed, 2 warnings in 1.11s**

---

## 1. 요약 표

비용 등급 정의 — GitHub Actions 분(minute) 기준 월간 추정:
**S** ≤ 25분 · **M** 25–150분 · **L** 150–500분 · **XL** > 500분 또는 Claude 토큰 반복 소모.
(private repo Free tier = 2,000분/월. PR 게이트 10개가 이미 이 예산을 일부 사용 중.)

| # | 워크플로 | 감시/실행 대상 | 스케줄 | 의존성 상태 | 비용 | 판정 |
|---|---|---|---|---|---|---|
| 1 | `agent-upgrades-monthly` | `.claude/agents/*.md` 정적 스캔 → 업그레이드 제안 Issue | 매월 1일 09:00 KST | ✅ 전부 실재 (agents 77개 git 추적) | S (~2분/월) | **지금 켜도 됨** |
| 2 | `daily-legal-scan` | 금지어 토큰 grep + `test_no_hardcoded_samples.py` | 매주 월 09:15 KST | ✅ 테스트 실재·통과. Slack 미등록이나 `-n` 가드 있음 | S (~17분/월) | **지금 켜도 됨** |
| 3 | `legal-risk-monitor` | 전체 FORBIDDEN 용어셋 + artifact HTML/PDF 샘플 + scrub 커버리지 | 매주 월 10:00 KST | ✅ stdlib 전용, DB_SCAN는 optional fallback | M (~22분/월) | **지금 켜도 됨** |
| 4 | `ssl-expiry-check` | `pivoxquant.com` TLS 인증서 만료 30일 트립와이어 | 매주 월 09:00 KST | ✅ 대상이 Vercel(생존). Slack 미등록이나 가드 있음 | S (~4분/월) | **지금 켜도 됨** |
| 5 | `weekly-security-scan` | KIS ToS 패턴 grep + `.env` 커밋 검사 + pytest 2건 | 매주 월 05:00 KST | ⚠️ `tests/test_alpaca_kill_switch.py` **MISSING** → pytest 확정 실패 | S (~17분/월) | **지금 켜도 됨** (단, 1줄 선행 수정 필수 — 아래 §2.1) |
| 6 | `agent-health-weekly` | `.bkit/state/agent_telemetry.jsonl` 기반 agent 이상 탐지 | 매주 일 11:00 KST | ❌ 텔레메트리 파일이 **.gitignore 됨** → CI에 영원히 부재 | S (~9분/월) | **폐기 권장** |
| 7 | `post-deploy-canary` | main push 후 180초 대기 → Railway health + 프론트 셸 | push→main | ❌ Railway 사망. 게다가 `vercel-deploy-canary` 헤더가 **"이 파일을 대체한다"** 명시 | L (~400분/월) | **폐기 권장** |
| 8 | `api-health` | Railway `/api/health` + 프론트 root 6시간 주기 핑 | 6시간마다 (4회/일) | ❌ Railway 404. `RAILWAY_BACKEND_URL` secret은 존재하나 죽은 호스트 | M (~120분/월) | **백엔드 복구 후** |
| 9 | `daily-api-smoke` | 프로덕션 엔드포인트 스모크 어서션 (status/shape) | 매일 06:00 KST | ❌ 전 스텝이 Railway curl | M (~60분/월) | **백엔드 복구 후** |
| 10 | `daily-regression-gate` | verify-api / verify-data / verify-security 3잡 병렬 프로덕션 검증 | 매일 06:00 KST | ❌ Railway 404 + `DEV_LOGIN_SECRET`·`SLACK_WEBHOOK_URL` 미등록 | L (~300분/월) | **백엔드 복구 후** |
| 11 | `nightly-bug-hunt` | 50종목 프로브 + 지수 정합성 + 9회 반복 엔드포인트 프로브 + pytest | 매주 월 02:00 KST | ❌ `BASE_URL=RAILWAY_BACKEND_URL`, 4개 스크립트 전부 prod 의존 | L (~215분/월, 1회 50분) | **백엔드 복구 후** |
| 12 | `weekly-memo-mon-0900-kst` | Railway `/api/artifacts/weekly-memo/trigger` POST → 전 유저 메일 팬아웃 | 매주 월 09:00 KST | ❌ 엔드포인트 소멸. secret은 존재 | S (~9분/월) — 단 **실메일 발송 blast radius** | **백엔드 복구 후** |
| 13 | `db-nightly-dump` | Railway PostgreSQL `pg_dump` → GPG 암호화 → GitHub Release | 매일 03:00 KST | ❌ **삼중 사망**: DB 자체 삭제 + `DATABASE_URL` 미등록 + `GPG_PASSPHRASE` 미등록 | L (~150분/월) | **백엔드 복구 후** |
| 14 | `vercel-deploy-canary` | main push 후 240초 대기 → Railway health(필수) + `/pricing`·`/login` 등 | push→main | ❌ Railway health `status:ok` 강제 → 무조건 실패. 프론트 프로브만은 통과 | L (~480분/월) | **백엔드 복구 후** |
| 15 | `morning-triage` | 최신 `nightly-bug-hunt` Issue를 Claude가 근본원인 코멘트 (Layer B) | 매일 09:00 KST | ⚠️ Claude 토큰은 OK. 그러나 **생산자(nightly-bug-hunt)가 죽어 분석 대상 없음** | L (Claude 매일 호출) | **백엔드 복구 후** |
| 16 | `self-healing` | Railway 런타임 로그 스캔 → Claude 패치 제안 → Draft PR (Layer C) | 12시간마다 (60회/월) | ❌ `RAILWAY_TOKEN` 미등록 + Railway 사망 → **2026-04-24 고정 fixture로 폴백** | XL (Claude 60회/월, ~360분) | **백엔드 복구 후** |
| 17 | `nightly-autonomous-dev` | `auto-eligible` 큐 1건 픽업 → Claude 구현 → Draft PR | 매일 03:00 KST | ⚠️ 큐 **비어 있음**(실측 `gh issue list --label auto-eligible` = `[]`) → 현재는 no-op. `NIGHTLY_AUTO_DEV=1` 로 킬스위치 꺼짐 | XL (7잡/19스텝, Claude, **최대 blast radius**) | **백엔드 복구 후** |
| 18 | `morning-brief` | 최근 24h 워크플로 성패 + 자동화 Issue 집계 → 단일 Issue | 매일 09:00 KST | ✅ gh API만 사용, prod 무의존 → **기술적으로는 오늘 동작** | M (~60분/월) | **백엔드 복구 후** (집계 대상이 전부 꺼져 있어 빈 브리프) |

**전 18개 동시 활성 시 추정 소모**: **약 2,500분/월** → private repo Free tier 2,000분 **초과**. PR 게이트 10개 소모분 별도.
활성화는 반드시 단계적으로 (§4 순서 참조).

---

## 2. 판정별 그룹 설명

### 2.1 `지금 켜도 됨` — 5개 (레포 내부만 검사, prod 무의존)

`agent-upgrades-monthly` · `daily-legal-scan` · `legal-risk-monitor` · `ssl-expiry-check` · `weekly-security-scan`(조건부)

공통점: **체크아웃한 레포 자체**를 검사하거나, 살아 있는 Vercel/도메인만 건드린다. Railway 사망과 무관.
합산 비용 ≈ **62분/월** (2,000분 예산의 3%).

로컬 실측 증거:
- `python3 scripts/agent_ops/propose_upgrades.py --out /tmp/pu.md` → `wrote /tmp/pu.md`, **agents scanned 23 / issues found 53**
- `python3 scripts/legal_monitor/monitor.py` → exit 0, **`severity=critical total=4`**
- `pytest tests/test_no_hardcoded_samples.py tests/test_agent_waitlist.py -q` → **25 passed**

두 가지 선행 주의:

**(a) `weekly-security-scan` — 1줄 선행 수정 필수.**
워크플로 34–41행이 `tests/test_alpaca_kill_switch.py` 를 pytest에 넘긴다. 이 파일은 commit `6bea95f8`(2026-05-27 Alpaca 통합 제거)로 삭제됐다 — 워크플로가 disabled 된 5/19 **이후**의 변경이라 아무도 못 잡았다. 지금 켜면 pytest가 collection error로 exit≠0 → 워크플로가 **매주 월요일 05:00 KST에 가짜 보안 인시던트 Issue를 열고 job을 fail** 시킨다. Alpaca 인자 한 줄만 빼면 나머지(KIS ToS grep, `.env` 커밋 검사, waitlist 회귀)는 전부 유효하다.

**(b) `legal-risk-monitor` — 첫 실행에서 즉시 critical Issue를 연다.**
오늘 로컬 실행 결과 `severity=critical, total=4`. 최상위 finding은 진짜다:

```
severity=critical  kind=artifact_sample
path=samples/artifacts/insider_mirror.html   terms=["매도"]
```

(`samples/artifacts/insider_mirror.html` 실재 확인 — 34,859 bytes.) 나머지 3건은 `medium / source_drift` 로, `services/quant/signals.py`·`engine.py` 의 **학술 인용문**("Disposition Effect", Frazzini 2006, "loss aversion")을 잡은 것 — 실무상 false positive에 가깝다. 켜기 전에 이 4건을 먼저 처리하거나, 첫 Issue가 노이즈가 아님을 인지하고 켤 것.

### 2.2 `백엔드 복구 후` — 11개

두 하위 유형으로 갈린다.

**(i) 직접 prod 폴링 — 켜면 곧바로 실패 알림 공장** (8개)
`api-health` · `daily-api-smoke` · `daily-regression-gate` · `nightly-bug-hunt` · `weekly-memo-mon-0900-kst` · `db-nightly-dump` · `vercel-deploy-canary` · `morning-brief`(간접)

`RAILWAY_BACKEND_URL` secret이 **등록돼 있다는 점이 오히려 함정**이다. 값이 비어 있으면 sanity 스텝에서 조기 종료할 텐데, 죽은 호스트를 가리키고 있어 curl은 정상 실행되고 404를 받아 "장애"로 판정한다. `api-health` 만으로 **하루 4건**, `daily-regression-gate` 로 **하루 3잡** 실패가 쌓인다.

**(ii) Claude 소모형 자동화 레이어 — 대상이 없는데 토큰만 태움** (3개)
`morning-triage`(Layer B) · `self-healing`(Layer C) · `nightly-autonomous-dev`(Phase 3A)

여기에 **감사에서 새로 발견한 cron 함정**이 있다. 세 워크플로 모두 Claude 스텝에 이런 가드가 걸려 있다:

```yaml
if: ${{ github.event.inputs.dry_run != 'true' }}
```

`dry_run` 의 `default: 'true'` 는 **workflow_dispatch 에만 적용된다.** schedule 트리거에서는 `github.event.inputs` 가 아예 비어 있으므로 `'' != 'true'` → **참** → **cron 실행은 항상 dry-run이 아니다.** 즉 `self-healing` 은 "기본 DRY RUN" 이라는 헤더 주석과 달리, 켜는 즉시 **12시간마다(월 60회) 실제로 Claude를 호출**한다. 그것도 Railway가 죽어 `scripts/self_healing/fixtures/railway_sample.log` (2026-04-24 고정 fixture)로 폴백한 **가짜 4개월 묵은 에러**를 고치려 든다. `AUTOFIX_ENABLED=1` 도 이미 켜져 있다.

`nightly-autonomous-dev` 는 `auto-eligible` 큐가 비어 있어(실측 `[]`) 현재는 픽업 단계에서 no-op 종료하지만, 킬스위치(`NIGHTLY_AUTO_DEV`)가 `1`(활성)이고 브랜치 push + PR 생성 권한을 가진 **blast radius 최대** 워크플로다. 누군가 이슈에 라벨 하나만 붙이면 즉시 코드를 쓰기 시작한다.

`morning-brief` 는 prod 의존이 전혀 없어 **오늘 켜도 green으로 돈다.** 그럼에도 `백엔드 복구 후` 로 분류한 이유는 순수 비용 판단이다 — 존재 이유가 "다른 cron들의 24h 결과 요약"인데 나머지가 전부 꺼져 있으면 매일 60분/월을 태워 빈 Issue를 만든다. 생산자들보다 **나중에** 켜야 한다.

### 2.3 `폐기 권장` — 2개

**`agent-health-weekly`** — 설계상 CI에서 영구 무력.
`scripts/agent_ops/analyze_health.py:30` 이 `REPO_ROOT/.bkit/state/agent_telemetry.jsonl` 을 읽는데, 이 경로는 `.gitignore` 에 **두 번** 걸려 있다 (`46:.bkit/`, `73:.bkit/state/agent_telemetry.jsonl`). 로컬에도 파일이 없다. 체크아웃한 러너에는 절대 존재하지 않으므로 `load_records()` 가 `[]` 를 반환하고, 리포트는 이상징후 0건이 된다 — 로컬 실행에서 anomaly grep 카운트 **0** 으로 확인했다. 즉 워크플로는 매주 green으로 돌지만 **어떤 신호도 낼 수 없다.** 텔레메트리를 CI로 실어 나르는 경로(아티팩트 업로드 등)를 먼저 설계하지 않는 한 켤 이유가 없다. (같은 디렉터리의 `propose_upgrades.py` 는 git 추적되는 `.claude/agents/` 만 읽어서 정상 동작한다 — 형제 워크플로 판정이 갈리는 이유.)

**`post-deploy-canary`** — 명시적으로 대체됨.
`vercel-deploy-canary.yml.disabled` 1–4행이 직접 선언한다: *"Replaces `post-deploy-canary.yml.disabled`. The disabled version sleep'd 180s on push to main, which races against Railway's actual deploy completion."* 두 파일 모두 `push: branches: [main]` + 동일 concurrency group 패턴이라 둘 다 켜면 매 push마다 중복 프로브가 돌고 합산 ~880분/월을 태운다. 후속 버전만 남기면 된다.

---

## 3. 발견한 stale 참조 목록 (수정 전 목록만 — 이번 감사에서 아무것도 고치지 않음)

| # | 파일 | 위치 | stale 내용 |
|---|---|---|---|
| S1 | `weekly-security-scan.yml.disabled` | 39행 | `tests/test_alpaca_kill_switch.py` — commit `6bea95f8`(2026-05-27)에서 삭제된 파일. **유일하게 확정 실패를 유발하는 참조.** |
| S2 | `agent-health-weekly.yml.disabled` | 경유 `scripts/agent_ops/analyze_health.py:30` | `.bkit/state/agent_telemetry.jsonl` 이 `.gitignore:46,73` 으로 제외 → CI 체크아웃에 영구 부재 |
| S3 | `db-nightly-dump.yml.disabled` | 10–11행 주석 | *"Release storage: GitHub Releases free for public repos"* — 레포는 **PRIVATE**. 전제가 틀림 |
| S4 | `db-nightly-dump.yml.disabled` | 4–5행 주석 | *"Railway already runs its own backups on the paid plan"* — Railway 계정 자체가 삭제됨 |
| S5 | `self-healing.yml.disabled` | 99행 `if: github.event.inputs.dry_run != 'true'` | cron 트리거에서 inputs가 비어 `'' != 'true'` → 참. 헤더의 *"Defaults to DRY RUN"* 주석과 실제 동작 불일치 |
| S6 | `morning-triage.yml.disabled` | 52행 | S5와 동일 패턴 — schedule 실행 시 Claude 스텝이 항상 발화 |
| S7 | `legal-risk-monitor.yml.disabled` | 76행 (`Open or update issue` 가드) | S5와 동일 패턴 — `dry_run` 기본 `'true'` 가 cron에는 적용 안 됨 → 예약 실행은 항상 Issue 생성 |
| S8 | `self-healing.yml.disabled` | 75행 | `curl -fsSL https://railway.app/install.sh` — Railway CLI 설치 후 `RAILWAY_TOKEN` 미등록으로 무조건 fixture 폴백 |
| S9 | `scripts/self_healing/fixtures/railway_sample.log` | 파일 자체 | 2026-04-24 고정 샘플. Layer C가 4개월 묵은 가짜 에러를 "치료" 대상으로 삼음 |
| S10 | `daily-regression-gate.yml.disabled` | 35–39행 주석 | 필수 secret로 `SLACK_WEBHOOK_URL`, `DEV_LOGIN_SECRET` 명시 — **둘 다 미등록** |
| S11 | `legal-risk-monitor.yml.disabled` | 55–56행 | `DB_SCAN_URL` / `DB_SCAN_TOKEN` 미등록 (스크립트가 optional 처리하므로 실패는 아님) |
| S12 | `db-nightly-dump.yml.disabled` | 13–18행 | `DATABASE_URL` / `GPG_PASSPHRASE` 미등록 |
| S13 | `self-healing.yml.disabled` | 78행 | `RAILWAY_TOKEN` 미등록 |
| S14 | `vercel-deploy-canary.yml.disabled` | 27행 주석 | `https://web-production-7b484b.up.railway.app` 하드코딩 예시 — 현재 전 경로 404 |
| S15 | `api-health` / `post-deploy-canary` / `vercel-deploy-canary` | 각각 48 / 62·69 / 68행 | apex `https://pivoxquant.com` 프로브. 실측 apex=**307**, www=**200**. 세 파일 모두 307/308을 허용하므로 통과하나, 정본 호스트가 `www` 로 이동한 사실이 반영 안 됨 |
| S16 | `db-nightly-dump.yml.disabled` | 38행 | `actions/checkout@v4` — 다른 20곳은 `@v6`. 버전 드리프트 |
| S17 | `post-deploy-canary.yml.disabled` | 파일 전체 | `vercel-deploy-canary.yml.disabled` 1–4행이 "대체한다"고 선언한 구버전이 아직 잔존 |
| S18 | `scripts/agent_ops/propose_upgrades.py` 출력 | 런타임 | `Reference HANDOVER: v9 (2026-04-25)` — HANDOVER.md 최신본과 불일치 (CLAUDE.md의 "v9는 옛 스냅샷" 경고와 동일 문제) |
| S19 | `nightly-autonomous-dev` / `morning-triage` / `self-healing` | 250 / 62 / 107행 | 모델 `claude-sonnet-4-6` 하드코딩. 2026-05-03 마이그레이션 시점 고정값 — 활성화 전 현행 모델 ID 재확인 필요 |

> 주의 (S15 관련): `SENDGRID_API_KEY` 가 secret에 남아 있으나, 메모리 기준 prod 메일은 2026-06-30 **Brevo** 로 전환됐다. 이 18개 워크플로 중 이 secret을 참조하는 것은 없지만, `weekly-memo` 재가동 시 발송 경로 검증 대상이다.

---

## 4. 백엔드 복구 시 되살릴 순서 (권장안)

원칙: **관측 → 검증 → 자동화 → 쓰기 권한** 순. 각 단계를 최소 1주 관찰하고 다음으로 넘어간다. 실패 알림이 노이즈가 되는 순간 그 단계에서 멈춘다.

### Wave 0 — 지금 (백엔드와 무관, 예산 ~62분/월)
1. `ssl-expiry-check` — 가장 싸고(4분/월) 대상이 살아 있음. 켜기 리스크 사실상 0
2. `agent-upgrades-monthly` — 월 1회, 레포 정적 스캔
3. `daily-legal-scan` — pytest 통과 확인됨 (9 passed)
4. `weekly-security-scan` — **S1(Alpaca 테스트 참조) 제거 후에만**
5. `legal-risk-monitor` — **critical 4건 선처리 후** (또는 첫 Issue를 예상하고)

### Wave 1 — 백엔드 복구 직후 (관측 전용, 쓰기 없음)
6. `api-health` — 가장 단순한 생존 신호. 이게 안정적으로 green이어야 나머지가 의미 있음
7. `daily-api-smoke` — 응답 shape까지 검증. api-health가 1주 green인 뒤에

### Wave 2 — 배포 파이프라인 (push 트리거 복원)
8. `vercel-deploy-canary` — **`post-deploy-canary` 는 되살리지 않는다** (§2.3). 240초 대기 창이 새 백엔드의 콜드 디플로이 p95와 맞는지 먼저 실측할 것

### Wave 3 — 심층 회귀 (비용 급증 구간, 예산 재계산 필수)
9. `daily-regression-gate` — 선행: `DEV_LOGIN_SECRET` 등록 (미등록 시 인증 프로브가 조용히 스킵됨)
10. `nightly-bug-hunt` — 1회 50분. Wave 3에서 가장 비쌈. 9-iteration 파라미터를 낮춰 시작 권장

### Wave 4 — 데이터 보존 / 유저 대면
11. `db-nightly-dump` — 선행: `DATABASE_URL` + `GPG_PASSPHRASE` 등록, **그리고 S3(private repo Release 스토리지 과금) 재검토**
12. `weekly-memo-mon-0900-kst` — **실유저 메일 팬아웃.** 선행: 발송 경로(Brevo) 검증 + `marketing_consent_at` 게이트 상태 확인. 반드시 `workflow_dispatch` 수동 1회로 리허설한 뒤 cron 활성화

### Wave 5 — 집계
13. `morning-brief` — 위 12개가 실제로 신호를 낼 때에만 가치가 생김. 여기서 켠다

### Wave 6 — Claude 자동화 레이어 (**S5/S6/S7 cron dry-run 함정 선결 필수**)
14. `morning-triage` — 선행: `nightly-bug-hunt` 가 실제 Issue를 생산 중일 것
15. `self-healing` — 선행: (a) `RAILWAY_TOKEN` 등록 (b) `fixtures/railway_sample.log` 갱신 또는 폴백 제거 (c) **cron에서 dry-run이 유지되도록 가드 수정** (d) `AUTOFIX_ENABLED` 를 명시적으로 재결정
16. `nightly-autonomous-dev` — **마지막.** 브랜치 push + PR 생성 권한을 가진 최대 blast radius. 선행: 위 15개가 전부 안정 + `auto-eligible` 큐 운영 규칙 재수립 + `NIGHTLY_AUTO_DEV` 킬스위치 의도 재확인 (현재 `1`=활성)

### 되살리지 않음
- `agent-health-weekly` — 텔레메트리 CI 반입 경로를 새로 설계하지 않는 한 영구 no-op (S2)
- `post-deploy-canary` — `vercel-deploy-canary` 가 명시적으로 대체 (S17)

---

## 5. 예산 가드레일

| 시점 | 활성 cron | 추정 소모 | 2,000분 대비 |
|---|---|---|---|
| 현재 | 0 (PR 게이트 10개만) | — | — |
| Wave 0 후 | 5 | ~62분/월 | 3% |
| Wave 3 후 | 10 | ~980분/월 | 49% |
| 전 18개 (비권장) | 18 | **~2,500분/월** | **125% — 초과** |

Wave 3 진입 시점에 실제 `gh api /repos/:owner/:repo/actions/billing` 실측으로 추정치를 교체할 것. Wave 4 이후는 추정만으로 진행하지 말 것.

---

## 부록 — 감사 방법

- 워크플로 18개 전문 read + `grep` 로 secret/vars/스크립트 경로 추출
- `gh secret list` / `gh variable list` / `gh repo view` / `gh issue list` 로 GitHub 측 실재 확인
- 참조된 스크립트·테스트 15개 파일 존재 여부 개별 확인 (1건 MISSING)
- `curl` 로 Railway·Vercel 라이브 상태 측정
- `propose_upgrades.py`, `analyze_health.py`, `legal_monitor/monitor.py` 로컬 실행
- `pytest` 로 레포 내부 검사 워크플로의 실제 통과 여부 확인 (25 passed)
- **워크플로 파일 수정 0건, 파일명 변경 0건**
