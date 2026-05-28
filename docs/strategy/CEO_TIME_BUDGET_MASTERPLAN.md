# CEO 시간 최소화 마스터플랜 (v56-M1)

> 작성: 2026-05-28 — Strategy Agent (기획부)
> 상위 문서: v54 자율 ramp 40→95% 마스터플랜, v55 Max-only 라우팅, project_autonomous_ops.md
> North Star: **CEO routine 월 5시간 미만** (Phase 3 종료 시점 = D+365)
> 출처 표기: [메모리] 메모리 인용 / [추정] Strategy Agent 추정 / [검증] CEO 검증 필요

---

## Executive Summary

v54 마스터플랜은 "자율도 %"라는 축으로 ramp를 잡았으나, **"CEO가 결과를 읽는 시간"은 별개의 축**이다. 자율 95% 시스템도 CEO가 매일 30분씩 로그를 읽으면 의미 없다.

본 문서는 CEO routine 시간을 **일/주/월/분기/연** 단위로 인벤토리화 → 4단계 ramp(A/B/C/D) 매핑 → **월 평균 시간 절감 path** 를 제시한다.

핵심 결론:
- **Stage A (현재) CEO 추정 월 routine = 약 38-50시간/월** ([추정], 검증 필요)
- **Stage D (D+365 목표) = 월 1-3시간** (자율 95% + 모바일-first + 결정 batching)
- 최대 절감 source는 **(1) 결정 batching (-12h/월) + (2) 자율 위임 (-15h/월) + (3) 외부 액션 batch (-6h/월)**
- 위험 mitigation: **결정 백로그 dashboard + 변호사 답변 throttle alarm + 자율 외 사고 catch-up loop**

---

## Situation Analysis

### Current State (Stage A — 2026-05-28 기준)
- 자율도: 약 25-30% (v54 Stage A 진입 직전) [메모리: project_autonomous_ops Phase 1 = 40% 목표]
- CEO 활용 패턴: 취준 30h + 사업 30-40h [메모리: project_autonomous_ops Phase 1 표]
- 결정 mode: 인터랙티브 (Claude Code 세션 동시 진행, AskUserQuestion 금지지만 carry-over 보고 매일)
- 알림: Slack webhook + 모바일 push + 새벽 cron 결과
- 외부 액션: `~/.pivoxquant-env` 변수 8개 + Keychain + 변호사 미팅 + 통신판매업 등록 등 [메모리: project_automation_v2 §환경변수]

### Target State (Stage D — D+365)
- 자율도: 95%
- CEO 월 routine: 1-3시간 (= 일 평균 2-6분)
- 결정 mode: 모바일 batch (일요일 저녁 + 06:30 push 1개)
- 알림: 단일 daily push (morning-brief)
- 외부 액션: 토요일 30분 batch

### Gap (절감 필요)
약 **월 35-47시간** 을 12개월에 걸쳐 압축해야 함. 단순 ramp가 아니라 **세 가지 layer (결정 / 정보 / 액션) 각각 시간 절감 필요**.

---

## Phase 1 — CEO routine 시간 인벤토리 (실측 + 추정)

> 단위: 분. 모든 시간은 [추정] 표기 없으면 CEO 검증 필요.

### 일일 routine (매일)

| 항목 | 현 소요 (분) | 출처 | 변동성 |
|---|---|---|---|
| morning-brief Slack push 읽기 | 2 | [메모리: morning_brief_kpi crontab 06:05] | 낮음 |
| bug-hunter / autopilot_log 결과 review | 8 | [추정] daily_sweep + autopilot_log read | 중 |
| Sentry alert triage (CEO 결정 필요분만) | 3 | [메모리: project_autonomous_ops §1 Sentry 자동] | 낮음 |
| 이메일 응답 (개인 + 사업) | 10 | [추정] 출시 전 베타 유저 0명 가정 | 출시 후 ↑↑ |
| 카페 / 인스타 / Threads 게시 | 15 | [추정] Pieter Levels 패턴 일 1회 | 높음 |
| 결제 / 분쟁 처리 | 0 (현재 user 0명) | [메모리: Phase 1 user 100 목표] | 출시 후 ↑ |
| 새벽 cron 결과 검증 (autopilot/launch-bugfix branch 등) | 12 | [추정] morning brief 후 detail dive | 중 |
| Claude Code 세션 작업 (개발 / 디자인 / 법무) | 90 | [추정] 풀타임 환산 — 본 문서 작성 같은 세션 자체 | 매우 높음 |
| **일일 routine 소계** | **140분 ≈ 2.3시간/일** | | |

