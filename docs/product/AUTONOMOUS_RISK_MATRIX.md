# PivoxQuant 자율 기능 위험 매트릭스

> v54-S4 / 2026-05-28 / Owner: 프로덕트부 + 법무부
> 짝 문서: `AUTONOMOUS_FEATURES_SPEC.md`
> 원칙: 자율로 굴러가되 유저 부정 영향 / 법적 위반 / prod 사고는 자동 게이트로 차단

---

## 0. 위험 카테고리 5종

| # | 카테고리 | 잠재 영향 | 대표 사례 |
|---|---|---|---|
| R1 | **잘못된 자동 응답** | 법적 책임 (§101 advisory) | 챗봇이 "이 종목 사세요" 응답 |
| R2 | **알림 spam** | 정통망법 §50 6% 과징금 | 자동 메일 야간 발송 / opt-in 누락 |
| R3 | **자동 PR 회귀** | prod 사고 | self-healing PR auto-merge → 결제 끊김 |
| R4 | **자동 marketing 위반** | 표시광고법 §3 / §101 / 뒷광고 | 자동 인스타 포스트 "수익 보장" |
| R5 | **자동 환불 / 회계 사고** | 영수증 / 세무 / 신뢰 | dunning 자동 환불 잘못 발동 |

---

## R1 — 잘못된 자동 응답

### 영향
- §101 면제 트랙 위반 = 유사투자자문업 무등록 행위
- 표시광고법 §3 (허위·과장 표시)
- 유저 손실 시 손해배상 청구 위험

### 감지 메커니즘
1. `services/legal/forbidden_terms.py` — 발송 직전 본문 grep
2. `services/legal_filter.py` — naked BUY/SELL, "수익 보장", "추천" 등 차단 (case-sensitive 의도)
3. agent `legal-kr-fintech` — CI 단계에서 정적 검사
4. 발송 로그 sample 5% 일일 manual audit (CEO 5min)

### 차단 게이트
- **사전**: PR merge 시 `legal-kr-fintech` agent 통과 필수
- **런타임**: 메시지 큐 enqueue 직전 `legal_filter.scrub()` 호출 → fail 시 enqueue 거부
- **사후**: Sentry custom event `legal_filter_blocked` → 누적 > 10/day → Slack alert

### CEO escalation 조건
- legal_filter 차단 누적 > 10/day → 즉시 SUPPORT_CHAT_LLM_ENABLED=0 토글
- 외부 신고 / 클레임 1건 → 전 시스템 OFF

### 영향 spec
- 후보 2 (자동 챗봇) — 가장 직접
- Spec 1 / 3 / 5 (이메일) — 본문 자동 생성 시

---

## R2 — 알림 spam (정통망법 §50)

### 영향
- §50 ① opt-in 없는 광고성 정보 = 3000만원 이하 과징금
- §50 ② 야간(21:00-08:00) 발송 = 별도 위반
- §50 ④ List-Unsubscribe 누락 = 별도 위반
- 2026-05 시행 6% 매출 과징금 (regulatory_changes_2026-05)

### 감지 메커니즘
1. 발송 직전 `users.email_consent_*` 컬럼 체크
2. 발송 시각이 KST 09:00-20:00 범위인지 코드 가드
3. `services/email/sender.py` — List-Unsubscribe 헤더 자동 삽입 통합 테스트
4. unsubscribe 클릭률 monitoring → > 5% 시 alert
5. SendGrid bounces / spam report 일일 수집

### 차단 게이트
- **사전**: `services/email/sender.py::send()` 가드 4중:
  - consent_required 컬럼 true 확인
  - 시각 check (KST_HOUR in 9..20)
  - List-Unsubscribe 헤더 존재 assert
  - body legal_filter 통과
- **런타임**: 큐 dispatcher가 가드 fail 시 메시지 deadletter
- **사후**: bounce rate > 3% → 자동 24h 발송 중단 + Slack

### CEO escalation 조건
- spam report 누적 > 5 (SendGrid 기준) → 전 마케팅 메일 즉시 중단
- KST 야간 발송 1건이라도 감지 → 즉시 cron 중단 + post-mortem

### 영향 spec
- Spec 1 / 3 / 5 (이메일 시퀀스) — 직접
- 후보 7 (churn 캠페인) — 직접

---

## R3 — 자동 PR 회귀

### 영향
- 자동 hotfix PR이 회귀 코드 merge → prod 사고
- alembic head 충돌 → migration 깨짐
- 결제 / 인증 / signal 끊김 → 즉시 비즈니스 영향

### 감지 메커니즘
1. PR pytest 게이트 — 1288 tests pass
2. alembic-head-guard.yml — heads 단일 확인
3. design-token-drift / motion-spec — UI 회귀 차단
4. post-deploy-canary.yml — 배포 후 health 20/20 ok 확인
5. Sentry error rate spike 5min window

