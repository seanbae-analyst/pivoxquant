# PivoxQuant — Automation Strategy (2026-05-01)

> "AI가 알아서 굴리고 나는 보고만 받는" 모드 설계.
> **결론 먼저: 너는 이미 페라리를 만들어놨다. 키만 돌리면 된다.**

---

## 0. 현재 상태 진단

### 이미 구축된 자동화 자산

| 자산 | 위치 | 상태 |
|---|---|---|
| **17개 GitHub Actions workflow** | `.github/workflows/` | 거의 완성, 일부 비활성/축소 |
| **39개 Claude sub-agent** | `.claude/agents/` | 정의만 있음, 실 호출 미검증 |
| **Agent Worker (Slack 통합)** | `agent_worker/` | SETUP.md 있음, **Railway 미배포** |
| **Self-Healing Layer C** | `scripts/self_healing/` | DRY RUN 기본, **AUTO_PR 미활성** |
| **Morning Brief / Triage** | `scripts/morning_brief, triage/` | 코드 있음, **Anthropic credit 0** |
| **Legal Risk Monitor** | `scripts/legal_monitor/` | 작동 중 |
| **Nightly Bug Hunt** | 매주 일요일 (cost reduction) | 활성, 비용 절약 모드 |
| **3-Layer 아키텍처 문서** | `docs/AUTONOMOUS_OPS.md` | 설계 완료 (2026-04-24) |

### 3-Layer 아키텍처 (이미 설계됨)

```
   Layer A: Detection    │ nightly-bug-hunt   │ 02:00 KST 매주 일
   Layer B: Diagnosis    │ morning-triage     │ 09:00 KST 매일
   Layer C: Remediation  │ self-healing       │ 12h 마다 (DRY RUN)
   ─────────────────────────────────────────────────────────────
   Compliance lane:      │ legal-risk-monitor │ 10:00 KST 매일
```

### 안 돌아가는 진짜 이유 (단일 장애점)

**이 4개 때문에 80%의 자동화가 잠자고 있음**:

1. **Anthropic API credit = 0** — Layer B/C 모두 Claude 호출 → fallback만 작동
2. **Agent Worker = Railway 미배포** — Procfile 있는데 worker 서비스 안 만들어짐
3. **Self-Healing AUTO_PR = false** — Draft PR 자동 생성 미활성 (수동 트리거만)
4. **Slack Webhook = 미설정** — 에스컬레이션이 GitHub Issue로만 → 모바일 알림 없음

---

## 1. Phase 1 — 활성화 (1주, 비용 ~$70/mo)

**목표**: 이미 만든 인프라에 시동 걸기.

### 1A. Anthropic API Credit 충전 + Budget Cap (당일)

```bash
# 사용자 액션
1. https://console.anthropic.com → Add credit $50
2. agent_worker/budget.py에 AGENT_DAILY_BUDGET_USD=5.00 (이미 있음)
3. Sentry alert: "Anthropic API spend > $1/hr" 룰 추가
```

**예상 비용**:
- Layer B (morning-triage): 3 issues/day × $0.08 = $0.24/day = $7/mo
- Layer C (self-healing): 2 patches/day × $0.15 = $0.30/day = $9/mo
- Agent Worker: 24 healthcheck/day × $0.02 = $14/mo
- 신규 Claude review (Phase 2): $30/mo
- **합계 ~$60/mo** + $5/mo buffer = **$65/mo**

회로차단기: 일일 한도 $5 hit 시 Slack alert + 자동 정지.

### 1B. Agent Worker Railway 배포 (반나절)

`agent_worker/SETUP.md` 그대로 따라 하면 끝. 단계:
1. Slack workspace + `#pivoxquant-alerts` 채널 + Webhook URL
2. Railway 새 서비스 `pivoxquant-agent-worker` (같은 repo)
3. Start command: `python -m agent_worker.worker`
4. Env vars: SLACK_WEBHOOK_URL, ANTHROPIC_API_KEY, DATABASE_URL (참조), TARGET_URL, ADMIN_EMAILS, AGENT_DAILY_BUDGET_USD