비고:
- "Claude Code 세션 작업 90분"은 본 마스터플랜이 압축 대상으로 삼는 핵심 풀. 출시 후 CEO가 다른 일/학업으로 옮기려면 이 90분이 가장 큰 절감 target.
- 출시 후 user 100 도달 시 "이메일 응답"은 [추정] 25-40분/일로 증가 — Stage B 핵심 리스크.

### 주간 routine (주 1회)

| 항목 | 현 소요 (분) | 출처 | 빈도 |
|---|---|---|---|
| Weekly Memo 결과 review | 15 | [메모리: project_autonomous_ops §1 자율 발송] | 주 1 |
| weekly_funnel_snapshot read | 10 | [메모리: signup_funnel crontab 5분 baseline] | 주 1 |
| lawyer_packet review (일요일 21:00) | 30 | [메모리: legal_question_queue 21건] | 주 1 |
| carry-over 정리 (Slack/Brevo/Sentry/Keychain) | 25 | [메모리: project_automation_v2 §외부 액션] | 주 1 |
| autopilot_log / session 회고 | 20 | [메모리: autopilot_log.md] | 주 1 |
| commit + push 별도 세션 (수동 일괄) | 30 | [메모리: feedback_push_workflow CEO 직접] | 주 1-2 |
| **주간 routine 소계** | **130분 ≈ 2.2시간/주** | | |

### 월간 routine (월 1회)

| 항목 | 현 소요 (분) | 출처 |
|---|---|---|
| burn_rate / monthly_finance check | 30 | [메모리: finance_weekly crontab 월 1회 환산] |
| 메모리 정리 (consolidate-memory) | 60 | [메모리: anthropic-skills consolidate-memory] |
| 통신판매업 등록 후속 | 20 | [메모리: legal/business_registration jaonsan] |
| 광고 예산 / 마케팅 의사결정 | 45 | [추정] 100만원 예산 분기 분배 |
| 분기/연 항목 월 환산 (분기 ÷ 3 / 연 ÷ 12) | 60 | 하단 계산 | 
| **월간 routine 소계** | **215분 ≈ 3.6시간/월** | |

### 분기 / 연간 routine

| 항목 | 회당 (분) | 빈도 | 월 환산 (분) |
|---|---|---|---|
| 변호사 미팅 (핀테크 상담소 1.5h 무료) | 90 | 분기 1 | 30 |
| 세무 / 회계 / 신고 | 120 | 반기 1 | 20 |
| 사업 모델 전략 회고 | 90 | 분기 1 | 30 |
| 통신판매업 / 부가세 / 사업자 갱신 | 60 | 연 1 | 5 |
| §101 면제 트랙 4요건 분기 증거 수집 | 30 | 분기 1 | 10 |
| **분기/연 월 환산 소계** | | | **95분 ≈ 1.6시간/월** |

[메모리: legal_question_queue Q-S3 / regulatory_changes_2026-05 / compliance-evidence skill]

---

## Phase 2 — 현 총 CEO 시간 합산

```
일일 routine    140분 × 30일 = 4,200분/월 ≈ 70시간/월
주간 routine    130분 × 4.3주 = 559분/월 ≈ 9.3시간/월
월간 routine               = 215분/월 ≈ 3.6시간/월
분기/연 환산               = 95분/월 ≈ 1.6시간/월
                          ───────────────────────
합계 (raw)                 ≈ 84.5시간/월
```

**raw 84.5h/월은 풀타임 창업자 시간 그 자체** — 본 문서가 "절감 대상"으로 잡는 범위는 **routine 성격(반복 / 자동화 가능 / 결정 batching 가능)** 만 포함.

### routine vs 비-routine 분리

