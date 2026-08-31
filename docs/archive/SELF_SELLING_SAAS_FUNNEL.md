# Self-Selling SaaS Funnel — v57-C3 자율 매출 사이클 spec

> **목적**: CEO 시간 = 매출 직선 종속 끊기. AI가 직접 SaaS funnel을 운영해, **CEO inbox는 신규 결제 알림 + 24h batch 결정 only**가 되도록 한다.
> **작성일**: 2026-05-28 (v57-C3)
> **상태**: spec only — 코드 변경/배포 없음. 변호사 BLOCKER 해소 후 단계적 활성.
> **0원 제약**: 모든 Loop는 Max + Railway + 도메인 + SendGrid/Brevo free tier + ImprovMX free 내부에서만 작동. 추가 결제 절대 금지(`feedback_no_extra_cost`).
> **데이터 제약**: 모든 분석/리포트는 KIS API + DART OpenAPI + KRX Open Data Portal + FMP만(`feedback_official_data_only`).

---

## 0. v54-v56 위에 새 각도

| Wave | 주제 |
|------|------|
| v54 | 운영 자동화 (cron / hook / GH Actions) |
| v55 | 의사결정 자동화 (agent → CEO 24h batch) |
| v56 | 단일 인터페이스 / 시간 압축 |
| **v57-C3** | **매출 사이클 = 가입 → 활성화 → 전환 → retention → churn → resurrection 전 단계 AI 자율** |

C3은 "AI가 SaaS를 직접 판다"의 spec. 이전 wave는 "AI가 코드/운영을 한다"였다면, C3은 **유저 lifecycle 자체가 자율 객체**.

---

## 1. Phase 1 — Funnel 현 상태 인벤토리

### 1.1 Lifecycle 7단계 + 자동화 수준

| # | 단계 | 자동화 수준 | CEO 개입 빈도 | BLOCKER |
|---|------|------------|--------------|---------|
| 1 | **Acquisition** (카페/인스타/검색/직접) | 10% | 매일 (수동 게시) | Q-M1 §101 광고 충돌 |
| 2 | **Activation** (가입+20문항+첫 portfolio) | 30% | 주 1-2회 | Q-S1 §50 분리동의 → welcome 메일 OFF |
| 3 | **Engagement** (morning brief + Artifact 17개) | 70% | 거의 없음 | env (SENDGRID/BREVO 키) |
| 4 | **Conversion** (Free → Pro/Premium) | 5% | 결제 직접 처리 | Q-S3 통신판매업 vs §101 — 출시 BLOCKER |
| 5 | **Retention** (월간 active) | 20% | 분석만 수동 | Q-S1 |
| 6 | **Churn** (7d/14d/30d 비활성) | 0% | 무시 중 | Q-S1 + PIPA 30d 보관룰 |
| 7 | **Resurrection** | 0% | 없음 | Q-S1 |

### 1.2 박혀있지만 OFF인 자산

- 이메일 시퀀스 4개 코드 (`services/email/sequences/*.py`) — Q-S1 해소 시 ON
- support chatbot (`services/support/chatbot.py`) — Anthropic credit 부담 → 영구 OFF, 대체 spec은 Loop E
- brag-card 자동 생성 (`services/artifacts/brag_card.py`) — OG public 통과(v44.8), 발송 trigger만 OFF
- 추천코드 미설치 (Wave 3 백로그)

### 1.3 변호사 BLOCKER 매트릭스

| Q | 내용 | 영향 Loop |
|---|------|----------|
| **Q-S1** | 정통망법 §50 분리동의 (마케팅 수신동의 6% 과징금) | B(welcome 외), C, D 전부 |
| **Q-M1** | §101 광고 충돌 (자문/추천 광고 금지) | A 광고 집행만, organic 게시는 무영향 |
| **Q-S3** | 통신판매업 신고 vs §101 "매월 청구 금지" 정면 충돌 | C 결제 활성 (출시 BLOCKER) |
| **Q-S4** | 영문 레짐 msg §49 비대칭 (코드 fix wave 진행 중) | E support 응답 |

→ Loop A organic / Loop B welcome / Loop E 분류·초안까지는 **변호사 답변 없이도 안전 ON 가능**.
→ Loop B nudge / Loop C / Loop D 전체는 **Q-S1 해소 전 OFF 유지**.
→ Loop C 결제는 **Q-S3 해소 전 OFF 유지** (출시 자체가 막힘).

