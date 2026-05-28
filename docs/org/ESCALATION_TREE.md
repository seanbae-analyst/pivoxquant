# PivoxQuant Escalation Tree
버전: v56-M3 | 기준일: 2026-05-28

---

## Branch 정의

| Branch | 기호 | CEO 개입 | 트리거 |
|--------|------|---------|--------|
| A | 🟢 자율 처리 | 없음 또는 24h batch | agent 즉시 처리 → autopilot_log 자동 기록 |
| B | 🟡 자율 처리 + CEO review queue | 24h 이내 OK/Defer/Drop | CEO 응답 없으면 자동 진행 |
| C | 🔴 즉시 escalation | CEO 즉시 푸시 알림 (Slack) | agent 처리 중단, CEO 응답 전까지 의존 시스템 대기 |

**Branch C 발동 시 자동 조치:**
- autopilot_log에 `BLOCKED: <상황번호>` 기록
- CEO Slack 채널 `#escalation` 즉시 메시지
- 의존 agent 작업 큐 일시 정지
- 24h 후 자동 reminder (응답 없으면 재전송 1회)

---

## 28 상황 Escalation 매트릭스

### TIER 1 — 자동 감지 가능 (cron / hook / Sentry)

| # | 상황 | 빈도 | 영향 | 감지 agent | 처리 agent | Branch | CEO 시한 |
|---|------|------|------|-----------|-----------|--------|---------|
| 1 | cron job 3-strike fail (emit_failure) | 주 0-2회 | P1 | scheduler / observability | scheduler.pause_job → bug-hunter 자동 fix | A | 24h batch |
| 2 | PG 커넥션 부족 (FATAL: too many clients) | 월 0-1회 | P0 | devops health-check | devops: pool 설정 PR 생성 → CEO 배포 | C | 즉시 |
| 3 | 5xx error rate > 5% (Sentry alert) | 월 0-3회 | P0 | Sentry / observability | engineering: 원인 분석 → fix PR 생성 | B | morning-briefing |
| 4 | KIS API 429 (rate limit) | 주 0-5회 | P1 | integrations | integrations: 자동 backoff 전환, 다음 window 대기 | A | 24h batch |
| 5 | FX rate 24h+ stale | 주 0-1회 | P1 | data-pipeline | data-pipeline: 수동 fetch 재시도 → 실패 시 stale 표시 | A | 24h batch |
| 6 | Sentry critical error (새 패턴) | 월 0-5회 | P1 | Sentry | investigate-bug → engineering fix PR | B | morning-briefing |
| 7 | SendGrid 100/day 도달 | 일 0-1회 | P1 | email-infra | email-infra: Brevo fallback 자동 전환 | A | 24h batch |
| 8 | Anthropic credit 80% 소진 | 월 0-1회 | P1 | finance-monitor | finance-monitor: 알림 생성 → CEO review | B | morning-briefing |
| 9 | CC Max token 80% (일일) | 일 0-1회 | P2 | agent-ops | agent-ops: 저우선 작업 연기, 압축 모드 전환 | A | 24h batch |
| 10 | PIPA 30일 hard-delete 실패 | 월 0-1회 | P0 법규 | compliance-evidence | compliance-evidence: 실패 기록 → 즉시 escalation | C | 즉시 |
| 11 | 베타 비번 secret leak (pre-commit guard) | 발생 시 | P0 보안 | git-hook (pre-commit) | git-hook: commit 자동 BLOCK → CEO 알림 | C | 즉시 |
| 12 | alembic head divergence | 배포 전 | P1 | migration-guard | migration-guard: BLOCK 신호 → engineering 수동 해결 | B | morning-briefing |
| 13 | 신규 결제 분쟁 (Stripe webhook) | 발생 시 | P0 법규/재무 | payment-handler | CEO 직접 처리 (agent 처리 금지) | C | 즉시 |
| 14 | cron 5분 timeout | 주 0-3회 | P1 | scheduler | scheduler: task kill → 재스케줄 → autopilot_log 기록 | A | 24h batch |
| 15 | cache poisoning suspect (user_id 누락) | 발생 시 | P0 보안 | security-monitor | security-monitor: 캐시 flush 즉시 실행 → CEO 알림 | C | 즉시 |

### TIER 2 — 외부 입력 발생

