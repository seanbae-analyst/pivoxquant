# PivoxQuant 자율 기능 Product Spec

> v54-S4 / 2026-05-28 / Owner: 프로덕트부
> 컨텍스트: 1인 창업자, 출시 직전, 0원 운영, 모바일 PWA primary
> 원칙: CEO 명령 없이 굴러가는 시스템 — 단, 유저 영향 / 법적 리스크 / 비용 모두 통제

---

## 0. 요약

- 이미 자율로 굴러가는 유저-facing 기능: **6개 카테고리** (artifact 14종 + price alert + Twin decisions + signal refresh + dunning + PIPA hard-delete)
- 본 spec에서 신규로 정의하는 자율 기능: **10개 후보 → top 5 우선순위 spec**
- 모든 신규 기능: 0원 / 1인 / 1주 내 구현 가능 범위로 한정
- 변호사 BLOCKER (Q-S1 / Q-S3 / Q-S4 / Q-M1/M2/M3 등) 미해제 항목은 **PENDING** 표기

---

## Phase 1 — 현 자율 유저-facing 기능 인벤토리 (실측)

| 카테고리 | 발동 메커니즘 | 실측 위치 | 유저 가시성 |
|---|---|---|---|
| **Artifact 14종** | crontab + 페르소나 trigger | `services/artifacts/*_service.py` (weekly_memo / brag_card / earnings_prebrief / dd_checklist / risk_board / monthly_finance / 등) | 매주/매월 자동 PDF·이메일 |
| **Price alert** | scheduler 5min poll | `services/alert_service.py` + `services/alert.py` (52w high/low, sector concentration, VIX) | push / 이메일 |
| **Twin decisions** | KR/US daily cron | `services/twin/` | 매일 9:00 KST 결과 카드 |
| **Signal refresh** | 3min cycle | `services/quant/` + APScheduler 26 jobs | detail 페이지 자동 갱신 |
| **Dunning (결제 실패)** | Stripe webhook trigger | `services/billing_followup.py` | 결제 실패 후 자동 retry 안내 |
| **PIPA hard-delete** | 30일 cron | `migrations 044` + `services/admin_emails.py` | 탈퇴 30일 후 자동 삭제 통지 |
| **Inactive nudge (24h)** | 신규 가입 24-25h window | `services/customer/inactive_nudge.py` | 첫 onboarding 액션 안 한 신규에게 1회 nudge |

**OFF / 미가동 (코드는 존재)**:
- `services/email/onboarding_sequence.py` — 변호사 Q-S1 PENDING
- `services/email/retention_sequence.py` — 변호사 Q-S1 PENDING
- `services/support/chatbot.py` (SUPPORT_CHAT_LLM_ENABLED=0) — Anthropic 비용 + Q-S4 잔존
- `.github/workflows/self-healing.yml.disabled` — 자동 hotfix PR
- `.github/workflows/nightly-bug-hunt.yml.disabled` — bug-hunter
- `.github/workflows/morning-brief.yml.disabled` — 데일리 다이제스트

---

## Phase 2 — 자율 가능한 유저-facing 기능 후보 10개

각 후보의 권한 tier 표기:
- 🟢 **유저 가시 자동**: 유저에게 직접 영향, 즉시 발송/적용 가능
- 🟡 **유저 가시 + 게이트**: 자동 생성하되 verify-policy / legal-kr-fintech 통과해야 발송
- 🔴 **CEO 승인 필수**: 자동 draft까지, 발송 / merge는 사람 손

---

### 후보 1. 자동 onboarding 메일 시퀀스
- **유저 영향**: 가입 직후 D+1/D+3/D+7 자동 가이드 메일 → 첫 액션율 ↑
- **법적**: 정통망법 §50 ① opt-in 확인 게이트 필수. §101 ② "매월 청구 금지" 충돌 없음 (정보성)
- **비용**: SendGrid 100/day free tier 내 0원
- **권한 tier**: 🟡 (legal_filter 통과 + 수신동의 컬럼 체크)
- **의존성**: Q-S1 PENDING (변호사 정통망법 §50 워딩 확정 대기). 코드는 `services/email/onboarding_sequence.py` 완성

