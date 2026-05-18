# 자본시장법 §101 면제 트랙 유지 결정문 (변호사 자문 첨부 자료)

**작성일**: 2026-05-18
**원본 SoT**: `~/.claude/projects/.../memory/legal_decision_no_advisory.md` (CEO 2026-05-04 확정)
**대상**: 금융규제·자본시장법 전문 변호사
**목적**: §101 면제 트랙 정합성 사인 요청

---

## 1. CEO 결정 (2026-05-04 확정)

**유사투자자문업 신고/등록 안 함**

---

## 2. 결정 사유 (Why)

- 자본시장법 §101 신고 의무를 **면제받는 트랙**으로 유지 결정
- 2026-04-29 §101 면제 트랙 채택 시점부터 일관 (HANDOVER v11)
- **"Personal Capital 모델"** — 자기 데이터 한정 PFM(Personal Finance Management) 도구로 포지셔닝

---

## 3. §101 면제 트랙 4요건 (PivoxQuant 정합성 자체 검증)

| 요건 | 현재 PivoxQuant 적용 |
|---|---|
| ① **광고 없음** | 외부 광고 X, organic + 추천 only. 마케팅 카피 `forbidden_terms.py` 패턴 필터링 |
| ② **매월 청구 없음** | ⚠️ Pro ₩9,900/월 + Premium ₩19,900/월 = 월 구독 → 변호사 자문 Q7 (SaaS 구독료 = "자문료 아님" 명시 필요성) |
| ③ **특정성 회피** | 본인 보유 종목 한정 분석. 챗봇 X, 양방향 Q&A X. → 변호사 자문 Q13 |
| ④ **일반화된 정보 제공만** | "이 종목 매수/매도" 직접 권유 X. 단, `services/ai/service.py:238` rec_shares 구체 수량 표시 = 회색지대 → 변호사 자문 Q10 |

**현재 상태**: 4요건 중 ②③④ 모두 회색지대 존재 — 변호사 의견서 사인 필요

---

## 4. 적용 방침 (How to apply)

1. **모든 신규 feature** 는 §101 면제 조건 안에서 설계
   - 자기 데이터 한정
   - 불특정 다수 대상 정보 제공 X
   - 1:1 자문 X

2. **HANDOVER 내 "유사투자자문업 신고 ⏳ 로펌 Q9 답 대기" 항목은 기각 처리**

3. **변호사 상담 방향**: "신고 여부 검토"가 아니라 **"면제 적정성 사인"** 받는 방향

4. **면제 트랙 방어선** (그대로 유지·강화):
   - `legal_filter` — 입력/출력 필터
   - `forbidden_terms.py` — BUY/SELL/HOLD/추천 등 금지어 차단
   - `DisclaimerBanner` — 분석·시그널 페이지 의무 표시
   - **Pre-Trade Friction** — 거래 직전 면책 모달 강제

---

## 5. 출시 후 4요건 유지 모니터링 메커니즘

**자동화 agent**: `compliance-gatekeeper` (B-1)
- 매 PR diff 검사 — §101 4요건 위반 패턴 자동 차단
- 신규 surface(페이지/컴포넌트) 추가 시 DisclaimerBanner 누락 게이트
- `forbidden_terms.py` 패턴 회귀 게이트 (CI)

**증거 수집** (`compliance-evidence` skill — 분기별 스냅샷):
- 광고 없음 증거
- 매월 청구 없음 증거 (구독료 = 자문료 아님 약관 명시)
- 특정성 회피 증거 (Artifact 본인 종목 한정 코드 경로)
- 일반화된 정보 제공만 증거 (forbidden_terms 차단 로그)

---

## 6. 변호사 검증 요청 (핵심 질문)

### Q. 본 결정이 자본시장법 §101 면제 트랙에 정합한가?

**구체 검증 포인트**:
1. **②번 요건** — Pro ₩9,900/월 + Premium ₩19,900/월 월 구독이 §101 ② "매월 청구" 해석상 자문료 청구로 분류되는가? 약관에 "구독료 = 자문 대가가 아니다" 직설 명시로 면제 유지 가능한가? → **Q7 연결**

2. **③번 요건** — 현재 운영 중인 `companion`, `ai-chat`, `pre-trade` surface가 "양방향 채널"로 해석될 수 있는가? Artifact 단방향 푸시는 안전 트랙임이 확실한가? → **Q13 연결**

3. **④번 요건** — `services/ai/service.py:238` "Suggested position size: N shares (~$X)" 구체 수량/금액 출력이 "일반화된 정보 제공" 회피 구조와 충돌하는가? 면책 첨부만으로 충분한가? → **Q10 연결**

4. **신규 규제 ② (유사투자자문업 양방향 채널 금지, 2024-08-14 시행)** 영향 — 현재 구조에서 즉시 §101 면제 깨질 surface 있는가? → 별첨 `regulatory-impact-2026-05.md` HIGH ② 참조

---

## 7. 변호사 의견서 후 조치 분기

### CASE A — §101 면제 트랙 정합성 PASS
- Stripe Live 결제 활성화 진행
- companion / ai-chat surface 그대로 유지
- 출시 D-day 진행

### CASE B — 부분 fix 필요 (회색지대 closure)
- 약관 §6.1 비자문업 면책에 "구독료는 자문 대가가 아니다" 직설 추가 (Q7)
- `services/ai/service.py:238` rec_shares 구체성 완화 (Q10)
- companion / ai-chat 인터페이스 단방향 보강

### CASE C — VIOLATION (면제 트랙 깨짐)
- 즉시 해당 surface 제거
- 유사투자자문업 신고 트랙으로 전환 검토 (5년 갱신 / 자본금 등 신규 요건 발생)
- 출시 일정 재조정

---

## 8. 관련 첨부 (본 디렉터리)

- `service-overview.md` — PivoxQuant 서비스 개요 (변호사 이해 돕기)
- `regulatory-impact-2026-05.md` — 신규 규제 7건 (특히 HIGH ② 양방향 채널 영향)
- `legal-questions-q1-q15.md` — Q7/Q10/Q13 상세

---

## 부록 — 원본 SoT 인용

```
## 결정 (2026-05-04 CEO 확인)
유사투자자문업 신고/등록 안 함

## Why
- 자본시장법 §101 신고 의무를 면제받는 트랙으로 유지 결정
- 2026-04-29 §101 면제 트랙 채택 시점부터 일관 (HANDOVER v11)
- "Personal Capital 모델" — 자기 데이터 한정 PFM 도구 포지셔닝

## How to apply
- 모든 신규 feature 는 §101 면제 조건 (자기 데이터 한정 /
  불특정 다수 대상 정보 제공 X / 1:1 자문 X) 안에서 설계
- HANDOVER 내 "유사투자자문업 신고 ⏳ 로펌 Q9 답 대기" 항목은
  기각 상태로 처리
- 변호사 상담 시 "신고 여부 검토"가 아니라 "면제 적정성 사인"
  받는 방향
- legal_filter / forbidden_terms / DisclaimerBanner /
  Pre-Trade Friction 등 면제 트랙 방어선은 그대로 유지·강화
```

(출처: `~/.claude/projects/-Users-seanbae-Desktop---/memory/legal_decision_no_advisory.md`, 2026-05-04)