---

## 2. Phase 2 — 5 Loop 설계

### Loop A. Acquisition Loop

**목표**: 신규 유입 자동 생성 — organic 채널 (광고는 Q-M1 후).

**구성**:
- `ops_marketing_calendar_dispatch` cron (Mon-Fri 08:00 KST)
  - `content-bank.json` (메모리 `marketing_copy.md` 기반)에서 당일 슬롯 추출
  - 카페(클리앙/뽐뿌/디씨 주식갤) / 인스타 / Threads 3채널 슬롯 분배
  - 게시 자체는 **수동 카피-페이스트 큐** (각 플랫폼 API 유료 → 0원 제약)
  - = AI는 "오늘 게시할 카피 3개" 큐를 CEO inbox에 매일 1줄로 제공
- 댓글 감정 분석 (KoBERT-light free model, 로컬 inference)
  - 부정 댓글 → 자동 응답 초안 생성 → CEO inbox 5초 응답
  - 긍정 댓글 → 무액션
- UTM 추적 (`?utm_source=cafe&utm_medium=organic&utm_campaign=YYYYMMDD`)
  - Plausible self-host (free) 이벤트 집계
  - 매주 일요일 23:59 KST `growth_experiments.md` 채널별 ROI 자동 갱신
- 광고 ROI 추적 (Q-M1 해소 후만)
  - 메타/인스타 CPC 자동 import (수동 CSV drop)
  - 1주 단위 carry-over

**자율 권한**:
- 🟢 자율: 카피 생성, 댓글 감정 분석, ROI 집계
- 🟡 CEO 24h batch: 카피 톤 변경 승인, 부정 댓글 응답 발송 (5초)
- 🔴 즉시 escalation: 광고 예산 결정 (Q-M1 해소 + 별도 budget 승인)

**Kill criteria**: 4주 연속 organic 신규 가입 < 10명/주 → A/B test (메모리 `growth_experiments.md`).

---

### Loop B. Activation Loop

**목표**: 가입자 80% questionnaire 완료 + 70% 첫 portfolio.

**구성**:
- **즉시 welcome 메일** (가입 직후, 동의 ✅ 자체)
  - Q-S1과 무관 — "거래상 통지 (Transactional)"이므로 §50 마케팅 수신동의 별도 필요 없음
  - 단, **광고/마케팅 카피 포함 금지** — 가입 확인 + 다음 단계 안내만
  - 변호사 1순위 확인 항목으로 큐에 추가
- **questionnaire nudge** (Q-S1 의존, 박힌 코드 ON 대기)
  - D+1 미완 → "5분이면 끝나요" 톤
  - D+3 미완 → 결과 미리보기 일부 노출
  - D+7 미완 → cohort 인사이트 ("같은 시점 가입자 85% 완료")
- **첫 portfolio 자동 brag_card** (입력 1시간 후)
  - 자동 이메일 발송 (Q-S1 의존)
  - brag_card OG public endpoint (v44.8 fix 완료) → viral seed
- **D+1 첫 morning brief** 자동 발송
- 활성화율 지표 (`questionnaire 완료 % × first portfolio %`) 매주 자동 추적

**자율 권한**:
- 🟢 자율: welcome 메일 (가입 확인 톤), morning brief, brag_card 생성
- 🟡 CEO 24h batch: questionnaire 미완 cohort 인사이트, nudge 톤 A/B 결과
- 🔴 즉시: Q-S1 해소 전 nudge/brag 발송 OFF 유지

**Kill criteria**: 활성화율 30% 미만 → Loop B 진단 (questionnaire 20문항 → 5+15 분할 실험).

---

### Loop C. Conversion Loop

**목표**: Free → Pro 5% / Pro → Premium 10% (12개월 누적).

**구성**:
- **Free 7d 활성 → Pro upgrade nudge** (Q-S1 의존)
  - "지난 7일간 X번 morning brief 열람, Pro 기능 Y개 lock 마주침"
- **Free 14d 활성 + 4+ portfolio → Pro 50% 첫달 자동 메일** (Q-S1 + Q-S3 의존)
- **Pro 30d 활성 + Premium feature 클릭 3+회 → Premium nudge** (Q-S1 의존)
- **가격 A/B test** (메모리 `growth_experiments.md`)
  - Pro ₩9,900 vs ₩12,900 vs ₩7,900 3-arm
  - 통계적 유의 (p<0.05) 도달 시 winner 자동 채택 → CEO inbox 1줄
  - 6개월 cooldown
