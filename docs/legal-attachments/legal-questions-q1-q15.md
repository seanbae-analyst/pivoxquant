# 변호사 자문 큐 Q1-Q15 (출시 전 일괄 의견서)

**작성일**: 2026-05-18
**원본 SoT**: `~/.claude/projects/.../memory/legal_question_queue.md` (last_updated 2026-05-10)
**상태**: pending CEO 변호사 미팅 예약
**예상 의견서 비용**: 300-500만원
**대상**: 금융규제·자본시장법 전문 변호사 (Kim & Chang / 율촌 / 광장 등 소형 분사 사무소도 가능)

---

## 우선순위 P0 (출시 차단 — 유료 결제 시작 전 필수)

### Q5 — 사업자등록 미완 상태 가격 광고 (전자상거래법 §13)

**질문**: 출시 전 사업자등록증 + 통신판매업 신고 미완 상태에서 유료 가격 광고 (`/pricing`) + "Coming Soon" 명시만으로 전자상거래법 §13 회피 가능한지.

**PivoxQuant 컨텍스트**:
- 사업자등록 발급 완료 (2026-05-08, 459-01-03808)
- 통신판매업 신고 미완
- `/pricing` 페이지에 Pro ₩9,900 / Premium ₩19,900 가격 표시 + "Coming Soon" 배너
- **관련 코드/UI**: `frontend/src/app/pricing/page.tsx`

**출처**: legal_full_audit_final.md (v28)

---

### Q6 — Cross-border 동의 GDPR cross-cite (PIPA §28-8 + GDPR)

**질문**: 회원가입 시 cross_border 동의가 PIPA §28-8 + GDPR 수준 cross-cite 요건 충족하는지 (Anthropic / Stripe / Vercel / Railway 미국 이전).

**PivoxQuant 컨텍스트**:
- PR #167 LegalConsentModal cross_border + 마이그레이션 024 적용 완료
- 해외 이전 데이터 처리자: Anthropic (US), Stripe (US), Vercel (US), Railway (US)
- **관련 코드/UI**: `frontend/src/components/legal/LegalConsentModal.tsx`, DB 마이그레이션 024
- **연결 규제**: regulatory-impact-2026-05.md MEDIUM ④ (PIPA 매출 10% 과징금)

**출처**: legal_full_audit_final.md (v28)

---

### Q7 — SaaS 구독료 = "자문료가 아님" 직설 명시 (§101 면제 ② 강화)

**질문**: SaaS 구독료가 "자문료가 아님"을 약관에 직설 명시 필요한지 — §101 면제 ② 강화.

**PivoxQuant 컨텍스트**:
- terms-ko.md §6.1 비자문업 면책은 있으나 "**구독료는 자문 대가가 아니다**" 직설 없음
- Pro ₩9,900/월 + Premium ₩19,900/월 월 구독 구조
- **관련 코드/UI**: `frontend/src/app/legal/terms/page.tsx` 또는 `legal/terms-ko.md`
- **연결**: section-101-exemption-decision.md §101 ② 요건

**출처**: legal_full_audit_final.md (v28)

---

### Q8 — 사업자등록 업태 적합성

**질문**: 정보통신업 단일 업태로 SaaS 유료결제 (Stripe + Pro ₩9,900/mo)를 받을 때, 전자상거래법 / 부가가치세법 / 소득세법상 '판매' 또는 '용역공급'으로 분류되어 추가 업태 등재가 필요한지. 통신판매업 신고만으로 충분한지.

**PivoxQuant 컨텍스트**:
- **현재 등재**: 정보통신업 / 데이터베이스 및 온라인 정보 제공업 (단독)
- **legal audit 권고**: 전자상거래업 + 응용소프트웨어개발 및 공급업 추가 등재
- 사업자등록증 PDF: `/Users/seanbae/Desktop/취준/사업자등록증-pivoxquant.pdf` (별도 첨부)

**출처**: 2026-05-10 legal audit (v29)

---

### Q13 — Artifact 단방향 푸시 vs 양방향 채널 (regulatory ② 연결)

**질문**: "Artifact 단방향 푸시 = 양방향 채널 해당 안 됨" 변호사 사인 필수. 유사투자자문업 양방향 채널 금지 (2024-08-14 시행) 적용 범위 확정.