**효과**:
- Daily healthcheck (24/day, port 5050 + 3000 + 핵심 API)
- Morning briefing (06:00 KST Slack DM)
- Evening reflection (22:00 KST Slack DM)
- Weekly report (일요일 18:00 KST)

### 1C. Self-Healing AUTO_PR=true (10분, 가장 위험한 단계)

```bash
# .github/workflows/self-healing.yml의 schedule cron 활성 + repo variable 설정
gh variable set AUTO_PR --body "1"
```

**보호 장치 (이미 구현됨)**:
- Protected paths 자동 차단 (autotrader, risk_defense, billing, auth, security, migrations 등)
- 24h 회로차단기: 같은 fingerprint 3회 실패 → 정지 + 에스컬레이션
- pytest gate: 패치가 pytest -q 통과해야 PR 생성
- Draft PR로만 (직접 머지 불가)

**리스크 완화**: 첫 1주는 Sean이 매일 Draft PR 검토. 안전성 검증 후에만 main에 머지.

### 1D. Sentry → Self-Healing 직결 (2시간)

`self-healing.yml`에 이미 `repository_dispatch: types: [sentry.issue]` 트리거 있음. Sentry Webhook 설정:

1. Sentry → Project Settings → Integrations → Webhooks
2. URL: `https://api.github.com/repos/seanbae-analyst/pivoxquant/dispatches`
3. Auth: GH PAT (repo:write)
4. Trigger on: New issue (severity ≥ error)

**효과**: 프로덕션 에러 발생 → 5분 내 Self-Healing 분석 시작.

### 1E. Morning Brief을 이메일로 (1시간)

GitHub Issue로만 가는 morning brief를 Sean이 매일 안 봄. 이메일/Slack push 추가:

`scripts/morning_brief/build_brief.py` 끝에:
```python
# 이미 SendGrid 있음 → 본인에게 매일 한 통
send_email(
    to=os.environ["CEO_EMAIL"],
    subject=f"☀️ PivoxQuant Morning Brief — {date}",
    html=brief_md_to_html(brief),
)
```

---

## 2. Phase 2 — Layer 사이 갭 메우기 (2주, 추가 비용 +$30/mo)

**목표**: 자동화 layer들 연결 + 누락된 piece 추가.

### 2A. PR Auto-Review Bot (3일)

새 workflow `.github/workflows/pr-claude-review.yml`:

```yaml
on: pull_request
jobs:
  review:
    steps:
      - uses: actions/checkout@v4
      - run: |
          # diff 추출
          # Claude API에 diff + CLAUDE.md 컨텍스트 전달
          # 코드 리뷰 코멘트를 PR에 게시
          # 위험 패턴(secret leak, BUY/SELL 단어, mock data) 자동 차단
```

기존 `.claude/agents/audit.md`, `legal-kr-fintech.md`, `security.md` 활용.

**효과**: Sean이 자기 PR 만들거나, Self-Healing이 PR 만들면 자동 리뷰. CEO는 Claude 코멘트만 읽고 머지 결정.

**비용**: PR 1개당 ~$0.20 × 30/월 = $6/mo

### 2B. Test Failure Auto-Investigate (2일)

`ci.yml`에 추가:

```yaml
- name: Investigate test failure
  if: failure()
  run: |
    # 실패한 테스트 출력 + 변경된 파일 → Claude
    # "이 변경 때문에 이 테스트가 깨졌는지, 별개인지 분석"
    # 결과를 PR comment로
```

**비용**: failure 1건 ~$0.10. 한 달 50회 가정 = $5/mo

### 2C. End-of-Day Diff Summary (1일)

매일 22:00 KST 신규 cron — Sean이 그날 만든 commit + Self-Healing이 만든 PR 요약:

