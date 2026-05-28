# PivoxQuant 자동화 갭 분석
> 작성: 2026-05-28 / 운영부 / 기준: Railway APScheduler 실측 + 메모리 실측

---

## Phase 1 — 일일 운영 task 인벤토리

| Task | CEO 직접 여부 | 현재 자동화 | 갭 | 시간(분/일) |
|---|---|---|---|---|
| 모닝 브리프 KPI 확인 | O | 50% (Slack 전송 자동, 확인은 CEO) | CEO가 Slack 열어서 읽어야 함 | 5 |
| Sentry 에러 스캔 | O | 50% (캡처 자동, 리뷰는 CEO) | 에러 없을 때도 열어봐야 함 | 5 |
| 변호사 큐 상태 확인 | O | 50% (weekly packet 자동, 판단은 CEO) | Q 항목별 상태 변경이 수동 | 5 |
| 유저 문의 응대 | O | 0% (Gmail 수신만 자동) | 분류/초안/발송 전부 수동 | 10~30 |
| 카페/인스타 포스팅 | O | 0% | 주제 선정/작성/발행 전부 수동 | 30~60 |
| autopilot_log 리뷰 | O | 100% (자율 기록) | 없음 — 읽기만 하면 됨 | 3 |
| SHIP_BLOCKERS 확인 | O | 50% (daily_ship 자동 생성) | 판단/우선순위 수동 | 5 |
| 배포 (railway up) | O | 0% | CEO 직접 실행 필수 (OAuth 브라우저) | 10 |

**총 일일 CEO 수동 시간 추정: 43~123분** (문의 없는 날 기준 ~50분)

---

## Phase 2 — 주간 운영 task

