# PivoxQuant SHIP_BLOCKERS.md

**SoT**: 자율 운영 시스템 외부 액션 + 변호사 큐 + 메모리 carry-over 통합 매트릭스.
**갱신 정책**: 매일 06:27 morning-briefing이 prepend 형태로 노출. 항목 변경 시 PR로 갱신.
**최근 갱신**: 2026-06-01 09:52 KST (ship_blockers_audit 자동 — RELEASE-BLOCKER 6건 / SHIP-AT-RISK 11건 / POST-LAUNCH 15건 / 변호사 큐 21건)

상태 코드: BLOCKED(외부 대기) / IN_PROGRESS / PENDING(미착수) / RESOLVED

---

## 🟥 RELEASE-BLOCKER (출시 전 해결 필수)

| # | 항목 | 카테고리 | Owner | ETA | 해제조건 | 상태 |
|---|---|---|---|---|---|---|
| R1 | 변호사 일괄 의견서 Q1-Q15 + Q-S1/S3/S4 + Q-M1/M2/M3 (총 21건) | legal | CEO + 변호사 | 미정 (CEO 미팅 예약 전) | 금융규제·자본시장법 전문 변호사 사인. 예상 300-500만원 1회 의견서 | BLOCKED |
| R2 | Q-S1 정통망법 §50 분리 동의 framework 답변 | legal | 변호사 | 미정 | 환영 메일 + onboarding nudge + retention 메일 (B/C 분류) 발송 가능 여부 사인 | BLOCKED |
| R3 | 통신판매업 신고 (성동구청, 등록세 ~45,000원) | legal | CEO | 미정 | 신고 완료 → `PIVOX_COMMERCE_REGISTERED=true` 전환, Stripe Live 활성 가능 | PENDING |
| R4 | Stripe 유료결제 활성화 (require_business_registration 게이트) | billing | CEO | R3 + R1 후 | R3 신고 완료 + R1 Q-S3 (§101 ②월구독 충돌) 사인 | BLOCKED |
| R5 | terms-ko.md "변호사 검토 대기 중" 표기 제거 | legal | CEO | R1 후 | 변호사 사인 후 표기 제거 | BLOCKED |
| R6 | privacy-ko.md "변호사 검토 대기 중" 표기 제거 | legal | CEO | R1 후 | 변호사 사인 후 표기 제거 | BLOCKED |

**출처**:
- R1: `legal_question_queue.md:9-148` (21건 누적, 2026-05-28 Q-S4 추가)
- R2: `legal_question_queue.md:40-65` (Wave D Sub-wave 2 BLOCKER, C-S1/S5/S2/R1/AC1 이메일 4종 OFF)
- R3: `business_registration.md:36` + `legal_question_queue.md:67-97` (Q-S3 §101 ② 상호작용 회색지대)
- R4: `MEMORY.md` Brand 섹션 + `session_2026-05-28.md:60` carry-over
- R5/R6: `autopilot_log.md:98` "Privacy-ko.md 변호사 검토 대기 중 — CEO must remove after lawyer review"

---

## 🟧 SHIP-AT-RISK (출시 가능하나 운영 리스크 큼)

