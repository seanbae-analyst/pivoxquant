# DRAFT — 개인정보처리방침: Journal Companion 섹션

**작성일**: 2026-04-23
**상태**: 로펌 검토 전 **1차 초안** (LAW FIRM REVIEW PENDING)
**삽입 위치**: 기존 `frontend/src/app/privacy/page.tsx` 본문의 8조(Contact) **직전**에 신규 9조로 삽입
**적용 대상**: Journal Companion 기능 (SAFE_FEATURE_SPECS §6)
**언어 원칙**: 기존 방침이 영문 단일인 반면, 본 섹션은 **한글+영문 병기**로 작성 (PIPA §30①1호 — 국내 거주자 대상 서비스 이해 용이성 제고). 변호사 최종 승인 시 기존 조항도 한글 병기로 확장 권고.

> **법적 고지 (초안 전용)**: 본 문서는 변호사 검토 전 내부 draft 입니다. 외부 공개·배포·프로덕션 반영 금지.

---

## 9. Journal Companion 관련 개인정보 처리 (신규 섹션)

### 9.1. 수집 항목 (Categories of Personal Data Collected)

**[한글]**
회사는 Journal Companion 기능 제공을 위해 아래 정보를 수집·처리합니다. (근거: 개인정보보호법 제15조 제1항 제1호·제4호, 제16조 수집 최소화 원칙)

| 구분 | 항목 | 형식 |
|---|---|---|
| 필수 | user_id (가명화 식별자) | sha256 hash 값 |
| 필수 | persona_code | 온보딩 20문항 결과 분류 코드 (예: "A3", "B1") |
| 필수 | 거래 이력 proxy | 섹터 버킷(sector bucket) + 금액 구간(amount bin, 예: 0~1천만원) + 보유기간 일수 |
| 필수 | 투자 일지 (Investment Journal) | 이용자가 직접 작성한 자유 텍스트 |
| 필수 | IPS(Investment Policy Statement) 선언 | 이용자가 직접 작성한 자기 투자원칙 텍스트 |
| 필수 | AI 응답 메타데이터 | request_id, verdict(응답 유형), 응답 길이, 응답 시각 |

회사는 이용자의 **실명·주민등록번호·계좌번호·원본 거래가격**을 Journal Companion 처리 경로에 포함시키지 않습니다.

**[English]**
For the Journal Companion feature, the Company collects and processes the following categories of data. (Legal basis: PIPA Art. 15(1)(i)(iv) and Art. 16 data-minimization principle.)

The Company does **not** include real names, Korean Resident Registration Numbers, brokerage account numbers, or raw transaction prices in any Journal Companion processing pipeline.

---

### 9.2. 수집·이용 목적 (Purposes)

**[한글]**
(근거: 개인정보보호법 제15조 제1항, 제17조, 제18조)

1. **자기 기록 재표시 (Own-record playback)** — 이용자가 과거에 작성한 일지·IPS를 원문 그대로 되돌려주기 위함
2. **거래 패턴 미러링 (Behavior mirroring)** — 이용자 본인의 과거 거래 패턴(보유기간·회전율 등)을 숫자로 재표시
3. **자기 질문 유도 (Self-questioning prompts)** — 이용자가 스스로에게 던질 만한 질문을 제시 (판단·평가·권유 목적 아님)
4. **감사 로그 (Regulatory audit log)** — AI 요청/응답의 재현 가능성 확보 및 규제 대응 (보유기간 2년)

회사는 Journal Companion 수집 정보를 **투자 자문·광고 타겟팅·타 이용자 프로파일링·외부 판매** 목적으로 사용하지 않습니다.

**[English]**
Legal basis: PIPA Arts. 15(1), 17, 18. The Company does **not** use Journal Companion data for investment advisory, advertising targeting, cross-user profiling, or external sale.

---

### 9.3. 보유 및 이용 기간 (Retention)