### 후보 2. 자동 customer support 챗봇
- **유저 영향**: 24/7 FAQ 응답, 답 못 찾을 시 이메일 ticket으로 escalate
- **법적**: §101 advisory 어휘 금지 (legal_filter 통과 필수). AI 생성물 표시제 (regulatory_changes_2026-05) 필수
- **비용**: Anthropic 크레딧 — Max 플랜 외 추가 결제 발생 가능 → **추가 비용 룰 위반 위험**. FAQ static fallback만 활성화는 0원 가능
- **권한 tier**: 🔴 (LLM 호출은 비용 발생, static FAQ만 🟢)
- **의존성**: Q-S4 PENDING (영문 레짐 msg §49 비대칭). 비용 룰 (memory `feedback_no_extra_cost`)

### 후보 3. 자동 marketing post (카페 / 인스타 / Threads)
- **유저 영향**: 잠재 유저에게 컨텐츠 노출
- **법적**: 표시광고법 §3 (허위·과장 금지) + §101 advisory 어휘 + Q-M1/M2/M3 PENDING (뒷광고 / §101 카피)
- **비용**: 0원 (수동 API 또는 RSS publish)
- **권한 tier**: 🔴 (Q-M1/M2/M3 PENDING — CEO 검토 후만 발송)
- **의존성**: Q-M1/M2/M3 변호사 답 + `services/marketing/publishers.py`

### 후보 4. 자동 retention 메일 (7d/14d/30d 비활성)
- **유저 영향**: 이탈 직전 재참여 nudge
- **법적**: §50 ① opt-in + §50 ② 야간 발송 금지 (21:00-08:00). PIPA 보유 목적 외 사용 금지
- **비용**: SendGrid 무료 한도 내 0원
- **권한 tier**: 🟡 (retention_sequence.py 게이트 후 발송)
- **의존성**: Q-S1 PENDING

### 후보 5. 자동 hotfix PR (bug-hunter → self-healing.yml)
- **유저 영향**: 간접 (prod 사고 ↓). 잘못된 PR auto-merge는 회귀 사고
- **법적**: 없음
- **비용**: GitHub Actions 무료 한도 + Anthropic — Max 한도 내 0원
- **권한 tier**: 🔴 (CEO merge 승인 — auto-merge 금지)
- **의존성**: pytest 게이트 + alembic-head-guard 재활성

### 후보 6. 자동 NPS 수집 (D+14)
- **유저 영향**: 가입 14일 뒤 1회 NPS 설문 이메일
- **법적**: §50 ① opt-in. PIPA 수집 목적 명시
- **비용**: 0원 (SendGrid + `migrations/039_nps_feedback.py` 기존 활용)
- **권한 tier**: 🟢 (단일 발송, legal_filter 통과 후 자동)
- **의존성**: Q-S1 PENDING (정통망법 워딩 부분만)

### 후보 7. 자동 churn 예측 + 재참여 캠페인
- **유저 영향**: 4주 미접속 + signal 0 유저에게 재참여 메일
- **법적**: §50 ① opt-in + §50 ② 야간 금지 + Q-S1 PENDING
- **비용**: 0원
- **권한 tier**: 🟡
- **의존성**: Q-S1 + retention_sequence.py 확장

### 후보 8. 자동 referral 보상 dispatch
- **유저 영향**: 추천인/피추천인 양쪽에 자동 보상 통지
- **법적**: §101 ② "매월 청구" 회피 — 보상이 구독 연장 형태면 충돌. 정보성 크레딧만 OK
- **비용**: 0원 (Stripe 쿠폰 무료)
- **권한 tier**: 🟡 (Q-S3 답 후)
- **의존성**: Q-S3 PENDING (§101 ② 월구독 충돌). referral 기능 자체 미구현

### 후보 9. 자동 disclaimer 갱신
- **유저 영향**: regulatory 변화 시 disclaimer 페이지 / PDF 자동 차이 알림
- **법적**: 없음 (오히려 컴플라이언스 ↑)
- **비용**: 0원 (legal-deep-scan.yml.disabled 재활성)
- **권한 tier**: 🔴 (CEO 검토 후 본문 반영)
- **의존성**: 없음