- **결제 분쟁 / 환불 자동 처리**
  - Stripe webhook → 자동 분류 (정당 환불 / 의심 / 챠지백)
  - 정당 환불: 자동 처리 + 사후 CEO inbox 알림
  - 의심/챠지백: 즉시 escalation

**자율 권한**:
- 🟢 자율: 활성/이용 데이터 집계, A/B test 운영, upgrade nudge 발송
- 🟡 CEO 24h batch: A/B winner 채택, 가격 변경 결정
- 🔴 즉시: 결제 분쟁, 챠지백, 환불 정책 예외, Q-S3 미해소 시 결제 자체 OFF

**Kill criteria**:
- Free → Pro 전환율 3% 미만 (90d cohort) → A/B test 강제
- Q-S3 미해소 시 본 Loop 전체 OFF — 결제 활성화 자체가 §101 면제 트랙 위반 위험

---

### Loop D. Retention + Resurrection Loop

**목표**: D+30 25% / D+90 15% / D+180 10%.

**구성** (Q-S1 의존):
- **7d 비활성 → retention 메일**
  - 톤: "지난 주 X 종목 ▲5% — 당신의 portfolio Y는 어땠나요?"
  - 데이터: 공식 라이선스만 (FMP / KRX Open Data Portal)
- **14d 비활성 → 다른 톤 retention 메일**
  - 톤: 사용자 페르소나 결과 재상기
- **30d 비활성 → "마지막" 메일 + 1개월 무료 incentive** (Q-S1 + Q-S3 의존)
  - 1개월 Pro free → 결제 정보 미요구 (Q-S3 매월 청구 회피)
- **60d+ 비활성 → cohort archive**
  - PIPA 30d 룰과 결합 — 60d 비활성 + 마지막 로그인 90d 경과 시 개인정보 익명화 처리
  - 변호사 PIPA SaaS 인벤토리 (`legal_pipa_saas_inventory.md`) 참조
- **resurrection 재참여** (cohort archive 전 재로그인)
  - 자동 welcome-back 메일 (Q-S1 의존)
  - brag_card 갱신 — 마지막 활성 시점 이후 portfolio 변화 자동 시각화

**자율 권한**:
- 🟢 자율: 7d/14d 메일 발송 (Q-S1 후), cohort 분석, brag_card 갱신
- 🟡 CEO 24h batch: 30d 마지막 메일 카피, incentive 톤
- 🔴 즉시: 60d+ archive 결정, PIPA 보관/파기 정책 변경

**Kill criteria**:
- 14d 메일 unsubscribe rate 30%+ → 톤 재조정 (§50 6% 과징금 노출 위험)
- D+30 retention 15% 미만 → 첫 주 가치 전달 진단 (`growth_experiments.md` Step 5)

---

### Loop E. AI-Powered Support Loop

**목표**: support 응답 시간 24h 이내, CEO 검토 1초.

**구성**:
- **챗봇 (현 OFF)**: Anthropic API direct 부담 → 영구 OFF
- **대체: email-only FAQ bot**
  - 사용자 이메일 → 자동 카테고리 분류 (billing / technical / feature request / spam)
  - 분류는 **로컬 keyword + KoBERT-light free model** (Anthropic credit 0원)
  - billing/technical → **Anthropic API direct (Max 한도 내)** — 답변 초안 생성
    - 1건당 ~$0.01 (Sonnet 4.7) — Max 월 한도 내 free tier (5000 유저 도달 전까지)
    - **부담 시점**: 5000+ 유저 도달 시 (월 ~500건 → ~$5/월) — 별도 결정
  - 응답 초안 → CEO inbox 1초 검토 → 자동 발송 (또는 수정 후 발송)
  - spam / 광고 → 자동 drop
  - feature request → 메모리 `product_features.md` 후보 자동 추가
- **응답 데이터셋 자동 누적** — 향후 fine-tune 후보 (별도 wave)

**자율 권한**:
- 🟢 자율: 분류, spam drop, feature request 추가, 초안 생성
- 🟡 CEO 24h batch: 초안 검토 1초 (대부분 그대로 발송)
- 🔴 즉시: billing 분쟁, 법적 문의, Q-S4 영문 §49 메시지 비대칭

