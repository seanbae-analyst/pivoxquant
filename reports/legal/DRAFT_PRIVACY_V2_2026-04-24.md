# DRAFT V2 — 개인정보처리방침: KIS 계좌 연동 + Journal Companion (Option C 반영)

**작성일**: 2026-04-24
**상태**: 로펌 검토 전 **2차 초안** (LAW FIRM REVIEW PENDING)
**버전**: V2 (V1 = `DRAFT_PRIVACY_POLICY_COMPANION_2026-04-23.md`, 보존)
**주요 변경**: Option C (Alpaca 제거 + KIS 단일 연동) 확정에 따른 조항 재정리
**삽입 위치**: 기존 `frontend/src/app/privacy/page.tsx` / `frontend/src/content/privacy-ko.md` 본문의 Contact 조항 **직전**에 신규 섹션 9(Journal Companion) + 신규 섹션 10(KIS 계좌 연동) 으로 삽입
**언어 원칙**: 한글+영문 병기

> **법적 고지 (초안 전용)**: 본 문서는 변호사 검토 전 내부 draft 입니다. 외부 공개·배포·프로덕션 반영 금지.

---

## 9. Journal Companion 관련 개인정보 처리

> V1 과 동일한 내용 유지 + Anthropic PBC 처리위탁 항목은 그대로 유지 (Journal Companion 은 Claude API 사용).

### 9.1. 수집 항목 (Categories)

| 구분 | 항목 | 형식 |
|---|---|---|
| 필수 | user_id (가명화 식별자) | sha256 hash 값 |
| 필수 | persona_code | 온보딩 20문항 결과 분류 코드 |
| 필수 | 거래 이력 proxy | 섹터 버킷 + 금액 구간 + 보유기간 일수 |
| 필수 | 투자 일지 (Investment Journal) | 이용자가 직접 작성한 자유 텍스트 |
| 필수 | IPS(Investment Policy Statement) 선언 | 이용자가 직접 작성한 자기 투자원칙 텍스트 |
| 필수 | AI 응답 메타데이터 | request_id, verdict, 응답 길이, 응답 시각 |

회사는 이용자의 **실명·주민등록번호·계좌번호·원본 거래가격**을 Journal Companion 처리 경로에 포함시키지 않습니다.

(근거: 개인정보보호법 제15조 제1항 제1호·제4호, 제16조 수집 최소화)

### 9.2. 수집·이용 목적

1. 자기 기록 재표시 (Own-record playback)
2. 거래 패턴 미러링 (Behavior mirroring)
3. 자기 질문 유도 (Self-questioning prompts)
4. 감사 로그 (Regulatory audit log, 보유 2년)

투자 자문·광고 타겟팅·타 이용자 프로파일링·외부 판매 목적 사용 **금지**.

(근거: PIPA 제15조 제1항, 제17조, 제18조)

### 9.3. 보유 및 이용 기간

| 데이터 | 보유기간 | 파기 방법 |
|---|---|---|
| AI audit 로그 | **2년** | 기간 경과 즉시 DB 물리 삭제 + 백업 24시간 내 동기 삭제 |
| 거래 이력 proxy | **90일 sliding window** | 매일 01:00 KST purge job |
| 투자 일지 / IPS 선언 | **계정 유지 기간** | 이용자 삭제 요청 수신 시 30일 내 백업 포함 완전 파기 |
| Waitlist 이메일 | 삭제 요청 즉시 | DB delete 즉시 |

### 9.4. 제3자 처리위탁 (Journal Companion 용)

| 수탁자 | 국가 | 위탁업무 | 전송 항목 | 근거 |
|---|---|---|---|---|
| Anthropic PBC | 미국 (California) | Claude API 기반 자연어 응답 생성 | 가명화된 payload (persona_code + sector bucket + amount bin + 이용자 작성 텍스트) — 실명/이메일/계좌번호 **제외** | PIPA §28조의8 제1항 제1호 + TIA |

DPA: (a) 보안 수준, (b) 재위탁 금지, (c) 72시간 침해 통지, (d) 모델 학습 이용 금지.

### 9.5. 민감정보 처리 여부
Journal Companion 은 민감정보를 수집·처리하지 않습니다. (PIPA §23)

### 9.6. 이용자 권리
`/settings/privacy` 1-click UI 로 열람·정정·삭제·처리정지·동의철회 가능. (PIPA §35~§37, §39-8)

