# 개인정보처리방침 · 이용약관 전수 코드 대조 (2026-09-17)

대상: `frontend/src/content/privacy-ko.md` (12개 조항) · `frontend/src/content/terms-ko.md` (13개 조항).
방법: 두 문서의 각 주장에 대응하는 코드 경로를 직접 확인. **확인된 것만 고쳤다.**
확인 못 한 것은 아래 "확인 불가" 및 "변호사 질문"으로 남겼다.

두 문서 모두 `status: DRAFT` · 변호사 검토 대기 배너 유지. 본 작업은 **문언을 현재 코드에
맞춘 것**이며 DRAFT → ACTIVE 전환이 아니다.

---

## A. 고친 항목 (코드 근거 있음)

### A-1. Anthropic 국외 이전 — 이미 정정 완료, 잔존 없음 (SHIP_BLOCKERS R0)

`services/ai/` 는 존재하지 않는다 (`git ls-files | grep ^services/ai` → 0건, 삭제 커밋 `e19f28c3`).
라이브 코드(`routes/` · `services/` · `models/` · `app.py` · `config.py`)에 `import anthropic` /
`api.anthropic.com` 히트 **0건**.

| 표면 | 상태 |
|---|---|
| `privacy-ko.md` §6 국외이전 표 | Anthropic 없음 — 2026-09-06 정정분이 실제로 반영돼 있음 |
| `frontend/src/components/auth/v2/consent-stack.tsx:153` (가입 필수 동의) | "Supabase / Render / Vercel / Google / SendGrid 외 8개" — Anthropic·Railway 없음 |
| `terms-ko.md` §6, `privacy-ko.md` §6.3 | Anthropic 언급은 **과거형 정정 이력 인용문** 안에만 존재 (제거하면 정정 사실 자체가 사라짐) → 유지 |

→ **국외 이전 항목 전체를 지우지 않았다.** 나머지 수탁사는 코드로 실사용을 확인했다:
Supabase(`CLAUDE.md:63` pooler DSN) · Render(`render.yaml`) · Vercel · Google OAuth ·
Brevo/SendGrid(`services/email/sender.py:462-474`) · Sentry(`app.py:95-102`) · Stripe(게이트 off).

**잔존 stale 참조 (내가 못 고치는 파일):**
- `migrations/versions/024_cross_border_consent.py:11-13` docstring — 아직 "Anthropic PBC … Railway Inc." 로 수탁자를 나열. 마이그레이션 파일이라 담당 밖.

### A-2. 호스팅 사업자 — Railway → Render, 리전은 싱가포르

`render.yaml:24,28,42`: `name: pivoxquant-api` · **`region: singapore`** · `plan: free`.
DB 는 render.yaml 에 없고 Supabase(ap-northeast-2 서울).

- `privacy-ko.md` 본문에 Railway 는 **이미 없었다** (2026-09-06 정정 반영됨).
- 고친 것: Render 의 국가 표기 `미국` → **`미국 법인 · 처리 리전은 싱가포르`** (§6 표 + frontmatter).
  종전 표기는 실제 처리 국가를 틀리게 알리고 있었다.
- §9.3 물리적 조치: "서버는 Supabase 서울 리전" → 앱 서버(Render·싱가포르)와 DB(Supabase·서울)를 분리 기재.

### A-3. 거래내역 가져오기 (PDF 업로드 · 2026-09-17 추가)