**[한글]**
(근거: 개인정보보호법 제21조 파기 원칙, 제29조 안전성 확보조치)

| 데이터 | 보유기간 | 파기 방법 |
|---|---|---|
| AI audit 로그 (request/response 메타) | **2년** — 자본시장법령상 분쟁 대응 목적 | 기간 경과 즉시 DB 물리 삭제 + 백업 24시간 내 동기 삭제 |
| 거래 이력 proxy (sector bucket + amount bin) | **90일 sliding window** | 매일 01:00 KST purge job 자동 삭제 |
| 투자 일지 본문 / IPS 선언 | **이용자 계정 유지 기간** (이용자 삭제 요청 시 즉시) | 이용자 1-click 삭제 요청 수신 시 30일 내 백업 포함 완전 파기 |
| Waitlist 이메일 | 이용자 삭제 요청 수신 **즉시** | request 수신 즉시 DB delete |

**[English]**
Legal basis: PIPA Arts. 21 (destruction) and 29 (technical safeguards). Any request for erasure triggers DB deletion within 24 hours and backup deletion within 30 days (GDPR-parity).

---

### 9.4. 제3자 처리위탁 (Third-party Processors)

**[한글]**
(근거: 개인정보보호법 제26조 처리위탁, 제28조의8 국외이전)

회사는 Journal Companion AI 응답 생성을 위해 다음 처리자에게 개인정보 처리를 위탁합니다.

| 수탁자 | 국가 | 위탁업무 | 전송 항목 | 근거 |
|---|---|---|---|---|
| Anthropic PBC | 미국 (California) | Claude API 기반 자연어 응답 생성 | **가명화된 payload**: persona_code + sector bucket + amount bin + 이용자 작성 텍스트 (실명/이메일/계좌번호 **제외**) | PIPA §28조의8 제1항 제1호 (이용자 동의) + Transfer Impact Assessment (TIA) 별도 문서 링크 |

위탁 계약서(DPA)에는 (a) 보안 조치 수준, (b) 재위탁 금지, (c) 침해 통지 72시간 의무, (d) 모델 학습 목적 이용 금지 조항이 포함됩니다.

**[English]**
Legal basis: PIPA Arts. 26 and 28-8. A Data Processing Agreement (DPA) with Anthropic PBC limits processing to response generation, prohibits re-transfer, mandates 72-hour breach notification, and forbids use of user content for model training.

---

### 9.5. 민감정보 처리 여부 (Sensitive Data)

**[한글]**
(근거: 개인정보보호법 제23조 민감정보 처리 제한)

Journal Companion 은 **민감정보를 수집·처리하지 않습니다**. 이용자가 자발적으로 일지에 감정·심리·건강 정보를 기록하더라도, 회사는 해당 정보를 (a) 민감정보로 재분류하지 않으며, (b) 감정분석·심리평가 목적으로 가공하지 않습니다.

단, 향후 회사가 **명시적 감정/심리 지표 수집 기능**을 추가하는 경우 별도 동의 창과 민감정보 처리 특례 고지를 제공합니다 (개인정보 영향평가(PIA) 선행 수행).

**[English]**
Legal basis: PIPA Art. 23. Journal Companion does **not** process sensitive categories of data. Any future addition of affect/sentiment-scoring will require a separate opt-in and a prior PIA.

---

### 9.6. 이용자 권리 (User Rights)

**[한글]**
(근거: 개인정보보호법 제35조 열람권, 제36조 정정·삭제권, 제37조 처리정지권, 제39조의8 손해배상)

이용자는 아래 권리를 `/settings/privacy` 페이지의 **1-click 인터페이스**를 통해 행사할 수 있습니다.