**Kill criteria**:
- 응답 시간 24h 초과 → 자동 escalation
- 분류 정확도 90% 미만 → 모델 재학습 (free model 한해서)
- Anthropic API direct 비용 월 $50 초과 → CEO 결정 (별도 budget 승인)

---

## 3. Phase 3 — 자율 권한 매트릭스 (요약)

| Loop | 🟢 자율 | 🟡 CEO 24h batch | 🔴 즉시 escalation |
|------|---------|------------------|-------------------|
| **A** Acquisition | organic 게시 카피 생성 / 댓글 감정 분석 / UTM ROI 집계 | 카피 톤 변경 / 부정 댓글 응답 (5초) | 광고 예산 결정 (Q-M1 후) |
| **B** Activation | welcome 메일 / morning brief / brag_card / 활성화율 집계 | nudge 카피 A/B 결과 / questionnaire cohort 인사이트 | Q-S1 미해소 시 nudge OFF 강제 |
| **C** Conversion | upgrade nudge / A/B test 운영 / Stripe 정당 환불 | A/B winner 채택 / 가격 변경 / 50% 할인 발동 조건 | 챠지백 / 의심 환불 / 결제 분쟁 / Q-S3 OFF |
| **D** Retention | 7d/14d 메일 / cohort 분석 / brag_card 갱신 | 30d 마지막 메일 카피 / incentive 톤 | 60d+ archive / PIPA 파기 / unsubscribe 30%+ |
| **E** Support | 분류 / spam drop / feature 후보 / 초안 생성 | 초안 검토 (1초) | billing 분쟁 / 법적 / Q-S4 비대칭 |

---

## 4. Phase 4 — 출시 후 시나리오

### 4.1 100 유저 (D+30 목표)
- CEO inbox 일일 1-2건
  - 결제 알림 (~0.5건/일, 신규 Pro)
  - support 응답 검토 (~1건/일, 1초)
- Loop 부담: A/B/E만 active (Q-S1 미해소 시)
- Anthropic API direct 부담: 거의 0원 (~$0.5/월)

### 4.2 1000 유저 (D+90 목표)
- CEO inbox 일일 3-5건
  - 결제 알림 (~3건/일)
  - support 검토 (~2건/일)
  - A/B test winner 채택 (~1건/주)
- Loop 부담: 전체 (Q-S1/S3 해소 가정)
- Anthropic API direct: ~$5/월 (Max 한도 내, free)

### 4.3 5000 유저 (D+180 목표)
- CEO inbox 일일 5-10건
- B2B 모델 결정 시점 — Loop A/B/C/D 자율 계속
- Anthropic API direct: ~$30/월 (Max 한도 초과 가능 → CEO budget 결정)
- Brevo/SendGrid free tier 한계 (1000 users 기준) — 결제 발생 시점

---

## 5. Phase 5 — Kill Criteria 종합

| 지표 | 기준 | 자동 액션 |
|------|------|----------|
| D+30 첫 100 user | 미달 | CEO inbox 1줄 + campaign 변경 요청 |
| 활성화율 (Step 2-4 완주) | 30% 미만 | Loop B 진단 자동 trigger + A/B test |
| Free → Pro 전환율 (90d) | 3% 미만 | Loop C A/B test 강제 + 가격 실험 |
| 14d 메일 unsubscribe | 30%+ | Loop D 톤 즉시 OFF + 재설계 (§50 위험) |
| Support 응답 시간 | 24h 초과 | 자동 escalation + 분류 모델 진단 |
| Anthropic API direct | 월 $50 초과 | CEO budget 결정 escalation |
| Q-S3 미해소 + 결제 ON 시도 | 항상 | 즉시 OFF (§101 면제 위험) |

---

## 6. Phase 6 — 창의 확장 (Bonus 3종)

### 6.1 Self-Pricing Loop

**아이디어**: 사용자 supply/demand 곡선 자동 학습 → 가격 6개월마다 자동 ±10% A/B → winner 자동 채택.

**구성**:
- 매 6개월: 현재 가격 ±10% 3-arm A/B (₩9,900 / ₩10,890 / ₩8,910)
- 표본 크기: arm당 최소 100명 (총 300명, 사실상 1000+ 유저 도달 후 가능)
- 통계 유의 (p<0.05, primary = 전환율 × ARPU) 시 winner 자동 채택
- CEO inbox 1줄: "가격 ₩9,900 → ₩10,890 (revenue +X% 검증, 6개월 후 재실험)"