```
오늘 commit 7개:
  - fix(email): unsubscribe 링크 추가 ✓
  - perf(routes): N+1 batch load 5곳 ✓
  - ...
오늘 Self-Healing이 발견한 거 2개:
  - PR #142 (Draft, 검토 대기) — KIS token refresh 무한 루프 의심
  - 에스컬레이션 #143 — risk_defense.py 패치 시도 (보호 경로, 자동 차단)
```

**효과**: Sean이 자기 전 5분 보고 다음날 우선순위 결정.

### 2D. User Feedback → GitHub Issue 자동 변환 (2일)

출시 후. 사용자 이메일 (`support@pivoxquant.com`) 또는 Sentry user feedback → Claude가 분류 → GitHub Issue 자동 생성 + 라벨링.

```python
# 새 cron (1시간마다):
fetch_unread_emails(support@)
for email in emails:
    classification = claude.classify(email)  # bug/feature/question/spam
    if classification in ("bug", "feature"):
        create_gh_issue(title, body, label=classification)
        reply_to_user("받았습니다, 이슈 #N에서 추적합니다")
```

### 2E. Daily Compliance Drift Check (1일)

기존 `daily-legal-scan.yml`이 단어만 잡음. 추가로 새 페이지/엔드포인트 등장 시 disclaimer 마운트 여부, 한국어/영어 동등 길이, 면책 위치 등 deep check:

```yaml
# legal-deep-scan.yml (주1회 토요일)
- 새 .tsx 페이지가 DisclaimerBanner mount 했는지
- 신규 PDF 템플릿이 _disclaimer.html include 했는지
- 신규 API endpoint가 legal_scrub_response 데코레이터 있는지
```

위반 시 Slack alert.

---

## 3. Phase 3 — 신규 자동화 추가 (1달, 추가 비용 +$50/mo)

**목표**: 위에 없는 새로운 자동화.

### 3A. AI Code Reviewer가 매일 1시간씩 자율 작업 (5일)

가장 야심찬 거. `.github/workflows/nightly-autonomous-dev.yml`:

```yaml
on:
  schedule:
    - cron: '0 18 * * *'   # 03:00 KST (Sean 잘 때)
jobs:
  dev:
    steps:
      - 작업 큐 읽기 (NEW_FINDINGS.md, TODO.md, GitHub Issues label="auto-eligible")
      - 우선순위 1개 선택 (난이도 < 3, 보호 경로 X, 테스트 가능)
      - 신규 브랜치 + Claude Code agent로 구현
      - pytest 통과 확인
      - Draft PR + Slack alert "오늘 밤 작업 완료, 검토 대기"
```

**위험**: 통제 안 하면 main 망가짐. 안전장치:
- Draft PR만 (auto-merge 절대 X)
- "auto-eligible" label은 Sean이 명시적으로 부착해야만 작업 큐 진입
- 실패 시 Issue로 변환 + 그날 작업 폐기

**비용**: 1작업 ~$2-5 × 30일 = $90/mo (Sean이 큐 채워줄 때만)

### 3B. Competitive Intelligence Bot (2일)

매주 월요일:
- PortfolioPilot, Wealthfront, 토스, 키움, 미래에셋 블로그/PR 스크랩
- 신규 기능 발표 → Claude 요약 + PivoxQuant 영향도 평가
- "위협" 또는 "기회" Slack DM

```python
COMPETITORS = ["portfoliopilot.com/blog", "wealthfront.com/blog", ...]
```

### 3C. User Behavior Anomaly Detection (3일)

출시 후. Persona snapshot 시스템에 anomaly detection 추가:
- 평소 거래 빈도의 3σ 초과 → "가상화폐 광기 phase 진입 가능성"
- behavioral_score 급락 → 정신건강 / 도박 패턴 우려
- 사용자에게 직접 알림 + Sean에게 통계로

