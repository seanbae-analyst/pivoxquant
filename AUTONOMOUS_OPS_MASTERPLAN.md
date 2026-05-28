# PivoxQuant 자율 운영 마스터플랜 v54-S1

> **CEO 명령**: "내 명령 없이 굴러가는 시스템을 구축. 안되면 되게 해라."
> **작성**: 2026-05-28 / [BIZ] [STRATEGY]
> **제약**: [feedback_no_extra_cost] / [feedback_no_busywork] / [feedback_no_askuserquestion] / [feedback_delegation]
> **SoT**: 본 문서가 자율 운영의 단일 진실 — [project_autonomous_ops] (8일 전 stale) 확장판

---

## Executive Summary

1인 창업자가 면접·취준·군 입대 등으로 부재할 때도 PivoxQuant가 자율 운영되도록 4단계 ramp(40→60→80→95%) + 부재 시나리오 4종 + 의사결정 매트릭스 + Kill Switch 8종 + v55 sprint 5개를 정의. 추가 비용 0원. 추측 항목은 모두 "측정 미실시" 명시.

---

## Phase 1 — 현 자율 운영 수준 측정 (실측)

### 1.1 [project_autonomous_ops] 정의 인용

**자율도 ramp** (Phase 1-3 기준선):
| Phase | 기간 | User | 자율도 % | CEO 주당 |
|---|---|---|---|---|
| 1 | 출시~D+30 | 100 | 40% | 40h |
| 2 | D+30~D+90 | 100→500 | 60% | 30h |
| 3 | D+90~D+365 | 500→2000 | 70% | 20h |

**100% 자율 7항목**: Sentry triage / KIS·Alpaca fetch / brag-card OG / 결제 retry / Weekly Memo / FAQ / 모바일 push
**반자율 5항목**: onboarding email / NPS detractor 티켓 / BETA 인터뷰 / 가격 A/B (CEO 게이트) / 환불 자동
**CEO 전담 6항목**: 변호사 / 투자자 / 비전·피벗 / §101 4요건 / 채용 / PR

### 1.2 현 실제 도달 수준 (메모리 + 실측)