### 9.7. Local-first 원칙
대화 이력은 기본적으로 기기 localStorage/IndexedDB 에만 저장. 서버 동기화는 명시적 opt-in + E2E AES-GCM 암호화.

### 9.8. 자동화된 결정
투자 결정 자동화 **없음**. (PIPA §37-2)

### 9.9. 쿠키 및 추적
추가 추적 쿠키 없음.

### 9.10. 연령 제한
만 19세 이상만 이용 가능.

---

## 10. KIS 계좌 연동 관련 개인정보 처리 (신규 V2)

> **[Option C 반영]** 본 섹션은 Alpaca 연동을 대체하는 KIS 단일 연동 조항. Alpaca 관련 모든 개인정보 처리 항목은 **삭제 처리**.

### 10.1 수집 항목 (Categories of Personal Data Collected for KIS Integration)

**[한글]**
(근거: 개인정보보호법 제15조 제1항 제1호·제4호, 제16조 수집 최소화 원칙, 전자금융거래법 제6조)

회사는 이용자가 `/settings/integrations` 에서 KIS 계좌 연동을 명시적으로 신청한 경우에 한해 다음 정보를 수집·처리합니다.

| 구분 | 항목 | 형식 | 보관 방법 |
|---|---|---|---|
| 필수 | KIS Open API **App Key** | 문자열 (이용자가 KIS 홈페이지에서 발급) | **AES-256-GCM 암호화** DB 저장 |
| 필수 | KIS Open API **App Secret** | 문자열 (이용자가 KIS 홈페이지에서 발급) | **AES-256-GCM 암호화** DB 저장 |
| 필수 | KIS **계좌번호** (account_no) | 숫자 (예: 12345678-01) | 마스킹 표시(앞 6자리 노출 + 뒷자리 * 처리), 원본은 암호화 저장 |
| 필수 (조회시점) | **잔고 정보** | 예수금·가용금·총평가금액 | 메모리 캐시 (TTL 30초, 영구 저장 안함) |
| 필수 (조회시점) | **보유 포지션** | 종목코드·수량·평균단가·평가손익 | 메모리 캐시 (TTL 30초, 영구 저장 안함) |
| 선택 | **주문 체결 이력** | 체결일시·종목·수량·단가·수수료 | 이용자 명시 요청 시에만 조회, **최대 90일 sliding window** 로 DB 저장 |

회사는 이용자의 **주민등록번호·실명·연락처·주소 등 KIS 에 등록된 고객 원본 정보**는 수집하지 않습니다. KIS Open API 는 설계상 이러한 정보를 반환하지 않습니다.

**[English]**
Legal basis: PIPA Arts. 15(1)(i)(iv) and 16 (data minimization); Electronic Financial Transactions Act Art. 6. The Company collects KIS Open API App Key/Secret, account number (masked display), balance (30s in-memory cache), positions (30s in-memory cache), and — if explicitly requested — execution history (90-day sliding window). The Company does **not** collect KIS-side customer master data (real name, RRN, phone, address), which are not exposed by the KIS Open API.

---

### 10.2 수집·이용 목적 (Purposes)

**[한글]**
(근거: 개인정보보호법 제15조 제1항, 자본시장법 비적용 — 회사는 투자중개업·투자매매업 수행 안함)

1. **포트폴리오 조회·시각화** — 이용자 본인의 보유 종목·잔고·평가손익을 PivoxQuant 대시보드에 표시
2. **성과 리포트 생성** — 이용자 개인의 수익률·리스크 지표·섹터 배분 분석 PDF 리포트 생성 (본인 열람 전용)
3. **Journal Companion 거래 패턴 미러링** — 이용자 본인의 거래 이력을 **가명화된 proxy(섹터 버킷·금액 구간)** 로 변환 후 Journal Companion 에서 자기 인식 유도 (원본 이력은 Claude API 로 전송되지 않음)
4. **Risk Defense 모니터링** — 이용자 본인 포트폴리오의 VaR·집중도·상관관계 계산 (전적으로 서버 내부, 외부 전송 없음)

회사는 KIS 연동 정보를 **투자 자문·광고 타겟팅·타 이용자 프로파일링·외부 판매·마케팅 수신 동의와 관계없는 마케팅 활용** 목적으로 **사용하지 않습니다**.

