# Post-Launch Monitoring — 출시 후 7일 액션 가이드

> 출시 ▶ 클릭 후 첫 7일 동안 모니터링할 신호 + 즉각 대응 절차.
> 작성: 2026-05-15 v43 second-shift. 본 가이드는 출시 후 살아있는 문서 — 사용자/이슈 발생 시 본 파일에 incident 기록.

---

## D-Day: 출시 ▶ 클릭 직전 last-mile checklist

- [ ] `docs/ops/launch-checklist.md` P0 항목 전부 ✅
- [ ] `curl /api/health` → `env.missing_recommended == 0`
- [ ] Cloudflare Email Routing 활성 + 테스트 발송 1통 receive 확인
- [ ] Railway Volume `/app/artifacts` mount 활성 (`docs/ops/pdf-storage.md`)
- [ ] CAUS state file: `python scripts/caus_auto_fix.py --state-dump` → 깨끗
- [ ] frontend `npm run build` → 0 errors (Vercel CI 통과)
- [ ] backend `pytest -q` → 0 failures
- [ ] 베타 게이트 비활성화 (BETA_PASSWORD Railway env 삭제) — 진짜 공개 시점
- [ ] Slack `#alerts` 채널 webhook 활성 확인

---

## Day 0 — 출시 직후 1시간