### 차단 게이트
- **사전**: auto-merge 금지 — 모든 PR CEO label `auto-pr-approved` 수동 부착 필수
- **사전**: pytest fail / alembic head 충돌 / migration self-heal 미통과 시 block
- **런타임**: Sentry threshold (5min window 에러율 > 2%) 초과 시 자동 rollback PR 생성
- **사후**: canary 실패 시 즉시 Slack + railway rollback 매뉴얼 alert

### CEO escalation 조건
- auto-PR 회귀 1건 = self-healing.yml 즉시 disable (1주 cooldown)
- alembic head 충돌 = migration-guard agent 사후 검증 의무

### 영향 spec
- 후보 5 (자동 hotfix PR) — 가장 직접
- Spec 4 (flag ramp) — 회귀 시 자동 down 메커니즘 자체가 게이트

---

## R4 — 자동 marketing 위반

### 영향
- 표시광고법 §3 = 5천만원 이하 / 매출 2% 과징금
- §101 advisory 어휘 = 면제 트랙 박탈 → 무등록 행위
- 뒷광고 = 공정위 신고 위험
- AI 생성물 표시제 (regulatory_changes_2026-05) 미준수

### 감지 메커니즘
1. `services/marketing/publishers.py` — 발송 직전 `legal_filter` 통과 필수
2. `services/marketing/content_bank.py` — 사전 승인 카피만 publish
3. AI 생성 컨텐츠는 본문 hash → 사전 CEO label `marketing-approved` 매핑
4. 일일 sample 5% manual review

### 차단 게이트
- **사전**: `marketing-approved` label 없는 컨텐츠 publish 금지
- **사전**: `brand-voice` agent 톤 검사
- **사전**: AI 생성물 시 본문에 "AI 생성" 메타 표기 자동 삽입
- **런타임**: publish API 호출 직전 final `legal_filter.scrub()` 재실행
- **사후**: 외부 클레임 / DM 1건 = 해당 포스트 즉시 삭제 + cron 중단

### CEO escalation 조건
- Q-M1/M2/M3 PENDING 동안 모든 자동 publish OFF
- 변호사 답 후에도 첫 30개 포스트는 CEO 수동 승인 필수

### 영향 spec
- 후보 3 (자동 marketing post) — 가장 직접

---

## R5 — 자동 환불 / 회계 사고

### 영향
- 잘못된 자동 환불 → 매출 손실
- 영수증 / 세무 신고 mismatch
- 유저 신뢰 ↓

### 감지 메커니즘
1. Stripe webhook → DB 트랜잭션 atomic
2. dunning 자동 retry는 최대 3회만, 4회째 CEO escalation
3. 일일 Stripe / DB reconciliation cron (기존)
4. 환불 자동 발동 트리거는 명시적 webhook event만

### 차단 게이트
- **사전**: 자동 환불 = `customer.refund_auto_enabled = true` 사전 동의자만
- **사전**: 환불 금액 > ₩10K = CEO escalation 필수
- **런타임**: dunning 4회 fail → 자동 처리 중단 + CEO 알림
- **사후**: 환불 후 영수증 자동 발송 + Stripe 로그 일일 audit

### CEO escalation 조건
- 자동 환불 1건이라도 mismatch 발견 → 즉시 자동 환불 OFF
- Stripe / DB reconciliation 차이 > ₩10K → 일일 cron alert

### 영향 spec
- 직접: 없음 (TOP 5에 환불 자동화 없음)
- 간접: 향후 referral 보상 (후보 8) 시 발동 시점

---

## 통합 위험 매트릭스

| Spec / 후보 | R1 (자동응답) | R2 (spam) | R3 (PR회귀) | R4 (marketing) | R5 (환불) | 종합 위험 |
|---|---|---|---|---|---|---|
| **Spec 1 (NPS)** | 낮 (단일 문항) | 중 (§50 게이트) | - | - | - | **낮** |
| **Spec 2 (disclaimer)** | - | - | 낮 (draft만) | - | - | **낮** |
| **Spec 3 (onboarding)** | 중 (본문) | 상 (§50) | - | - | - | **중** |
| **Spec 4 (flag ramp)** | - | - | 중 (자동 down) | - | - | **중** |
| **Spec 5 (retention)** | 중 (본문) | 상 (§50) | - | - | - | **중** |
| 후보 2 (챗봇) | 상 (LLM) | - | - | - | - | **상** (보류) |
| 후보 3 (marketing) | - | - | - | 상 (광고법) | - | **상** (보류) |
| 후보 5 (hotfix PR) | - | - | 상 (auto-merge 금지) | - | - | **상** (보류) |
| 후보 8 (referral) | - | - | - | - | 중 (보상) | **중** (Q-S3 PENDING) |

---

## 발동 / 차단 게이트 통합 표

