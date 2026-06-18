# CEO 외부설정 체크리스트 (콘솔별) — 2026-06-09

> 출처: SHIP_BLOCKERS A1–A13 + 메모리(project_email_infra/automation_v2/business_registration)
> 를 **라이브 소스 실측**(`.env.example`, `frontend/src/lib/business-info.ts`,
> `services/launch_prep.py`, `services/news_service.py`, `services/push_service.py`)으로 재검증.
> 변수명은 전부 코드 정본 그대로(오타 금지).

**총 11개 항목 · 퀵윈 7개(~70분) · 신규가입/발급 4개(별도).**

> 🔑 핵심: `launch_prep.py` 의 env 인벤토리에 **required(부팅 차단) = 0개.** 아무것도 안 해도
> prod 는 뜬다. 아래는 전부 "기능 degrade 해제"용. 현재 prod `/api/health` 의
> `missing_recommended:1` = **SendGrid webhook key 단 하나**(C4).

> ⚠️ **이 체크리스트가 잡은 SHIP_BLOCKERS/메모리 STALE 오류 5건**:
> - **A1 (MX)**: 이미 RESOLVED 가능성 높음 — `project_email_infra.md:28` 2026-06-04 로그에 MX 2줄 active 기록. 확인만.
> - **A7 (사업자 footer)**: 5개 아니라 **6개**(코드가 `_SUBTYPE`도 읽음).
> - **A10 (VAPID)**: "Vercel만" 아님 — 공개키=Vercel / **비밀키=Railway** 2곳 분리.
> - **A2 (Brevo)**: "Vercel env" 아님 — 소비처가 백엔드라 **Railway** 가 맞음.
> - **A4 (`~/.pivoxquant-env` 8개)**: 랩탑 cron RETIRED(2026-05-28)로 **전부 무가치/중복 — 건너뛰기.**

---

## 1. 가비아 DNS — 퀵윈 (~2~15분) · A1

수신 메일(MX)만. 발신(SPF/DKIM/DMARC)은 이미 verified.

- [ ] `MX @ mx1.improvmx.com` 우선순위 **10**
- [ ] `MX @ mx2.improvmx.com` 우선순위 **20**
- [ ] 검증: `dig pivoxquant.com MX` → 위 2줄
- **unblock**: support@/legal@/billing@/noreply@ 수신 포워딩
- **메모**: ImprovMX 표준은 MX **2줄**(SHIP_BLOCKERS A1 의 1줄 표기는 부정확). 이미 박혀있을 가능성 높음 → 확인만.

## 2. ImprovMX — 퀵윈 (~5분) · A1 후속

- [ ] 도메인 pivoxquant.com **active** (seanbae1521 계정)
- [ ] catch-all `*@pivoxquant.com → seanbae1521@gmail.com`
- [ ] 100% 검증: **외부 메일**에서 support@pivoxquant.com 으로 1통 → Gmail 도착
- **메모**: 자동발송 noreply 테스트메일은 Gmail 자체필터로 안 보이는 게 정상 — 외부 실문의로만 검증.

## 3. Vercel (env)

### 3-A. 사업자정보 6종 (전자상거래법 §13) — 퀵윈 (~10분) · A7

SoT = `frontend/src/lib/business-info.ts`. canonical 키 한 벌이면 footer 점등.

- [ ] `NEXT_PUBLIC_BUSINESS_NAME` = `피복스퀀트 (PivoxQuant)`
- [ ] `NEXT_PUBLIC_BUSINESS_REPRESENTATIVE` = `배상현`
- [ ] `NEXT_PUBLIC_BUSINESS_REGISTRATION_NUMBER` = `459-01-03808`
- [ ] `NEXT_PUBLIC_BUSINESS_ADDRESS` = `서울특별시 성동구 독서당로 272, 107동 401호`
- [ ] `NEXT_PUBLIC_BUSINESS_TYPE` = `정보통신업`
- [ ] `NEXT_PUBLIC_BUSINESS_SUBTYPE` = `데이터베이스 및 온라인 정보 제공업`
- **얻는 곳**: 사업자등록증 PDF
- **메모**: 통신판매업 신고번호(`NEXT_PUBLIC_TELESELLER_REGISTRATION_NUMBER`)는 **신고 후** 입력. 무료 출시면 신고 불필요(대가성 판매 아님).

### 3-B. Push 공개키 — 퀵윈 · A10