### 후보 10. 자동 feature flag 점진 rollout
- **유저 영향**: V2 토글 9개를 5% → 25% → 100% 자동 단계 증가
- **법적**: 없음
- **비용**: 0원
- **권한 tier**: 🟡 (Sentry 에러율 게이트)
- **의존성**: Sentry free tier, 에러율 임계값 정의

---

## Phase 4 — 우선순위 매트릭스

| # | 후보 | 출시 영향 | 시간 절약 | 위험도 | 의존성 | 우선순위 |
|---|---|---|---|---|---|---|
| 6 | **자동 NPS 수집** | 중 (PMF 신호) | 주 1h | 낮 | Q-S1 일부만 | **TOP 1** |
| 9 | **자동 disclaimer 갱신** | 중 (컴플라이언스) | 월 2h | 낮 | 없음 | **TOP 2** |
| 1 | **자동 onboarding 메일** | 상 (활성화 ↑) | 주 3h | 중 (§50) | Q-S1 PENDING | **TOP 3** |
| 10 | **자동 feature flag rollout** | 상 (안전 출시) | 주 2h | 중 (회귀) | Sentry | **TOP 4** |
| 4 | **자동 retention 메일** | 상 (유지율) | 주 4h | 중 (§50) | Q-S1 PENDING | **TOP 5** |
| 5 | 자동 hotfix PR | 중 | 주 5h | 상 (회귀) | 없음 | 보류 |
| 7 | 자동 churn 캠페인 | 중 | 월 4h | 중 | Q-S1 | 후순위 |
| 2 | 자동 챗봇 (LLM) | 중 | 주 5h | 상 (비용) | Q-S4 | 보류 |
| 3 | 자동 marketing post | 상 (유저 획득) | 주 6h | 상 (광고법) | Q-M1/M2/M3 | 보류 |
| 8 | 자동 referral 보상 | 하 (referral 미구현) | - | 중 | Q-S3 | 보류 |

선정 기준:
- **TOP 1 (NPS)**: 변호사 의존도 최소 + 출시 후 즉시 발동 + PMF 신호 확보
- **TOP 2 (disclaimer)**: 법적 의존성 0 + 컴플라이언스 ↑
- **TOP 3 (onboarding)**: 활성화율 직결, Q-S1 해제 즉시 발동
- **TOP 4 (flag rollout)**: V2 토글 9개 안전 출시 게이트
- **TOP 5 (retention)**: 유지율 직결, Q-S1 묶음 발동

---

## Phase 5 — TOP 5 자율 기능 1페이지 Spec

---

### Spec 1. 자동 NPS 수집

- **기능명**: Auto NPS D+14
- **1줄 설명**: 가입 14일 차 유저에게 NPS 0-10 단일 문항 메일 자동 1회 발송 → DB 저장 → 주간 집계 다이제스트
- **자율 권한 tier**: 🟢 (단일 발송, legal_filter 통과 게이트)
- **발동 조건**:
  - `users.created_at` BETWEEN now-14d AND now-13d
  - `users.nps_sent_at IS NULL`
  - `users.email_consent_marketing = true` (§50 ①)
  - 발송 시간: 09:00-20:00 KST (§50 ② 야간 회피)
- **유저 경험 (전/후)**:
  - 전: NPS 0 → PMF 신호 없음
  - 후: D+14 메일 1회 (제목 "1분만 시간 내주실 수 있나요?") → 클릭 시 1-tap 점수 페이지 → 자유 코멘트 옵션
- **법적 검증 (자동 게이트)**:
  - `services/legal/forbidden_terms.py` + `legal_filter.py` 본문 통과
  - `legal-kr-fintech` agent CI 게이트
  - opt-in 컬럼 체크 (`users.email_consent_marketing`)
- **측정 지표**:
  - 성공: 응답률 ≥ 15%, NPS ≥ 30
  - 실패: 응답률 < 5% (재발송 금지, 발송 주기 재검토)
- **Rollback 메커니즘**:
  - feature flag `NPS_AUTO_ENABLED=0` 1초 OFF
  - `users.nps_sent_at` 컬럼 NULL로 리셋 가능 (재발송용)
- **의존성**: `migrations/039_nps_feedback.py` 기존, Q-S1 워딩 일부만

---

### Spec 2. 자동 Disclaimer 갱신