**PivoxQuant 컨텍스트**:
- **CRITICAL**: 챗봇 / Q&A / "이 종목 어떤가요?" 응답 도입 시 즉시 §101 면제 깨짐
- **현재 surface 검토 필요**: `companion`, `ai-chat`, `pre-trade` 페이지
- Artifact (Weekly Memo / Brag Card / Earnings Pre-Brief) = 정기 발송형 (단방향)
- **관련 코드/UI**:
  - `frontend/src/app/companion/*`
  - `frontend/src/app/ai-chat/*`
  - `frontend/src/app/pre-trade/*`
- **연결**: regulatory-impact-2026-05.md HIGH ②

**출처**: regulatory_changes_2026-05.md HIGH ②

---

## 우선순위 P1 (출시 권고 fix)

### Q9 — 만 14세 자가선언 단일 체크박스 (PIPA §22 ⑥)

**질문**: 만 14세 미만 가입 차단을 자가선언 단일 체크박스로 운영하는 것이 PIPA §22 ⑥항 충족하는지. OAuth 로그인 1차 방어 + 자가선언 결합으로 실무 수준 충분한지.

**PivoxQuant 컨텍스트**:
- 현재: `signup_v2/page-v2.tsx:404-411` `agree_age` 체크박스 단일
- OAuth (Google/Kakao) 1차 방어 + 자가선언 결합

**출처**: 2026-05-10 legal audit F WARN

---

### Q10 — rec_shares 구체성 (§101 ④)

**질문**: `services/ai/service.py:238` "Suggested position size: N shares (~$X)" — `rec_shares` 구체 수량·금액 출력이 §101 ④ "일반화된 정보 제공" 회피 구조와 충돌하는지.

**PivoxQuant 컨텍스트**:
- 현재: numerical specificity. 면책 첨부됐으나 회색지대.
- Suggested position size 출력 — 특정 수량/금액 명시
- **관련 코드**: `services/ai/service.py:238`
- **연결**: section-101-exemption-decision.md §101 ④ 요건

**출처**: 2026-05-10 legal audit A WARN

---

### Q11 — Free 사용자 손해배상 한도 (약관규제법 §7)

**질문**: 약관규제법 §7 손해배상 한도 (terms-ko.md:223 "직전 6개월 결제액") — Free 사용자 (₩0) 적용 시 무효 가능성. Free / 유료 분리 한도 작성 필요한지.

**PivoxQuant 컨텍스트**:
- 현재: 단일 한도 적용 (Free=₩0 → 한도 0원 무효 가능성)
- terms-ko.md:223 "직전 6개월 결제액"
- 3-tier 구조 (Free / Pro ₩9,900 / Premium ₩19,900)

**출처**: 2026-05-10 legal audit C WARN

---

### Q14 — AI 생성물 라벨링 적용 방식 (regulatory ③ 연결)

**질문**: Artifact 템플릿 "AI 생성" 배지 적용 방식 변호사 확인. 워터마크 / 자막 / 텍스트 라벨 중 표시광고법 (2026-01 시행) 충족 형식.

**PivoxQuant 컨텍스트**:
- Weekly Memo / Brag Card / Earnings Pre-Brief 모든 Artifact = AI 생성물
- 기존 disclaimer ("AI 분석") 외에 시각적 명확 라벨 추가 필요
- **연결**: regulatory-impact-2026-05.md HIGH ③

**출처**: regulatory_changes_2026-05.md HIGH ③

---

### Q15 — 가분적 디지털콘텐츠 월구독 환불 (regulatory ⑥ 연결)

**질문**: Pro / Premium 월 구독이 "가분적 디지털콘텐츠"로 해석되어 월 중도 해지 시 미사용분 환불 의무 발생하는지. terms-ko.md §17 환불 정책 갱신 방향.

**PivoxQuant 컨텍스트**:
- **시행**: 2026-07-21
- Pro ₩9,900/월 + Premium ₩19,900/월 월 구독
- terms-ko.md §17 14일 청약철회 단서 재검토 필요
- **연결**: regulatory-impact-2026-05.md MEDIUM ⑥

