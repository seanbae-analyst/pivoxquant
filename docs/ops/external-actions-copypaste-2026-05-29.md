# 출시 전 외부 콘솔 액션 시트 — 복붙 전용 (2026-05-29)

> 목표: CEO가 외부 콘솔(Stripe / Google / Kakao / 가비아 / SendGrid / 정부24)에서
> **"정확한 값을 복사 → 지정된 칸에 붙여넣기"** 만 하면 끝나게 만든다. 손작업 = 0.
> 모든 env var 이름·redirect 경로·DNS 레코드 값은 **실제 코드에서 grep 추출**(추측 X).
> 코드에서 확인 불가능한 값(키 자체, 사업자번호 등)은 "코드 미확인 — 콘솔에서 발급" 명시.

근거 파일:
- `routes/billing.py` (Stripe env var, line 29/34/35/36/207)
- `routes/auth.py` (OAuth redirect URI, line 642/643/649/654/1023/1252; 허용 origin 442-448)
- `services/launch_prep.py` (env 인벤토리, line 134-140)
- `docs/ops/email-setup.md` (DNS 레코드 실측값)

---

## ⚠️ 선행 게이트 (이거 안 하면 Stripe 켜도 503)

`routes/billing.py:60-65` — 아래 **두 env var이 동시에** Railway에 있어야 결제 endpoint가
503 `BUSINESS_REGISTRATION_PENDING`을 벗어남:

```
BUSINESS_REGISTRATION_NUMBER       = 459-01-03808     ← 발급 완료 (사업자등록)
TELESELLER_REGISTRATION_NUMBER     = (통신판매업 신고번호)   ← 코드 미확인 — §4에서 신고 후 발급
```

→ 즉, **통신판매업 신고(§4) + 변호사 Q-S3(월구독 vs §101②) 확정 전까지는 Stripe를 등록해도 결제가 안 열린다.**
   Stripe Products/키 셋업(§1)은 미리 해둬도 무해(게이트가 막음). 단 활성화는 위 2개 + 변호사 후.

---

## 1. Stripe — 유료 구독 활성화

### 1-A. Stripe Products 3-tier 생성

[무엇] Stripe Dashboard → Products → "Add product" 3번 (Free는 Stripe 상품 불필요 — 코드상 무료 tier).
[어느 콘솔/메뉴] https://dashboard.stripe.com/products (우상단 **Live mode** 토글 ON 확인)
[소요시간] 10분

생성할 상품 (월 정기결제 = Recurring / monthly):

| 상품명 | 가격 | 통화 | 청구주기 | 코드상 plan key |
|--------|------|------|----------|-----------------|
| PivoxQuant Pro | 9,900 | KRW | Monthly (recurring) | `pro` |
| PivoxQuant Premium | 19,900 | KRW | Monthly (recurring) | `premium` |
| (Free) | — | — | — | Stripe 상품 안 만듦 (앱 기본 tier) |

> ⚠️ KRW는 **0-decimal 통화** — Stripe에 금액 입력 시 `9900` / `19900` 으로 입력(센트 환산 ✗, ×100 ✗).
> 상품 만든 뒤 각 상품의 **Price ID**(`price_xxxxxxxxxxxxx` 형태)를 복사해 둘 것 → 1-C에서 사용.

### 1-B. Stripe Webhook endpoint 등록

[무엇] Dashboard → Developers → Webhooks → "Add endpoint"
[어느 콘솔/메뉴] https://dashboard.stripe.com/webhooks (Live mode)
[소요시간] 3분

Endpoint URL (정확히 이 문자열 붙여넣기):
```
https://pivoxquant.com/api/billing/webhook
```
> 코드: `billing_bp = Blueprint("billing", url_prefix="/api/billing")` + webhook 핸들러.
> Vercel이 `/api/*` → Railway 리라이트하므로 **앱 도메인(pivoxquant.com)** 으로 등록.
> Listen할 events 최소: `checkout.session.completed`, `customer.subscription.updated`,
> `customer.subscription.deleted`, `invoice.payment_failed`.
> 등록 후 화면의 **Signing secret**(`whsec_...`)을 복사 → 1-C `STRIPE_WEBHOOK_SECRET`.

> 🟥 signature mismatch는 401(인증 실패) 처리됨 — 503 아님(DoS auto-opt-out 방지, v44.8).
> 따라서 Signing secret이 틀리면 webhook이 전부 401 → 구독 상태 반영 안 됨. 값 정확히 복사.

### 1-C. Railway에 등록할 env var (정확한 변수명)

[무엇] Railway → `web` 서비스(id 8687c9ac) → Variables → New Variable (각각)
[어느 콘솔/메뉴] Railway Dashboard → project `vibrant-blessing` → web → Variables
[소요시간] 5분

코드가 실제로 읽는 키 (`os.environ.get(...)` 실측, 그대로 입력):