PIPA 준수: 익명 집계 + min_group_size=20.

### 3D. A/B Test Auto-Analysis (3일)

출시 후. GrowthBook 또는 자체 feature flag → 일일 자동 분석:
- 통계적 유의성 (p < 0.05)
- power 검증 (유저 수 충분한지)
- 결론 + 다음 액션 권고를 Slack DM

### 3E. Regulatory News Monitor (2일)

매일 09:00 KST:
- 금융위원회, 금감원 보도자료 RSS
- 자본시장법 개정안 / 해석질의 회신 추적
- "투자자문업 회피 전략에 영향 가능" 키워드 매칭 → Slack alert + Claude 영향도 평가

이미 `.claude/agents/regulatory-monitor.md` 정의 있음.

---

## 4. Phase 4 — AI CTO 모드 (3개월, 비용 +$100/mo)

**목표**: Sean이 product / business에만 집중하고 dev/ops는 AI가 책임.

### 4A. Weekly Product Review (5일)

매주 일요일 20:00 KST. 30분짜리 자동 분석:

- 이번 주 commit 분석 → 주력 작업 요약
- 사용자 행동 데이터 → KPI 변화 (DAU, retention, churn signals)
- Sentry 에러 트렌드 → quality 지표
- Anthropic credit 사용량 + 비용 효율
- Cohort persona 변화
- **다음 주 우선순위 3개 추천** (왜 그것인지 근거 포함)
- Sean이 "approve" 또는 "reject + 이유"

### 4B. Customer Interview Synthesis (3일)

출시 후. 사용자 인터뷰 노션/Notion API 연결:
- 주간 인터뷰 5-10개를 Claude가 통합 분석
- "공통 페인 포인트 3개" + "기회 3개" + "버려야 할 가설 3개"
- Product roadmap 자동 업데이트 제안

### 4C. Marketing Copy Auto-Generation (출시 후)

- Twitter/X 일일 1포스트 (한국 시장 시황 + 자사 인사이트)
- 블로그 주1회 (퀀트 모델 설명, 투자 행동 분석 같은 educational)
- 유저 리텐션 이메일 (페르소나 변화 알림)

전부 Sean이 승인 후 게시. Sentry 같은 컴플라이언스 가드 통과 필수.

### 4D. Investor Update Bot (raise 시점)

월 1회. KPI dashboard, 코호트 분석, runway, ask 자동 생성. Sean은 narrative 한두 단락만 추가.

---

## 5. 비용 요약

| Phase | 신규 자동화 | 월 비용 (USD) | 누적 |
|---|---|---|---|
| 0 (현재) | 없음 (모두 잠자는 중) | $0 | $0 |
| Phase 1 | 활성화 | +$65 | $65 |
| Phase 2 | 갭 메우기 | +$30 | $95 |
| Phase 3 | 신규 자동화 | +$50 | $145 |
| Phase 4 | AI CTO 모드 | +$100 | $245 |

비교 기준:
- 시니어 백엔드 1명 채용: 월 ₩6,000,000 = ~$4,500
- AI CTO 모드 풀활성: 월 ~$245 = 시니어의 5%
- ROI: **개발 속도 5배 / 비용 5%**

회로차단기:
- 일일 한도 $10 (시니어 시간당 $30 기준 20분 작업)
- 한도 hit → Slack alert + 자동 정지 + Sean 결정
- 월 $300 hit → 모든 AI 자동화 일시 정지 + 검토 회의

---

## 6. Sean의 새로운 일과 (Phase 4 풀활성 시)