| 문서 주장 | 코드 근거 |
|---|---|
| 형식 CSV · XLSX · XLS · PDF | `services/imports/csv_parser.py:110-127` (유일한 allowlist). 실제로는 `txt`/`tsv`/`xlsm`/무확장자도 통과하나, 프론트 `accept` 와 에러 문구는 4종만 안내 (`journal/import/page.tsx:47`) |
| 원본 파일 미저장 | `routes/imports.py:331` `blob = upload.read(...)` → `:345` 파싱 후 어떤 저장 호출에도 전달 안 됨. `services/imports/` 전체에 `tempfile`/`boto3`/`s3`/`UPLOAD_FOLDER` 0건. `models/import_batch.py:76` 에 파일 바이트 컬럼 없음 |
| 파일명·건수는 기록됨 | `routes/imports.py:329,423` `filename[:255]` → `ImportBatch` |
| PDF 암호 미저장·미로깅 | `routes/imports.py:491` → `:507` → `csv_parser.py:121` → `pdf_parser.py:82` `pdfplumber.open(io.BytesIO(data), password=...)`. `pdf_password` 가 들어가는 `logger.*` 0건. Sentry 유출 차단 `app.py:95-102` `include_local_variables=False`. 회귀 테스트 `tests/test_imports_pdf.py:259-269` |
| 계좌번호 미추출 + 마스킹 | 추출 필드는 `csv_parser.py:35-72 HEADER_SYNONYMS` (거래 데이터만). `services/imports/__init__.py:82-89 mask_sensitive()` 가 계좌번호 패턴을 `***` 치환, 300자 컷 → `models/import_batch.py:129 raw_snippet String(300)` |
| 용량 제한 | 파일 2MB (`routes/imports.py:78`) · PDF 40쪽 (`pdf_parser.py:50`) · 텍스트 20,000자 (`:79`) · 1회 500건 (`:80`) |

→ `privacy-ko.md` §1.2 행 + §2 **"가져오기(Import) 처리 원칙"** 절 신설.

**생년월일 주의**: 커밋 `bb6e6c64` 의 "birth-date lock" 은 저장되는 개인정보가 아니라
**키움이 걸어 둔 PDF 암호**다. 별개로 `users.birthdate` 는 가입 시 PIPA §22 ⑥ 만14세
게이트용으로 저장된다 (`models/user.py:148`, `services/age_verification.py`) — 두 건은
서로 무관하며 방침에도 각각 §2(암호·미저장)와 §1.1(생년월일·저장)로 분리해 적었다.

### A-4. 가져오기 토큰 · 웹훅 (2026-09-13~15)

`POST /api/portfolio/imports/webhook` — `routes/imports.py:513-555`.

- 인증: Bearer PAT, `routes/imports.py:120-140`, 평문 미저장 — `models/import_token.py:47` `token_hash`(sha256) + `:48` `prefix`(앞 12자). 발급 응답에서 1회만 노출 (`:630-637`).
- **종전 방침 문구가 틀렸다**: "이용자가 승인하기 전에는 기록되지 않음" → 실제로는 수신 즉시
  `pending_trades` 에 저장되고(마스킹 조각 포함) 승인해야 `trade_history` 로 확정된다
  (`services/imports/text_parser.py:144`). → "대기 목록에 저장되며, 승인해야 확정" 으로 정정.
- 한도: 활성 토큰 5개 · 일 200배치 (`routes/imports.py` `ACTIVE_TOKEN_LIMIT` / `TOKEN_DAILY_BATCH_LIMIT`).

### A-5. 증권사 연동 — 기능 자체가 없다

- `frontend/src/app/(auth)/onboarding/broker/page.tsx:44` `const BROKER_LINKING_AVAILABLE = false;` (하드코딩 상수, env 아님).
- `routes/broker.py` 파일이 없고 `routes/__init__.py:6-26` 블루프린트 목록에도 없다.
- `encrypted_app_key` / `encrypted_app_secret` / `encrypted_account_no` 에 **쓰기를 하는 앱 코드 0건** — 모델 정의(`models/broker_connection.py:29-31`), 스키마 self-heal(`app.py:765-767`), 마이그레이션 006, 키 로테이션 스크립트, export **제외** 목록(`routes/profile.py:2780-2782`), 테스트가 전부.

→ 고친 곳: `privacy-ko.md` §1.3(제목·본문 전면) · §2(수집 방법 3항 삭제) · §9.1(암호화 문구),
`terms-ko.md` §5.1 · §8.3.
**DB 컬럼은 남아 있으나 값이 쓰이지 않으므로 "수집하지 않는다"가 사실이다.**

### A-6. 탈퇴 · 보관기간 — 30일 유예의 실제 동작