```
STRIPE_SECRET_KEY        = sk_live_...            ← 코드 미확인 — Stripe Dashboard ▸ Developers ▸ API keys (Live ▸ Secret key)
STRIPE_WEBHOOK_SECRET    = whsec_...              ← 1-B에서 복사한 Signing secret
STRIPE_PRICE_PRO         = price_...              ← 1-A Pro 상품의 Price ID
STRIPE_PRICE_PREMIUM     = price_...              ← 1-A Premium 상품의 Price ID
```

선택(있으면 좋은 것 — `services/billing_followup.py:69`, `billing_notifications.py:234`):
```
STRIPE_CUSTOMER_PORTAL_URL = https://billing.stripe.com/p/login/...   ← Customer Portal "No-code" 활성화 후 발급되는 link (코드 미확인)
```

> ⚠️ Public key(`STRIPE_PUBLIC_KEY` / `pk_live_...`)는 **백엔드 코드에 참조 없음**.
> 결제는 Stripe Checkout(서버 세션 redirect) 방식이라 frontend publishable key가 불필요.
> grep 결과 코드가 읽는 Stripe env는 위 4개(+포털 URL)뿐. 그 외 변수 추가 불필요.

> ⚠️ Frontend(Vercel)에는 Stripe 키 넣지 말 것 — `NEXT_PUBLIC_STRIPE*` 코드 참조 없음.

### 1-D. Stripe Live 5법 sweep (결제 켜기 전 필수 체크)

`routes/billing.py:245-253`은 이미 서버측에서 `consent = {key_info, recurring, stripe_overseas}`
3개 동의를 강제한다(금소법 §19 + 전자상거래법 §22의2 + PIPA §28-8). 콘솔 작업 아님(코드 완료)이나
출시 전 아래 5법 동의 UI/문구가 pricing·checkout 페이지에 살아있는지 육안 확인:

| 법령 | 요건 | 확인 포인트 |
|------|------|-------------|
| 전자상거래법 §17 | 청약철회 7일(디지털콘텐츠 가분) | 환불정책 명시 |
| 금소법 §19 | 설명의무(수수료/위험) | `key_info` 동의 체크박스 |
| 표시광고법 §3 | 기만표시 금지 | "월 9,900원" 정직 표시, 숨은 수수료 ✗ |
| PIPA §28-8 | 카드정보 국외이전(Stripe=US) 동의 | `stripe_overseas` 체크박스 |
| 정통망법 §50 | 마케팅 별도 동의 | 결제 동의 ≠ 마케팅 동의 |

> 🟥 결제 코드/문구 변경 시 legal-kr-fintech agent 사전 호출 + 변호사 Q-S3(월구독 vs §101②) 확정 필수.

---

## 2. OAuth redirect URI (prod 등록)

코드 실측: redirect_uri = `{frontend_origin}/api/auth/{provider}/callback`
(`routes/auth.py:1023` google, `:1252` kakao). 허용 origin(`:442-448`)에 `https://pivoxquant.com`,
`https://www.pivoxquant.com`, `https://pivoxquant.vercel.app` 포함.
→ prod에서 user가 보는 origin이 그대로 redirect 도메인이 됨.

### 2-A. Google

[무엇] Authorized redirect URIs에 아래 문자열 등록(3개 다 추가 권장 — www/vercel 폴백 대비)
[어느 콘솔/메뉴] Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID → **Authorized redirect URIs**
[소요시간] 3분

```
https://pivoxquant.com/api/auth/google/callback
https://www.pivoxquant.com/api/auth/google/callback
https://pivoxquant.vercel.app/api/auth/google/callback
```

> 같은 화면 "Authorized JavaScript origins"에는 origin만:
> `https://pivoxquant.com`, `https://www.pivoxquant.com`
> Railway env(이미 설정됐을 가능성 높음, 없으면): `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` (코드 미확인 — Console에서 발급)

### 2-B. Kakao

[무엇] Redirect URI에 아래 문자열 등록
[어느 콘솔/메뉴] Kakao Developers → 내 애플리케이션 → 제품 설정 → **카카오 로그인 → Redirect URI**
[소요시간] 3분

```
https://pivoxquant.com/api/auth/kakao/callback
https://www.pivoxquant.com/api/auth/kakao/callback
https://pivoxquant.vercel.app/api/auth/kakao/callback
```

> 추가 카카오 콘솔 작업(코드상 scope `profile_nickname profile_image account_email` — `auth.py:658`):
> - 카카오 로그인 → **동의항목**: 닉네임 / 프로필 사진 / **카카오계정(이메일)** ON(이메일은 검수 필요할 수 있음)
> - 카카오 로그인 → **보안**: Client Secret 사용 ON → 생성한 코드를 Railway `KAKAO_CLIENT_SECRET`
> - **활성화 설정** 카카오 로그인 ON
> Railway env: `KAKAO_CLIENT_ID`(=REST API 키) / `KAKAO_CLIENT_SECRET` (코드 미확인 — Console 발급)

---

## 3. DNS — 이메일 수신(MX) (가비아 콘솔)