| Task | 자동화 상태 | 비고 |
|---|---|---|
| weekly_memo (일 08:00) | 100% — APScheduler | 이미 박힘 |
| weekly_funnel_snapshot (월 09:30) | 100% — APScheduler | 이미 박힘 |
| finance_weekly_check (일 09:00) | 100% — APScheduler | 이미 박힘 |
| lawyer_packet_weekly (일 21:00) | 100% — APScheduler | 이미 박힘 |
| 메모리 정리 (memory/*.md 갱신) | 0% — CEO 수동 | 에이전트가 append하나 최종 정리는 CEO |
| 카페 글 작성 | 0% — CEO 수동 | 주제 선정~발행 전부 수동 |
| 인스타/Threads 포스팅 | 0% — CEO 수동 | API 미연동 |
| 통신판매업 진행 확인 | 0% — CEO 수동 | Q8 변호사 답변 후 착수 가능 |

---

## Phase 3 — 월간 운영 task

| Task | 자동화 상태 | 비고 |
|---|---|---|
| brag_card 생성 | 유저 트리거 | 자동 생성 |
| burn_rate 리포트 | 100% — APScheduler monthly | 이미 박힘 |
| commerce_registration_reminder | 100% — APScheduler | 이미 박힘 |
| domain_expiry 알림 | 100% — APScheduler | 이미 박힘 |
| 세무 처리 | 0% — CEO 수동 | 매출 0원 구간이라 기록만; 첫 매출 후 변화 |
| 변호사 미팅 예약 | 0% — CEO 수동 | 핀테크 상담소 직접 예약 필요 |
| 광고 예산 편성 | 0% — CEO 수동 | 현재 0원 정책이라 실질 없음 |
| 월간 규제 스캔 | 부분 (section101 daily) | 전체 규제 변화 스캔은 수동 |

---

## Phase 4 — 자동화 갭 매트릭스 (상위 10개, 시간 절약 큰 순)

| # | Task | 빈도 | 현재 자동화 | 갭 | 해소 방법 | 절약(분/주) |
|---|---|---|---|---|---|---|
| 1 | 유저 문의 초안 작성 | 수시 | 0% | 수신~응답 전체 수동 | `ops_inbox_triage` — Gmail API + Claude 초안 생성 | 60~120 |
| 2 | 카페/SNS 포스팅 큐 | 주 2~3회 | 0% | 주제 선정~발행 수동 | `ops_marketing_calendar` — 주제 자동 생성 + CEO 승인 1클릭 | 60~90 |
| 3 | KPI 대시보드 1장 요약 | 매일 | 50% (Slack) | Slack 열어야 함, 집계 항목 제한적 | `ops_kpi_dashboard` — 매일 09:00 signup/activation/churn 집계 | 10 |
| 4 | 경쟁사 가격/기능 모니터링 | 매주 | 0% | 수동 서핑 필요 | `ops_competitor_scan` — 토요일 WebFetch + diff | 30 |
| 5 | 유저 피드백 감정 분석 | 주간 | 0% | 카페/이메일 개별 읽기 수동 | `ops_user_feedback_digest` — 카페 크롤 + Claude 분류 | 30 |
| 6 | 법규 변화 스캔 | 월간 | 0% (수동) | `regulatory_changes` 수동 업데이트 | `ops_regulatory_scan` — WebFetch FSC/FSS 공고 + diff | 20 |
| 7 | 메모리 파일 정기 정리 | 주간 | 30% (에이전트 append) | CEO가 최종 merge/정리 | `ops_memory_consolidate` — 주간 중복 제거 + archive | 15 |
| 8 | SHIP_BLOCKERS 우선순위 정렬 | 매일 | 50% (daily_ship 생성) | 판단/우선순위 수동 | `ops_blocker_triage` — severity 자동 분류 | 10 |
| 9 | 배포 상태 체크 (Vercel canary) | 매 30분 | 100% — APScheduler | 없음 (완전 자동) | 유지 | 0 |
| 10 | 변호사 큐 상태 집계 | 주간 | 50% (packet 자동) | 개별 Q 상태 변경 수동 | `ops_legal_queue_tracker` — Q별 status 자동 업데이트 | 10 |

**주간 절약 가능 총합: 235~325분 (약 4~5시간)**

---

## Phase 5 — 다음 Sprint 자동화 후보 5개 (0원, 구상 단계)

### 1. `ops_inbox_triage` — 이메일 수신 자동 분류
- **목적**: ImprovMX를 통해 들어오는 이메일을 (유저문의 / 법무 / 결제 / 스팸)으로 자동 분류하고 Claude가 초안 생성, CEO는 승인만
- **의존성**: Gmail API (무료) + Claude API (Max 요금제 내 사용) + ImprovMX 기존 설정
- **비용**: 0원
- **우선순위**: 1위 — 유저 수 증가 시 응대 부하 직격

### 2. `ops_kpi_dashboard` — 매일 09:00 KPI 1장 집계
- **목적**: DB에서 signup/activation(첫 포트폴리오 추가)/churn(30일 미접속) 자동 집계 → Slack 1장
- **의존성**: Railway PostgreSQL 기존 연결 + `ops_morning_brief_kpi` 확장
- **비용**: 0원 (APScheduler 기존 잡 확장)
- **우선순위**: 2위 — 모닝 브리프와 합산해 단일 Slack 메시지로 통합 가능

### 3. `ops_competitor_scan` — 매주 토요일 경쟁사 모니터링
- **목적**: 토스증권/뱅크샐러드/크레파스솔루션 등 경쟁 서비스 가격페이지 + 공지 WebFetch → 변화 감지 시 CEO Slack 알림
- **의존성**: WebFetch (무료) + APScheduler 기존 인프라
- **비용**: 0원
- **우선순위**: 3위 — 출시 후 가격 경쟁 대응 속도 확보

### 4. `ops_user_feedback_digest` — 주간 피드백 감정 분석
- **목적**: 네이버 카페 + 이메일 문의 텍스트 → Claude 감정 분류(긍정/부정/건의) + 반복 패턴 상위 3개 요약 → 주간 Slack
- **의존성**: 카페 RSS 또는 크롤 (공개 게시판) + Claude API
- **비용**: 0원 (Max 요금제 내)
- **우선순위**: 4위 — 유저 목소리를 제품 개선으로 빠르게 연결

### 5. `ops_marketing_calendar` — SNS 포스팅 큐 관리
- **목적**: 주간 시장 이벤트(FOMC/실적 시즌/KOSPI 특이점) 기반 카페/Threads 포스팅 주제 3개 자동 생성 → CEO 선택만
- **의존성**: Claude API + APScheduler 금요일 실행
- **비용**: 0원
- **우선순위**: 5위 — 콘텐츠 마케팅 일관성 확보

---

## 자동화 불가 영역 (CEO 직접 필수)

| Task | 이유 |
|---|---|
| `railway up` 배포 | OAuth 브라우저 인증 필요 |
| 변호사 미팅 예약 | 대인 협상 |
| 통신판매업 신고 | 정부기관 대면/온라인 본인인증 |
| 세무 처리 | 본인 인증 + 세무사 상담 |
| Vercel env 변경 | REST API 가능하나 보안상 CEO 직접 권고 |
| 신규 법규 최종 판단 | 법적 책임은 CEO에게 귀속 |

---

## 현재 APScheduler 잡 전체 목록 (57 → 실측 28개 활성)

| job_id | 스케줄 | 목적 |
|---|---|---|
| ops_api_health | 매 6시간 | Railway + 헬스 체크 |
| ops_db_backup | 매일 02:00 | PostgreSQL 덤프 |
| ops_ssl_expiry | 월 09:00 | TLS 만료 경고 |
| ops_vercel_canary | 매 30분 | Vercel 배포 상태 |
| ops_daily_regression | 매일 06:00 | pytest 회귀 |
| ops_sendgrid_quota | 매일 14:00 | SendGrid 한도 |
| ops_morning_brief_kpi | 매일 06:05 | KPI Slack |
| ops_signup_funnel | 매 5분 | 가입 전환율 |
| ops_credentials_expiry | 매일 10:00 | API 키 만료 |
| ops_env_audit | 월 11:00 | .env 감사 |
| ops_error_rate | 매 5분 | 500 에러율 |
| ops_ticker_name_audit | 매일 06:30 | naked ticker 회귀 |
| ops_email_compliance | 월 12:00 | §50 준수 |
| ops_section101_check | 매일 07:00 | §101 4-req 확인 |
| ops_checkout_followup | 매 15분 | 결제 이탈 follow-up |
| ops_email_scheduler | 매 15분(+1) | 이메일 발송 큐 |
| ops_inactive_nudge | 매 시간 | 비활성 유저 알림 |
| ops_caus_daily_sweep | 매일 03:00 | 코드 자율 sweep |
| ops_finance_weekly_check | 일 09:00 | 주간 재무 |
| ops_fx_staleness_check | 매 시간 | FX 데이터 신선도 |
| ops_anthropic_cost_estimate | 매일 22:00 | 토큰 비용 추정 |
| ops_railway_resource | 매 2분 | Railway 리소스 |
| ops_domain_expiry | 1일 09:30 | 도메인 만료 |
| ops_commerce_registration | 1일 09:00 | 통신판매업 리마인더 |
| ops_oauth_failure_check | 매 15분 | OAuth 실패 감지 |
| ops_pipa_purge | 매일 03:30 | PIPA 데이터 정리 |
| ops_weekly_funnel_snapshot | 월 09:30 | 유입 퍼널 주간 |
| ops_marketing_daily_dispatch | 매일 08:00 | 마케팅 발송 |
| ops_ship_blockers_daily | 매일 06:00 | SHIP_BLOCKERS 갱신 |
| ops_data_integrity_sweep | 매일 04:00 | 데이터 정합성 |
| ops_lawyer_packet_weekly | 일 21:00 | 변호사 패킷 |

---

## 결론 — CEO 30분 루틴으로 달성 가능 조건

현재 시스템은 **자동화 60~70% 수준**이다. 나머지 30~40%(문의 응대 / SNS 포스팅 / 배포)는 구조적으로 CEO가 필요하거나 다음 sprint에서 자동화 가능하다.

다음 sprint 5개 잡(`ops_inbox_triage`, `ops_kpi_dashboard`, `ops_competitor_scan`, `ops_user_feedback_digest`, `ops_marketing_calendar`) 구현 시 **자동화 80~85%** 달성 예상. CEO 일일 운영 시간 **50분 → 15~20분** 단축 가능.