### 1시간 안에 봐야 할 것 (5분 주기)
- **Railway Deploy Logs** (https://railway.app → vibrant-blessing → web → Logs)
  - `LAUNCH_PREP env-missing` CRITICAL 라인 0개 (PR #400)
  - 5xx Python traceback 0개
- **Vercel Deploy Logs** — frontend build 성공
- **Sentry Issues** — 첫 1시간 새 이슈 0개 (이전 dev session noise 제외)
- **/api/health response time** — p95 < 1s
- **landing → /signup 회원가입 path** — 직접 신규 계정 1개 만들어보면서 전 단계 클릭

### 즉시 대응
| 신호 | 대응 |
|---|---|
| /api/health 503 | Railway 대시보드 → Restart. 안 되면 last-known-good redeploy |
| /signup 500 | Sentry trace 확인 → `routes/auth.py:260` register endpoint 직접 grep |
| 사용자 가입 안 되고 빠짐 | OAuth redirect_uri Google/Kakao console 등록 상태 확인 |
| 무한 skeleton 어디서든 | PR #395 timeout 15s 후 504 fallback 발동 — Sentry 확인 |

---

## Day 1-3 — 안정화 모니터링

### 매일 09:00 KST 체크
1. **자동 CAUS 시뮬 리포트**: `cat ~/projects/pivoxquant/docs/qa/auto-sim-reports/$(date +%F).md`
   - 정상: `findings: 0`
   - 비정상: P0/P1 항목 → 즉시 review + auto-fix PR (label `caus-auto-fix`) merge or escalate
2. **Phase 4 auto-fix state**: `python scripts/caus_auto_fix.py --state-dump`
   - `recent_outcomes` 마지막 3개 모두 성공 또는 SKIP이면 정상
   - 3연속 escalate/insufficient → cooling-off 활성 (24h)
3. **Sentry 일일 issue count** — 비정상: 어제 대비 5배 spike
4. **Railway 일일 비용 추정** — Railway 대시보드 → Usage. Hobby plan $5/mo cap 안 일치 확인 (CEO 본인 Railway 결제 의문 — 본 세션 답변 참조)

### 사용자 첫 피드백 받기
- support@pivoxquant.com inbox 매일 체크 (Cloudflare Routing → Gmail)
- /api/email/unsubscribe 클릭 통계 — 비정상 spike는 발송 빈도 과다 신호

---

## Day 4-7 — 트렌드 관찰

### 주요 지표 트래킹
| 지표 | 목표 | 어디서 확인 |
|---|---|---|
| 회원가입 완료율 | OAuth start vs /home 도달 비율 ≥ 60% | Sentry breadcrumbs 또는 self-hosted Analytics |
| 베타 활성 사용자 | 7일 active users | 직접 DB `SELECT COUNT(DISTINCT user_id) FROM positions WHERE updated_at > NOW() - INTERVAL '7 days';` |
| AI 호출 503 ratio | < 5% (Anthropic credit 정상) | Railway logs grep `swot 503` 또는 `coaching 503` 빈도 |
| PDF 발송 성공률 | ≥ 95% (Cloudflare Routing 정상) | SendGrid Activity Feed |
| 결제 시도 | 출시 초기 0건 정상 (Stripe 미활성) | Railway logs grep `create-checkout` |

### 첫 주 사용자 인터뷰 (5-10명)
- Slack DM 또는 Calendly 링크 보내기
- 질문: "어디서 멈췄나" / "이해 안 된 한국어 카피" / "PDF 보고 뭐 했나"

---

## Incident Response 절차

### Severity 1 (전체 서비스 다운)
1. **Railway 대시보드 → Logs** — 마지막 5분 5xx traceback 확인
2. **Status**: Slack `#alerts` + Twitter @pivoxquant (있다면) "일시 서비스 점검 중"
3. **Rollback**: `git revert <last-bad-commit> && git push origin main` — Railway 자동 redeploy
4. **Post-mortem**: 24h 안 incident log `docs/incidents/YYYY-MM-DD-<title>.md` 생성

### Severity 2 (부분 기능 다운, 예: AI 503)
1. **Sentry breadcrumb** → 어떤 endpoint
2. **Graceful path 확인**: PR #387 + #397 graceful copy 동작 중 → 사용자 noise 최소
3. **Root cause**: Anthropic credit / FMP key / KIS API 어느 하나
4. **CEO 액션**: `docs/ops/launch-checklist.md` P1 #4 (외부 데이터 소스) 절차

### Severity 3 (개별 사용자 이슈)
1. **support@pivoxquant.com**으로 사용자 보고 도착
2. **`/api/profile/export`** 또는 직접 DB 조회로 사용자 데이터 상태 확인
3. **Fix**: 코드 fix 필요 시 일반 PR flow

---

## 자동 작동 cron 모니터링 (CEO 부재 시)

| 작업 | 시각 | 정상 signal | 비정상 시 |
|---|---|---|---|
| CAUS Day N sim | 매일 03:00 KST | `findings: 0` in daily report | P0 → auto-fix PR (label caus-auto-fix) 자동 생성 |
| finance_weekly_check | 매주 일 09:00 KST | Slack `[finance-weekly] STATUS 🟢 GREEN` | 🟡 YELLOW (>14d stale) / 🔴 RED (>21d) |
| monthly_brag cron | 매월 1일 09:00 KST | SendGrid Activity Feed 100+ delivered | 발송 실패 → SendGrid 콘솔 + Railway 로그 |
| weekly_memo cron | 매주 일 08:00 KST | 같음 | 같음 |
| Phase 4 auto-fix | CAUS P0 발견 시 trigger | state.recent_outcomes 마지막 = "success" | "escalate" or "insufficient" 3연속 → cooling-off |

---

## 본 가이드 작성 근거 / 메모리 룰 부합

- ✅ `feedback_no_extra_cost`: 모든 모니터링은 Railway 대시보드 + Sentry free tier + Slack webhook + Cloudflare Email Routing — 추가 비용 0원
- ✅ `feedback_no_false_reports`: 각 항목마다 "어디서 확인" 명시 (UI path 또는 SQL 또는 grep command)
- ✅ `legal_compliance`: incident log 작성 PIPA §29 (개인정보 침해 사고 신고 의무 — 24h 안 한국인터넷진흥원 신고 + 사용자 통지)
- 작성 traceability: 본 세션 PR #399~#407 자동화 + 가이드 종합 + bug-hunter 6 wave 학습

다음 incident가 본 가이드의 첫 살아있는 항목입니다 (없기를 바라며).