| 게이트 | 위치 | 발동 시점 | 차단 조건 | 영향 spec |
|---|---|---|---|---|
| `legal_filter.scrub()` | `services/legal_filter.py` | 발송 / publish 직전 | 금지 어휘 1개라도 | 1 / 3 / 5 / 챗봇 / marketing |
| `forbidden_terms` grep | `services/legal/forbidden_terms.py` | CI + 런타임 | naked BUY/SELL / "수익 보장" 등 | 동일 |
| `email_consent_*` 컬럼 | DB users 테이블 | sender 직전 | consent false | 1 / 3 / 5 |
| KST 시각 가드 | `services/email/sender.py` | 발송 직전 | 21:00-08:00 KST | 1 / 3 / 5 |
| List-Unsubscribe 헤더 | `services/email/sender.py` | 헤더 빌드 | 헤더 누락 | 1 / 3 / 5 |
| Sentry error rate | Sentry rule | 5min window | > 2% | Spec 4 |
| pytest gate | CI | PR 직전 | fail | 모든 PR |
| alembic-head-guard | `.github/workflows/` | PR 직전 | heads ≥ 2 | migration |
| canary post-deploy | `.github/workflows/` | 배포 후 5min | health < 20/20 | 모든 배포 |
| CEO label `marketing-approved` | GitHub | publish 직전 | label 없음 | 후보 3 |
| Stripe / DB reconcile | 일일 cron | 매일 09:00 | 차이 > ₩10K | 결제 전반 |

---

## 자율 권한 tier별 운영 룰

### 🟢 유저 가시 자동 (게이트만 통과하면 즉시 발송)
- 적용: Spec 1 (NPS) / Spec 2 disclaimer draft 생성까지
- 룰:
  - legal_filter / §50 가드 통과 시 즉시 발송
  - CEO 알림 사후 (Slack `#autopilot-log`)
  - 실패 1건 발생 시 즉시 OFF

### 🟡 유저 가시 + 게이트 (verify-policy / legal-kr-fintech 통과 필수)
- 적용: Spec 3 / Spec 4 / Spec 5 / 후보 7 / 후보 8
- 룰:
  - 본문 / 토글 변경 시 PR 단계에서 agent 통과
  - 런타임 가드 4중 통과 (legal_filter / consent / 시각 / 헤더)
  - 실패율 / unsubscribe 임계 초과 시 자동 ramp-down
  - CEO 일일 audit (5min)

### 🔴 CEO 승인 필수 (draft까지 자동, merge / 발송은 사람)
- 적용: Spec 2 (disclaimer merge) / 후보 3 (marketing publish) / 후보 5 (hotfix PR merge)
- 룰:
  - draft / PR / issue 자동 생성까지만
  - CEO label / approve 명시 필수
  - 48h 내 응답 없으면 자동 label `stale-review` + Slack daily reminder

---

## 출시 전 위험 검증 체크리스트

### R1 (자동 응답)
- [ ] `legal_filter.scrub()` 테스트 90개 모두 pass
- [ ] `forbidden_terms.py` 한·영 어휘 130개+ 최신
- [ ] 챗봇 OFF 확인 (SUPPORT_CHAT_LLM_ENABLED=0)

### R2 (spam)
- [ ] `users.email_consent_marketing` 컬럼 default false 확인
- [ ] `services/email/sender.py` KST 시각 가드 unit test
- [ ] List-Unsubscribe 헤더 통합 테스트
- [ ] SendGrid bounce/spam report 일일 수집 cron

### R3 (PR 회귀)
- [ ] self-healing.yml 비활성 확인
- [ ] alembic-head-guard.yml 재활성
- [ ] post-deploy-canary.yml 재활성
- [ ] Sentry rule 5min window 2% threshold 설정

### R4 (marketing)
- [ ] Q-M1/M2/M3 PENDING 동안 publishers.py OFF
- [ ] `marketing-approved` label workflow 정의

### R5 (환불)
- [ ] dunning 최대 retry 3회 코드 가드
- [ ] Stripe / DB reconciliation cron 일일 실행 확인

---

## 사고 시 Rollback 매트릭스

| 위험 발생 | 1차 자동 대응 | 2차 자동 대응 | CEO 액션 |
|---|---|---|---|
| legal_filter 차단 누적 > 10/day | Slack alert | 챗봇 OFF | 본문 / 어휘 점검 |
| SendGrid spam report > 5 | 24h 발송 중단 | 메일 전체 OFF | 본문 수정 + opt-in 점검 |
| Sentry error spike > 2% / 5min | flag 자동 down 1단계 | 자동 rollback PR | 코드 hotfix |
| 자동 PR 회귀 1건 | (수동 merge 필수라 차단) | self-healing.yml disable | post-mortem |
| 외부 신고 / 클레임 1건 | - | 해당 컨텐츠 즉시 삭제 | 변호사 자문 |
| Stripe / DB mismatch > ₩10K | 일일 cron alert | 자동 환불 OFF | reconcile 수동 |

---

## 결론

- **즉시 가동 가능 (D+0)**: Spec 2 (disclaimer) / Spec 4 (flag ramp) — 위험 낮, 의존성 0
- **Q-S1 해제 후 즉시**: Spec 1 (NPS, 일부 의존) / Spec 3 (onboarding) / Spec 5 (retention)
- **보류 (변호사 답 + 추가 검증)**: 후보 2 / 3 / 5 / 8
- **모든 자율 기능 공통 원칙**: 게이트 통과 안 하면 발송 X, 사고 1건이면 즉시 OFF, CEO 일일 audit 5min
