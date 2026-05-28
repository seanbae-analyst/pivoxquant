# PivoxQuant Decision Batching Policy
버전: v56-M3 | 기준일: 2026-05-28

---

## 개요

CEO 판단이 필요한 사항을 **무작위 즉흥 요청 없이** 정해진 시간대에 일괄 처리한다.
CEO 루틴: 일일 2분 / 주간 15분 / 월간 30분 / 분기 변호사 미팅.

---

## Batch 시간대 4계층

### 1. 일일 Batch — 06:27 morning-briefing

**대상:** Branch B 항목 중 24h 이내 처리 필요 / Branch A 결과 요약

**CEO 소요 시간:** 1-2분 (모바일)

**포함 항목:**
- 전날 자율 처리(A) 결과 요약 (autopilot_log 자동 파싱)
- Branch B 항목 중 24h 이내 OK/Defer/Drop 필요한 항목
- P0/P1 알림이 있었을 경우 상태 업데이트
- 오늘 예정 cron 작업 목록

**CEO 응답 방식:**
- OK: 자동 진행
- Defer: 다음 morning-briefing으로 이월
- Drop: 항목 폐기 + autopilot_log 기록

**24h 무응답 처리:** Branch B 기본값 = 자동 진행 (단, 법규/결제 항목은 자동 진행 불가, 48h 후 재escalation)

---

### 2. 주간 Batch — 일요일 21:00 weekly_packet

**대상:** Branch B 항목 중 긴급하지 않은 외부 입력 / 운영 최적화 제안

**CEO 소요 시간:** 15분

**포함 항목:**
- 광고 집행 결과 + 다음 주 예산 조정 제안 (growth-monitor)
- 경쟁사 가격 변동 요약 (market-intel)
- 커뮤니티 응답 초안 검토 대기 건 (community-monitor)
- 주간 KPI 대비 실적 (growth + finance)
- 다음 주 agent 우선순위 제안 (agent-ops)

**일요일 21:00 선택 이유:** 월요일 업무 준비 직전, 주중 가장 방해 없는 시간대

---

### 3. 월간 Batch — 매월 1일 09:00 monthly_finance

**대상:** 재무 검토 / 인프라 비용 / 중기 의사결정

**CEO 소요 시간:** 30분

**포함 항목:**
- 월간 MRR / 유료 전환율 / 이탈률 (finance)
- 인프라 실비용 (Railway + Vercel + API 비용 합산)
- Anthropic credit 소진율 + 예상 소진 시점
- 이달 Branch C 발동 건 복기 (escalation 품질 리뷰)
- 자율 위임 Stage 진입 조건 달성률 체크
- Kill Switch 발동 이력 요약

---

### 4. 분기 Batch — 변호사 미팅 시점

**대상:** 법규 해소 + 약관 / 처리방침 업데이트

**CEO 소요 시간:** 1.5h (핀테크 상담소 무료 자문 활용)

**포함 항목:**
- legal_question_queue.md 미해소 P0 전체 (Q5/Q6/Q7/Q8/Q13/Q-S1/Q-S3/Q-S4)
- 신규 regulatory_changes 건 중 법률 해석 필요 항목
- 이용약관 / 개인정보처리방침 초안 검토
- PIPA §28-8 국외이전 고지 문구 확정

---

## CEO 응답 프로토콜

### OK (승인)
- 즉시 자동 진행
- autopilot_log에 `CEO_APPROVED: <항목 ID> <타임스탬프>` 기록

### Defer (다음 batch로 이월)
- 이월 횟수 추적 (3회 이월 시 자동 Branch C 격상)
- 이월 사유 기록 권고 (없어도 무방)

### Drop (폐기)
- autopilot_log에 `CEO_DROPPED: <항목 ID>` 기록
- 동일 유형 항목 향후 Branch A 강등 가능성 검토

### 무응답 (24h 경과)
- Branch B 일반 항목: 자동 진행
- Branch B 법규/결제/외부 공개 항목: 자동 진행 불가 → 48h 재escalation → 72h에 Branch C 격상