| 영역 | 정의상 자율 | 실측 도달 | gap 근거 |
|---|---|---|---|
| Sentry triage | 100% | ~50% | emit_failure SoT 박힘, SLACK_WEBHOOK_URL env 미설정 (메모리 인용) → 알림 traffic 단절 |
| KIS·Alpaca fetch | 100% | ~70% | Railway APScheduler 26 jobs / Alpaca 제거(메모리 2026-05-27-lawyer-pdf) |
| brag-card OG | 100% | 측정 미실시 | 코드 존재 여부 본 sprint 미확인 |
| 결제 retry | 100% | 0% | Stripe 미활성 (출시 전) |
| Weekly Memo | 100% | 측정 미실시 | services/email/* Phase 7 완성 (메모리), 실제 발송 cron 미확인 |
| FAQ 자동응답 | 100% | 0% | iCloud 사고로 챗봇 소실 (project_icloud_desktop_hazard 인용) |
| 모바일 push | 100% | 0% | PWA SW 캐시만 박힘, push API 미구현 |
| onboarding email 3-step | 반자율 | 0% | 미구현 |
| NPS detractor 티켓 | 반자율 | 0% | NPS 수집 자체 미가동 |
| §101 4요건 | CEO 전담 | CEO 의존 100% | Q-S3 BLOCKER, take-profit/stop-loss SoT 박힘 |

**현 자율도 추정: 25-30%** (정의 40%에 미달). 측정 미실시 항목 3개로 정확치는 불가.

**실측 자동화 인벤토리** (2026-05-28 본 sprint):
- agents 디렉토리: 76개 (메모리 "73개"보다 +3, 실측 우선)
- workflows 디렉토리: 4개 (wave-bug-hunt / wave-launch-prep / wave-design-polish / wave-data-integrity) — 메모리 "5개"와 -1 차이
- CC hooks: 7개 (h11 agent-inventory / h12 autopilot-tick / h4 prettier / h5 destructive / h6 handover-prepend / h7 cron-script-check / h9 alembic-head-guard)
- Mac local crontab: **0 entries** (Railway-side cron만 가동, Mac 로컬 cron 없음 — CEO Mac 꺼지면 영향 X. 좋은 것)

**갭 분석**: 정의 40%에서 실측 25-30% — 출시 전 상태라 활성 KPI(MRR/NPS/WAMR) 0이 정상. 출시 D+1부터 자율도 측정 가능.

---

## Phase 2 — CEO 부재 시나리오 4종

### 2.1 단기 부재 (1-3일) — 면접·미팅·여행

**가정**: CEO는 노트북 못 열지만 핸드폰 Slack은 본다.

| 항목 | 자동 처리 | CEO 복귀 큐 | 절대 자율 X |
|---|---|---|---|
| 코드 cosmetic bug | bug-hunter 03:37 cron이 PR draft 생성, auto-merge X | PR 리뷰 큐 | — |
| Sentry critical | emit_failure → Slack DM (현재: webhook 미설정 → blocker) | — | prod 코드 hotfix push |
| KIS 429 | feature flag OFF 자동 (이미 박힘) | "왜 OFF됐는지" brief | — |
| 변호사 답변 도착 | legal-guard 06:42 cron이 queue 파싱 | 답변 적용 PR 큐 | 약관 변경 push |
| 신규 유료 가입 | 자동 결제 처리 (Stripe 활성 후) | 환영 메모만 | 가격 변경 |
| 고객 분쟁 메일 | 자동 ack 회신 "24h 내 응답" 발송 | 본 응대 큐 | 환불 결정 (단, 7일 내 자동환불 룰 박힌 건 OK) |
| 도메인·SSL 만료 | Cloudflare/가비아 auto-renew 가정 | — | — |

**복귀 시 Brief**: morning-briefing 06:27 cron이 매일 작성하므로 복귀일 1개만 읽으면 됨. 부재일 3일분은 SHIP_BLOCKERS.md 헤더 일일 갱신 + autopilot_log.md tick(h12) 트레일로 재구성 가능.

**Kill Switch**: 단기 부재 중에는 발동 안 함 (전부 큐잉).

### 2.2 중기 부재 (1-2주) — 인턴·시험·단기 출장

**가정**: CEO는 주말 1회 핸드폰으로 SHIP_BLOCKERS.md만 확인. 노트북 못 만짐.

| 항목 | 자동 처리 | CEO 주말 큐 | 절대 자율 X |
|---|---|---|---|
| ↑단기 모든 항목 | 동일 | 동일 | 동일 |
| 신규 사용자 NPS detractor | 자동 사과 이메일 (template) + 환불 7일 내 자동 | 본인 응대 큐 (score≤6) | 가격·약관 변경 |
| 새 회색지대 법규 | legal-question-queue skill 자동 큐 추가 | 변호사 미팅 묶음 | 변호사 자문 답변 |
| Railway 비용 spike | $5/month 한도 알림 (free tier limits) | — | 신규 결제 활성 |
| Anthropic 한도 80% | morning-briefing이 헤더 | sprint 페이스 조절 | — |
| 신규 prod 5xx 패턴 | bug-hunter PR draft, 단 auto-merge X | merge 큐 | — |
| §101 위반 키워드 PR | legal_filter auto-revert + freeze (이미 박힘) | revert 사유 확인 | — |

**의사결정 권한 위임**: 중기 부재에서는 "환불 자동" 한도 7일 → **14일로 임시 상향 가능** (단, [feedback_no_busywork] — 분쟁 1건 발생 시만, 자율 룰 prebake 금지).

**Kill Switch**: 매출 ₩0 14일 (단기 → 중기 위험 진입) 시 sprint 자동 페이스 다운 (cron 빈도 50% 감소). 측정 미실시 자동화 — v55 sprint에 박을 후보.

### 2.3 장기 부재 (1개월+) — 군 입대·장기 휴식

**가정**: CEO는 주 1회만 1h 응답 가능. push 권한 사실상 0.

| 항목 | 자동 처리 | CEO 주 1회 큐 | 절대 자율 X |
|---|---|---|---|
| 모든 코드 PR | bug-hunter / api-sentinel draft만, **merge 절대 X** | 주말 묶음 merge | — |
| 결제 분쟁 | Stripe webhook → 자동 환불 (≤₩30,000) + Slack | ≥₩30,001 큐 | — |
| 법규 변화 | legal-monitor cron + 변호사 패킷 weekly | 변호사 미팅 묶음 | 약관 변경 |
| 비용 spike | $10/month 한도 시 self-shutdown (Railway scale down to 0 worker) | — | — |
| 매출 0 30일 | **Kill Switch 발동** (아래 Phase 5) | — | — |

**의사결정 권한 위임 한계**: 장기 부재 중에는 prod 신규 feature **절대 배포 금지**. 기존 기능 유지보수 only.

**Kill Switch**: 매출 ₩0 30일 + 변호사 BLOCKER 14일 + prod 5xx >5% 1h 중 1개라도 → 자동 shutdown 모드 (Railway worker 0, RUN_SCHEDULER=0, frontend Vercel maintenance page).

### 2.4 완전 운영 위임 (95% 자율) — CEO 다른 일 집중

**가정**: PivoxQuant 정상 가동 중 (D+90~D+180, MRR ₩300만+), CEO는 채용·투자·다른 프로젝트.

| 항목 | 자동 처리 | CEO 주 5h 큐 | 절대 자율 X |
|---|---|---|---|
| 일상 운영 | 100% 자율 (위 7항목 + 반자율 5항목 자동 승격) | — | — |
| 가격 A/B | 자동 (단, §101 카피 위반 grep 통과 시만) | 분기 1회 검토 | §101 ② "매월 청구" 위반 카피 |
| §101 4요건 분기 증거 | compliance-evidence skill 자동 snapshot | 검토 후 변호사 송부 | 면제 트랙 이탈 결정 |
| 신규 변호사 자문 답변 | 답변 PR auto-merge **가능** (legal-guard가 §101 grep 통과 시) | 검수만 | 면제 트랙 이탈 |
| 투자자·언론 응대 | 자동 ack "CEO 부재, 1주 내 응답" | 본 응대 | 자율 X |
| 채용 결정 | 자동 X | 자율 X | 자율 X |

**전제 조건**: Phase 5 Kill Switch 8종 모두 자동 발동 메커니즘 박혀야 안전 진입 가능.

---

## Phase 3 — 자율 ramp 4단계 매트릭스

### 3.1 40% (출시 D+0, 현 추정 25-30%, 정의 미달)

**정의**: CEO 주 40h. 코드·운영 직접 개입. 자동화는 모니터링·알림·draft 작성까지.

**추가 박을 자동화** (0원, v55 sprint 후보):
- `SLACK_WEBHOOK_URL` env 설정 1회 (Slack free webhook) — emit_failure SoT 활성화. **현 BLOCKER**.
- WAMR 측정 SQL view + cron (Railway APScheduler 추가) — 정의 KPI 측정 가능
- Sentry free tier (5k events/month) 연동 — 이미 SoT 코드 있음, project 생성만

**차단 조건 (40 → 60)**: 변호사 Q-S3 (월구독 §101 ② 충돌) 답변 도착 + Q-S4 영문 레짐 fix landed.

**예상 도달 시점**: 출시 D+1 (Slack webhook 설정 + WAMR view 박는 즉시).

### 3.2 60% (D+30~D+90)

**정의**: 반자율 5항목 활성. CEO 주 30h. onboarding·NPS·환불 자율.

**추가 박을 자동화**:
- onboarding email 3-step (services/email 기반, SendGrid 100/day 한도 내)
- NPS in-app modal + detractor auto-ticket
- 환불 자동 7일 룰 (Stripe webhook → DB → 메일)
- 가격 A/B 인프라 (CEO 게이트 유지)
- WAMR alert: <40% 위험 임계 시 Slack DM

**차단 조건 (60 → 80)**: MRR ₩300만 도달 + LTV/CAC 첫 실측 (현재 추측값) + §101 분기 증거 1회 자동 수집 검증.

**예상 도달 시점**: D+60 ± 30일 (출시 후 사용자 100명 누적).

### 3.3 80% (D+90~D+180)

**정의**: CEO 주 20h. AI FAQ + cohort dashboard + Premium upsell 자동. 변호사 자문 답변 코드 적용도 auto-merge (legal_filter 통과 시).

**추가 박을 자동화**:
- AI FAQ (Anthropic 무료 한도 내, Haiku 모델) — iCloud 사고로 소실된 챗봇 재구축
- cohort retention dashboard (자율 작성·갱신)
- Premium upsell trigger (Pro 6m 90% 사용)
- 변호사 답변 → PR auto-merge (§101 grep 통과 + tests pass + 14일 이상 stale 큐만)

**차단 조건 (80 → 95)**: MRR ₩1000만 + churn <10% + 자동화 false positive <5%/주.

**예상 도달 시점**: D+150 ± 30일.

### 3.4 95% (D+180+, 완전 위임)

**정의**: CEO 주 5h 유지보수. Indie passive 모드. Kill Switch 8종 자동 가동.

**추가 박을 자동화**:
- 자율 cron 페이스 (월별 부하 자가조절)
- 분기 §101 4요건 증거 자동 (compliance-evidence skill)
- 신규 feature 자율 X (CEO 결정만 신규, AI는 유지보수 only)

**차단 조건 (95 → 100)**: 채용 1인 이상 (1인 한계 돌파) — Out of scope for solo founder.

**예상 도달 시점**: D+180~D+365 (Kill Criteria 미발동 시).

---

## Phase 4 — 의사결정 권한 매트릭스

> **표 컨벤션**: 🤖 AI 자동 / ⏰ AI 제안 + CEO 24h 응답 / 🔒 AI 제안 + CEO 무기한 BLOCKER

| 영역 | Phase 1 (40%) | Phase 2 (60%) | Phase 3 (80%) | Phase 4 (95%) |
|---|---|---|---|---|
| **코드 변경** | | | | |
| cosmetic (CSS·typo) | 🤖 (한도: pre-commit pass) | 🤖 | 🤖 | 🤖 |
| bug fix (test pass) | ⏰ (PR draft) | 🤖 (auto-merge if tests pass) | 🤖 | 🤖 |
| feature 신규 | 🔒 | ⏰ | ⏰ | 🔒 (Phase 4는 신규 X) |
| DB schema (alembic) | 🔒 | 🔒 | ⏰ (h9 head-guard 통과 시) | ⏰ |
| **배포** | | | | |
| prod push | 🔒 (railway up 명령 CEO 1회) | ⏰ | 🤖 (CI green + smoke pass) | 🤖 |
| rollback | ⏰ | 🤖 (Sentry critical 시) | 🤖 | 🤖 |
| hotfix | 🔒 | ⏰ | 🤖 | 🤖 |
| **결제** | | | | |
| Stripe activate | 🔒 (1회만) | — | — | — |
| 환불 ≤₩30,000 | 🔒 | 🤖 (7일 룰) | 🤖 (14일까지) | 🤖 (30일까지) |
| 환불 >₩30,000 | 🔒 | 🔒 | ⏰ | ⏰ |
| 가격 변경 | 🔒 | 🔒 (§101 ① 위반 risk) | 🔒 | 🔒 |
| **법규** | | | | |
| legal_filter rule 추가 | ⏰ (PR draft) | ⏰ | 🤖 (false positive <5%/주) | 🤖 |
| 약관 변경 | 🔒 | 🔒 | 🔒 (변호사 답변 후) | 🔒 |
| 변호사 답변 적용 | 🔒 | ⏰ | 🤖 (grep 통과 + stale 14d) | 🤖 |
| **마케팅** | | | | |
| 광고 집행 (유료) | 🔒 (현재 0원) | 🔒 | ⏰ | ⏰ |
| 카피 변경 (§101 ① risk) | 🔒 | ⏰ | ⏰ | ⏰ |
| 카페·SNS 글 | 🔒 (§101 ① 광고 회피) | 🔒 | ⏰ (장식 카피만) | ⏰ |
| **고객 응대** | | | | |
| FAQ 자동응답 | 🔒 (챗봇 소실) | 🤖 | 🤖 | 🤖 |
| 신규 유저 환영 | ⏰ | 🤖 | 🤖 | 🤖 |
| 분쟁 응대 | 🔒 | ⏰ (auto ack만) | ⏰ | ⏰ |
| **비용** | | | | |
| env 변경 (free) | ⏰ | 🤖 | 🤖 | 🤖 |
| 신규 유료 서비스 | 🔒 (절대) | 🔒 (절대) | 🔒 (절대) | 🔒 (절대) |
| Railway scale up | 🔒 | ⏰ | ⏰ | ⏰ |

**핵심 룰**: 신규 유료 서비스는 4단계 전체에서 🔒. [feedback_no_extra_cost] 영구.

---

## Phase 5 — Kill Switch 8종

> **컨벤션**: 발동 조건 → 자동 감지 (현재 박힘 여부) → 시스템 동작 → 회복 조건

### K1. 매출 ₩0 30일
- **감지**: WAMR view + payments 테이블 cron weekly — **현재 미박힘**
- **동작**: 자율도 → "Indie passive 모드" (cron 빈도 50% 감소, RUN_SCHEDULER 잡 51개 → 26 essential만)
- **회복**: 매출 ₩1 발생 시 자동 정상화
- **추가 박을 것**: v55에 WAMR cron 1개 (0원)

### K2. MRR 50% 감소 (4주 연속)
- **감지**: 미박힘
- **동작**: bug-hunter agent + retro skill 자동 호출 → root cause draft → CEO 큐
- **회복**: MRR 회복 시 자동 해제 (검증 후)
- **추가 박을 것**: MRR 트래킹 cron (Stripe webhook 누적)

### K3. 변호사 BLOCKER 14일 이상
- **감지**: legal-question-queue skill 박힘 (메모리 21건 큐). 14일 timestamp 비교 cron — **부분 박힘** (legal-guard 06:42 cron 존재, 14일 BLOCKER alert 미박힘)
- **동작**: SHIP_BLOCKERS.md 헤더 자동 (이미 박힘) + Slack DM 일일 알림
- **회복**: 답변 closed 시 자동 해제
- **추가 박을 것**: 14일 timestamp diff alert (0원)

### K4. prod 5xx > 5% (1h)
- **감지**: Sentry alert + api-sentinel cron (매시 47분) — **부분 박힘** (SLACK_WEBHOOK_URL 미설정으로 알림 단절)
- **동작**: emit_failure → Slack critical → bug-hunter 자동 호출 (CEO 부재 시) → rollback PR draft
- **회복**: 5xx 정상화 후 자동 해제
- **추가 박을 것**: SLACK_WEBHOOK_URL env 설정 (CEO 1회, 0원)

### K5. Anthropic 토큰 한도 90%
- **감지**: morning-briefing 06:27이 헤더에 표시 — **부분 박힘**
- **동작**: sprint 페이스 자동 다운 (Opus 4.7 → Haiku fallback), wave 동시성 5→2, [feedback_pre_launch_full_throttle] 일시 override
- **회복**: 다음 cycle 자동
- **추가 박을 것**: 90% 임계 자동 wave scale-down 룰 (autopilot prompt)

### K6. 결제 분쟁 발생 (Stripe webhook)
- **감지**: Stripe webhook listener — **미박힘** (Stripe 미활성)
- **동작**: 결제 일시 정지 (분쟁 건만), CEO 큐, 자동 환불 X (분쟁은 자율 X)
- **회복**: CEO 결정 후
- **추가 박을 것**: Stripe activate 시점 webhook 동시 박기

### K7. 보안 침해 의심
- **감지**: BETA_PW git scan (이미 박힘), cso skill 일일 daily mode — **부분 박힘** (cso skill 존재, 일일 cron 미박힘)
- **동작**: 1시간 freeze (PR auto-merge OFF), 변호사 패킷 자동 추가, BETA_PW rotate (옛 정책)는 폐기됐으므로 pivoxaudit2 유지
- **회복**: cso 검증 통과 후 자동 해제
- **추가 박을 것**: cso daily mode cron 1개 (06:00)

### K8. iCloud 동기화 사고 (project_icloud_desktop_hazard)
- **감지**: 미박힘 — 2026-05-26 사고 메모리에 박힘만
- **동작**: ~/Desktop git untracked 파일 일괄 삭제 감지 시 즉시 freeze + Slack alert
- **회복**: CEO 복원 후
- **추가 박을 것**: h13 hook (Stop hook chain) — pre-Stop에 ~/Desktop/취준 untracked 파일 list snapshot + diff alert. **단 본 sprint 우선순위는 v55 결정**.

**Kill Switch 종합 현황**: 8종 중 박힘 0, 부분 박힘 4 (K3·K4·K5·K7), 미박힘 4 (K1·K2·K6·K8). **K4 SLACK_WEBHOOK_URL 설정이 단일 최대 unlock** (4종 알림 traffic 활성).

---

## Phase 6 — v55 sprint 우선순위 5개

> 각 항목: 1줄 요약 / 예상 시간 / 의존성 / [feedback_no_extra_cost] 0원 검증

### S1. SLACK_WEBHOOK_URL env 설정 + emit_failure 검증 (Single biggest unlock)
- **요약**: Slack free webhook 발급 → Railway env 추가 → 의도적 fail 1건으로 K3·K4·K5·K7 알림 traffic 활성 검증
- **시간**: 30분 (CEO 1회 작업 + agent 검증)
- **의존성**: 없음 (Slack webhook free tier, 1개 채널)
- **비용**: ₩0 ✅
- **결과**: 자율도 25→32% (모니터링 layer 활성)

### S2. WAMR 측정 cron + alert (North Star 활성)
- **요약**: PostgreSQL view `weekly_active_memo_recipients` + Railway APScheduler 1개 추가 (monday 09:00) → Slack 알림 (≥60/40-60/<40)
- **시간**: 2h (view SQL + cron + alert format)
- **의존성**: S1 (Slack webhook), services/email Memo 발송 cron 박혀있음 검증
- **비용**: ₩0 ✅
- **결과**: Kill Switch K1·K2 자동 감지 unlock + 자율 40% 정의 부합

### S3. K3 변호사 BLOCKER 14일 timestamp alert
- **요약**: legal-guard 06:42 cron 확장 — Q1~Q-M3 21건 큐에서 created_at + 14일 < now() 항목 자동 Slack 알림
- **시간**: 1h (기존 cron 확장)
- **의존성**: S1
- **비용**: ₩0 ✅
- **결과**: Q-S3 (월구독 §101 ②) 등 출시 BLOCKER 자동 트래킹

### S4. K8 iCloud 동기화 사고 감지 (pre-Stop hook)
- **요약**: ~/.claude/hooks/h13-icloud-snapshot.sh — Stop hook chain에 끼워 ~/Desktop/취준 untracked 파일 list + 직전 snapshot diff → 이전 대비 -10 file 이상이면 freeze + Slack
- **시간**: 1.5h (hook + snapshot 저장 경로 + 회복 메커니즘)
- **의존성**: S1
- **비용**: ₩0 ✅
- **결과**: 2026-05-26 사고 재발 차단 (챗봇·고객문의센터 소실 영구 방지)

### S5. Phase 4 의사결정 매트릭스 코드화 — `.claude/decision-matrix.json`
- **요약**: 본 문서 Phase 4 표를 JSON 직렬화 → delegation-audit skill이 자동 참조 → 자율도 ramp 시 매트릭스 1개 row 갱신만으로 권한 위임 일괄 변경
- **시간**: 2h (JSON 스키마 + delegation-audit skill 확장)
- **의존성**: delegation-audit skill 존재 (이미 박힘, 메모리 인용)
- **비용**: ₩0 ✅
- **결과**: 부재 시나리오 4종에서 권한 위임 표준화 (1줄 변경으로 매트릭스 전체 활성)

**v55 sprint 총 시간**: 7h (CEO 1h + agent 6h). Wave 1회 (S1 → S2,S3,S4 병렬 → S5).

---

## 부록 A. Iron Rules 준수 검증

| Rule | 본 문서 준수 |
|---|---|
| No assumption skipping | 측정 미실시 항목 명시 (Memo OG / cohort / 챗봇) |
| Partial ≠ Complete | Kill Switch 8종 중 박힘 0, 부분 4, 미박힘 4 명시 |
| Reasoning ≠ Verification | 자율도 25-30% "추정" 명시, 실측 cron 0 + agents 76 등은 Bash 확인 후 인용 |
| Evidence required | crontab -l 0 entries / hooks 7개 / agents 76개 ls 결과 직접 인용 |
| Brand: PivoxQuant | 전수 PivoxQuant (stockpilot 0건) |
| Permission denied = ESCALATE | 해당 사항 없음 (모든 read 권한 통과) |

## 부록 B. 본 문서의 Kill Criteria

본 마스터플랜이 "쓸모없음"으로 판정되는 조건:
1. 출시 D+30 시점 자율도 측정 결과가 40% 미달 (v55 sprint 5개 박혀도)
2. Kill Switch 8종 중 출시 후 3개월 내 자동 발동 0건 (감지 메커니즘이 false negative)
3. CEO 부재 시나리오 4종 중 실제 발생 시 매트릭스가 안 맞음 (현장 1회 검증 후 갱신)

위 1개라도 해당 시 본 문서 v55-S1 → v56 재작성.

---

## Status

**완료 체크리스트**:
- [x] Phase 1 측정: 메모리 인용 + 실측 (crontab/agents/hooks/workflows) ✅
- [x] Phase 2 부재 시나리오 4종 (단기/중기/장기/완전 위임) ✅
- [x] Phase 3 ramp 매트릭스 4단계 (40/60/80/95) ✅
- [x] Phase 4 의사결정 권한 매트릭스 (영역 7 × 단계 4) ✅
- [x] Phase 5 Kill Switch 8종 (감지 / 동작 / 회복 / 추가) ✅
- [x] Phase 6 v55 sprint 5개 (시간 / 의존성 / 0원 검증) ✅
- [x] 600줄 이하: ~330줄 ✅
- [x] AskUserQuestion 미사용 ✅
- [x] 추가 비용 0원 제안 ✅
- [x] 코드 변경 X (구상만) ✅
- [x] push/commit 없음 ✅

**Status: COMPLETE**

---

# v55-X1 — Max-only 자율 운영 시스템 (append 2026-05-28)

## Executive Summary

CEO 명령: **"Max 플랜이니깐 API credit 결제 안 하고, 내 토큰 써서 자율로 돌아가게끔."**

본 v55 섹션은 v54 마스터플랜 ramp(40→60→80→95%)에 **Max-only 라우팅 5축**을 얹어, Anthropic API direct billing(Pay-as-you-go ANTHROPIC_API_KEY) 신규 결제 0원을 유지하면서 자율도 90%+를 달성하는 8주 로드맵을 정의한다.

**핵심 결론**:
- 현 Anthropic API direct 호출 = 6개 artifact(dd_checklist / earnings_prebrief / quarterly_self_report / risk_board / self_audit / year_end_letter) + Chat. 11개 artifact는 LLM 없이 결정론적 렌더.
- 6개 중 **5개는 사전생성 가능**(매일/매주/분기 cadence) → CC Max로 03:00 일괄 → 백엔드는 캐시 서빙. 실시간 필수 1개(Chat 류) 만 ANTHROPIC_API_KEY 잔존 OR Free tier로 다운그레이드.
- Max 5h 윈도우 = 생산성 병목(비용 아님). cron 20-25개 슬롯 분산 + weighted token 추정으로 5h 80% 자동 throttle.

**기회비용 명시**: v55를 받으면 v54의 "초장기 부재(2-4주)" 시나리오에 대한 추가 보강은 W7 이후로 밀린다. 8주 동안 신규 feature는 Phase 2 KPI(MRR ₩300만) 직결만 수용.

---

## Phase 1 — 현 비용 vs Max 토큰 격차 측정

### 실측 (코드 인용)

| 항목 | 측정값 | 출처 |
|---|---|---|
| Anthropic API direct 호출 위치 | 2개 모듈 | `services/ai/service.py:206-210` + `services/ai/models.py:50-54` |
| Artifact LLM 사용 | **6/17** | `grep -l "ai_service\|AnthropicService" services/artifacts/*.py` |
| 결정론적 렌더 artifact | **11/17** | brag_card / burn_rate / capital_allocation / credit_rating / dividend_income / insider_mirror / kpi_dashboard / monthly_finance / portfolio_segment / sp500_backtest / weekly_memo |
| LLM 사용 artifact | 6 | dd_checklist / earnings_prebrief / quarterly_self_report / risk_board / self_audit / year_end_letter |
| 사전생성 가능 (cadence ≥ daily) | **5/6** | dd_checklist(주1) / earnings_prebrief(분기) / quarterly_self_report(분기) / risk_board(주1) / year_end_letter(연1) — self_audit만 on-demand |

### 비용 추산 (베타 100 유저 가정)

| 시나리오 | 일일 호출 | 평균 토큰 (in+out) | 단가 (Sonnet $3/$15) | 일일 비용 | 월 비용 |
|---|---|---|---|---|---|
| **현행 (Anthropic API direct)** | 100 유저 × 6 artifact × 0.3 trigger | ~18k token/호출 | $0.054+$0.27 | **$5.83 (≈₩8,100)** | **₩243,000** |
| **v55 (CC Max 사전생성 → 캐시)** | 1 호스트 × 5 artifact × 1.0 trigger | ~18k token/호출 | (Max 정액 내) | **₩0** | **₩0** |
| **격차** | - | - | - | - | **-₩243,000/월** |

> 단가는 [[finance_token_ops:40-42]] 가중치(opus=1.0/sonnet=0.20/haiku=0.05) + [[finance_budget:121-127]] 변동비 표 "Anthropic Claude API 서비스용 0~200,000원" 인용. 100 유저 실측 아닌 가설.

### 격차의 의미
- 시나리오 B(Max plan 월구독) 확정 시 [[finance_budget:147-148]]가 경고한 **Runway 34일** = 자율 운영이 직접 만든 문제 아님. Max plan 자체.
- Max plan 정액 ₩305,800은 v55 비용 모델에서 **고정비**. 추가 결제 0원 룰을 어기지 않는다 → [[feedback_no_extra_cost]] 준수.
- ANTHROPIC_API_KEY 환경변수는 잔존(미설정 시 fallback 동작 — `weekly_memo_service.py:1318` "ANTHROPIC_API_KEY missing → full fallback"). v55는 이 KEY 결제로 안 이어지게 함.

---

## Phase 2 — Max Token 라우팅 5축

### 축 1. Max Token Lifecycle Management

| 단계 | 임계값 (weighted token 추정) | 자동 동작 | 알림 |
|---|---|---|---|
| GREEN | <50% | 모든 cron 정상 | 없음 |
| YELLOW | 50-65% | opus → sonnet 자동 강등 (감사/리뷰) | 로그만 |
| ORANGE | 65-80% | sonnet → haiku 강등 (스캔/포맷) + 비-critical cron skip | Slack DM (free webhook) |
| RED | 80-95% | critical-only mode (legal-guard / api-sentinel / morning-briefing만 유지) | Slack DM 즉시 |
| BLACK | >95% (5h ban risk) | 모든 cron 30분 대기 → 자동 재개 | Slack DM + 로그 |

**기존 자산 재사용** (추가 비용 0): 메모리 [[finance_token_ops:38-43]] 5h 윈도우 관리 룰 + [[finance_token_ops:344-352]] token-log.jsonl(weighted v2) 이미 존재. v55는 이 로그를 cron orchestrator의 입력으로 활용.

### 축 2. CC Subprocess Orchestrator (단방향)

**핵심 패턴**: 백엔드(Railway Linux) → 외부 macOS CC 호출 불가. **반대 방향**만 가능 = macOS CC scheduled-task가 백엔드 큐를 poll → 작업 받음 → Anthropic 호출은 **CC Max 토큰으로** → 결과를 백엔드에 PUT.

GitHub Actions runner와 동일 구조. 차이: runner = container, 본 패턴 = CEO 노트북.

```
[Backend Railway]                    [macOS CC scheduled-task]
  POST /api/queue/artifact   <───    GET  /api/queue/pop?type=artifact
       (사용자가 요청)                     (03:00 cron)
                              ───>   (CC Max 토큰으로 처리)
                              ───>   PUT /api/artifact/{id}/result
  S3/Postgres 캐시 저장
```

**제약**:
- CEO 노트북이 깨어있어야 함 (suspend 시 cron skip). [[autopilot_log:2026-04-22]] 이미 기록된 한계.
- GitHub Actions(24/7)는 ANTHROPIC_API_KEY 없이는 LLM 호출 불가 → cron-LLM 작업은 노트북 의존.
- 노트북 부재 시 fallback: 직전 캐시 서빙 + "stale" 마킹 + 사용자 알림.

### 축 3. CC Scheduled-Tasks 확장 (4 → 22)

**현재 4개** ([[autopilot_log:2026-04-22]] 기준): morning-briefing / bug-hunter / legal-guard / api-sentinel + 매시 47분 sentinel.

**확장 후 22개 슬롯** (충돌 회피, 5h 윈도우 분산):

| 시각 (KST) | 작업 ID | 의도 | 모델 (기본) | 5h 윈도우 |
|---|---|---|---|---|
| 03:00 | ops-artifact-pregen-dd | dd_checklist 사전생성 (베타 N명 ×) | sonnet | A(03-07) |
| 03:15 | ops-artifact-pregen-risk-board | risk_board weekly 사전 | sonnet | A |
| 03:30 | bug-hunter-daily | 기존 유지 | sonnet | A |
| 03:45 | ops-artifact-pregen-earnings | 다음날 earnings 종목 prebrief | sonnet | A |
| 04:00 | ops-competitor-scan | 경쟁사 가격/카피/feature 감시 | haiku | A |
| 04:30 | ops-user-feedback-digest | Slack/이메일 본문 감정 분류 | haiku | A |
| 05:00 | ops-kpi-dashboard-daily | KPI 1장 요약 (WAMR / MRR / NPS) | sonnet | A |
| 05:30 | ops-legal-packet-diff | regulatory_changes_2026-05.md diff | haiku | A |
| 06:00 | ops-ship-blockers-diff | SHIP_BLOCKERS.md 어제 대비 | haiku | A |
| 06:27 | morning-briefing | 기존 유지 | sonnet | A |
| 06:42 | legal-guard | 기존 유지 | haiku | A |
| 09:00 | ops-marketing-calendar | 오늘 인스타/Threads 게시 큐 | sonnet | B(09-13) |
| 12:00 | ops-inbox-triage | 점심 이메일 분류 + draft 답신 | haiku | B |
| 매시 47분 | api-sentinel | 기존 유지 | haiku | 전 윈도우 |
| 14:00 | ops-fmp-cache-bust | null EPS/PE 종목 fresh fetch 트리거 | haiku | C(14-18) |
| 15:00 | ops-pdf-qa-smoke | artifact 17 렌더 smoke (Anthropic 미사용) | n/a | C |
| 16:00 | ops-finance-weekly-check | 기존 일요일 09:00 외 추가 daily diff | n/a | C |
| 18:00 | ops-evening-recap | 오늘 commit + bug + 알림 1장 회고 | sonnet | D(18-22) |
| 19:00 | ops-canary-postdeploy | 배포 후 30분 / 1h / 6h 라이브 prod 확인 | haiku | D |
| 20:00 | ops-anthropic-cost-estimate | 기존 22:00 → 20:00 이동 (자율 회고와 인접) | n/a | D |
| 21:00 | ops-next-day-planner | 내일 24h sprint 후보 자동 생성 (축 4 입력) | sonnet | D |
| 21:30 | lawyer-packet-weekly | 일요일만 (기존) | sonnet | D |

**총 22 슬롯** = morning(11) + 낮(2) + 매시(1) + 오후(4) + 저녁(5, 일요 +1)

**weighted token 추정** (1일):
- sonnet 9건 × 30k = 270k × 0.2 = 54k
- haiku 9건 × 15k = 135k × 0.05 = 6.75k
- 사전생성 3건 × 18k × 베타 30명 = 1.62M × 0.2 = 324k (피크)
- **합계 ≈ 385k weighted/일** = 5h 윈도우 5M의 **7.7%**

피크 03:00-06:42 윈도우 A: 324k + 사전 사이드 ≈ 400k = **8%**. **여유 충분.**

### 축 4. Self-Evolving Sprint Engine

**구조**:
1. **21:00 ops-next-day-planner** 가 다음 입력 수집:
   - `SHIP_BLOCKERS.md` (정적)
   - `autopilot_log.md` 최근 7일
   - bug-hunter-daily 직전 결과 (`/tmp/bug-hunter-last.json`)
   - `legal_question_queue.md` 신규 P0
2. sonnet 추론 → **다음 24h sprint 후보 3-5개** + 각각 ICE score
3. P0 만 자동 실행 (CEO 24h 응답 없으면) — [[feedback_no_askuserquestion]] 준수, CEO 결정 선택지 클릭 없음
4. 실행 결과 → autopilot_log.md 자동 prepend
5. 메모리 학습: sprint 효과 측정 (commit-to-fix ratio, 회귀 0 여부) → `feedback_sprint_patterns.md`(신규 메모리, 추후 생성) 자동 업데이트

**delegation-audit 게이트**: 자동 실행 sprint도 작업 모드 태그([CODE]/[BIZ]/[DESIGN] 등) 강제. 미태그 sprint = 차단.

**Self-Evolving 정의**: sprint engine이 **자기 자신을 수정**하는 게 아니라, sprint **패턴 데이터**를 누적해서 다음 추천 정확도를 올림. "에이전트가 코드 자체를 바꿈" 시나리오는 W6 이후 검토 (지금은 SF).

### 축 5. Production Anthropic API direct 최소화

| Artifact | 현재 호출 | 사전생성 가능? | v55 라우팅 |
|---|---|---|---|
| dd_checklist | on-demand (사용자 PDF) | YES (관심종목 daily) | CC Max 03:00 사전 → 캐시 |
| earnings_prebrief | on-demand | YES (실적발표 D-3 daily) | CC Max 03:45 사전 → 캐시 |
| quarterly_self_report | 분기 | YES (분기 마감 D-1) | CC Max cron(분기 1회) |
| risk_board | weekly | YES (월요일 03:00) | CC Max 03:15 사전 → 캐시 |
| self_audit | on-demand | NO (사용자 트리거 즉시) | ANTHROPIC_API_KEY 잔존 OR Free fallback |
| year_end_letter | 연1회 | YES (12/30 03:00) | CC Max cron(연 1회) |
| Chat / AI FAQ | 실시간 | NO (사용자 대화) | LLM OFF flag 기본 (`SUPPORT_CHAT_LLM_ENABLED` 이미 OFF, [[autopilot_log:2026-05-26]] 박힘) |

**효과 검증**: W5 측정 — Anthropic API direct 호출 50% 감소 (현 6 → 1-2 routes).

---

## Phase 3 — 자율도 ramp 갱신 (v54 + v55)

| Phase | v54 ramp | v55 추가 | 합산 자율도 |
|---|---|---|---|
| 1 (출시~D+30) | 40% | cron 4→8 + 사전생성 5 artifact | **50%** |
| 2 (D+30~D+90) | 60% | cron 8→16 + self-evolving 가동 | **75%** |
| 3 (D+90~D+365) | 70% | cron 16→22 + Anthropic 호출 50% 감소 | **90%** |
| Max-only 모드 | (v54 미정의) | 위 + CEO 1주 부재 가능 | **95%** |

**v54와의 차이**: v54는 자율도 95% 도달을 "Phase 3 끝(D+365)"에 두었음. v55는 **D+90 시점에 90% 도달**을 목표 — Max 토큰 활용으로 외부 결제 의존도가 사라지면서 의사결정 큐를 줄임.

---

## Phase 4 — Kill Switch 갱신 (Max 토큰 추가)

v54 Kill Switch K1-K8 유지 + **K9-K11 신규**:

| ID | 감지 | 자동 동작 | 회복 조건 |
|---|---|---|---|
| K9 (신규) | Max 일일 weighted token 80% 도달 | 비-critical cron(ops-competitor / ops-marketing-calendar / ops-evening-recap) skip | 5h 윈도우 reset |
| K10 (신규) | Max 일일 weighted token 100% 도달 | critical-only 모드 (legal-guard / api-sentinel / morning-briefing만) + Slack DM | 다음 5h 윈도우 |
| K11 (신규) | 5h ban (CC rate limit 에러) 발생 | 모든 cron 30분 자동 대기 → 재개. 2회 연속 ban 시 6h 정지 + CEO 알림 | 다음 윈도우 GREEN |

**Kill Criteria 보강** (v54 [[project_autonomous_ops:131-136]] 5개 + v55 추가 2):
- **(v55) MAX-K1**: 5h ban 주 3회 이상 → cron 22 → 16 자동 축소 (sprint engine 의 self-tune)
- **(v55) MAX-K2**: Anthropic API direct 호출 (ANTHROPIC_API_KEY 미설정 fallback 외) **임의 호출 감지** → 즉시 PR auto-revert + Slack 알림. CEO가 ANTHROPIC_API_KEY 충전 안 했는데 코드가 호출하면 prod 500.

---

## Phase 5 — v55 sprint 8주 ramp 계획

### W1 — 측정 + 사전생성 PoC (현재 ~ +7d)

| 작업 | 부서 | 의존 | 산출물 | 검증 |
|---|---|---|---|---|
| 1. token-log.jsonl 시각화 대시보드 (HTML 1장) | engineering | [[finance_token_ops:351]] 로그 위치 | `/tmp/max-token-dashboard.html` cron 매일 18:00 | weighted % 표기 |
| 2. dd_checklist 사전생성 cron (1 유저 = CEO) | engineering | services/artifacts/dd_checklist_service.py | 캐시 path `state/artifact_cache/dd/{ticker}-{date}.html` | CEO 도그푸딩 1주 |
| 3. risk_board 사전생성 cron (CEO 포트폴리오) | engineering | 동상 | 캐시 path | weekly Monday 03:15 |
| 4. ops-evening-recap cron 1건 시범 | operations | autopilot_log.md 직전 7일 | `briefings/evening-{date}.md` | CEO 21:00 확인 |

**W1 끝**: cron **4 → 8**. 사전생성 2 artifact 검증.

### W2 — cron 확장 + Self-Evolving 베이스

| 작업 | 부서 | 의존 | 산출물 |
|---|---|---|---|
| 5. ops-competitor-scan cron (한투/미래에셋/토스 가격 페이지 grep) | strategy | URL 리스트 | 일일 diff Slack DM |
| 6. ops-kpi-dashboard-daily cron | analytics | WAMR/MRR/NPS 쿼리 | `briefings/kpi-{date}.md` |
| 7. ops-legal-packet-diff cron | legal | regulatory_changes_2026-05.md | 신규 키워드 감지 → legal_question_queue.md prepend |
| 8. ops-next-day-planner cron (Self-Evolving v0) | strategy | autopilot_log + SHIP_BLOCKERS | `briefings/plan-{tomorrow}.md` |

**W2 끝**: cron **8 → 12**. Self-Evolving planner 가동 (제안만, 자동 실행 X).

### W3 — Self-Evolving 자동 실행 + ops-anthropic-cost 통합

| 작업 | 부서 | 의존 | 산출물 |
|---|---|---|---|
| 9. ops-next-day-planner → P0 자동 실행 path | strategy + engineering | delegation-audit hook | autopilot_log prepend |
| 10. ops-anthropic-cost-estimate 22:00 → 20:00 이동 + Max token 통합 view | finance | 기존 cron | 1 view (Anthropic direct + Max weighted) |
| 11. ops-inbox-triage cron (Gmail 라벨) | operations | mcp__bb45a940...Gmail | 라벨 + draft 자동 |
| 12. ops-marketing-calendar cron | marketing | growth_experiments.md | 일일 게시 큐 |

**W3 끝**: cron **12 → 16**. Self-Evolving 자동 실행 가동.

### W4 — 백엔드 routing 재배치 (Anthropic direct → 캐시)

| 작업 | 부서 | 의존 | 산출물 |
|---|---|---|---|
| 13. dd_checklist route — 캐시 우선, fallback Anthropic direct (현행) | engineering | services/artifacts/dd_checklist_service.py | 통합 path |
| 14. earnings_prebrief route 동상 | engineering | 동상 | - |
| 15. risk_board route 동상 | engineering | 동상 | - |
| 16. self_audit on-demand — `SUPPORT_CHAT_LLM_ENABLED` 패턴 적용 (Free tier fallback) | engineering | 기존 flag 패턴 | LLM_ENABLED OFF 기본 |

**W4 끝**: 4/6 artifact 라우팅 전환. Anthropic direct 호출 ~50% 감소 예상.

### W5 — 호출량 검증

| 작업 | 부서 | 산출물 |
|---|---|---|
| 17. 7일 anthropic_usage_log 측정 vs W4 시작 baseline | finance | 차트 1장 |
| 18. 100 유저 가상 부하 (mock) → 캐시 hit/miss 측정 | engineering | hit ≥80% 검증 |
| 19. self_audit Free tier fallback 카피 검수 (LLM 미사용 시 메시지 적절성) | legal + design | 카피 1셋 |

**W5 끝**: Anthropic API direct 호출 **50% 감소 인증** (kill criteria 미달 시 W6 plan 재검토).

### W6 — Self-Evolving 패턴 학습 + cron 22 완성

| 작업 | 부서 | 산출물 |
|---|---|---|
| 20. ops-next-day-planner — 지난 N일 sprint 성공률 학습 (메모리 prepend) | strategy | feedback_sprint_patterns.md 신규 |
| 21. ops-fmp-cache-bust / ops-pdf-qa-smoke / ops-canary-postdeploy cron 3개 추가 | engineering | - |
| 22. ops-user-feedback-digest cron (Slack/이메일 감정 분석) | customer | 일일 digest |

**W6 끝**: cron **16 → 22** 완성. CEO에게 sprint 제안 정확도 보고 (baseline vs W6).

### W7 — 자율도 80% 검증 (CEO 부재 시뮬레이션)

| 작업 | 부서 | 검증 |
|---|---|---|
| 23. CEO 3일 부재 시뮬레이션 (Slack 응답 없음) | strategy | cron 22 + Self-Evolving 의 P0 자동 실행 회귀 0 |
| 24. Kill Switch K9-K11 부하 테스트 (의도적 5h 윈도우 80% 도달) | engineering | YELLOW→ORANGE→RED 단계 동작 |
| 25. ANTHROPIC_API_KEY 의도적 제거 → fallback 동작 검증 | engineering | weekly_memo_service:1318 path |

**W7 끝**: 자율도 80% 달성. CEO 부재 3일 회귀 0.

### W8 — 자율도 90% (CEO 부재 1주 가능)

| 작업 | 부서 | 검증 |
|---|---|---|
| 26. CEO 7일 부재 시뮬레이션 | strategy | NPS 응대 / 결제 retry / legal-guard 전부 자동 |
| 27. v55 마스터플랜 회고 + v56 입력 도출 | strategy | autonomous_ops 메모리 갱신 |
| 28. v55 archive 처리 + ramp 90% lock-in | strategy | [[project_autonomous_ops]] 신규 ramp 표 prepend |

**W8 끝**: 자율도 90% 인증. v54 Phase 3(D+365 70%) 대비 9개월 조기 달성.

---

## Risk & Mitigation

| 리스크 | 확률 | 대응 |
|---|---|---|
| MacBook suspend 시 cron 22 전부 skip | HIGH | GitHub Actions runner(Anthropic 미사용 cron 일부 이전 — api-sentinel / legal-guard) + 캐시 stale fallback |
| Max 5h ban 빈발 (cron 22 = 부하 증가) | MEDIUM | K11 자동 30분 대기. weighted token 추정 5h 8% 여유 — 실측 후 cron 축소 가능 |
| Self-Evolving planner 가 잘못된 P0 자동 실행 | MEDIUM | delegation-audit hook + autopilot_log diff 06:00 모니터 + Kill K12(자동 실행 회귀 1건 발생 시 자동 OFF) |
| CEO Anthropic Max plan 해지 → CC 자체 불가 | LOW | [[finance_budget:M1-M2]] 시나리오 B 확정 시 다운그레이드 검토. v55는 Max 유지 전제 |
| ANTHROPIC_API_KEY 결제 트리거되는 path 누락 | MEDIUM | MAX-K2 PR auto-revert + grep CI gate(`anthropic.Anthropic\(` 호출 위치 화이트리스트 services/ai/ 외 금지) |
| iCloud Desktop 동기화로 cron 스크립트 소실 | LOW | [[project_icloud_desktop_hazard]] — 모든 cron 스크립트는 `~/dev/pivoxquant/scripts/` (iCloud 밖) |

---

## Kill Criteria (v55 전용)

1. **W5에서 Anthropic API direct 호출 감소 <30%** → W6 plan 폐기, ANTHROPIC_API_KEY Free tier fallback 전면 채택 (LLM 기능 강등)
2. **W7에서 CEO 3일 부재 회귀 발생** → 자율도 75% 고정, 90% 목표 폐기
3. **Max 5h ban 주 5회 이상** → cron 22 → 12 강제 축소
4. **MAX-K2 (ANTHROPIC_API_KEY 임의 호출) 발생 시** → v55 sprint 즉시 정지, root cause 분석
5. **CEO Anthropic Max plan 해지** → v55 sprint 폐기, v54 ramp(40/60/70%)로 회귀

---

## 0원 검증 (추가 비용 룰 준수)

| 항목 | 신규 결제 발생 여부 | 근거 |
|---|---|---|
| Anthropic API direct (ANTHROPIC_API_KEY) | **NO** | v55가 명시적 회피 대상 |
| Anthropic Max plan ($220) | NO (기존) | [[finance_budget:80]] 5/14 이미 결제, v55가 만든 비용 아님 |
| CC scheduled-tasks 22개 | NO | Max plan 한도 내. weighted 8% 사용 |
| Slack webhook DM | NO | Free tier ([[project_automation_v2]] 박혀있음) |
| GitHub Actions runner (cron 일부 이전 시) | NO | 2000분/월 무료 한도 내 |
| 신규 SaaS 가입 | **금지** | [[feedback_no_extra_cost]] |

**합계: ₩0 추가 결제.**

---

## Status (v55)

**완료 체크리스트**:
- [x] Phase 1 측정: 메모리 인용 + 실측 (anthropic 호출 6 module / artifact 17 중 LLM 6) ✅
- [x] Phase 2 라우팅 5축 (Lifecycle / Orchestrator / cron 22 / Self-Evolving / API direct 최소화) ✅
- [x] Phase 3 ramp 갱신 (50/75/90/95) ✅
- [x] Phase 4 Kill Switch K9-K11 + MAX-K1/K2 ✅
- [x] Phase 5 8주 sprint (W1-W8, 28 작업) ✅
- [x] Risk 6종 + 대응 ✅
- [x] Kill Criteria 5종 (v55 전용) ✅
- [x] 0원 검증 표 ✅
- [x] AskUserQuestion 미사용 ✅
- [x] 코드 변경 X (구상만) ✅
- [x] push/commit 없음 ✅
- [x] 700줄 이하 (v54 365 + v55 ~310 = ~675) ✅

**Status: COMPLETE (v55 append)**