| # | 항목 | 카테고리 | Owner | ETA | 해제조건 | 상태 |
|---|---|---|---|---|---|---|
| A1 | DNS MX 레코드 미설정 (ImprovMX 수신) | email | CEO | 미정 (15분 작업) | 가비아 콘솔에서 `MX @ mail.improvmx.com 10` + ImprovMX alias 4개(noreply/support/legal/billing) | PENDING |
| A2 | Brevo fallback API key 미설정 | email | CEO | 미정 | Brevo 가입 + API key 발급 → Vercel env `BREVO_API_KEY` / `BREVO_FROM_EMAIL` / `BREVO_FROM_NAME` 입력 | PENDING |
| A3 | SENDGRID_WEBHOOK_PUBLIC_KEY 미설정 (이벤트 추적 OFF) | email | CEO | 미정 | SendGrid Event Webhook 서명 키 입력 → `/api/webhooks/sendgrid` 503 해제. 발송과 무관, 추적만 OFF | PENDING |
| A4 | `~/.pivoxquant-env` 8개 변수 미입력 (랩탑 cron RETIRED 후 가치 낮음) | env | CEO | 미정 | SLACK_WEBHOOK_URL / DATABASE_URL / GPG_PASSPHRASE / SENDGRID_API_KEY / SENTRY_AUTH_TOKEN / SENTRY_ORG_SLUG / SENTRY_PROJECT_SLUG / STRIPE_SECRET_KEY | PENDING |
| A5 | Slack webhook URL 미설정 (모든 alert silent) | env | CEO | 미정 | Slack incoming webhook 발급 → Railway env `SLACK_WEBHOOK_URL` + `~/.pivoxquant-env` | PENDING |
| A6 | Naver News API key 미설정 (`.KS` News empty) | data | CEO | 미정 | Naver Developers 등록 → Railway env 입력 | PENDING |
| A7 | Vercel 사업자정보 footer env 6개 미입력 (전자상거래법 §13) | env | CEO | 미정 | Vercel env: NEXT_PUBLIC_BUSINESS_REGISTRATION_NUMBER / _NAME / _REPRESENTATIVE / _ADDRESS / _TYPE | PENDING |
| A8 | 로컬 14 commit + 이전 carry-over push 안 됨 (canonical=~/dev/pivoxquant) | infra | CEO | 미정 | CEO 별도 세션에서 reconcile 후 push (feedback_push_workflow 규칙) | BLOCKED |
| A9 | Anthropic 크레딧 0 → 챗봇 LLM OFF, FAQ 즉답만 작동 | infra | CEO | 미정 | 크레딧 충전 시 `SUPPORT_CHAT_LLM_ENABLED=1` 전환. 미충전 시 FAQ 검색만 (0원 운영) | PENDING |
| A10 | VAPID env 미설정 (push 알림 OFF) | env | CEO | 미정 | Vercel env VAPID 키쌍 입력 | PENDING |
| A11 | 변호사 미팅 자료 준비 (사업자등록증 PDF, terms/privacy, regulatory 자료, Q-S1 KISA 가이드) | legal | CEO | R1 전 | 자료 패킷 완성 → 변호사 컨택 (`session_2026-05-18-v45.md` 컨택 가이드 488줄 + 첨부 4 PDF 완성) | IN_PROGRESS |

**출처**:
- A1: `project_email_infra.md:28` "ImprovMX 수신(MX 레코드 + alias) 미설정"
- A2: `project_email_infra.md:140-161` Brevo 설정 + `session_2026-05-28.md:40` "Brevo 키 부재"
- A3: `project_email_infra.md:18` "SENDGRID_WEBHOOK_PUBLIC_KEY 단 하나 누락"
- A4: `project_automation_v2.md:118-129, 143-149` 8개 env 변수 carry-over
- A5: `project_automation_v2.md:121` SLACK_WEBHOOK_URL carry-over
- A6: `autopilot_log.md:99` "Naver News API key Railway env var missing"
- A7: `business_registration.md:37-43` Vercel env 6개 footer
- A8: `session_2026-05-28.md:14, 60` "push 안 함" + `session_2026-05-26.md:38, 41` push reconcile carry-over
- A9: `session_2026-05-26.md:41` "Anthropic 크레딧 충전 시 SUPPORT_CHAT_LLM_ENABLED=1"
- A10: `MEMORY.md` v49.1/.2 "VAPID env 근본수정" + `session_2026-05-22-v49.md:24` "VAPID env 미설정(CEO Vercel)"
- A11: `legal_question_queue.md:171-183` CEO 액션 + `MEMORY.md` v45 컨택 가이드

---

## 🟨 POST-LAUNCH (출시 후 처리 가능)