**출처**: regulatory_changes_2026-05.md MEDIUM ⑥

---

## 기존 큐 유지 (2026-04-20 legal_full_audit_final.md)

### Q1-Q4 — 마이데이터 / 신용정보법 §32 회색지대

**질문**: KIS read-only 단일 broker (Alpaca BYO + KIS) 모델이 마이데이터 §22의9 신고 의무 회피 가능한지.

**PivoxQuant 컨텍스트**:
- KIS API: read-only (시세 + 본인 계좌 조회만)
- Alpaca: BYO 키 (사용자 본인 키 입력 — 서비스 보관 없음)
- 신용정보법 §22의9 마이데이터 사업자 등록 X
- **상세**: legal_full_audit_final.md §A-2

---

## 시행령 추적 (재점검 일정)

### Q12 — 정통망법 §50 매출 6% 과징금 시행령 (regulatory ① 연결)

**질문**: 시행령 확정 시 opt-out 처리 시한 정확치 + 2년 주기 수신동의 재확인 자동화 구현 방식.

**PivoxQuant 컨텍스트**:
- **시행 예상**: 2026-Q3 (공포 후 6개월)
- **재스캔**: 2026-08-15
- **확인 항목**: opt-out 처리 시한 (통상 14일) / 2년 주기 수신동의 재확인 자동화
- **관련 코드**: `services/email/sender.py:100` (EmailSender, PR #5886fe0)
- **연결**: regulatory-impact-2026-05.md HIGH ①

**출처**: regulatory_changes_2026-05.md HIGH ①

---

## CEO 액션

### 변호사 미팅 준비 (예상 300-500만원, 1회 의견서)

- **자문 범위**: Q1-Q15 일괄 의견서 요청
- **전문 분야**: 금융규제·자본시장법 전문 변호사 (Kim & Chang / 율촌 / 광장 등 소형 분사 사무소도 가능)

### 첨부 자료 (4종)
1. **사업자등록증 PDF** (459-01-03808) — `/Users/seanbae/Desktop/취준/사업자등록증-pivoxquant.pdf`
2. **`service-overview.md`** — PivoxQuant 서비스 개요 (별첨)
3. **`section-101-exemption-decision.md`** — §101 면제 트랙 결정문 (별첨)
4. **`regulatory-impact-2026-05.md`** — 신규 규제 7건 영향도 (별첨)
5. **`legal-questions-q1-q15.md`** — 본 문서

### 의견서 수령 후 분기
- **VIOLATION** 시 → 즉시 fix 또는 surface 제거
- **PASS** 시 → cross_border 동의 + §101 명시 + 업태 적합성 사인 → **Stripe Live 활성화 진행**

---

## 변경 이력 (원본 SoT)

- 2026-05-10 (v29): Q9-Q15 신규 추가 (legal audit + regulatory monitor 결과)
- 2026-04-20 (v28 baseline): Q1-Q4 (legal_full_audit_final.md), Q5-Q7 (legal_full_audit_final.md), Q8 (사업자등록 발급 후 신규)

---

## 우선순위 매트릭스 (변호사 답변 순서 권고)

| 순위 | 질문 | 차단 영향 |
|---|---|---|
| 1 | Q13 | §101 면제 트랙 깨짐 위험 (즉시 surface 제거) |
| 2 | Q7 | §101 면제 ② 요건 강화 — 약관 직설 필수 |
| 3 | Q8 | Stripe Live 결제 분류 — 업태 등재 추가 여부 |
| 4 | Q5 | 통신판매업 신고 — 결제 활성화 직접 차단 |
| 5 | Q6 | PIPA cross-border — 9월 시행 전 정합 |
| 6 | Q10 | §101 ④ 회색지대 closure |
| 7 | Q14 | AI 생성물 라벨링 — 즉시 fix 가능 |
| 8 | Q15 | 환불 정책 — 7월 시행 전 약관 갱신 |
| 9 | Q11 | Free 사용자 손배 한도 분리 |
| 10 | Q9 | 만 14세 자가선언 충분성 |
| 11 | Q12 | 시행령 확정 후 재스캔 (8월) |
| 12 | Q1-Q4 | 마이데이터 회색지대 (기존) |