---

## Inbox 구조 (morning-briefing 표시 형식)

```
[2026-05-29 06:27 morning-briefing]

## 어제 자율 처리 (Branch A) — 확인만
- [A-4] KIS API 429 → backoff 전환 완료 (03:14)
- [A-7] SendGrid 100/day → Brevo 자동 전환 (18:42)
- [A-14] cron timeout 2건 → 재스케줄 완료

## 검토 필요 (Branch B) — OK/Defer/Drop
- [B-6] Sentry critical: TypeError in /api/signals (엔지니어링 fix PR #142 대기) → OK/Defer/Drop
- [B-17] 사용자 문의: "KRX 데이터 오류 신고" 응답 초안 준비됨 → OK/Defer/Drop
- [B-12] alembic divergence: 041/042 head 충돌, migration-guard BLOCK 중 → OK(해제)/Drop

## 오늘 예정 작업
- 09:00 weekly_data_fetch (KIS)
- 12:00 pdf_generation_batch
- 18:00 PIPA_hard_delete_check
```

---

## agent별 Batch 귀속 규칙

| agent | 기본 보고 시점 | 예외 |
|-------|-------------|------|
| scheduler | 06:27 daily | 3-strike fail 즉시 |
| devops | 06:27 daily | PG 100% / K10 즉시 |
| integrations | 06:27 daily | prod API 키 변경 → C |
| growth-monitor | 일요일 21:00 | KPI 급락(>30%) → B |
| market-intel | 일요일 21:00 | 없음 |
| community-monitor | 24h rolling | 법적 언급 댓글 → C |
| customer-support | 24h rolling | 결제/환불 요청 → C |
| legal-kr-fintech | 즉시 (C 전용) | 없음 |
| finance-monitor | 월 1일 09:00 | credit 95%+ → 즉시 |
| regulatory-monitor | 분기 or 즉시 | HIGH 건 즉시 |
| security-monitor | 즉시 (C 전용) | 없음 |
| compliance-evidence | 즉시 (C 전용) | 없음 |

---

## Batch 운영 자동화 전제 조건

현재 자동화 수준 (2026-05-28 기준):

| 기능 | 현황 | 비고 |
|------|------|------|
| 06:27 morning-briefing cron | 설정됨 (crontab 16개 중 포함) | autopilot_log 파싱 별도 구현 필요 |
| Slack push 알림 (Branch C) | 미구현 | Branch C webhook 연결 필요 (0원 Slack 무료 플랜) |
| CEO OK/Defer/Drop 인터페이스 | 미구현 | 이메일 reply-to 또는 Slack reaction |
| 주간 weekly_packet | 설정됨 | |
| 월간 monthly_finance | 설정됨 | |

**P0 미구현: Slack Branch C 알림.** 현재 Branch C 발동 시 CEO 모바일 알림 수단 없음.
임시 대안: morning-briefing에 `[C] BLOCKED` 항목 포함 → CEO 다음날 인지 (24h 지연 감수).

---

## delegation-audit hook 연동 (v56 UserPromptSubmit)

CEO가 prompt 입력 시 → UserPromptSubmit hook에서 자동 분류:

```
1. 입력 분석: 키워드 추출 (법률/결제/보안/신규기능/디자인/운영)
2. 상황 번호 매핑: 28개 상황 매트릭스 조회
3. Branch 자동 태그: [A] [B] [C]
4. Branch C 미명시 상황에서 C 판단 시 → CEO에게 1회 확인
   "이 요청은 Branch C (즉시 escalation) 항목으로 분류됩니다. 계속하시겠습니까?"
5. CEO 확인 후 적절한 agent 위임
```

**규칙:**
- 분류 1회 오류 허용 → 2회 연속 오류 시 해당 키워드 패턴 Branch C 고정
- AskUserQuestion 금지 (feedback_no_askuserquestion.md) → 확인은 인라인 텍스트로만
- 확인 없이 자율 분류로 처리 가능한 경우 즉시 위임