- `POST /api/auth/delete-request` (`routes/auth.py:1572-1879`): `deletion_requested_at` 스탬프 + 로그인 차단(`app.py:284`, `routes/auth.py:843/1198/1418`) + 철회 경로(`:2104-2115`).
- 최종 파기: **`services/alert.py` 가 아니라** `scripts/nightly/pipa_purge.py` (`GRACE_PERIOD_DAYS = 30`, `:69`), 스케줄 `services/scheduler/cron_jobs.py:565-573` 매일 03:30 KST `ops_pipa_purge`.
- 하드 삭제 범위: `pipa_purge.py:193-233` + `routes/auth.py:1652-1681` 동적 FK 스윕 (→ `pending_trades`·`import_batches`·`import_tokens` 도 포함).
- 익명화: `auth_events.email` → salted SHA256 (`pipa_purge.py:239-245`). 행은 남는다.
- `DELETE /api/auth/delete-account` = 즉시 하드 삭제 경로도 병존 (`routes/auth.py:1559-1788`).

→ 종전 "탈퇴 시 지체 없이 파기, 최대 30일간 이메일·접속 로그 보관" 은 방향이 반대였다.
실제는 **30일 유예 후 자동 완전 삭제**다. §4.1 을 4개 항목으로 재작성.

### A-7. 접속 기록 3개월 — 코드에 근거 없음

`scripts/nightly/` 전체에 `AuthEvent` 파기 잡이 없다(`oauth_failure_check.py` 는 조회만).
`auth_events` 는 무기한 남고 탈퇴 시 이메일만 해시된다.
→ "3개월 / 통신비밀보호법" 행을 실제 동작 기재로 교체하고, 적정 보존기간은 아래 Q-P3 으로 넘김.

### A-8. 이메일 발송 — Primary 가 Brevo 다 (SendGrid 아님)

`services/email/sender.py:408-409,458-474` — `BREVO_PROVIDER_PRIMARY` 가 tier 순서를 뒤집는다.
`render.yaml` 은 `BREVO_PROVIDER_PRIMARY: "true"`. render.yaml 자체 주석(2026-09-07 실측):
SendGrid 는 `HTTP 401 Maximum credits exceeded`, SMTP 는 Render free 에서 아웃바운드 차단.
→ §6 표에서 Brevo = Primary / SendGrid = 예비 경로로 교체. SendGrid 행의 "발송 이벤트(오픈·클릭)"
도 삭제 — `POST /api/webhooks/sendgrid` 는 서명키 미배포로 503, 오픈·클릭 추적이 실제로 꺼져 있다.

### A-9. Sentry · 쿠키 · 애널리틱스

- Sentry: `app.py:95-102` `if _sentry_dsn:` 게이트, `send_default_pii=False`, `include_local_variables=False`. **`render.yaml` 에 `SENTRY_DSN` 없음** → 백엔드는 현재 비활성. 프론트는 `frontend/sentry.client.config.ts:15-17` 에서 `hasAnalyticsConsent()` 통과 시에만 init. → §6 검토 비고 2 에 반영.
- 애널리틱스: `gtag` / `googletagmanager` / `posthog` / `plausible` / `@vercel/analytics` / `mixpanel` / `amplitude` / `hotjar` / `clarity` — `frontend/src` · `package.json` 에 구현 히트 **0건**.
- 실제 쿠키 4종: `session` · `remember_token` (`security.py:290-308`), `csrf_token` (`security.py:502-510`, `httponly=False` — double-submit), `sp_locale` (`frontend/src/lib/locale.tsx:61`, `frontend/middleware.ts:108`). 쿠키 배너 선택값은 **localStorage** (`frontend/src/lib/consent.ts:14-15`) — 쿠키가 아니다.
→ §8 을 실제 목록 표 + "추적 스크립트 없음" 으로 재작성.

### A-10. KIS 는 시세 전용이다

`KISService()` 인스턴스화 지점 전부가 시세·지수·펀더멘털이다 (`routes/portfolio.py:2037`,
`services/data/indices.py:201,244`, `services/data/fetcher.py:761`, `kis_market_adapter.py`,
`kr_fundamentals.py`). `get_balance()` 는 정의만 있고 호출부 0건이며, 쓰더라도 운영자 명의
계좌(`services/kis/service.py:110` `KIS_ACCOUNT_NO`)를 본다 — 그리고 `render.yaml` 에
`KIS_ACCOUNT_NO` 가 없어 prod 에서 동작 불가.
→ §6.2 국내 위탁 표의 KIS 항목을 "이용자 연동 계좌 조회" → "시세·펀더멘털 데이터 조회
(운영자 명의 키, 종목코드만 전송 — 개인정보 미전송)" 로 정정.