| 분류 | 시간/월 | 본 문서 대상? |
|---|---|---|
| Claude Code 세션 (개발/디자인/법무) | 약 45시간 | ❌ 창업 활동 본체 |
| 인스타/Threads/카페 게시 (마케팅) | 약 7.5시간 | ❌ 본인 직접 필요 (§101) |
| 이메일 (대인 응답) | 약 5시간 | △ AI auto-draft 가능 부분만 |
| **자동화/결정 routine (본 문서 target)** | **약 27시간/월** | ✅ |

**Stage A CEO routine target = 약 27시간/월** ([추정], CEO 검증 필요)

### 목표선

| Stage | 자율도 | 시점 | CEO routine 목표 |
|---|---|---|---|
| A | 30% | 현재 | 27시간/월 |
| B | 60% | D+90 | 12시간/월 |
| C | 80% | D+180 | 5시간/월 |
| D | 95% | D+365 | **1-3시간/월** |

목표: 월 5시간 미만 = Stage C 이후. 창업 풀타임 X, 다른 일 / 학업 가능.

---

## Phase 3 — 시간 절감 ramp 4단계

v54 자율 ramp 40→60→80→95% 와 매핑한 4단계.

### Stage A (현재 → D+30): "측정 + baseline"
- 자율도: 30-40%
- CEO routine: **약 27h/월**
- 진입 조건: 출시 D-day
- 핵심 활동:
  - 본 인벤토리를 실측으로 보정 (1주 time-tracker)
  - morning-brief 1개로 알림 통합 (현재 다양한 cron 출력 분산)
  - autopilot_log 자동 요약(top 3 issues) 도입
- 시간 절감 source: **결정 batching 시작 (-3h)**, **알림 통합 (-2h)** = **-5h/월**
- 측정 KPI: CEO 매주 일요일 self-report "이번 주 PivoxQuant routine 시간"

### Stage B (D+30 → D+90): "결정 위임 가속"
- 자율도: 60% [메모리: project_autonomous_ops Phase 2]
- CEO routine: **약 12h/월** (-15h vs A)
- 진입 조건: MRR ₩100만 + NPS≥30 + §101 위반 0
- 핵심 활동:
  - 26개 🟢 권한 agent가 CEO 보고 없이 진행 [메모리: project_agent_inventory]
  - onboarding email 3-step / NPS detractor auto-ticket / 환불 자동 처리 [메모리: project_autonomous_ops §1 반자율]
  - 결정 백로그 dashboard 도입 (Slack threads → DB queue)
  - 외부 액션 1주일 batch 토요일 정리
- 절감 source: **자율 위임 (-8h)**, **외부 액션 batch (-4h)**, **read-only auto-curation (-3h)** = **-15h/월**
- Kill: 2주 연속 routine 15h/월 초과 → 자율도 OFF + root cause

### Stage C (D+90 → D+180): "모바일-first 운영"
- 자율도: 80%
- CEO routine: **약 5h/월** (-7h vs B)
- 진입 조건: MRR ₩300만 + LTV/CAC>3 + churn<10%
- 핵심 활동:
  - 모든 결정을 모바일 카드 UI (OK / Defer / Drop / Comment) 로 전환
  - 일요일 저녁 15분 weekly review 정형화
  - 06:30 push 외 모든 알림 silent log (Slack DM 폐지)
  - 변호사 미팅 → 분기 1회 1.5h 무료 자문 만 (별도 routine 없음)
- 절감 source: **모바일 batching (-4h)**, **알림 throttle (-2h)**, **AI draft email (-1h)** = **-7h/월**
- Kill: 결정 백로그 7일 초과 항목 5건+ → Stage B 회귀

### Stage D (D+180 → D+365): "indie passive 모드"
- 자율도: 95%
- CEO routine: **1-3h/월** (-3h vs C)
- 진입 조건: MRR ₩2,000만 + k>0.3 (viral coefficient)
- 핵심 활동:
  - CEO routine = (1) 일요일 저녁 15분 + (2) 분기 변호사 1.5h + (3) 사고 대응 ad-hoc
  - 결정 권한 95% 자율 (광고 카피 §101만 게이트)
  - 메모리 정리 분기 1회 → 자동 consolidate skill 적용