| # | 항목 | 카테고리 | Owner | ETA | 해제조건 | 상태 |
|---|---|---|---|---|---|---|
| P1 | NPS baseline 수집 (분석 시스템 가동) | data | agent | 출시 +30일 | 가입자 ≥50 후 첫 NPS 설문 | PENDING |
| P2 | PIPA §28-8 국외이전 신고 (SendGrid + Stripe + Vercel + Railway + Anthropic 미국 이전) | regulatory | CEO + 변호사 | R1 사인 후 | 변호사 사인 → 신고서 제출 | BLOCKED |
| P3 | 세무 고문 계약 (월 ~100,000원, 6월부터 권고) | finance | CEO | 출시 후 | 세무사 컨택 | PENDING |
| P4 | 법인카드 발급 | finance | CEO | 출시 후 | 은행 신청 | PENDING |
| P5 | 출시 +7일 후: `PIVOX_FUNNEL_ALERT_MODE=alert` + `PIVOX_ERROR_RATE_MODE=alert` 전환 (warn-only → enforce) | env | CEO | 출시 +7일 | Railway env 토글 | PENDING |
| P6 | 출시 +7일 후: `PIVOX_H4_MODE=enforce` + `PIVOX_H9_MODE=enforce` 전환 | env | CEO | 출시 +7일 | Railway env 토글 | PENDING |
| P7 | 정통망법 §50 시행령 재스캔 (매출 6% 과징금 + 야간 22-08 시간대 별도 동의 + 2년 주기 재확인 자동화) | regulatory | agent | 2026-08-15 | 시행령 공포 후 6개월 추적, 재스캔 자동 | PENDING |
| P8 | DMARC 정책 `p=none` → `p=quarantine` 검토 | email | CEO | 출시 +30일 | 모니터링 리포트 검토 후 강제 모드 전환 | PENDING |
| P9 | Q-S4 영문 레짐 신호 (engine.py "avoid new longs"/"momentum favors longs") KR/EN 비대칭 정리 | legal | 변호사 → agent | R1 후 | 변호사 사인 후 (a) engine.py 영문 중립화 or (b) legal_filter 영문 패턴 추가 or (c) 현 구조 유지 결정 | BLOCKED |
| P10 | persona 이중 매핑 (PDF taxonomy vs 피어 코호트 taxonomy) blind 통합 검토 | data | persona-quant-domain agent | 출시 후 | 도메인 판단 필요 (의도적 별개 가능성) | PENDING |
| P11 | DEFERRED 기존 carry-over: regime Sharpe rf / VARCHAR(10) / email_category flag / SSE Vercel proxy / agent_worker | infra | agent | 출시 후 | 개별 도메인 판단 | PENDING |
| P12 | DEFERRED owner 판단 항목: 알림 prefs 6 event wiring / past_due 강등 정책 / refund 부분환불 §17 / DCA XIRR / backtester lookahead / Composer synthetic backtest / KR 52w KIS range / SSE 테스트 인프라 / worktree 20 locked | infra | agent + CEO | 출시 후 | 개별 결정 | PENDING |
| P13 | merry-abundance Railway 프로젝트 정체불명 (과금 방지 삭제 검토) | infra | CEO | 미정 | 웹 대시보드에서 사용 여부 확인 후 삭제 | PENDING |
| P14 | 구 `~/Desktop/취준/pivoxquant` (11G) Finder 휴지통 삭제 (iCloud 동기화 위험 회피 완료) | infra | CEO | 미정 | canonical=~/dev/pivoxquant 안정 확인 후 삭제 | PENDING |
| P15 | section101 fix prod 배포 (랩탑 working tree만, in-container 스케줄러 미적용) | regulatory | CEO | A8 push 시 동시 | push → Railway auto-deploy 시 자동 반영 | PENDING |