- [ ] `NEXT_PUBLIC_VAPID_PUBLIC_KEY` = (web-push 출력 Public Key)
- **얻는 곳**: `npx web-push generate-vapid-keys` 1회 (공개/비밀 동시 출력)
- **메모**: 비밀키(4-C)까지 둘 다 있어야 실제 발송.

## 4. Railway (env, 백엔드)

> 모든 소비처 서버사이드 → **Vercel 아니라 Railway**.

### 4-A. Naver News API — 신규 가입 (~15분) · A6
- [ ] `NAVER_CLIENT_ID` · [ ] `NAVER_CLIENT_SECRET`
- **얻는 곳**: developers.naver.com → 앱 등록 → 검색(Search)/News. 무료 25,000/day.
- **unblock**: `.KS` 한국 종목 뉴스(현재 빈 배열)

### 4-B. Slack incoming webhook — 신규 발급 (~10분) · A5
- [ ] `SLACK_WEBHOOK_URL` = `https://hooks.slack.com/services/...`
- **unblock**: 모든 cron 실패 + Stripe 결제실패 알림(현재 전부 silent)

### 4-C. VAPID 비밀키 — 퀵윈(3-B와 동시) · A10
- [ ] `VAPID_PRIVATE_KEY` = (web-push 출력 Private Key)
- [ ] `VAPID_EMAIL` = `mailto:seanbae1521@gmail.com`

### 4-D. SendGrid Event Webhook 공개키 — 발급 (~5분) · A3 ★현재 유일한 missing_recommended
- [ ] `SENDGRID_WEBHOOK_PUBLIC_KEY`
- **얻는 곳**: SendGrid → Settings → Mail Settings → "Signed Event Webhook" ON → Verification Key 복사
- **unblock**: `/api/webhooks/sendgrid` 503 해제(바운스/스팸 추적). 발송과 무관, 추적만.

## 5. Brevo — 신규 가입 (선택, 비차단·출시 후 OK) · A2
- [ ] `BREVO_API_KEY` · [ ] `BREVO_FROM_EMAIL`=`reports@pivoxquant.com` · [ ] `BREVO_FROM_NAME`=`PivoxQuant Research`
- **위치**: **Railway**(백엔드 소비처). SHIP_BLOCKERS A2 의 "Vercel" 표기는 오류.
- **메모**: SendGrid 100/day fallback. 베타 규모에선 비차단.

## 6. Anthropic — 크레딧 충전(결제, 비차단) · A9
- [ ] 크레딧 충전 → Railway `SUPPORT_CHAT_LLM_ENABLED=1`
- **메모**: `ANTHROPIC_API_KEY` 는 이미 prod 설정(SWOT/coaching 작동 중). 이건 잔액 + support-chat 전용 플래그.

## ⛔ A4 (`~/.pivoxquant-env` 8개) — 건너뛰기 (무가치/중복)
랩탑 crontab/launchd 2026-05-28 RETIRED. 8변수 전부 다른 콘솔과 중복(SLACK=4-B, SENDGRID=완료, STRIPE=결제블로커, DATABASE_URL=Railway 자동, GPG/SENTRY 3종=죽은 로컬 레이어). Sentry **발신**은 `SENTRY_DSN` 으로 이미 라이브.

---

## 권장 순서 (퀵윈 먼저 ~70분)
1. 가비아 MX 확인(2분) → 2. ImprovMX 외부메일 테스트(5분) → 3. Vercel 사업자 6개(10분) →
4. `npx web-push generate-vapid-keys`(2분) → 5. Vercel 공개키(2분) → 6. Railway 비밀키(3분) →
7. **Railway SendGrid webhook key**(5분, missing_recommended 해소) → 8. Slack webhook(10분) →
9. Naver(15분) → 10.(출시후) Brevo → 11.(비차단) Anthropic 크레딧

> `NEXT_PUBLIC_*` 변경 후 **Vercel redeploy 필요**(빌드타임 인라인). Railway 변수는 저장 시 자동 재배포.

---

## 범위 밖 (env 아님, 법무/행정) — R3/R4
- 통신판매업 신고(성동구청 ~45,000원) → 무료 출시면 불필요, 유료 Stage-1 시 발효
- Stripe Live = `STRIPE_ENABLED=true`+키 4종(Railway). 변호사 Q-S3 + 신고 후.