- **기능명**: Auto Disclaimer Diff Alert
- **1줄 설명**: regulatory 변화 (legal-deep-scan 결과) 발생 시 disclaimer 페이지 / PDF 자동 diff → CEO 검토 issue 생성
- **자율 권한 tier**: 🔴 (draft까지 자동, merge는 CEO)
- **발동 조건**:
  - 매주 월 09:00 KST `legal-deep-scan.yml` 실행
  - regulatory change detected (FSC / FSS / PIPA / 표시광고법)
  - 영향 키워드가 `legal_terms.md` / `legal_privacy.md` / `disclaimer.md` 본문에 포함
- **유저 경험 (전/후)**:
  - 전: 규제 변화 → 수동 발견 → 며칠 delay → 잠재 위반
  - 후: 변화 발생 → 24h 내 CEO 검토 → 1주 내 disclaimer 갱신
- **법적 검증 (자동 게이트)**:
  - `legal-kr-fintech` agent로 변화 분류
  - CEO label `legal-review` 자동 부착
- **측정 지표**:
  - 성공: 규제 변화 → disclaimer 반영 SLA 7d
  - 실패: SLA 7d 초과 = label `legal-overdue` 자동 부착
- **Rollback 메커니즘**:
  - workflow disable 1줄 (`mv self-healing.yml self-healing.yml.disabled`)
- **의존성**: `.github/workflows/legal-deep-scan.yml.disabled` 재활성

---

### Spec 3. 자동 Onboarding 메일 시퀀스

- **기능명**: Auto Onboarding Drip
- **1줄 설명**: 가입 D+1 / D+3 / D+7 3단계 가이드 메일 자동 발송 (1차 무료 페르소나 결과 / 2차 첫 artifact 안내 / 3차 Pro 베네핏 정보성)
- **자율 권한 tier**: 🟡 (legal_filter + §50 ① opt-in + §50 ② 야간 회피 게이트)
- **발동 조건**:
  - `users.created_at` 기준 D+1, D+3, D+7 (정확 24h±2h window)
  - `users.email_consent_*` 컬럼별 동의 확인
  - 09:00-20:00 KST 발송 (§50 ②)
  - `users.unsubscribed_at IS NULL`
- **유저 경험 (전/후)**:
  - 전: 가입 → 가이드 없음 → 첫 액션율 < 30%
  - 후: 3단계 메일 → 첫 액션율 50%+ 목표
- **법적 검증 (자동 게이트)**:
  - 본문 `services/legal/forbidden_terms.py` 통과
  - "수익 보장" / "투자 추천" 등 자동 차단
  - List-Unsubscribe 헤더 자동 삽입 (정통망법 §50 ④)
- **측정 지표**:
  - 성공: D+7 액션율 50%+, unsubscribe rate < 2%
  - 실패: unsubscribe rate > 5% (메시지 수정)
- **Rollback 메커니즘**:
  - feature flag `ONBOARDING_DRIP_ENABLED=0`
  - 1차 OFF → 2차/3차도 자동 중단
- **의존성**: **Q-S1 PENDING** (변호사 정통망법 워딩). 코드 `services/email/onboarding_sequence.py` 완성됨

---

### Spec 4. 자동 Feature Flag 점진 Rollout

- **기능명**: Auto Flag Ramp
- **1줄 설명**: V2 토글 9개를 5% → 25% → 50% → 100% 단계 자동 증가 (Sentry 에러율 게이트 통과 시)
- **자율 권한 tier**: 🟡 (Sentry 에러율 < 1% 게이트)
- **발동 조건**:
  - 새 flag enable 시 5%로 시작
  - 24h 동안 Sentry 에러율 < 1% → 25%로 ramp
  - 48h 동안 < 1% → 50%
  - 72h 동안 < 1% → 100%
  - 임계 초과 시 자동 50% → 25% → 5% 단계 down
- **유저 경험 (전/후)**:
  - 전: 100% 일괄 출시 → 회귀 시 전유저 영향
  - 후: 5% 카나리 → 회귀 즉시 자동 down → 전유저 보호
- **법적 검증**: 없음
- **측정 지표**:
  - 성공: ramp 평균 < 4d, 회귀 자동 down < 1h
  - 실패: 자동 down 미발동 (Sentry alert 누락)