### A-11. 결제 — 무료 베타가 맞다

`routes/billing.py:60-65,86-90,93-101` 게이트 + `:117-124` `_gate_billing_when_stripe_off()`
before_request 로 전 엔드포인트 503. `render.yaml` 에 `STRIPE_*` 변수 없음 →
`routes/billing.py:29` `stripe.api_key = ""`.
`terms-ko.md` §3 은 이미 "전면 무료"로 적혀 있어 **가격 숫자를 포함해 손대지 않았다**
(요금 SoT 보존). `privacy-ko.md` §1.5 "결제수단 정보 미수집" 도 사실과 일치.

### A-12. 삭제된 AI 생성물 항목 제거

`Artifact(` 생성 호출이 tracked 코드에 0건. → `privacy-ko.md` §1.2 의
"AI 생성물(주간 메모·카드 등) 및 발송·열람 기록" 행 삭제, §3 목적 표에서 "AI 생성물" 제거.

### A-13. 백테스팅 기능 없음

`frontend/src/lib/endpoints.ts:66-67` — "2026-09-01 removed four constants whose backend
routes do not exist: … backtest". `routes/` 에 backtest 히트 0건.
→ `terms-ko.md` §6.3 을 "과거 데이터의 한계 / 백테스팅 미제공" 으로 재작성, §6 제목과
§11.2.2 의 "백테스팅 결과" 인용도 함께 정리.

### A-14. 문의 이메일

`support@pivoxquant.com` — 두 문서 frontmatter · 본문 모두 이미 일치.
`frontend/src/app/contact/page.tsx:15` 및 `landing-v2.tsx:294-295` 주석이 같은 주소를 SoT 로 참조.
변경 없음.

### A-15. 이용약관 신규 의무 (가져오기 대응)

가져오기 업로드는 제3자 개인정보가 섞일 수 있는 최초의 표면이다.
→ `terms-ko.md` §7 제8호(타인 자료 업로드 금지) · §8 제4항(본인 자료 확인 책임 · 토큰 관리)을 신설.

---

## B. 배포 전이라 문서에 쓰지 않은 것 (배포되면 반영 필요)

### B-1. 로그인/가입 통합 + 동의 수집 시점 변경 — 작업 중
`frontend/src/app/(auth)/signup/page.tsx` 는 현재 워킹트리에서 34줄짜리 login 리렌더로 축소돼
있고(주석: "2026-09-17 CEO decision"), 4필수+1선택 동의 스택이
`signup/oauth-finalize/page.tsx:391 <ConsentStackV2>` 로 이동해 **OAuth 이후 신규 가입자에게만**
표시된다. `frontend/src/components/auth/v2/consent-stack.tsx` 는 아직 untracked.

**배포되면 `privacy-ko.md` 를 이렇게 바꿔야 한다:**
- §1.1 머리말 "회원가입 시" → "OAuth 인증을 마친 뒤 최초 1회 진행되는 가입 완료 절차에서" 로 수집 시점 명시.
- §6.1 "회원가입 시 별도 동의" → 같은 취지로 시점 문구 정정 (§28-8 동의 시점이 OAuth 이후로 바뀌므로).
- §11(만 14세) 의 생년월일 입력 시점도 동일하게 oauth-finalize 기준으로 기재.

### B-2. 월간 거울 리포트 PDF — 작업 중
`routes/reports.py` · `services/reports/` · `services/reports_delivery.py` 전부 **untracked**
(`git ls-files` 0건). 배포 전이므로 방침에 쓰지 않았다.

**배포되면 추가해야 한다:**
- `privacy-ko.md` §1.2 에 "월간 거울 리포트(PDF) 생성 및 발송·열람 기록" 행.
- §3 목적 표에 정기 리포트 발송 목적.
- 이메일 발송이 함께 켜지면 `EmailCategory.INFORMATION` (`services/reports_delivery.py:302`)
  이므로 §6 이메일 수탁자 항목의 "발송 콘텐츠" 에 PDF 첨부가 포함됨을 명시.

---

## C. 확인 불가 (고치지 않음)