**출처**:
- P1: `analytics_metrics.md` (메모리 인덱스)
- P2: `legal_question_queue.md:18-21` Q6 cross_border + `project_email_infra.md:265-266`
- P3/P4: `business_registration.md:44-45`
- P5/P6: `project_automation_v2.md:147-149`
- P7: `legal_question_queue.md:161-165` Q12 정통망법 §50 시행령 추적
- P8: `project_email_infra.md:105` "출시 후 p=quarantine 검토"
- P9: `legal_question_queue.md:142-147` Q-S4 + `session_2026-05-28.md:55`
- P10: `session_2026-05-28.md:50` DEFERRED persona-quant-domain
- P11: `session_2026-05-24.md:80` 기존 carry-over
- P12: `session_2026-05-22-v49.md:42` DEFERRED owner 판단 + `MEMORY.md` v49~v51
- P13: `session_2026-05-27.md:16` merry-abundance 정체불명
- P14: `session_2026-05-26.md:41` 구 Desktop 11G 삭제
- P15: `project_automation_v2.md:31` "미배포: fix는 로컬 working tree만"

---

## 부록 — RESOLVED (참고용, 최근 해결)

| # | 항목 | 해결 일자 | 출처 |
|---|---|---|---|
| ✅ | BETA_PASSWORD rotate 영구 해결 (`<BETA_PASSWORD>` 평문 고정값 + Vercel REST API, literal은 MEMORY.md/Vercel env 만) | 2026-05-26 | `MEMORY.md` Brand 섹션 |
| ✅ | OAuth provisioning_failed P0 hotfix (alembic 035 prod 미적용 → _do_migrations runtime ADD COLUMN) | 2026-05-17 v44.7 | `MEMORY.md` |
| ✅ | Railway PG too-many-clients (pool 3/2 + self-heal 가드 7개) | 2026-05-20 v46 | `MEMORY.md` Brand 섹션 |
| ✅ | SendGrid Domain Authentication 완료 (SPF+DKIM+DMARC) | 2026-05-20 | `project_email_infra.md:23-27` |
| ✅ | PDF 이메일 END-TO-END 실발송 검증 (admin diag 엔드포인트) | 2026-05-20 v46.2 | `project_email_infra.md:10-12` |
| ✅ | Sentry prod ingest 라이브 확정 (event id be776584 검증) | 2026-05-26 | `project_automation_v2.md:33-37` |
| ✅ | Vercel V2 플래그 9개 모두 true (LOGIN/SIGNUP/HOME/PORTFOLIO/SIGNALS/REPORTS/RISK/SETTINGS/PROFILE) | 2026-05-20 v45.8 | `autopilot_log.md:31` |
| ✅ | section101 §101 요건3 prod BLIND 버그 fix (artifacts.content → data_json) | 2026-05-26 | `project_automation_v2.md:27-31` (로컬만, prod 배포는 P15) |
| ✅ | 사업자등록 발급 (459-01-03808, 피복스퀀트(PivoxQuant)) | 2026-05-08 | `business_registration.md` |
| ✅ | i18n 한글화 (온보딩 + 컴포넌트 + 페르소나 8종) | 2026-05-28 | `session_2026-05-28.md:26` commit 3198edc1+2cd797d4 |

---

## 운영 메모

- **CEO만 가능한 작업**: 변호사 컨택 / DNS 가비아 콘솔 / Vercel env 입력 / 신고서 제출 / 결제 활성화 / push reconcile (canonical=~/dev/pivoxquant)
- **agent 가능**: 코드 변경 / 테스트 작성 / 메모리 갱신 / 외부 액션 진행 시 follow-up 자동 수행
- **본 매트릭스 갱신 트리거**: (a) 매일 06:27 morning-briefing prepend (b) CEO/변호사 답변 수령 시 즉시 (c) prod env 변경 시 즉시
- **신규 BLOCKER 발견 시**: 본 파일 PR로 갱신, 추측·날조 항목 절대 금지 — 메모리 file:line 출처 인용 필수