| 권리 | 근거 | 실행 UI |
|---|---|---|
| 열람권 | §35 | "내 데이터 전부 보기" 버튼 → JSON/CSV export |
| 정정권 | §36 | 일지 본문 직접 수정 (원문 업데이트) |
| 삭제권 | §36 | "Journal Companion 데이터 전부 삭제" 버튼 (즉시 큐잉 + 30일 내 백업 포함 완전 파기) |
| 처리정지권 | §37 | "AI 처리 중지" 토글 (향후 전송 차단) |
| 동의 철회 | §15·§22 | "Journal Companion 동의 철회" 버튼 (기존 데이터 일괄 삭제 연동) |

**[English]**
Legal basis: PIPA Arts. 35–37, 39-8. All rights are exercisable via 1-click controls in `/settings/privacy`.

---

### 9.7. Local-first 원칙 (Local-first Memory)

**[한글]**
Journal Companion 이용자 대화 이력은 **기본적으로 이용자 기기의 브라우저 로컬 저장소(localStorage/IndexedDB)에만 저장**됩니다. 서버 저장(클라우드 동기화)은 이용자가 Settings 에서 **명시적으로 옵트인**한 경우에만 활성화됩니다. 서버 동기화 시에도 이용자 기기에서 생성된 passphrase 기반 AES-GCM 암호문만 전송되며, 회사는 복호화 키를 보관하지 않습니다 (End-to-End 암호화).

**[English]**
Journal Companion conversation history is stored **by default only in the user's device** (localStorage/IndexedDB). Server-side synchronization is strictly opt-in and uses end-to-end AES-GCM encryption with a user-held passphrase; the Company does not retain decryption keys.

---

### 9.8. 자동화된 결정 (Automated Decision-making)

**[한글]**
(근거: 개인정보보호법 제37조의2 자동화된 결정에 대한 대응권, 2024-03 신설)

Journal Companion 은 **투자 결정을 자동화하지 않습니다.** AI 응답은 (a) 이용자 자기 기록의 재표시, (b) 이용자 거래 패턴 숫자 미러링, (c) 이용자 자기 질문 유도에 한하며, 매수·매도·보유·종목·가격·시점에 관한 자동화된 권유·제안·예측을 생성하지 않습니다.

이용자는 언제든 AI 응답에 대해 (a) 설명 요구, (b) 이의 제기, (c) 처리 거부를 `/settings/privacy` 를 통해 행사할 수 있습니다.

**[English]**
Legal basis: PIPA Art. 37-2 (new 2024-03). Journal Companion does **not** make automated investment decisions. Users may demand explanation, object, or opt out at any time.

---

### 9.9. 쿠키 및 추적 (Cookies and Tracking)

**[한글]**
Journal Companion 은 별도의 추적 쿠키를 설정하지 않습니다. 기존 세션 쿠키 정책(본 방침 제5조)만 적용됩니다. AI 응답 요청/응답 로그는 서버측 DB 에 저장되며 클라이언트 쿠키를 이용하지 않습니다.

**[English]**
Journal Companion does not set additional tracking cookies. Only the existing session-cookie policy (§5) applies.

---

### 9.10. 연령 제한 (Age Restriction)

**[한글]**
(근거: 개인정보보호법 제22조의2 아동 동의, 자본시장법 유사투자자문업 신고기준)

Journal Companion 기능은 **만 19세 이상** 이용자에게만 제공됩니다. 만 19세 미만 이용자의 Premium Plus 구독은 허용되지 않으며, 동 기능은 entitlement 레이어에서 차단됩니다.

**[English]**
Journal Companion is available only to users aged 19 or older (Korean legal adulthood). Users under 19 are blocked at the entitlement layer.

---

### 9.11. 개인정보 보호책임자 및 문의 (Contact)

**[한글]**
Journal Companion 관련 개인정보 관련 문의: **seanbae1521@gmail.com**
개인정보 침해 신고: 개인정보보호위원회 (privacy.go.kr / 국번 없이 182)

**[English]**
Contact: seanbae1521@gmail.com. Complaints may be filed with the Personal Information Protection Commission (privacy.go.kr).

---

**본 초안 종료. 로펌 검토 후 최종본에서 조항 번호 재정리 예정.**