[어느 콘솔/메뉴] My가비아 → 도메인 통합 관리 → pivoxquant.com → DNS 정보 → DNS 관리 → 레코드 추가/수정
[소요시간] 가입 2분 + DNS 5분 + propagation ~10분~1h
근거: `docs/ops/email-setup.md` (2026-05-23 dig 실측). 발신 SPF/DKIM/DMARC는 이미 OK, **남은 건 수신**.

### 3-A. ImprovMX 가입 + Alias (가입 2분)

[무엇] https://improvmx.com 무료 가입(`seanbae1521@gmail.com`) → 도메인 `pivoxquant.com` 입력 → alias 추가(전부 → `seanbae1521@gmail.com`)
```
support@pivoxquant.com
reports@pivoxquant.com
hello@pivoxquant.com
dmarc@pivoxquant.com
*@pivoxquant.com           (권장: catch-all, 오타 흡수)
```

### 3-B. 가비아 DNS — MX 2건 추가 (신규)

복붙 값(타입 / 호스트 / 값 / 우선순위 / TTL):
```
MX   @   mx1.improvmx.com   10   3600
MX   @   mx2.improvmx.com   20   3600
```

### 3-C. 가비아 DNS — SPF 병합 1건 (⚠️ 추가 아님, 기존 TXT 교체)

기존 SPF `v=spf1 include:sendgrid.net ~all` 의 **값을 아래로 교체**(SPF는 도메인당 1개만 유효):
```
TXT   @   "v=spf1 include:spf.improvmx.com include:sendgrid.net ~all"
```

### 3-D. 검증
```
dig +short MX pivoxquant.com        # mx1/mx2.improvmx.com 두 줄 나오면 성공
# + 다른 메일에서 support@pivoxquant.com 으로 test 발송 → seanbae1521@gmail.com 도착 확인
```

---

## 4. 기타 외부 액션

### 4-A. 통신판매업 신고 (선행 게이트 — §위 ⚠️ 참조)

[무엇] 통신판매업 신고 → 신고번호 발급 → Railway env `TELESELLER_REGISTRATION_NUMBER` 에 입력
[어느 콘솔/메뉴] 정부24(www.gov.kr) "통신판매업 신고" 또는 관할 시·군·구청. (구매안전서비스 이용확인증 = 결제대행사/은행 발급분 첨부)
[소요시간] 신청 20분 + 처리 3~5영업일
[값] 코드 미확인 — 신고 후 발급되는 "제20XX-지역-NNNNN호" 번호를 콘솔에서 받아 입력.

### 4-B. SendGrid Sender 이름/주소 검증

[무엇] 발신자 신원(From) 검증 — `noreply@pivoxquant.com` / `reports@pivoxquant.com` (코드: `brevo_provider.py:95-97`)
[어느 콘솔/메뉴] SendGrid → Settings → Sender Authentication (Domain Authentication은 SPF/DKIM 이미 OK이므로 Single Sender면 충분) + Settings → API Keys로 `SENDGRID_API_KEY` 발급 → Railway 입력
[소요시간] 5분
[값] `SENDGRID_API_KEY` = 코드 미확인 — SendGrid 콘솔 Create API Key(Mail Send 권한)에서 발급. (CLAUDE.md: prod `missing_recommended:1` 후보 = 이 키 또는 `SENDGRID_WEBHOOK_PUBLIC_KEY`)

### 4-C. Anthropic / GitHub billing 한도

[무엇] 비용 폭주 방지 상한선 설정(코드 변경 아님, 콘솔 설정만)
[어느 콘솔/메뉴]
  - Anthropic: console.anthropic.com → Settings → Limits/Billing (Claude API는 Max plan(CC) + 일부 API credit 사용 — `feedback_no_extra_cost`상 신규 충전 금지, 기존 한도 확인만)
  - GitHub: github.com → Settings → Billing and plans → "Spending limit" → Actions/Packages **$0 또는 무료 한도 고정**(billing 결제 차단 정책 유지 — CLAUDE.md 로컬 hooks 이전 사유)
[소요시간] 각 2분
[값] 코드 미확인 — 콘솔에서 한도 숫자 직접 설정. PivoxQuant 정책: 신규 비용 0원 유지(`feedback_no_extra_cost`).

---

## 빠른 순서 (의존성 정렬)

1. (병렬 가능) §2 Google/Kakao redirect URI 등록 — 출시 로그인 작동 (즉시 가능)
2. (병렬 가능) §3 가비아 MX/SPF + ImprovMX — 이메일 수신 (즉시 가능)
3. §4-B SendGrid API Key → Railway — 이메일 발신 확정 (즉시 가능)
4. §4-A 통신판매업 신고 → 번호 발급 (3~5영업일, 결제 선행 게이트)
5. §1 Stripe Products/Webhook/키 → Railway (미리 가능, 단 활성화는 4 + 변호사 Q-S3 후)
6. 선행 게이트 2개 env 입력 + 변호사 의견서 → 결제 ON