- 절감 source: **메모리 자동화 (-1h)**, **결정 권한 더 풀림 (-1h)**, **사고 빈도 감소 (-1h)** = **-3h/월**
- Kill criteria [메모리: project_autonomous_ops §8]: D+180 MRR ₩500만 미달 → shutdown 또는 indie passive 유지 (자율 95% / CEO 주 5h 유지)

---

## Phase 4 — 절감 source 매트릭스

CEO 시간이 **어디서** 줄어드는가. 5개 source 별 누적 절감 추정.

### Source 1: 자동 batching (결정 → 24h 단위)

- 메커니즘: 모든 CEO 결정 사항을 Slack thread / DB queue 로 누적 → 일 1회 (저녁 21:00) Slack push 1개로 묶음
- 현 상태: AskUserQuestion 금지 [메모리: feedback_no_askuserquestion] 이미 부분 적용, 단 Claude Code 세션 carry-over는 매 세션 보고
- Stage별 절감:
  - A: -3h/월 (carry-over 매일 1회 → 격일)
  - B: -5h/월 (carry-over → 주 2회)
  - C: -3h/월 (주 1회 일요일 저녁)
  - D: -1h/월 (분기 검토)
- 누적: **-12h/월** (A→D)
- 위험: 결정 사항 잊혀짐 → mitigation은 §5

### Source 2: 자율 권한 위임 (🟢 26 agent)

- 메커니즘: 인벤토리화된 39 agent 중 26개에 🟢 자율 권한 (CEO 보고 없이 진행) [메모리: project_agent_inventory]
- 단, 권한 범위: 코드 / 디자인 / QA / 분석 / 메모리 정리. **CEO 전담 6** 항목은 절대 위임 안 함 [메모리: project_autonomous_ops §1]
  - 변호사 자문 / 투자자 / 비전·피벗 / §101 4요건 / 채용 / 언론
- Stage별 절감:
  - A: -2h/월 (현재 13개 인터랙티브 → 14개)
  - B: -8h/월 (26개 🟢 enable)
  - C: -3h/월 (권한 범위 확대)
  - D: -2h/월 (CEO 전담 6 외 풀 자율)
- 누적: **-15h/월**
- 위험: 자율 판단이 CEO 의도와 어긋남 → mitigation §5

### Source 3: read-only auto-curation (top 3만)

- 메커니즘: 새벽 cron 결과 / autopilot_log / bug-hunter / Sentry triage 결과를 **우선순위 알고리즘으로 top 3** 만 morning-brief에 표시. 나머지는 silent log
- 현 상태: morning_brief_kpi crontab 06:05 [메모리: project_automation_v2] — top N 큐레이션 없음, 전체 dump
- Stage별 절감:
  - A: -2h/월 (top 5 큐레이션)
  - B: -3h/월 (top 3 + AI 요약)
  - C: -2h/월 (top 1 critical만 push, 나머지 dashboard)
  - D: -1h/월 (zero-touch — critical 없으면 push 없음)
- 누적: **-8h/월**
- 위험: top 3 외 사고 miss → mitigation §5

### Source 4: 외부 액션 batch (1주일 토요일 30분)

- 메커니즘: Slack / Brevo / Sentry env 갱신 / 변호사 답변 입력 / 통신판매업 등록 단계 등 **외부 액션은 토요일 30분 1회로 묶음**
- 현 상태: carry-over가 일/주 분산 [메모리: project_automation_v2 §외부 액션 carry-over 5항목]
- Stage별 절감:
  - A: -1h/월 (carry-over checklist 도입)
  - B: -3h/월 (토요일 batch 정착)
  - C: -2h/월 (Keychain 등록 자동화, env file 자동 prompt)
  - D: -0h/월 (이미 최저)
- 누적: **-6h/월**
- 위험: 외부 액션 잊혀짐 → mitigation §5

### Source 5: 알림 throttle (06:30 모닝 1개)

