# KIS 한국투자증권 연동 안내 (신규 유저용)

> 작성: 2026-05-15 (Wave 6 bug-hunter Bug #3/#4 fix 동반 문서). KIS Connect modal에서 사용자가 막히는 지점 안내.
> 본 문서는 **사용자에게 보여줄 안내문** 초안 — `/settings` 페이지의 KIS connect modal 또는 `/help/kis-broker` 페이지에 추가 가능.

---

## TL;DR (이 3가지가 있어야 합니다)

1. **한국투자증권 KIS 발급 API key 2종** (App Key + App Secret) — kis.koreainvestment.com → API 신청 메뉴
2. **계좌번호 정확히 8자리** (예: `12345678`) + 상품번호 2자리 (예: `01`)
3. **KIS 계좌 모의투자 또는 실거래 활성화** (Read-Only로 사용)

---

## 단계별 (CEO + 신규 사용자 작업, 약 15-20분)

### 1. 한국투자증권 계좌 확보 (이미 있는 경우 skip)
- 한국투자증권 (단축: KIS) 일반 계좌 또는 모의투자 계좌 개설
- 모바일 앱 또는 영업점 가능

### 2. API 발급 신청 (KIS 사이트, 5분)

1. https://apiportal.koreainvestment.com 접속 → 로그인 (계좌 본인)
2. **신청/관리 → 모의/실전 → API 신청**
3. 약관 동의 + 본인 계좌 선택
4. 발급 완료 시 다음 2가지를 메모:
   - **App Key** (대문자+숫자 ~36자, `PSXXXXXXXX...`)
   - **App Secret** (대소문자+숫자 ~100+자)

### 3. PivoxQuant 연동 (3분)

1. PivoxQuant 로그인 → **Settings** → **B BROKERS** 섹션 → **CONNECT KIS ACCOUNT**
2. 모달 입력:
   - **App Key**: Step 2에서 메모한 값 (Paste)
   - **App Secret**: Step 2에서 메모한 값 (Paste)
   - **계좌번호 (Account No)**: 정확히 **8자리** 숫자
     - 예: `12345678` (`-` 없이)
     - ⚠️ 6-7자리 또는 9자리 이상은 거부됩니다 (2026-05-15 fix)
   - **상품번호 (Account Product)**: 정확히 **2자리** 숫자
     - 일반 계좌: `01`
     - 모의 계좌: `04` 또는 `21` (계좌별 상이)
3. **CONNECT** 클릭 → 성공 시 "KIS synchronized." toast 표시

### 4. 연동 검증 (1분)

- /portfolio 페이지 → 보유 종목이 KIS 동기화 자동 import
- /market → KOREA 탭 → KOSPI/KOSDAQ 실시간 시세
- 만약 import 안 됨: `Settings → B BROKERS → KIS Sync` 클릭

---

## 알려진 제약 + 안내

### Read-Only 모드만 지원
PivoxQuant는 **주문 기능 비활성**. 자본시장법 §6/§17/§101 컴플라이언스로 인해 매수/매도 요청은 KIS API로 전송하지 않습니다. 종목 가격, 잔고, 거래내역 조회만 사용.

### 사용량 한도
KIS Open API 무료 한도:
- 분당 ~20 호출 (실시간)
- 일별 ~10,000 호출
초과 시 우리 backend가 retry 또는 cache hit으로 graceful degrade.

### API key 만료
KIS API key는 만료가 없으나, 보안 이슈 발견 시 KIS 측이 무효화 가능. 무효화 시 PivoxQuant에서 "KIS 연결 해제됨" 알림 + 재발급 안내.

### 모의 vs 실전
- **모의 계좌** (paper): 가상 자금, 가격은 실시간 동기화. PivoxQuant 추천 (출시 직후 학습용)
- **실전 계좌**: 본인 실 자금. Read-only mode이므로 PivoxQuant가 주문할 수 없으나, 잔고가 본인 실 자금이라 익숙해진 후 사용 권장.

---

## 자주 묻는 질문 (FAQ)

### Q. 모의 계좌가 없습니다.
A. KIS 앱 → "모의투자 만들기" → 5분 안에 계좌 + API 모두 발급 가능. 가상 자금 ₩100,000,000 자동 지급.

### Q. App Key를 잃어버렸어요.
A. apiportal.koreainvestment.com → "API 신청/관리" → 재발급. PivoxQuant 연동 정보도 새로 입력 (이전 key 자동 무효화).

### Q. 계좌번호 8자리에서 거부됩니다.
A. 입력란에 `-`이나 공백 없이 숫자만. 예: `12345678` (O), `1234-5678` (X), `12345678 ` (X).

### Q. CONNECT 버튼이 비활성화 (회색)됩니다.
A. 4가지 필드(App Key, App Secret, 계좌번호 8자리, 상품번호 2자리) 모두 input 필요. 입력하면 자동 활성화.

### Q. 연결 후 종목이 안 보입니다.
A. 1) Settings → KIS Sync 클릭. 2) /portfolio 새로고침. 3) 종목이 영문/숫자만이면 (예: 005930) 자동으로 `.KS` 또는 `.KQ` suffix 부여됨 (registry 기반).

### Q. Alpaca (미국 broker) 연동도 됩니까?
A. PivoxQuant는 BYOK (Bring Your Own Key) 방식. Settings에서 활성화 시 본인의 Alpaca paper 계좌 연동. 현재 베타는 `ALPACA_ENABLED` 환경변수 gate.

---

## 보안 / 컴플라이언스 (PIPA + 자본시장법)

- **App Key + App Secret 암호화 저장**: PivoxQuant 서버에서 `Fernet` AES-128 암호화 (`PIVOX_BROKER_ENCRYPTION_KEY` env). 재시작 시 영속.
- **재발급 시 이전 key는 즉시 폐기**: User가 PivoxQuant에서 KIS Disconnect 시 DB row 삭제 + 메모리 cache 즉시 invalidate.
- **API 호출 로그**: 사용자 본인의 호출만 로그. 다른 user 데이터 접근 0.
- **주문 기능 비활성**: backend `ALPACA_ENABLED=0` + KIS service에서 주문 endpoint 호출 코드 자체 부재.

---

## 본 안내 작성 근거 (감사 traceability)

- `frontend/src/components/broker/kis-connect-modal.tsx:31` — 계좌번호 regex `^\d{8}$` (PR #404, 2026-05-15)
- `frontend/src/components/broker/kis-connect-modal.tsx:32` — 상품번호 regex `^\d{2}$`
- `services/kis/service.py` — Read-only mode (주문 endpoint 없음)
- `Dockerfile:43` — `ENV ALPACA_ENABLED=0` 기본값 (BYOK 활성 시 1)
- `legal_compliance.md` — 자본시장법 §6/§17/§101 컴플라이언스 정책
- Wave 6 bug-hunter Bug #3 (cursor) + #4 (regex) — PR #404