**제약**:
- Q-S3 해소 전 작동 불가 (가격 변경 자체가 결제 활성에 의존)
- 가격 표시 변경 시 정통망법 §50 별도 통지 의무 검토 필요 → 변호사 확인 큐 추가

---

### 6.2 Self-Discovering Feature

**아이디어**: 사용자 클릭/검색/요청 분석 → 우선순위 feature 자동 도출.

**구성**:
- **클릭 heatmap** — Plausible self-host 이벤트
- **검색 로그** — 내부 검색바 query 누적
- **support feature request** — Loop E에서 자동 분류된 항목
- **lock 마주침** — Free 사용자가 Pro 기능 클릭 시 자동 카운트
- 매월 1일 새벽: top-3 자동 도출 → `product_features.md` 후보 섹션에 자동 prepend
- CEO inbox 1페이지: "이번 달 top-3 feature 후보: A (요청 X회), B (lock Y회), C (검색 Z회)"
- CEO 24h batch 결정: 다음 v-sprint 등록 / pass / 추가 분석

**제약**:
- 변호사 자문 회피 — 분석은 자동, **feature 자체 구현은 reviewer/security agent 거쳐야 함** (§101 면제 트랙 유지)
- 사용자 데이터 분석 = PIPA 처리목적 내 (현 처리방침에 분석 명시 필요 — 변호사 큐)

---

### 6.3 Self-Marketing Pivot

**아이디어**: 채널별 효과 매월 측정 → winner 채널 비중 자동 조정.

**구성**:
- 채널: 카페(클리앙/뽐뿌/디씨 주식갤) / 인스타 / Threads / 블로그 SEO / 추천코드 (Wave 3)
- 매월 1일: UTM 기반 channel별 CAC × LTV 계산
  - CAC = 게시 시간 × 시급 환산 (광고 0원 가정)
  - LTV = cohort 6개월 누적 revenue
- top-2 채널 비중 자동 +20%, bottom-1 채널 자동 폐기 (월간 게시 슬롯 재분배)
- CEO inbox 1줄: "이번 달 winner: 인스타 (LTV/CAC 4.2x), 폐기: 디씨 (LTV/CAC 0.3x)"

**제약**:
- "광고비 자동 분배"가 아닌 **무료 게시 시간 분배**만 (0원 제약)
- 채널 콘텐츠는 §101 광고 회피 — 일반화된 정보 제공 only (변호사 큐 Q-M1)

---

## 7. 구현 우선순위 (변호사 답변 의존 명시)

| 단계 | Loop | 변호사 의존 | env 의존 | 예상 시점 |
|------|------|------------|---------|----------|
| **즉시 (코드 박혀있음)** | A organic 게시 큐 | 없음 | content-bank.json | 출시 직전 |
| **즉시** | B welcome 메일 (거래상 통지) | 1순위 확인 | SENDGRID_API_KEY | 출시 직전 |
| **즉시** | B morning brief | 없음 | SENDGRID 동일 | 출시 직전 |
| **즉시** | B brag_card 생성 (발송 X) | 없음 | 없음 | 출시 직전 |
| **즉시** | E 분류 + 초안 | 없음 (Q-S4 fix 진행) | KoBERT-light | 출시 직전 |
| **Q-S1 후** | B nudge + brag 발송 | Q-S1 | SENDGRID | 변호사 답변 + 7d |
| **Q-S1 후** | D 7d/14d retention | Q-S1 | SENDGRID + BREVO | 변호사 답변 + 7d |
| **Q-S1 + Q-S3 후** | C upgrade nudge | Q-S1 + Q-S3 | Stripe live | 변호사 답변 + 14d |
| **Q-S1 + Q-S3 후** | C 가격 A/B | Q-S3 | Stripe live | 변호사 답변 + 30d |
| **Q-S1 + Q-S3 후** | D 30d incentive | Q-S1 + Q-S3 | Stripe + SENDGRID | 변호사 답변 + 30d |
| **Q-M1 후** | A 광고 집행 | Q-M1 | 별도 광고 예산 | 변호사 답변 + 별도 budget |
| **1000+ 유저** | 6.1 Self-Pricing | Q-S3 | Stripe + 통계 | D+180 |
| **출시 후** | 6.2 Self-Discovering | 없음 (분석만) | Plausible self-host | 출시 + 60d |
| **출시 후 30d** | 6.3 Self-Marketing | Q-M1 (광고만) | UTM 6개월 누적 | 출시 + 60d |