- 메커니즘: 모든 push 알림을 06:30 morning-brief 1개로 통합. critical Sentry / §101 위반 / DB 손상만 즉시 push, 나머지는 silent
- 현 상태: Slack webhook 다수 cron이 개별 push
- Stage별 절감:
  - A: -1h/월
  - B: -2h/월
  - C: -2h/월
  - D: -1h/월
- 누적: **-6h/월**
- 위험: 알림 missed → mitigation은 critical 임계 룰

### 절감 source 합산표

| Source | A | B | C | D | 누적 |
|---|---|---|---|---|---|
| 1. 결정 batching | -3 | -5 | -3 | -1 | **-12h** |
| 2. 자율 위임 | -2 | -8 | -3 | -2 | **-15h** |
| 3. read-only curation | -2 | -3 | -2 | -1 | **-8h** |
| 4. 외부 액션 batch | -1 | -3 | -2 | 0 | **-6h** |
| 5. 알림 throttle | -1 | -2 | -2 | -1 | **-6h** |
| **Stage 절감 합계** | **-9h** | **-21h** | **-12h** | **-5h** | **-47h** |

검산:
- A 시작 27h → A 끝 18h (-9)
- B 끝 12h ≈ 17 -5 (B에선 v54 Phase 2 = 60% 자율 + user 증가로 응대 시간도 함께 늘어 -15 절감만 순효과)
- C 끝 5h
- D 끝 1-3h ✅

---

## Phase 5 — 위험: 자율화 시 놓치는 것

각 절감 source 별 위험과 mitigation.

### 위험 1: CEO 직감으로 catch 했을 사고를 자율이 miss
- 시나리오: §101 위반 카피가 marketing agent 자율 생성 → CEO 검수 없이 prod 게시 → 변호사 경고
- 확률: 중 (marketing 자율도 60% 이상에서)
- 영향: 변호사 경고 1회 = Kill criteria 2번 발동 [메모리: project_autonomous_ops §8]
- Mitigation:
  - §101 4요건 자동 검사 cron 매일 07:00 [메모리: section101-check]
  - marketing copy는 CEO 전담 6 유지 (절대 자율화 X)
  - 변호사 답변 받은 룰셋만 자율 게이트 통과 [메모리: feedback_legal_filter_design]

### 위험 2: 자율 판단이 CEO 의도와 어긋남
- 시나리오: 가격 A/B test agent가 §101 ① "광고 회피" 위반 카피 자동 출시
- 확률: 낮음 (§101 게이트 명시)
- 영향: 카피 전수 점검 (감사팀 wave)
- Mitigation:
  - "CEO 승인 게이트" 룰 명시 [메모리: project_autonomous_ops §5]
  - 결정 백로그 dashboard 일요일 review 시 회고
  - feedback_no_false_reports 강제

### 위험 3: 결정 백로그 누적 → 갑자기 거대해짐
- 시나리오: CEO 1주일 부재 → 일요일 백로그 50건 누적 → 처리 못함 → 결정 적체 → autopilot 중단
- 확률: 중 (취준 면접 / 가족 일정 등)
- 영향: 일요일 routine 폭증 (15분 → 3시간)
- Mitigation:
  - 백로그 7일 초과 항목 5건+ → Stage 회귀 트리거
  - "Defer" 기본값 (24h 응답 없으면 자동 defer, agent가 가용 옵션으로 진행)
  - 모바일 카드 UI 도입 (Stage C) — 한 카드당 10초 이내 결정

### 위험 4: 변호사 답변 / 외부 액션 잊혀짐
- 시나리오: 변호사 Q-S3 (§101 ② "매월 청구 금지" vs 월구독) 답변 4주 미수령 → 출시 BLOCKER 상태 유지
- 확률: 높음 (현재 21건 큐 + 핀테크 상담소 무료 자문 미예약) [메모리: legal_question_queue]
- 영향: 출시 BLOCKER
- Mitigation:
  - 변호사 큐 항목 14일 이상 답변 미수령 시 Slack push (escalation)
  - 외부 액션 carry-over checklist crontab 매 토요일 09:00
  - 핀테크 상담소 무료 자문 예약 = 출시 전 단일 P0 task