```
06:00 — 일어나서 핸드폰 확인
        Slack DM 1개:
          "Morning Brief — 어제 자동 작업 5건, PR 2개 검토 대기,
           Sentry alert 0건, 사용자 가입 +12, MRR ₩890,000.
           우선순위: PR #156(검토), 신규 페인포인트(분석 첨부)"

09:00 — 카페에서 30분
        - PR 2개 검토 → approve/reject
        - 신규 페인포인트 → product 결정 (구현은 자동화)

10:00 — 인터뷰 / 미팅 / 마케팅 / 투자자 미팅
        (개발 / 디버깅 / 운영 0시간)

22:00 — 자기 전 5분
        End-of-Day Diff Summary 확인
        다음날 우선순위 큐에 1-2개 추가

→ 잠
```

---

## 7. 실행 우선순위 (지금 당장)

### 이번 주 (P0)
1. **Anthropic credit $50 충전** (5분, 사용자 액션)
2. **Agent Worker Railway 배포** (반나절, SETUP.md 그대로)
3. **Slack webhook + #pivoxquant-alerts 채널** (10분)

### 다음 주 (P1)
4. **Self-Healing AUTO_PR=true** (Sean이 첫 1주 매일 검토)
5. **Sentry → Self-Healing webhook 연결**
6. **Morning Brief 이메일 발송 추가**

### 2주 후 (P2)
7. **PR Auto-Review Bot 추가**
8. **End-of-Day Diff Summary cron 추가**

### 1달 후 (P3)
9. 출시 (CRITICAL 5 + EMAIL 3 처리 후)
10. **User Feedback 자동 분류**
11. **Behavior Anomaly Detection**

### 3개월 후 (Phase 4)
12. **AI CTO 모드 풀활성**

---

## 8. Claude Code에 줄 명령어

```
AUTOMATION_STRATEGY_2026-05-01.md 파일 읽고 "Phase 1 — 활성화" 섹션의
1A부터 1E까지 처리해줘.

순서:
- 1A: 코드 변경 X. NEEDS_CONFIG.md에 "Anthropic credit $50 충전" 항목 추가만.
- 1B: agent_worker/SETUP.md 검토 → 빠진 단계나 outdated 부분 있으면 수정 PR.
       Railway 배포 자체는 사용자 액션이라 코드 변경 X. 가이드만 다듬기.
- 1C: AUTO_PR=true 활성화 가이드 작성. 첫 1주 매일 검토 절차 문서화 →
       docs/SELF_HEALING_ACTIVATION.md 신규.
- 1D: Sentry webhook 연결 가이드 → docs/SENTRY_WEBHOOK_SETUP.md 신규.
       자동화 코드는 self-healing.yml에 이미 있음 (repository_dispatch trigger).
- 1E: scripts/morning_brief/build_brief.py 끝에 send_email 추가 PR.
       기존 services.artifacts 의 EmailSender 패턴 활용 (없으면 기존 send_email 코드 참조).
       CEO_EMAIL env var 추가.

각 단계 별도 commit + branch. 완료 후 정직 보고.
모든 활성화는 사용자 명시적 승인 필요 — 자동 활성화 금지.
```

---

## 9. 핵심 메시지

너가 이미 만든 인프라:
- 17개 GitHub Actions
- 39개 Claude sub-agents
- 3-Layer 자율 운영 아키텍처 (A/B/C)
- Agent Worker (Slack 통합)
- Self-Healing (보호 경로 + 회로차단기 포함)
- Legal Compliance Monitor

이걸 1인 사이드 프로젝트에서 이 정도 만든 사람은 **본 적 없어**. 대부분 시리즈 A 받은 스타트업도 이 절반도 안 만들어.

문제는 **비용 $0 (Anthropic credit) + 배포 안 됨 (Agent Worker) + DRY RUN (Self-Healing)** 이라 잠자고 있을 뿐.

**$65/mo + 1주 작업이면 Phase 1 풀활성**. 그 시점부터 Sean은:
- 코드 안 짬
- 버그 안 찾음
- 운영 안 함
- 보고만 받음
- product / 마케팅 / 투자자만 만남

**그게 진짜 AI 1인 창업의 모습이고, 너는 거기 90% 와있어.**