| # | 상황 | 빈도 | 영향 | 감지 agent | 처리 agent | Branch | CEO 시한 |
|---|------|------|------|-----------|-----------|--------|---------|
| 16 | 변호사 답변 수령 (legal_question_queue.md) | 월 0-2회 | P0 법규 | regulatory-monitor (이메일 감지) | legal-kr-fintech: 검수 요약 → CEO 판단 | C | 즉시 |
| 17 | 사용자 문의 (이메일 / 카페 댓글) | 주 0-10회 | P2 | customer-support | customer-support: 초안 응답 작성 → CEO 검토 후 발송 | B | 24h 이내 |
| 18 | 통신판매업 신고 완료 | 1회성 | P1 법규 | regulatory-monitor | legal-kr-fintech: business_registration.md 업데이트 | B | morning-briefing |
| 19 | 사업자등록 update (정보 변경) | 연 0-1회 | P1 법규 | regulatory-monitor | CEO 직접 처리 → legal-kr-fintech 기록 | C | 즉시 |
| 20 | 광고 집행 결과 (메타/인스타 CPC) | 주 1회 | P2 | growth-monitor | growth-monitor: KPI 업데이트 → 주간 batch | B | 일요일 21:00 |
| 21 | 카페 글 댓글 (커뮤니티 응답 필요) | 주 0-5회 | P2 | community-monitor | community-monitor: 응답 초안 → CEO 검토 후 발행 | B | 24h 이내 |
| 22 | 규제 변화 (regulatory_monitor cron 감지) | 분기 1-3건 | 건별 판단 | regulatory-monitor | legal-kr-fintech: 변화 요약 + 영향 분석 → CEO 판단 | C | 즉시 (HIGH) / B (MEDIUM/LOW) |
| 23 | 경쟁사 가격 변동 | 월 0-2회 | P2 | market-intel | market-intel: 가격 비교표 업데이트 → 주간 batch | B | 일요일 21:00 |

### TIER 3 — CEO 발상 (인바운드 요청)

| # | 상황 | 빈도 | 영향 | 처리 agent | Branch | CEO 시한 |
|---|------|------|------|-----------|--------|---------|
| 24 | 신규 기능 결정 | 월 0-3회 | P1 | engineering: 구현 계획 작성 → CEO 승인 후 실행 | C | CEO 발의 |
| 25 | 가격 변경 | 분기 0-1회 | P0 | finance + legal-kr-fintech: 영향 분석 → CEO 결정 | C | CEO 결정 |
| 26 | 마케팅 카피 변경 | 월 0-5회 | P1 | marketing + legal-kr-fintech: §101/뒷광고 검토 → CEO 승인 | C | CEO 결정 |
| 27 | 디자인 변경 | 월 0-5회 | P2 | design: v3 토큰 내 변경 자율 / 브랜드 정체성 변경은 CEO | A (마이너) / C (브랜드) | 건별 |
| 28 | 비즈니스 모델 pivot | 연 0-1회 | P0 | 전체 부서 분석 → CEO 단독 결정 | C | CEO 발의 |

---

## Branch 판단 기준 요약

```
롤백 가능?
  └─ NO  → C
  └─ YES →
      법률/결제/보안/prod DB 직접?
        └─ YES → C
        └─ NO  →
            외부 공개 영향?
              └─ YES → B
              └─ NO  →
                  금전 비용 발생?
                    └─ YES → B
                    └─ NO  → A
```

---

## Kill Switch 통합

v54 Kill Switch 8종 (K1-K8) + v55 K9-K11 발동 시 → **모든 Branch를 즉시 C로 격상.**

| Kill Switch | 발동 조건 | 자동 조치 |
|-------------|----------|----------|
| K1 법규 위반 감지 | regulatory-monitor 신호 | 전체 agent 정지 + CEO 즉시 escalation |
| K2 데이터 침해 | security-monitor 신호 | 외부 연결 차단 + CEO 즉시 escalation |
| K3 Stripe 결제 오류 | payment-handler 신호 | 결제 모듈 비활성 + CEO 즉시 escalation |
| K4 Railway prod DB 직접 손상 | migration-guard 신호 | 배포 롤백 시도 + CEO 즉시 escalation |
| K5 Anthropic credit 소진 | finance-monitor 신호 | AI 기능 graceful degradation + CEO |
| K6 CEO 명시 정지 명령 | CEO 직접 입력 | 전체 agent 즉시 정지 |
| K7 연속 P0 3건 (24h 내) | observability 집계 | 자율 모드 일시 정지 + CEO |
| K8 법원/규제기관 조치 수령 | CEO 또는 legal 감지 | 전체 정지 + 변호사 즉시 연락 |
| K9 PG 커넥션 풀 100% 소진 | devops | prod 읽기 전용 전환 + CEO |
| K10 OAuth 전체 실패 (0/6) | devops health | 신규 가입 차단 + CEO |
| K11 alembic heads 3개+ 동시 이탈 | migration-guard | 배포 BLOCK + CEO |

**Kill Switch 발동 후 복구 절차:**
1. CEO 원인 확인 + 승인
2. 영향 범위 제한 (격리)
3. 롤백 또는 fix 적용
4. CEO 최종 승인 후 agent 재활성

---

## 자율 권한 위임 강도 Ramp

### Stage 정의

| Stage | 시점 | A% | B% | C% | 진입 조건 |
|-------|------|----|----|----|---------|
| A (현재) | 2026-05 ~ | 30% | 30% | 40% | 초기 기본값 |
| B | Stage A + 3개월 | 50% | 30% | 20% | 조건 1-4 모두 충족 |
| C | Stage B + 3개월 | 70% | 20% | 10% | 조건 5-7 모두 충족 |
| D | Stage C + 6개월 | 85% | 10% | 5% | 조건 8-10 모두 충족 |