### 위험 5: top 3 큐레이션 외 사고 miss
- 시나리오: top 3 외 6번째 항목이 실은 critical (예: DB 손상 진행 중)
- 확률: 낮음 (critical 임계 분리)
- 영향: 사고 대응 지연
- Mitigation:
  - critical 임계 (severity=critical, §101 violation, DB fail, BETA_PW leak)는 top 3 와 무관하게 즉시 push [메모리: project_autonomous_ops §6]
  - silent log도 일요일 weekly review 시 전수 스캔

---

## Phase 6 — 모바일-first 가설

### 가설
CEO는 PC 앞에 매일 앉아있지 않을 수 있음 (취준생, 다른 일 / 학업). Stage C 이후 routine은 **모바일 단독 운영 가능** 해야 함.

### 모바일 routine 디자인

| 시점 | 디바이스 | 시간 | 내용 |
|---|---|---|---|
| 매일 06:30 | 스마트폰 | 2분 | 모닝 push 1개 — top 3 + critical 0 표시 |
| 매일 21:00 (선택) | 스마트폰 | 1-2분 | 결정 카드 0-3건 OK/Defer/Drop 스와이프 |
| 일요일 21:00 | 스마트폰 | 15분 | weekly review — funnel / NPS / lawyer queue / autopilot_log 요약 |
| 토요일 10:00 | 스마트폰 | 30분 | 외부 액션 batch — Slack/Sentry/env / 변호사 큐 / 통신판매업 |
| 분기 1회 | 노트북 | 90분 | 변호사 무료 자문 + 회고 + 메모리 정리 |

**모바일 routine 월 합산**:
- 매일 2분 × 30 = 60분
- 매일 21:00 1.5분 × 30 = 45분 (Stage B 이후, A는 매일 X)
- 일요일 15분 × 4.3 = 65분
- 토요일 30분 × 4.3 = 130분
- 분기 90분 ÷ 3 = 30분
- **소계: 약 330분 = 5.5시간/월**

→ Stage C 목표 5h/월 와 일치. Stage D는 매일 21:00 카드 빈도를 격일/3일에 1회로 줄여 1-3h/월 달성.

### 가능성 검토

| 항목 | 가능? | 근거 |
|---|---|---|
| 모닝 push Slack 모바일 | ✅ | 이미 webhook 사용 [메모리: project_automation_v2] |
| 결정 카드 UI | △ | 별도 모바일 web 또는 Slack thread reply 활용 가능 (코드 변경 필요, 본 문서 범위 외) |
| 일요일 15분 weekly | ✅ | 현 weekly_funnel_snapshot + lawyer_packet review 시간 합산 가능 |
| 토요일 30분 batch | ✅ | 현 carry-over 5항목 30분 내 처리 가능 [추정] |
| 분기 변호사 90분 | ✅ | 핀테크 상담소 1.5h 무료 [메모리: legal_question_queue] |

**결론: 모바일-first Stage C 운영 모델은 실현 가능.** 단 결정 카드 UI 구현은 별도 Engineering wave 필요 (본 문서 범위 외).

---

## Recommendation

### 추천안: Stage A 보강 → B/C 점진 ramp

**즉시 실행 (Stage A 보강)**
1. CEO time-tracker 1주일 self-report → 본 인벤토리 보정
2. morning-brief top 3 큐레이션 도입 (현 dump → AI 우선순위)
3. 결정 carry-over → 일 1회 → 격일 1회로 throttle
4. 외부 액션 carry-over checklist → 토요일 09:00 crontab 출력

**Stage B 진입 조건 (D+30 ~ D+90)**
- MRR ₩100만 + NPS≥30 + §101 위반 0
- 26개 🟢 agent 권한 enable (delegation-audit skill로 강제) [메모리: skills delegation-audit]
- 모바일 카드 UI MVP (Slack thread reply 활용으로 코드 변경 최소)

**Stage C/D 진입 조건**
- Stage C: MRR ₩300만 + LTV/CAC>3 + churn<10%
- Stage D: MRR ₩2,000만 + k>0.3