---

## 8. CEO Inbox 일일 포맷 (목표)

```
[YYYY-MM-DD KST]

신규 결제: 3건 (Pro 2, Premium 1) — Stripe link
support 검토: 2건 (1초) — [link] [link]
A/B test: KEEP (Pro ₩9,900, 14d 표본 부족)
이슈: 없음

[24h batch]
- A: 카피 톤 "공격적 → 친근" 제안 (UTM CTR 검증 데이터)
- B: questionnaire D+3 nudge 카피 2종 A/B 시작 제안
- C: 가격 A/B 6개월 cooldown 잔여 3개월

[escalation]
- 없음
```

**CEO 소요 시간 목표**: 일일 30초 ~ 2분.

---

## 9. 0원 검증 (`feedback_no_extra_cost`)

| 자원 | 사용처 | 비용 |
|------|--------|------|
| Max | Loop E 응답 초안 (월 ~500건 @ 1000 유저) | ₩0 (Max 한도 내) |
| Railway PostgreSQL | 모든 Loop 데이터 | ₩0 (현 HOBBY) |
| SendGrid free | 100/day = 3000/월 (Loop B/C/D) | ₩0 (1000 유저까지) |
| Brevo free | 300/day fallback | ₩0 |
| ImprovMX free | 수신 | ₩0 |
| Plausible self-host | UTM / 이벤트 | ₩0 (Railway 동일 서버) |
| KoBERT-light free model | Loop A 댓글 감정 / Loop E 분류 | ₩0 (로컬 inference) |
| Stripe | Loop C (출시 후) | ₩0 (수수료만, 별도 비용 X) |
| **합계** | | **₩0** |

**한계 시점**:
- 5000+ 유저 → SendGrid/Brevo free 초과 → 결제 발생 (별도 CEO 결정)
- 5000+ 유저 → Anthropic API direct 월 $30+ → 별도 budget 결정
- 모든 추가 비용 발생 시점은 **사후 CEO 결정**, 사전 자동 결제 X

---

## 10. 출시 직전 액션 (코드/배포 X, spec 합의만)

본 문서는 **spec only**. 실제 코드 활성화는:
1. CEO 본 문서 검토 후 OK → 별도 wave에서 메모리 `growth_experiments.md` + `marketing_copy.md` + `legal_question_queue.md` 동기화
2. 출시 직전 Loop B welcome 메일 변호사 1순위 확인
3. Q-S1 답변 도착 시 별도 wave에서 Loop B nudge / D 7d/14d ON
4. Q-S3 답변 도착 시 별도 wave에서 Loop C 결제 funnel ON
5. Q-M1 답변 도착 시 별도 wave에서 Loop A 광고 ON

**현 wave에서는 코드 변경 / push / commit / Stripe activate 일절 없음.**

---

## 11. 메모리 / 문서 연결

- `growth_experiments.md` — Loop A/B 결과 누적, A/B test winner
- `marketing_copy.md` — Loop A content-bank, Loop B/D 카피
- `product_features.md` — Loop E feature 후보, 6.2 Self-Discovering 결과
- `legal_question_queue.md` — Q-S1/Q-M1/Q-S3/Q-S4 답변 도착 시 Loop ON trigger
- `legal_pipa_saas_inventory.md` — Loop D 60d archive 시 PIPA 8개 외부 SaaS 통보 의무 검토
- `finance_token_ops.md` — Loop E Anthropic API direct 비용 추적
- `INCIDENT_RUNBOOK.md` — Stripe 챠지백, support 24h 초과 escalation
- `customer_feedback.md` — Loop E feature request 자동 누적 결과

---

## 12. 한 줄 요약

**v57-C3 = AI가 SaaS funnel 7단계를 자율 운영. CEO는 inbox 일일 30초 ~ 2분.**
**변호사 BLOCKER 3건 (Q-S1, Q-S3, Q-M1) 해소 단계별로 Loop ON.**
**현재 활성 가능: Loop A organic + Loop B welcome/morning brief/brag_card + Loop E 분류·초안.**
**Q-S1 해소 후: Loop B nudge + Loop D 7d/14d.**
**Q-S3 해소 후: Loop C 결제 funnel.**
**Q-M1 해소 후: Loop A 광고 (별도 budget).**
**모든 단계 0원 (Max + Railway + free tier 내).**
