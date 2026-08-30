---
name: wave-launch-prep
description: 출시 직전 컴플라이언스+법규+정책 검증 wave + D-day 4단계 게이트 (D-7/D-3/D-1/D-day) 자동화
---

# wave-launch-prep

## 목적
유료 결제 활성화/출시 전 법적·정책적 SHIP-BLOCKER를 전수 점검 + D-day 4단계 게이트 자동 진행.

## CEO 트리거 매핑
| 발화 | 해당 단계 |
|------|----------|
| "launch wave" / "런치 wave" | 1~4 전수 자동 (현재 D-day에 맞춰 적절 단계만) |
| "launch wave D-7" | D-7 단계만 |
| "launch wave D-3" | D-3 단계만 |
| "launch wave D-1" | D-1 단계만 |
| "launch wave D-day" / "go-live" | D-day cutover 단계 |

## D-day 4단계 게이트

### 단계 1 — D-7 (출시 1주 전, Readiness 검증)

3개 Task 병렬:

```
Task 1 — launch-coordinator dashboard:
  agent: launch-coordinator
  prompt: "현재 D-7 게이트 점검 (launch-coordinator.md §2 D-7 리스트):
           변호사 큐 status / 통신판매업 신고 status / DNS 4 레코드 /
           Brevo+SendGrid+Slack env / artifact-qa fixture / Stripe Live precondition /
           Vercel BETA_PASSWORD / PR open / pytest+vitest / alembic prod head.
           실측 결과만 인용 (grep / file check / env check). 추측 0건.
           각 게이트 PASS/FAIL/BLOCKED + CEO Action 우선순위 표 출력."

Task 2 — compliance-gatekeeper B-1~B-7:
  agent: compliance-gatekeeper
  prompt: "출시 체크리스트 전수 점검:
           B-1 사업자등록 / B-2 통신판매업 신고 / B-3 약관·개인정보 게시 /
           B-4 환불정책 §17 / B-5 Stripe Live 키 / B-6 DNS / B-7 베타PW 해제 시점.
           SHIP-BLOCKER / ACTION-REQUIRED / OK 분류."

Task 3 — legal-kr-fintech §101 + 신규 규제:
  agent: legal-kr-fintech
  prompt: "§101 면제 조건 4요건 재검증 + 2026-04~05 신규 7건 적용 상태.
           legal_filter take-profit/stop-loss 커버리지 / PIPA §21·§28-8 / 정통망법 §50."
```

### 단계 2 — D-3 (Final Lock)

3개 Task 병렬:

```
Task 1 — launch-coordinator D-3:
  agent: launch-coordinator
  prompt: "D-3 게이트 점검 (launch-coordinator.md §2 D-3 리스트):
           변호사 답변 수령 / 통신판매업 / DNS 발송 테스트 / Stripe Live 토글 준비 /
           OAuth redirect URI / 베타리스트 노티 카피 / Producthunt / Twitter."

Task 2 — verify-policy 카피 전수:
  agent: verify-policy
  prompt: "~/dev/pivoxquant/frontend/src/ 전수 스캔. 약관·면책·이용제한 문구 /
           §101 위반 가능 문구 (BUY/SELL/HOLD/추천/조언/매수/매도 직접 권유) 추출."

Task 3 — stripe-billing Pre-Live:
  agent: stripe-billing
  prompt: "Stripe Live mode precondition 5룰 점검. test → live 전환 시나리오 dry-run."
```

### 단계 3 — D-1 (Cutover)

2개 Task 병렬:

```
Task 1 — launch-coordinator D-1:
  agent: launch-coordinator
  prompt: "D-1 게이트 점검 (launch-coordinator.md §2 D-1 리스트):
           BETA_PASSWORD 해제 시점 / Stripe Live 최종 토글 / DNS 전환 100% /
           Railway alembic prod head / Sentry+Slack active / 베타테스터 직접 노티 /
           런치 트윗 예약."

Task 2 — migration-guard prod 검증:
  agent: migration-guard
  prompt: "alembic prod head 일치 확인. drift 발견 시 즉시 SHIP-BLOCKER + 마이그 적용 plan."
```

### 단계 4 — D-day (Live)

순차 진행 (시각 dependent):

```
1) launch-runner agent 직접 호출 — 6 SHIP-BLOCKER 실측 + Slack 변경분 알림
2) launch-coordinator D-day 게이트 점검 — 09:00 BETA_PW 해제 / 09:30 Stripe Live /
   10:00 베타 메일링 / 10:30 트윗 / 11:00 Producthunt
3) 매시간 autopilot-monitor — health/Sentry/Stripe webhook/첫가입+첫결제 alert
```

## 통합 출시 판정 (모든 단계 공통)

```
Task (마지막) — legal-kr-fintech 통합 판정:
  agent: legal-kr-fintech
  prompt: "위 Task 1~N 결과 종합. SHIP-BLOCKER 남은 건 수 집계.
           출시 GO/NO-GO 최종 판정 + CEO 액션 아이템 우선순위."
```

## 예상 소요
- 각 단계 병렬 Task: ~15-20분
- 통합 판정: ~5분
- D-day는 시각 dependent (CEO 라이브 관찰)

## 완료 기준
- SHIP-BLOCKER 0건 또는 각 건 CEO 결정 사유 명시
- GO/NO-GO 최종 판정문
- /tmp/ship_blockers_status.json 최신 (ship_blockers_audit cron 06:00 KST 결과)

## 참조 인프라
- **SoT**: `~/dev/pivoxquant/SHIP_BLOCKERS.md` (RELEASE-BLOCKER / SHIP-AT-RISK / POST-LAUNCH 표)
- **일일 audit**: `scripts/nightly/ship_blockers_audit.py` (cron `ops_ship_blockers_daily` 06:00 KST)
- **launch-coordinator agent**: `~/dev/pivoxquant/.claude/agents/launch-coordinator.md` (명세 SoT)
- **launch-runner agent**: `~/dev/pivoxquant/.claude/agents/launch-runner.md` (매일 실측 layer)
- **compliance-gatekeeper agent**: `~/dev/pivoxquant/.claude/agents/compliance-gatekeeper.md` (B-1~B-7)