| 항목 | 이유 |
|---|---|
| Vercel 접속 로그 "30일" 보유 기간 (§6 표) | 제공자 정책이라 코드로 검증 불가. 기존 기재 유지 |
| Brevo / SendGrid / Google / Stripe 의 "제공자 정책" 보유 기간 | 동일 |
| prod Render 대시보드의 실제 env 값 | 코드에서 볼 수 있는 것은 `render.yaml` 뿐. `sync: false` 항목은 실제 설정 여부 확인 불가 |
| 이메일 4종 ON/OFF 의 실제 prod 상태 | `SHIP_BLOCKERS.md:63,73` 은 "이메일 4종 OFF"(R2 BLOCKED), `render.yaml` 은 네 개 모두 `"true"` (2026-09-12 커밋). **둘이 충돌한다.** 방침의 "동의자에 한함" 기재는 양쪽 모두에서 참이므로 그대로 두었다 |
| ImprovMX / Cloudflare 사용 여부 (§6 검토 비고 3) | 레포에서 확인 불가. 기존 비고 유지 |

---

## D. 변호사 질문 (고치지 않고 넘김)

기존 큐(`legal_question_queue.md` Q1-Q15)와 별개로 이번 대조에서 새로 나온 것.

### Q-P1 (P0) — 국외 이전 동의 철회 수단이 UI 에 없다
방침 §6.1·§7.2 는 동의 철회 경로를 안내해야 한다. 백엔드
`routes/consents.py:185 DELETE /api/consents/cross-border` 는 있으나,
`frontend/src` 에 `revokeCrossBorderConsent` 호출부가 **0건**이다
(`frontend/src/lib/consents.ts:268` 는 dead code). 설정 화면에는 마케팅 동의 카드
(`components/settings/v2/marketing-consent-card.tsx`)만 있다.
- 임시 조치: 문언을 "이메일 요청 → 10일 이내 처리(설정 내 기능은 준비 중)"로 정정했다.
- 질문: **PIPA §28-8 동의의 철회를 이메일 접수로만 받는 것이 적법한가?** 동의를 받은 것과
  같은 수단(화면 내 토글)으로 철회를 제공해야 하는가? 그렇다면 출시 전 UI 구현이 P0 이다.

### Q-P2 (P1) — 파일명 보관의 성격
원본 파일은 저장하지 않지만 파일명(최대 255자)은 `import_batches.filename` 에 남는다.
증권사 PDF 파일명에는 계좌번호·성명이 들어가는 경우가 있다.
- 질문: 파일명을 그대로 저장하는 것이 최소수집 원칙에 반하는가? 마스킹 또는 미저장으로
  바꿔야 하는가? (바꾼다면 `routes/imports.py:329,423` 수정이 필요 — 코드 변경 사안)

### Q-P3 (P1) — 접속 기록(auth_events) 보존 기간
현재 파기 잡이 없어 무기한 보관되고, 탈퇴 시 이메일만 해시된다.
- 질문: 개인정보 안전성 확보조치 기준의 접속기록 1년(또는 2년) 보존 요건과, 종전 방침이
  적었던 "3개월(통신비밀보호법)" 중 무엇이 본 서비스에 적용되는가? 상한을 정해
  파기 잡을 추가해야 하는가?

### Q-P4 (P1) — 대기 목록(pending_trades) 무기한 보관
승인/거절되지 않은 체결 정보에 TTL 이 없다 (`scripts/`·`services/scheduler/` 에
`PendingTrade` 참조 0건). 탈퇴 CASCADE 가 유일한 삭제 경로다.
- 질문: "목적 달성 시 지체 없이 파기" 원칙상 미승인 대기 건에 보관 상한(예: 90일)을
  두어야 하는가?

### Q-P5 (P1) — Render 싱가포르 리전의 §28-8 표기
Supabase(미국 법인·서울 리전)에 대해 이미 열려 있는 Q6 와 대칭 문제다.
Render 는 미국 법인이고 처리 리전은 싱가포르 — 이전 대상 "국가" 를 무엇으로 고지해야 하는가?
보수적으로 "미국 법인 · 처리 리전 싱가포르" 병기로 적었다. → **Q6 에 병합 권고.**