### Recommendation 근거
- 자율 ramp만으론 부족 — **결정 batching + 알림 throttle 가 시간 절감의 60%** ([추정] 표 Source 1+3+5 = -26h/47h)
- 모바일-first는 Stage C부터 가능 — Stage A/B는 PC 병행 (디버그 / 변호사 큐 input)
- Kill criteria [메모리: project_autonomous_ops §8] 와 정렬 — D+180 MRR ₩500만 미달 시 자율 95% indie passive 유지로 routine 1-3h 고정

---

## Execution Plan

| 단계 | 기한 | 성공 기준 |
|---|---|---|
| CEO time-tracker self-report 1주 | 2026-06-04 | 본 인벤토리 27h/월 ±20% 검증 |
| morning-brief top 3 큐레이션 | 2026-06-14 | 일일 routine -1h/월 |
| 결정 carry-over throttle (격일) | 2026-06-14 | 주간 routine -2h/월 |
| 외부 액션 토요일 batch | 2026-06-21 | 주간 routine -2h/월 |
| Stage B 진입 (MRR ₩100만 + 자율 60%) | 2026-08-28 | CEO routine 12h/월 |
| 모바일 카드 UI MVP | 2026-09-15 | Slack thread reply 결정 가능 |
| Stage C 진입 (MRR ₩300만 + 자율 80%) | 2026-11-28 | CEO routine 5h/월 |
| Stage D 진입 (MRR ₩2,000만 + 자율 95%) | 2027-05-28 | CEO routine 1-3h/월 |

---

## Kill Criteria

본 마스터플랜 중단 조건:
1. **Stage A 시작 1개월 후 routine 측정값이 35h/월 초과** (목표 27h 와 30% 이상 괴리) → 인벤토리 재작성
2. **Stage B 시작 후 2주 연속 routine 15h/월 초과** → 자율도 OFF + root cause
3. **결정 백로그 7일 초과 항목 5건+** → Stage 회귀
4. **자동화 false positive >20%/주** → 해당 자동화 disable [메모리: project_autonomous_ops §8 Kill #4]
5. **D+180 MRR ₩500만 미달** → indie passive 모드 (자율 95% / CEO 주 5h)

---

## Risk & Mitigation 요약표

| 리스크 | 확률 | 영향 | Mitigation |
|---|---|---|---|
| 자율 §101 위반 | 중 | 변호사 경고 = Kill | marketing CEO 전담 + 일일 cron |
| 자율 의도 어긋남 | 낮 | 카피 전수 점검 | 승인 게이트 + weekly review |
| 결정 백로그 폭증 | 중 | routine 폭증 | 24h auto-defer + 백로그 dashboard |
| 변호사 답변 missed | 높 | 출시 BLOCKER | 14일 escalation push + 토요일 batch |
| top 3 외 사고 miss | 낮 | 대응 지연 | critical 임계 별도 push |
| CEO 1주 부재 | 중 | 백로그 50건 | auto-defer 기본값 |

---

## 부록 A: 본 문서가 다루지 않는 것

- 모바일 카드 UI 코드 구현 → 별도 Engineering wave
- 결정 dashboard DB 스키마 → 별도 design 문서
- AI auto-draft email tone → 별도 Marketing wave
- 변호사 답변 자동 룰셋 적용 메커니즘 → legal-question-queue skill 확장
- 사고 catch-up loop 알고리즘 → DevOps wave

---

## 부록 B: 참조 메모리

- `project_autonomous_ops.md` — 자율도 ramp 40/60/70%, Kill criteria
- `project_automation_v2.md` — 16 crontab + 5 CC hooks + 환경변수
- `project_agent_inventory.md` — 39 agent 인벤토리, 26 🟢 권한
- `legal_question_queue.md` — 21건 (Q-S3 출시 BLOCKER)
- `feedback_no_askuserquestion.md` — 인터랙티브 결정 금지
- `feedback_no_extra_cost.md` — 추가 비용 0원 제약
- `feedback_pre_launch_full_throttle.md` — 출시 전 Full Throttle (본 문서 ramp 출시 후 적용)

---

_작성: 2026-05-28 Strategy Agent — v56-M1 마스터플랜 / CEO 검증 대기 (Phase 1 인벤토리 시간 추정값)_
