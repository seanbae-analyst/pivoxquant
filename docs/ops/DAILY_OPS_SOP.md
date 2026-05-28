# PivoxQuant 일일 운영 SOP
> 작성: 2026-05-28 / 운영부 / 갱신 주기: 분기

1인 창업자 CEO가 **하루 30분** 안에 서비스 전체를 파악·결정하는 루틴.
Railway APScheduler(57 cron job)가 대부분 자동화되어 있으므로, CEO는 "결과 확인 + 의사결정"만 한다.

---

## 일일 루틴 (30분, 매일 아침)

### 06:27 — 모닝 브리프 확인 (5분)
- Railway `ops_morning_brief_kpi` (06:05 KST)가 Slack에 KPI 요약 전송.
- CEO 확인 항목:
  - 신규 가입자 수 (목표: D+30 까지 누적 100)
  - 에러율 < 1% (Sentry 대시보드 링크 포함)
  - API health 상태 (pivoxquant.com/api/health 200 여부)
- 이상 없으면 통과. 이상 있으면 → 인프라부 에이전트 세션 열어 조사.

### 06:30 — Sentry 에러 스캔 (5분)
- sentry.io → pivoxquant project → Issues → Last 24h
- P0 기준: `500 Internal Server Error` / `UndefinedColumn` / `OAuth` 관련 exception
- P0 발견 시: Railway 로그 → 에이전트 세션 → 핫픽스 커밋 → railway up
- P1/P2: SHIP_BLOCKERS.md에 추가, 다음 sweep 대상

### 06:35 — 변호사 큐 상태 확인 (5분)
- `legal_question_queue.md` P0 그룹(Q5/Q6/Q7/Q8/Q13/Q-S1/Q-S3/Q-S4) 미결 여부 체크
- 핀테크 상담소 무료 자문 1.5h 예약 진행 상황 확인
- Q-S3(월구독 §101 충돌) 미해결 = 유료 결제 출시 BLOCKER

### 06:40 — 유저 피드백 확인 (5분)
- 이메일(seanbae1521@gmail.com) 신규 문의 확인 (ImprovMX → Gmail 수신)
- 네이버 카페 댓글/DM 확인
- 피드백은 `customer_feedback.md`에 추가, 반복 패턴은 제품 이슈로 전환

### 06:45 — 간단 결정 (10분)
- 오늘 배포/커밋이 있는가 → railway up 여부 결정
- 새 마케팅 포스팅 필요한가 → 카페/인스타 예약
- 에이전트 위임 작업 결과 확인 (autopilot_log.md 신규 항목)

---

## 주간 루틴 (매주 일요일 저녁, 30분)

### 일요일 21:00 — 변호사 패킷 확인 (10분)
- `ops_lawyer_packet_weekly` (21:00 KST) 자동 생성된 변호사 패킷 확인
- 신규 Q 항목 없으면 통과. 신규 규제 변화 있으면 `regulatory_changes_2026-05.md` 업데이트

### 일요일 09:00 — 주간 재무 체크 (10분)
- `ops_finance_weekly_check` 자동 실행 결과 확인
- burn_rate: Railway($5/mo) + 도메인($1.65/mo) = $6.65/mo 예산 vs 실제 지출
- Claude Code Max 토큰 사용량 확인 (finance_token_ops.md)

### 월요일 09:30 — 유입 퍼널 스냅샷 (10분)
- `ops_weekly_funnel_snapshot` 자동 실행 결과 확인
- 가입 → 활성 → 유료 전환율 주간 추이
- 이상 하락 시: 원인 분석 에이전트 세션 열기

---

## 월간 루틴 (매월 1일, 45분)

### 매월 1일 09:00 — 도메인/상거래 리마인더 확인 (5분)
- `ops_commerce_registration` / `ops_domain_expiry` 자동 알림 확인
- 통신판매업 신고 진행 상황 점검 (Q8 변호사 답변 수령 후 진행)

### 매월 1일 — 소각률(burn rate) 리포트 (10분)
- APScheduler `monthly_finance` 자동 생성 리포트 확인
- 예산 100만원 기준 누적 소진 % 확인
- 광고 예산(0원 정책) 유지 여부 판단

### 매월 — 세무 처리 (15분)
- 부가가치세: 사업자 인별합산 과세표준 확인
- 소득세: 수입금액 기록 유지 (수입 발생 시점부터)
- 현재 매출 0원 단계는 기록만; 첫 유료 전환 후 세무사 상담 검토

### 매월 — 마케팅 캘린더 (15분)
- 다음달 카페/인스타/Threads 주요 포스팅 주제 3개 선정
- 시장 이벤트(실적 시즌/FOMC/KOSPI 특이점) 캘린더 반영

---

## CEO 부재 시 큐잉 메커니즘

| 상황 | 시스템 동작 | CEO 복귀 후 |
|---|---|---|
| 일반 자동화 실패 | APScheduler `emit_failure` → Slack 알림 누적 | autopilot_log.md 확인 후 판단 |
| P0 에러 (500/DB crash) | Sentry 실시간 캡처, Railway 자동 재시작 | Sentry 이슈 + Railway 로그 확인 |
| 유저 문의 수신 | ImprovMX → Gmail 보관 | 복귀 후 24h 이내 응답 |
| 변호사 큐 신규 발생 | weekly packet에 자동 포함 | 패킷 확인 후 처리 |
| 배포 필요 (railway up) | 자동 배포 불가 — CEO 직접 필요 | `railway up --service 8687c9ac` |

**핵심 원칙**: 시스템이 큐잉한 것은 쌓이지만 망하지는 않는다. CEO 복귀 시 autopilot_log.md → Sentry → Gmail 순서로 트리아지.

---

## 긴급 대응 체크리스트 (장애 시)

1. `/api/health` 직접 curl — 200이면 앱 살아있음
2. Railway 로그: `railway logs --service 8687c9ac` (recent 50줄)
3. Sentry: 최근 exception 시간대 + stack trace
4. DB 연결 문제 시: Railway Postgres 재시작 (대시보드 → Restart)
5. 해결 불가 시: `SHIP_BLOCKERS.md`에 기록 + 에이전트 세션 위임

---

## 중요 링크 모음

| 대상 | URL/명령 |
|---|---|
| Railway 대시보드 | railway.app → vibrant-blessing |
| Sentry | sentry.io → pivoxquant |
| Vercel | vercel.com → pivoxquant |
| 백엔드 health | https://pivoxquant.com/api/health |
| Railway 로그 | `railway logs` |
| HANDOVER | /Users/seanbae/dev/pivoxquant/HANDOVER.md |
| autopilot log | 메모리 → autopilot_log.md |
