# Spawn Recommendations — 2026-05-18 (v45 Agent Inventory 대정비 후속)

> **작성일**: 2026-05-18
> **출처**: agent 인벤토리 대정비 v45 세션 (Wave 1-4 완료)
> **대상**: CEO 액션 필요 후속 spawn task
> **메모리 룰 준수**: `feedback_no_extra_cost` / `feedback_pre_launch_full_throttle`

---

## 1. 개요

본 문서는 2026-05-18 agent 인벤토리 대정비 (v45) 세션 결과 도출된 **CEO 액션 필요 후속 작업 리스트**다.

- 각 항목은 **우선순위 (P0/P1/P2)** + **예상 시간** + **비용 영향** 명시
- 메모리 룰:
  - `feedback_no_extra_cost` — 추가 비용 0원 원칙 (Max + 도메인 + Railway 외 신규 결제/API/구독 금지)
  - `feedback_pre_launch_full_throttle` — 출시 전까지 토큰/모델/wave 절약 금지 (Opus 4.7 default + 5-10 agent 병렬)

- 분류:
  - **P0 SHIP-BLOCKER** — 출시 전 필수 (#17 DNS / #18 artifact-qa fixture)
  - **P1 출시 직전 (D-7)** — 통신판매업 / 변호사 자문
  - **P2 출시 후 D+7** — SoT 통합 / SoT 버전 통일 / 문서 정리

---

## 2. P0 SHIP-BLOCKER (출시 전 필수)

### #17 — DNS SPF/DKIM/DMARC 설정

**상태**: 실측 `dig` 결과 전부 **NOT_CONFIGURED** (2026-05-18 검증)

```bash
dig +short pivoxquant.com TXT          # → (empty)
dig +short _dmarc.pivoxquant.com TXT   # → (empty)
dig +short MX pivoxquant.com           # → (empty)
```

**영향**: Weekly Memo 발송 활성화 시 Gmail/Naver/Daum **즉시 spam** 분류 → **출시 BLOCKER**

#### 옵션 A: Google Workspace 결제 (월 약 8천원)
- **장점**: 표준 메일 서비스 + 자동 SPF/DKIM/DMARC 설정
- **단점**: `feedback_no_extra_cost` 위반 (Max + 도메인 + Railway 외 추가 비용 금지)
- **예상 시간**: 30분 (결제 + DNS 설정 + verification)

#### 옵션 B: SendGrid Free Tier 100/day
- **장점**: 추가 비용 **0원** (`feedback_no_extra_cost` 준수) ✅
- **단점**: 100/day 한도 (베타 100명 첫 주 충분 / 출시 후 1000명 단계 부족)
- **예상 시간**: 60분 (계정 생성 + DNS 설정 + API key + 코드 통합)

#### 옵션 C: Resend (1000 emails/month free)
- **장점**: 100 emails/day 한도 없음 (월 1000건)
- **단점**: 신규 서비스 (DNS reputation 약함)
- **예상 시간**: 60분

**권고**: **옵션 B (SendGrid)** 우선 → 1000명 단계에서 Workspace 결제 검토

**CEO 결정 필요**: 옵션 A/B/C 중 선택 + 즉시 spawn

---

### #18 — artifact-qa fixture 빌드

**상태**: `tests/fixtures/virtual_users.py` **미존재** (2026-05-18 실측 `find` 0건)

**영향**: 17 Artifact × 10 profile = **170 케이스 회귀 검증 불가능** → **출시 BLOCKER**

#### Spawn 작업

1. `tests/fixtures/__init__.py` 신설
2. `tests/fixtures/virtual_users.py` 신설 — **10 profile 정의**:
   - 초보 / 한국전용 / 혼합 / 고도집중 / 고분산 / 배당 / 데이트레이더 / 신규 / 취소임박 / 국제분산
3. `tests/fixtures/sample_data_factory.py` 신설 — portfolio + 종목 시뮬레이션
4. `tests/test_artifact_rendering.py` 신설 — 17 × 10 parametrize
5. `.github/workflows/artifact-qa.yml` 신설 — `pytest-xdist` 자동 실행

**예상 시간**: 2-4시간 (`artifact-qa.md` Mode 3 spec 따라)
**비용**: **0원** (pytest 기존 인프라)

---

## 3. P1 출시 직전 (D-7)

### #19 — 통신판매업 신고

- **상태**: 미신고 (`business_registration.md`)
- **영향**: **Stripe Live 활성화 BLOCKER** (`compliance-gatekeeper` B-2)
- **Spawn 작업**:
  - 성동구청 (사업장 관할) 온라인 신청
  - 등록세 약 **45,000원**
  - 예상 시간: **30분 (online)**
- **CEO 액션**: 직접 신청 (자동화 불가)

### #20 — 변호사 자문 큐 Q1-Q15

- **상태**: 15건 pending (`legal_question_queue.md`)
- **영향**: §101 면제 트랙 유효성 + Stripe Live precondition
- **비용**: **300-500만원 예상** (일괄 의견서)
- **CEO 액션**: 금융규제 전문 변호사 컨택

---

## 4. P2 출시 후 D+7

### SoT 통합 결정 — `feedback_bug_fix_patterns.md`

- **상태**: v44.x 도메인 확장 패턴 (`qa.md` / `bug-hunter.md` #10-12) SoT 추가 검토 필요
  - `qa.md`: idempotency / N+1 query / cross-user cache leak
  - `bug-hunter.md`: equity curve FX / viral loop OG / webhook signature 강제
- **CEO 결정**: SoT §10-15 통합 추가 vs 도메인 특화 유지

### v44.8 vs v44.9 SoT 통일

- **상태**: `stripe-billing` + `audit`는 v44.9 (40 PR) / 나머지 v44.8 (32 PR)
- **작업**: 다음 세션에서 v44.9로 통일 또는 명시적 분리

### Railway 행 중복 (`finance.md`)

- **상태**: Cost Breakdown 표에 Railway 일반 행 + Railway PostgreSQL 행 **2개 존재**
- **작업**: 통합 또는 명확 분리 (PostgreSQL은 일반 Railway에 포함)

---

## 5. 모니터링 (D-day 이후 자동)

| Agent | Cadence | 목적 |
|---|---|---|
| `launch-coordinator` | D-7 ~ D+30 매일 cron | 출시 전후 코디네이션 |
| `compliance-gatekeeper` | 일일 dashboard | BLOCKER 7건 추적 |
| `cost-monitor` | 일일 | 8 서비스 추적 (Anthropic v28 재발 방지) |
| `data-freshness-monitor` | 매시간 | KIS/DART/KRX/FMP staleness |
| `secrets-rotator` | 90일 cadence | 9종 시크릿 (BETA_PW REST API 자동화) |
| `beta-onboarding-monitor` | 일일 | 첫 100명 funnel |
| `billing-incident-handler` | 즉시 | Stripe webhook 대응 |
| `release-coordinator` | 매 prod 배포 | 5룰 게이트 |
| `prod-migration-sync-verifier` | 매 배포 | alembic 동기화 |
| `pwa-cache-validator` | 회귀 시 | SW lifecycle |

---

## 6. CEO 즉시 결정 항목 (Action Items)

- [ ] **#17 DNS 옵션 선택 (A/B/C)**
- [ ] **#18 artifact-qa fixture spawn 시점**
- [ ] **#19 통신판매업 신고 일정**
- [ ] **#20 변호사 컨택 시점**
- [ ] `business_registration.md` 사업장 주소 → `email-deliverability.md` 반영 완료 확인

---

## 7. 비용 검증 (`feedback_no_extra_cost`)

- **본 세션 신규 15 agent + 27 agent 업그레이드**: 전부 **0원** ✅
- **SHIP-BLOCKER #17 옵션**:
  - 옵션 A (Workspace): 월 약 8천원 — `feedback_no_extra_cost` 충돌 (**CEO 결정**)
  - 옵션 B (SendGrid free): **0원** ✅
  - 옵션 C (Resend free): **0원** ✅
- **#19 통신판매업**: 약 45,000원 (1회성, 행정 비용 — 출시 필수)
- **#20 변호사**: 300-500만원 (출시 후 분할 가능)

---

**End of document — `spawn-recommendations-2026-05-18.md`**