**[English]**
Purposes: (1) portfolio dashboard rendering, (2) personal performance report generation (for user's own viewing), (3) Journal Companion behavior mirroring using **only anonymized proxies** (sector bucket + amount bin — raw history is never transmitted to Claude API), (4) Risk Defense monitoring (server-internal only). KIS integration data is **never** used for investment advisory, ad targeting, cross-user profiling, external sale, or unrelated marketing.

---

### 10.3 보유 및 이용 기간 (Retention)

**[한글]**
(근거: 개인정보보호법 제21조 파기 원칙, 제29조 안전성 확보조치, 전자금융거래법 제22조 거래기록 5년 보관 예외)

| 데이터 | 보유기간 | 파기 방법 |
|---|---|---|
| KIS API 키 (App Key / App Secret) | **연동 해제 시 즉시** | 이용자 `/settings/integrations` 에서 "연동 해제" 클릭 시 DB 물리 삭제 + 백업 30일 내 완전 파기 |
| 계좌번호 (암호화 저장본) | **연동 해제 시 즉시** | 동일 |
| 잔고·포지션 정보 | **영구 저장 안함** (메모리 캐시 30초 TTL) | 캐시 만료 또는 프로세스 재시작 시 자동 소멸 |
| 주문 체결 이력 (선택 동의 시) | **90일 sliding window** | 매일 01:00 KST purge job 자동 삭제 |
| KIS 연동 audit 로그 (API 호출 기록 메타) | **2년** — 이용자 요청·분쟁 대응 목적 | 기간 경과 즉시 DB 삭제 |

**전자금융거래법 제22조 "거래기록 5년 보관" 예외**: 본 서비스는 **주문 체결 기능을 제공하지 않으므로** 전자금융거래 기록 생성 주체가 아니며, 동 조항의 보관 의무는 KIS(거래 체결 주체)에게 귀속됩니다. PivoxQuant 의 조회 로그는 참고 목적의 audit log 로 2년 보관합니다.

**[English]**
Legal basis: PIPA Arts. 21, 29; EFTA Art. 22 (5-year retention is **not applicable** — the Service does not execute trades and is therefore not the transaction-record issuer). Retention: API keys and account number deleted immediately upon disconnect (+30-day backup purge). Balance/position data is never persisted (30s in-memory cache only). Execution history (opt-in) uses a 90-day sliding window. KIS API audit logs retained 2 years for dispute resolution.

---

### 10.4 제3자 제공 및 처리위탁 (Third-party Disclosure / Processing)

**[한글]**
(근거: 개인정보보호법 제17조 제3자 제공, 제26조 처리위탁, 제28조의8 국외이전)

1. **KIS 관련 개인정보의 제3자 제공: 없음.**
   - 회사는 이용자의 KIS API 키·계좌번호·잔고·포지션·체결이력을 **어떠한 제3자에게도 제공하지 않습니다.**
   - 특히 **KIS Open API 로 수신한 시세·호가·체결 정보는 제3자에게 공유·배포되지 않습니다** (KIS Open API 이용약관 제4조~제6조 준수).
   - Anthropic PBC (Claude API) 에게 전송되는 Journal Companion payload 에도 KIS 원본 데이터는 포함되지 않으며, 오직 **가명화된 proxy(섹터 버킷·금액 구간)** 만 전송됩니다.

2. **인프라 처리위탁 (개인정보 저장 기반)**:

| 수탁자 | 국가 | 위탁업무 | KIS 관련 전송 항목 | 근거 |
|---|---|---|---|---|
| Railway Inc. | 미국 / 싱가포르 | PostgreSQL DB 호스팅 | 암호화된 KIS API 키 / 암호화된 계좌번호 (평문 접근 불가) | PIPA §28조의8 + DPA |
| Vercel Inc. | 미국 | 프론트엔드 정적 자산 호스팅 | KIS 데이터 전송 없음 (API 응답은 서버→클라이언트 직통) | PIPA §28조의8 + DPA |

3. **KIS API 호출 자체는 제3자 제공이 아닙니다**. 이용자가 본인 명의 KIS 계좌를 조회하기 위해 KIS 서버에 API 요청을 전송하는 행위이며, 제공 주체는 이용자 본인입니다 (회사는 API 호출 게이트웨이 역할).

**[English]**
### 10.4 Third-party Disclosure
1. **No third-party disclosure of KIS-related personal data.** KIS API keys, account numbers, balances, positions, and execution history are **not** shared with any third party. In particular, KIS market data (quotes/order book/executions) is **not** redistributed (KIS Open API Terms Arts. 4-6). Journal Companion payloads to Anthropic PBC contain **only anonymized proxies** (sector bucket + amount bin) — never raw KIS data.
2. **Infrastructure processors**: Railway Inc. (USA/Singapore, PostgreSQL hosting — encrypted keys only, no plaintext access) and Vercel Inc. (USA, static frontend — no KIS data transmitted).
3. **API calls to KIS are not third-party disclosures** — the user is the originator of the request to their own KIS account; the Company acts solely as an API gateway.

---

### 10.5 보안 조치 (Technical and Organizational Measures)

**[한글]**
(근거: 개인정보보호법 제29조, 개인정보의 안전성 확보조치 기준 고시, 전자금융감독규정 제13조·제14조)

1. **암호화 저장**: KIS API App Key / App Secret / 계좌번호는 **AES-256-GCM** 방식으로 DB 저장. 암호화 키는 KMS(Key Management Service) 에 분리 보관.
2. **전송 암호화**: KIS API 요청/응답, 이용자 브라우저↔서버 통신은 모두 **TLS 1.3** 강제.
3. **접근 통제**: DB 접근은 최소권한 원칙, 모든 접근은 감사 로그(audit log)로 기록. 복호화 권한은 런타임 애플리케이션에만 부여 (관리자 수동 접근 차단).
4. **정기 점검**: API 키 유출 탐지를 위한 비정상 호출 패턴 모니터링 (rate limit, 지역 불일치 등).
5. **침해 통지**: 개인정보 유출 시 PIPA §34 에 따라 **72시간 내** 이용자 및 개인정보보호위원회에 통지.
6. **이용자 자기보호**: 이용자는 KIS 홈페이지에서 **API 키 즉시 재발급**이 가능하며, PivoxQuant 는 이를 유도하는 안내를 제공합니다.

**[English]**
Technical and organizational measures:
1. AES-256-GCM encryption at rest (API keys, account numbers). Encryption keys stored separately in KMS.
2. TLS 1.3 enforced for all traffic (KIS API, browser ↔ server).
3. Least-privilege DB access with audit logging. Decryption permission granted only to runtime application.
4. Anomaly monitoring for API call patterns (rate limits, geo mismatches).
5. Breach notification within 72 hours per PIPA Art. 34.
6. Users may immediately rotate API keys via the KIS website.

Legal basis: PIPA Art. 29; PIPC Safeguard Standards Notice; Electronic Financial Supervisory Regulation Arts. 13-14.

---

### 10.6 이용자 권리 (User Rights)

**[한글]**
(근거: 개인정보보호법 제35조 열람권, 제36조 정정·삭제권, 제37조 처리정지권, 제37조의2 자동화된 결정 거부권)

이용자는 `/settings/integrations` 및 `/settings/privacy` 페이지의 **1-click 인터페이스**를 통해 아래 권리를 행사할 수 있습니다.

| 권리 | 근거 | 실행 UI |
|---|---|---|
| 열람권 | §35 | "내 KIS 연동 데이터 보기" 버튼 → 암호화 저장된 항목 목록 표시 (API 키는 복호화하지 않고 마스킹 표시) |
| 정정권 | §36 | API 키 재등록 버튼 (기존 키는 물리 삭제 후 신규 저장) |
| **연동 해제 / 삭제권** | §36 | **"KIS 연동 해제" 버튼** → 즉시 DB 에서 API 키·계좌번호 물리 삭제, 백업은 30일 내 완전 파기 |
| 처리정지권 | §37 | "KIS 조회 일시 중지" 토글 (재개 시까지 API 호출 차단) |
| 동의 철회 | §22 | "KIS 연동 동의 철회" 버튼 (연동 해제와 동시 작동) |

이용자 요청 수신 시 **지체 없이 (최대 10일 이내)** 처리하며, 처리 결과를 이용자에게 통지합니다 (PIPA §38).

**[English]**
Legal basis: PIPA Arts. 35-37, 37-2, 38. All rights are exercisable via 1-click controls in `/settings/integrations` and `/settings/privacy`. Requests are processed within 10 days and results notified to the user.

---

### 10.7 자동화된 결정 여부 (Automated Decision-making)

**[한글]**
(근거: 개인정보보호법 제37조의2, 2024-03 신설)

**KIS 연동 정보를 기반으로 한 자동화된 투자 결정은 이루어지지 않습니다.**

1. PivoxQuant 는 이용자의 KIS 계좌에 대해 **자동 매수·매도 주문을 실행하지 않습니다** (주문 기능 미제공, 이용약관 §11 참조).
2. 이용자 포트폴리오에 대한 분석·시그널·리스크 지표는 **정보 표시 목적**이며, 이용자의 명시적 매매 결정을 대체하지 않습니다.
3. 이용자는 언제든 AI 분석에 대해 **설명 요구·이의 제기·처리 거부** 권리를 `/settings/privacy` 에서 행사할 수 있습니다.

**[English]**
Legal basis: PIPA Art. 37-2. No automated investment decisions are made based on KIS integration data. The Service does **not** execute orders. Analysis/signals are informational only. Users may demand explanation, object, or opt out at any time.

---

### 10.8 연령 제한 및 본인 확인 (Age Restriction)

**[한글]**
(근거: 개인정보보호법 제22조의2 아동 동의, 전자금융거래법 본인확인 원칙)

1. KIS 계좌 연동은 **만 19세 이상** 이용자에게만 허용됩니다.
2. KIS 계좌는 이용자가 **KIS 에서 본인 명의로 개설한 계좌**여야 하며, 이용자는 본인의 API 키를 타인 계좌에 대해 사용하지 않음을 확인합니다.
3. 타인 명의 계좌 연동 시도가 확인될 경우 회사는 **즉시 연동을 해제**하고, 심각한 경우 법적 조치를 취할 수 있습니다.

**[English]**
KIS integration is available only to users aged 19 or older. API keys must correspond to the user's **own** KIS account. Attempted linking of another person's account triggers immediate disconnection and possible legal action.

---

### 10.9 KIS Open API 관련 고지 (KIS Open API Notice)

**[한글]**
1. KIS Open API 는 한국투자증권㈜ 이 제공하는 독립된 API 서비스이며, 이용자는 PivoxQuant 와는 별도로 **한국투자증권의 Open API 이용약관에 동의**하여야 합니다.
2. API 사용 한도(Rate Limit)·일일 호출 제한·KIS 서비스 중단 시 조회 실패는 KIS 정책에 따르며, PivoxQuant 는 이에 대한 책임을 부담하지 않습니다.
3. KIS Open API 정책 변경으로 인한 연동 중단·기능 제한은 회사가 **즉시 고지**합니다.

**[English]**
KIS Open API is an independent service of Korea Investment & Securities Co., Ltd. Users must separately agree to KIS's Open API Terms. Rate limits, daily call caps, and service outages follow KIS policy; the Company is not liable for such. Users will be notified immediately of any KIS-policy-driven changes.

---

### 10.10 개인정보 보호책임자 및 문의 (Contact)

**[한글]**
KIS 연동 관련 개인정보 문의: **seanbae1521@gmail.com**
개인정보 침해 신고: 개인정보보호위원회 (privacy.go.kr / 국번 없이 182)
금융 관련 분쟁: 금융감독원 (fss.or.kr / 1332)

**[English]**
KIS-related inquiries: seanbae1521@gmail.com. PIPC (privacy.go.kr). FSS (fss.or.kr).

---

**본 초안 종료. 로펌 검토 후 최종본에서 조항 번호 재정리 예정.**

## 부록. V1 → V2 변경 요약 (개인정보처리방침)

1. **[유지]** §9 Journal Companion 섹션 — V1 내용 그대로 유지 (Anthropic PBC Claude API 처리위탁 포함)
2. **[신규]** §10 KIS 계좌 연동 관련 개인정보 처리 — 10개 세부 조항 전부 신규
3. **[삭제]** Alpaca 관련 개인정보 처리 조항 (V1 에는 명시적 조항 없었으나, 향후 방침에 포함되지 않도록 확인)
4. **[주의]** KIS Open API 약관 준수 조항 신설 — 시세정보 제3자 제공 금지 명시
5. **[신설]** 전자금융거래법 §22 "거래기록 5년 보관" 예외 해석 명시 — PivoxQuant 는 거래 체결 주체 아님