### Q-P6 (P0) — `/pricing` 이 유료 요금제를 광고하는데 약관 §3 은 전면 무료다
`frontend/src/app/pricing/page.tsx:96-98` 은 Free / Pro / Premium 3-tier 를 표시하고,
주석은 요금 SoT 를 "terms-ko.md **§8.1**" 로 가리키는데 **현행 약관에 §8.1 이 없다**
(§8 은 계정 관리 책임, 요금은 §3 이고 내용은 "전면 무료").
결제는 prod 503 이고 통신판매업 미신고다 (`SHIP_BLOCKERS.md` R3).
- 질문: 미신고 상태에서 가격을 게시하는 것이 전자상거래법 §13 위반인가? (기존 Q5 와 동일 쟁점)
- 별건: `/pricing` 은 본 작업의 담당 파일이 아니라 손대지 않았다. 요금 SoT 주석의
  조번호(§8.1)도 stale 이므로 정정 필요.

### Q-P7 (P2) — 가져오기 파일 형식 안내와 코드 allowlist 불일치
`csv_parser.py:110-127` 은 `txt` · `tsv` · `xlsm` · 무확장자도 통과시키는데, UI 와 에러 문구는
CSV·XLSX·XLS·PDF 4종만 안내한다. 방침에도 4종으로 적었다.
- 질문/조치: 문서를 넓힐 게 아니라 **코드 allowlist 를 4종으로 좁히는 것**이 맞아 보인다
  (안내와 동작을 일치시키는 방향). 코드 변경 사안이라 여기서는 손대지 않았다.

---

## E. 이번에 손대지 않은 것 (의도적)

- **법정 필수 기재사항** (PIPA §30): 처리목적 · 보유기간 · 제3자 제공 · 위탁 · 정보주체 권리 ·
  파기 · 안전성 확보조치 · 보호책임자 · 권익침해 구제 · 변경 고지 — 12개 조항 구조를 그대로 두고
  내용만 사실에 맞췄다. 삭제한 조항 없음.
- **DRAFT 배너 / `status: DRAFT` / `review_required: true` / `reviewer: null`**: 유지
  (SHIP_BLOCKERS R5·R6 은 변호사 사인 후 CEO 가 제거).
- **frontmatter 키 구조** (`contact:` · `dpo_email:` · `version:` · `effective_date:`): 변경 없음.
  `last_updated` 만 `2026-06-05` → `2026-09-17`, `version` 은 `2.0-draft` 유지.
- **`terms-ko.md` §3 요금 조항**: 가격 숫자 없음 · 현행 무료와 일치 → 무변경.
- **`<a id="cross-border">` 앵커**: `frontend/src/lib/consents.ts:185` 와
  `frontend/src/app/__tests__/oauth-finalize-consent.test.tsx:97` 이 참조하므로 보존.
- **AI 정정 이력 인용문** (`terms-ko.md` §6, `privacy-ko.md` §6.3): Anthropic 이 등장하지만
  과거형 정정 기록이다. 지우면 "왜 바뀌었는가" 가 사라진다 → 유지.

---

## F. 검증

```
./venv/bin/python -m pytest -q tests/test_disclaimer_sot.py tests/test_forbidden_terms_sync.py \
  tests/test_legal_deep_scan_local.py tests/test_legal_filter.py \
  tests/test_legal_filter_forbidden_parity.py tests/test_legal_scrub_decorator.py
cd frontend && npx vitest run src/lib/__tests__/legal-markdown.test.ts
```

`legal-markdown.test.ts` 가 두 문서를 실제로 렌더해 `**` 쌍·블록 구조를 검사한다
(2026-09-12 회귀: 리터럴 `**` 가 /terms·/privacy 에 노출됨). 결과는 세션 보고 참조.

`.githooks/pre-commit` 의 자본시장법 금지어 스캔은 스코프가
`frontend/src/app|routes|services|templates` 의 `py|ts|tsx|jsx|js|html` 이므로
`frontend/src/content/*.md` 는 대상이 아니다 — `<!-- legal-ok -->` 주석은 불필요했다.
그럼에도 추가 문장에 BUY/SELL/HOLD/추천/조언 지시어는 쓰지 않았고, 기존
부정문("추천하지 않습니다" 등)은 그대로 보존했다.