- **Rollback 메커니즘**:
  - Sentry threshold 초과 → 즉시 1단계 down
  - 수동 override: `FEATURE_FLAG_AUTO_RAMP=0`
- **의존성**: Sentry free tier (월 5K events), V2 토글 9개 (기존)

---

### Spec 5. 자동 Retention 메일

- **기능명**: Auto Retention Nudge
- **1줄 설명**: 비활성 7일 / 14일 / 30일 유저에게 단계별 재참여 메일 자동 발송 (정보성 컨텐츠만, 광고 X)
- **자율 권한 tier**: 🟡 (legal_filter + §50 게이트)
- **발동 조건**:
  - `users.last_active_at` < now - 7d / 14d / 30d
  - 각 단계당 1회만 발송 (`users.retention_d7_sent_at` 등)
  - 09:00-20:00 KST
  - `users.email_consent_marketing = true`
- **유저 경험 (전/후)**:
  - 전: 비활성 → 자연 churn
  - 후: 단계별 재참여 → "이번 주 Top signal" / "유사 페르소나의 최근 artifact" / "1달간 시장 요약"
- **법적 검증 (자동 게이트)**:
  - 본문 §101 "투자 추천" 어휘 금지
  - 정보성 generalized 표현만 (Q-S3 충돌 회피)
- **측정 지표**:
  - 성공: 7d nudge 재방문율 25%+, 30d 재방문율 10%+
  - 실패: unsubscribe > 5%
- **Rollback 메커니즘**:
  - feature flag `RETENTION_NUDGE_ENABLED=0`
- **의존성**: **Q-S1 PENDING** + `services/email/retention_sequence.py` (기존)

---

## 부록 — 의존성 요약

| 의존 항목 | 영향 spec | 상태 |
|---|---|---|
| **Q-S1** (정통망법 §50 워딩) | Spec 1 / 3 / 5 (NPS는 일부만) | PENDING (핀테크 상담소 무료 자문 1.5h 대기) |
| **Q-S3** (§101 ② 월구독 충돌) | 후보 8 (referral) | PENDING |
| **Q-S4** (영문 §49 비대칭) | 후보 2 (챗봇) | engineering wave 진행 중 |
| **Q-M1/M2/M3** (마케팅 카피) | 후보 3 (marketing post) | PENDING |
| `legal-deep-scan.yml` 재활성 | Spec 2 | 코드 OK, workflow rename만 |
| Sentry free tier | Spec 4 | 기존 가동 |
| SendGrid 100/day | Spec 1 / 3 / 5 | 기존 가동 |

---

## 부록 — 출시 후 90일 자율 기능 로드맵

| 시점 | 적용 spec | 조건 |
|---|---|---|
| **D+0** (출시) | Spec 2 (disclaimer) | 즉시 가동 |
| **D+0** | Spec 4 (flag ramp) | 즉시 가동 |
| **D+14** | Spec 1 (NPS) | 첫 유저 14d 도달 시 |
| **Q-S1 해제 후** | Spec 3 (onboarding) | 변호사 답 즉시 |
| **Q-S1 해제 +14d** | Spec 5 (retention) | onboarding 안정화 후 |
| **D+30 이후** | 후보 7 (churn) / 후보 10 비교 | 유저 N>100 시 |
| **Q-M 해제 후** | 후보 3 (marketing) | 변호사 답 후 |

---

## 출시 전 검증 체크리스트

- [ ] Spec 1: NPS 메일 본문 `legal_filter` 통과 확인
- [ ] Spec 1: `users.email_consent_marketing` 컬럼 신규 가입 default false 확인
- [ ] Spec 2: legal-deep-scan.yml.disabled → .yml rename + dry-run
- [ ] Spec 2: CEO label `legal-review` 자동 부착 테스트
- [ ] Spec 3: Q-S1 답변 수령 → 본문 변호사 검수 컬럼 정리
- [ ] Spec 4: Sentry threshold rule 1% / 24h window 설정
- [ ] Spec 4: 자동 down 시나리오 staging dry-run
- [ ] Spec 5: D+7/14/30 메일 본문 변호사 검수 (Q-S1 묶음)
- [ ] 모든 spec: List-Unsubscribe 헤더 자동 삽입 통합 테스트