### Stage 진입 조건

**Stage B 진입 (A → B):**
1. Stage A에서 Branch A 처리 건 중 6주 연속 P0/P1 회귀 0건
2. CEO morning-briefing 검수 6주 × 5일 = 30회 연속 "이상 없음" 확인
3. Kill Switch 발동 이력 0건 (Stage A 기간 중)
4. PIPA 30일 hard-delete 자동화 검증 통과 (2회 연속)

**Stage C 진입 (B → C):**
5. Stage B에서 자율 처리 건 중 12주 연속 P0 회귀 0건
6. 변호사 자문 큐 P0 그룹 (Q5/Q6/Q7/Q8/Q13/Q-S1) 전부 해소
7. 유료 전환 사용자 50명 이상 (실제 사용 데이터 기반 검증)

**Stage D 진입 (C → D):**
8. Stage C에서 6개월 연속 법규 위반 0건
9. MRR ₩500만 달성 (Kill Switch D+180 조건 회피)
10. CEO 명시적 Stage D 승인 (서면 또는 Slack 기록)

### Stage 강등 조건 (자동)

- P0 사고 1건 → 한 단계 강등
- Kill Switch 발동 → Stage A 리셋
- CEO 명시 강등 명령 → 즉시 적용

---

## 28 상황 × agent 전체 매핑 요약

| # | 상황 | 감지 agent | 처리 agent | Branch | CEO 시한 |
|---|------|-----------|-----------|--------|---------|
| 1 | cron 3-strike fail | scheduler | scheduler + bug-hunter | A | 24h batch |
| 2 | PG 커넥션 부족 | devops | devops PR → CEO 배포 | C | 즉시 |
| 3 | 5xx > 5% | Sentry/observability | engineering fix PR | B | morning-briefing |
| 4 | KIS API 429 | integrations | integrations backoff | A | 24h batch |
| 5 | FX 24h+ stale | data-pipeline | data-pipeline 재시도 | A | 24h batch |
| 6 | Sentry critical (신규) | Sentry | investigate-bug → engineering | B | morning-briefing |
| 7 | SendGrid 100/day | email-infra | email-infra Brevo 전환 | A | 24h batch |
| 8 | Anthropic credit 80% | finance-monitor | finance-monitor 알림 | B | morning-briefing |
| 9 | CC Max 80% | agent-ops | agent-ops 저우선 연기 | A | 24h batch |
| 10 | PIPA hard-delete 실패 | compliance-evidence | compliance-evidence → escalation | C | 즉시 |
| 11 | secret leak | git-hook | git-hook BLOCK | C | 즉시 |
| 12 | alembic divergence | migration-guard | migration-guard BLOCK → engineering | B | morning-briefing |
| 13 | Stripe 결제 분쟁 | payment-handler | CEO 직접 | C | 즉시 |
| 14 | cron 5min timeout | scheduler | scheduler 재스케줄 | A | 24h batch |
| 15 | cache poisoning | security-monitor | security-monitor flush + CEO | C | 즉시 |
| 16 | 변호사 답변 수령 | regulatory-monitor | legal-kr-fintech 검수 | C | 즉시 |
| 17 | 사용자 문의 | customer-support | customer-support 초안 | B | 24h 이내 |
| 18 | 통신판매업 신고 완료 | regulatory-monitor | legal-kr-fintech 기록 | B | morning-briefing |
| 19 | 사업자등록 update | regulatory-monitor | CEO 직접 | C | 즉시 |
| 20 | 광고 집행 결과 | growth-monitor | growth-monitor KPI | B | 일요일 21:00 |
| 21 | 카페 댓글 | community-monitor | community-monitor 초안 | B | 24h 이내 |
| 22 | 규제 변화 HIGH | regulatory-monitor | legal-kr-fintech | C | 즉시 |
| 22 | 규제 변화 MEDIUM/LOW | regulatory-monitor | legal-kr-fintech | B | 주간 batch |
| 23 | 경쟁사 가격 변동 | market-intel | market-intel 비교표 | B | 일요일 21:00 |
| 24 | 신규 기능 결정 | CEO 발의 | engineering 계획 | C | CEO 발의 |
| 25 | 가격 변경 | CEO 발의 | finance + legal | C | CEO 결정 |
| 26 | 마케팅 카피 변경 | CEO 발의 | marketing + legal | C | CEO 결정 |
| 27 | 디자인 변경 (마이너) | CEO 발의 | design (v3 내) | A | 24h batch |
| 27 | 디자인 변경 (브랜드) | CEO 발의 | design → CEO 승인 | C | CEO 결정 |
| 28 | 비즈니스 모델 pivot | CEO 발의 | 전 부서 분석 | C | CEO 발의 |
