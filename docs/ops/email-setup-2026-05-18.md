# Email 인프라 셋업 — ImprovMX + SendGrid (2026-05-18)

> **출시 BLOCKER 클래스.** 추가 비용 **0원** (ImprovMX free + SendGrid free + 가비아 기존 도메인).
> **작업 시간**: CEO 20–30분 (DNS 전파 대기 별도 30분-2시간).
> **마지막 갱신**: 2026-05-18 (CEO 결정: Workspace $96/년 보류, ImprovMX + SendGrid 무료 path 선택).
>
> **본 가이드 vs 이전 가이드**: `docs/ops/email-setup.md` 는 Cloudflare Email Routing 기반이었음. CEO 2026-05-18 재결정으로 **Cloudflare 위임 없이** 가비아 DNS 그대로 두고 ImprovMX(MX) + SendGrid(발송) 만 추가. NS 변경·propagation 24h 대기 없음.

---

## 왜 ImprovMX + SendGrid 인가

| 후보 | 비용 | 결정 |
|---|---|---|
| Google Workspace | $6/mo·user = **$96/년** | ❌ `feedback_no_extra_cost` 위반 |
| Cloudflare Email Routing | $0 (NS 위임 필요) | ⚠️ 가비아 → Cloudflare NS 이전 24h 대기 + import 회귀 위험 |
| **ImprovMX (수신 forward)** | **$0** (free tier 25 alias, 무제한 forward) | ✅ **선택** — 가비아 DNS 그대로 |
| **SendGrid (발송 primary)** | **$0** (free tier 100/day) | ✅ **선택** — DKIM 도메인 인증 |
| **Brevo (발송 fallback, ex-Sendinblue)** | **$0** (free tier **300/day 영구**) | ✅ **선택** (2026-05-18 추가) — SendGrid quota 초과 시 자동 대체. 결합 **400/day** |
| Postmark / Mailgun | $15+/mo | ❌ 출시 후 검토 |

**조합 근거**:
- ImprovMX = 수신 전용. `support@pivoxquant.com` → `seanbae1521@gmail.com` 자동 forward. MX 2개 + SPF 1줄.
- SendGrid = 발송 전용. `noreply@pivoxquant.com` 으로 17 Artifact 이메일. DKIM 3 CNAME.
- SPF 1개 TXT 에 **두 provider 모두 include** (SPF는 도메인당 1개만 허용).

---

## §1. CEO 가 직접 해야 하는 단계 (수동)

### 1-1. ImprovMX 계정 + 도메인 + alias 등록 (5분)

1. https://improvmx.com 접속 → **Sign up** (이메일 + 비밀번호만, 신용카드 X)
2. 로그인 후 대시보드 → **+ Add domain** → `pivoxquant.com` 입력
3. **+ Add alias** ×4 (모두 forward 대상은 `seanbae1521@gmail.com`):
   - `support@pivoxquant.com`  → `seanbae1521@gmail.com`
   - `legal@pivoxquant.com`    → `seanbae1521@gmail.com`
   - `hello@pivoxquant.com`    → `seanbae1521@gmail.com`
   - `seanbae@pivoxquant.com`  → `seanbae1521@gmail.com`
4. (선택) **Catch-all** `*@pivoxquant.com` → `seanbae1521@gmail.com` (오타 흡수, free tier 안에서 가능)
5. ImprovMX 대시보드가 **DNS Configuration** 영역에 보여주는 MX 2개 + SPF 1개를 메모 (§2 와 일치하는지 확인)

### 1-2. SendGrid 계정 + Domain Authentication + API Key (10분)

1. https://sendgrid.com/free 접속 → **Start for Free** (free tier 100 emails/day)
2. 회원가입 — 신용카드는 **identity 확인용만**, 결제 발생 X (Free plan 유지하면 0원)
3. 좌측 메뉴 → **Settings → Sender Authentication**
4. **Authenticate Your Domain** 클릭 (Single Sender 가 아니라 **Domain Authentication** — 17 artifact 발송 전용)
5. DNS host: **Other Host (Gabia)** 선택
6. Domain: `pivoxquant.com`
7. Advanced settings:
   - ✅ Use a custom return path (uncheck 기본값 OK)
   - ✅ Use automated security (DKIM 자동 회전 — 권장)
8. **Next** → SendGrid 가 3개의 CNAME 제공 (정확한 값은 SendGrid 화면에서 복사):
   - `em<NUM>.pivoxquant.com` → `u<NUM>.wl<NUM>.sendgrid.net`
   - `s1._domainkey.pivoxquant.com` → `s1.domainkey.u<NUM>.wl<NUM>.sendgrid.net`
   - `s2._domainkey.pivoxquant.com` → `s2.domainkey.u<NUM>.wl<NUM>.sendgrid.net`
9. 3개 값을 메모 (§2 가비아 입력에 사용)
10. 좌측 메뉴 → **Settings → API Keys → Create API Key**
    - Name: `pivoxquant-prod-2026-05-18`
    - Permissions: **Restricted Access → Mail Send: Full Access** (다른 권한 모두 No Access)
    - **Create & View** → 한 번만 보이는 키 복사 → `/tmp/sendgrid-key.txt` (chmod 600) 임시 저장
11. SendGrid 대시보드 돌아가서 (§2 DNS 입력 + 전파 후) **Verify** 클릭 → 5분 안에 ✅

### 1-4. Brevo 계정 + Domain Auth + API Key (10분) — **0원 fallback**

> **왜 Brevo?** SendGrid free = 100/day 가 베타 100명 단계에서 임박. Brevo (구 Sendinblue) free = **300/day 영구**. 결합 시 400/day, 월 12k 발송. 별도 결제 없음 — `feedback_no_extra_cost` 정합. SendGrid 가 429 (quota) / 5xx (장애) 반환 시 `services/email/sender.py` cascade 가 자동으로 Brevo 로 전환.

1. https://www.brevo.com (구 sendinblue.com 자동 redirect) 접속 → **Sign up free**
2. 이메일 + 비밀번호만 입력 (신용카드 X). 가입 직후 회사 정보 설문 — "PivoxQuant / Solo founder / Transactional" 응답
3. 좌측 메뉴 → **Senders, Domains & Dedicated IPs → Domains → Add a domain** → `pivoxquant.com`
4. Brevo 가 DKIM CNAME 2개 (또는 1개 TXT) 와 Brevo-code TXT 1개 제공:
   - `mail._domainkey.pivoxquant.com` → `<brevo-provided-target>` (DKIM)
   - `brevo-code.pivoxquant.com` → `<brevo-provided-code>` (도메인 소유권 확인)
   - (선택) Brevo 가 별도 DMARC 권고 시 §2 의 `_dmarc` 와 충돌 — 무시. 우리 DMARC 가 SoT.
5. 위 값을 메모 (§2 가비아 입력에 추가) — **SendGrid `s1./s2._domainkey` 와 충돌 없음** (selector 가 `mail`)
6. 좌측 → **SMTP & API → API Keys → Generate a new API key**
   - Name: `pivoxquant-prod-2026-05-18`
   - **Create** → 한 번만 보이는 키 복사 → `/tmp/brevo-key.txt` (chmod 600) 임시 저장
7. (§2 DNS 입력 + 전파 후) Brevo 도메인 페이지에서 **Authenticate this domain** 클릭 → 5분 안에 ✅

> **SPF 추가 변경 없음** — Brevo 는 발송 시 **자체 envelope-sender 도메인** (`*.brevosend.com`) 을 사용하고, From 도메인 (`noreply@pivoxquant.com`) 의 DKIM 만 우리 도메인에 위탁. 우리의 SPF 에 `include:spf.brevo.com` **추가 불필요** (만일 Gmail 이 SPF align 강제하면 § 5-A 갱신). DMARC 는 DKIM align 으로 통과.

### 1-3. 가비아 DNS 콘솔 입력 (§2 표대로, 10분)

1. https://my.gabia.com 로그인 → My가비아 → **도메인 통합 관리툴** → `pivoxquant.com` 선택
2. **DNS 정보 → DNS 설정** → **DNS 레코드 수정**
3. §2 표의 레코드 7개를 그대로 추가 (또는 SPF 충돌 시 §2-B 합본 SPF 1개로 교체)
4. **저장** → 가비아 안내 대로 5-10분 대기 (가비아 DNS 갱신은 빠름, 전파는 별도 30분-2시간)

### 1-4. Vercel env 변수 추가 (§4 참조)

### 1-5. 검증 (§3 dig + 수신/발송 테스트)

---

## §2. 가비아 DNS 레코드 (정확한 값)

> **호스트 입력 주의**: 가비아 콘솔은 호스트에 도메인 자체 표기 시 `@` 또는 빈칸 사용. 서브도메인은 `s1._domainkey` 처럼 접미사 제외해 입력. **레코드값 끝 점(`.`) 가비아가 자동 처리** — 입력 시 점 빼고 입력.

| Type | Host | Value | TTL |
|------|------|-------|-----|
| MX | `@` | `mx1.improvmx.com` (우선순위 **10**) | 3600 |
| MX | `@` | `mx2.improvmx.com` (우선순위 **20**) | 3600 |
| TXT | `@` | `v=spf1 include:spf.improvmx.com include:sendgrid.net ~all` | 3600 |
| CNAME | `s1._domainkey` | `s1.domainkey.u<NUM>.wl<NUM>.sendgrid.net` (SendGrid 화면 복사) | 3600 |
| CNAME | `s2._domainkey` | `s2.domainkey.u<NUM>.wl<NUM>.sendgrid.net` (SendGrid 화면 복사) | 3600 |
| CNAME | `em<NUM>` | `u<NUM>.wl<NUM>.sendgrid.net` (SendGrid 화면 복사) | 3600 |
| CNAME | `mail._domainkey` | (Brevo 화면 복사 — DKIM fallback selector) | 3600 |
| CNAME | `brevo-code` | (Brevo 화면 복사 — 도메인 소유권 확인) | 3600 |
| TXT | `_dmarc` | `v=DMARC1; p=quarantine; rua=mailto:legal@pivoxquant.com; pct=100` | 3600 |

### §2-A. SPF 합본 규칙 (단일 TXT 만 허용)

⚠️ **RFC 7208 §3.2**: SPF 레코드는 도메인당 **1개만 허용**. 두 provider 별로 TXT 2개 만들면 PermError → 발송·수신 모두 실패. 반드시 **하나의 TXT 에 `include:` 두 개** 동시 명시:

```
v=spf1 include:spf.improvmx.com include:sendgrid.net ~all
```

- `~all` (SoftFail) — 출시 초기 권장. Gmail/Naver 가 일치 안 해도 즉시 reject 안 하고 spam 라벨만. 운영 안정 후 `-all` (HardFail) 로 강화.
- DNS lookup 한도 10회 (SPF spec) — ImprovMX(1) + SendGrid(1) = 2회로 여유 충분.

### §2-B. DMARC 정책 근거

- `p=quarantine` — 인증 실패 시 spam 폴더 (reject 대신). 운영 6개월 후 `p=reject` 강화.
- `rua=mailto:legal@pivoxquant.com` — 집계 리포트 수신 (ImprovMX 통해 Gmail 도착). 분석은 https://dmarcian.com 무료 tier (월 10k 메시지).
- `pct=100` — 100% 적용. 점진 도입(`pct=10`) 단계는 SPF/DKIM 모두 PASS 확인 후 생략 가능.

---

## §3. 검증 (DNS 전파 후 30분-2시간)

### 3-1. `dig` 명령어

```bash
# MX (수신)
dig +short pivoxquant.com MX
# expected:
#   10 mx1.improvmx.com.
#   20 mx2.improvmx.com.

# SPF (발송 인증)
dig +short pivoxquant.com TXT
# expected (다른 TXT 와 함께 1줄로):
#   "v=spf1 include:spf.improvmx.com include:sendgrid.net ~all"

# DKIM s1
dig +short s1._domainkey.pivoxquant.com CNAME
# expected:
#   s1.domainkey.u<NUM>.wl<NUM>.sendgrid.net.

# DKIM s2
dig +short s2._domainkey.pivoxquant.com CNAME
# expected:
#   s2.domainkey.u<NUM>.wl<NUM>.sendgrid.net.

# SendGrid return path
dig +short em<NUM>.pivoxquant.com CNAME
# expected:
#   u<NUM>.wl<NUM>.sendgrid.net.

# DMARC
dig +short _dmarc.pivoxquant.com TXT
# expected:
#   "v=DMARC1; p=quarantine; rua=mailto:legal@pivoxquant.com; pct=100"
```

### 3-2. 수신 테스트

다른 Gmail / 휴대폰 메일에서:
```
받는사람: support@pivoxquant.com
제목: improvmx test 2026-05-18
본문: (아무거나)
```
→ `seanbae1521@gmail.com` 받은편지함 1분 안에 도착 ✅
→ `legal@` / `hello@` / `seanbae@` 도 동일 테스트.

### 3-3. 발송 테스트

1. SendGrid 콘솔 → **Email API → Integration Guide → Web API (cURL)** 으로 1통 테스트:
```bash
curl --request POST \
  --url https://api.sendgrid.com/v3/mail/send \
  --header "Authorization: Bearer $SENDGRID_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '{
    "personalizations":[{"to":[{"email":"seanbae1521@gmail.com"}]}],
    "from":{"email":"noreply@pivoxquant.com","name":"PivoxQuant"},
    "subject":"sendgrid test 2026-05-18",
    "content":[{"type":"text/plain","value":"hello from sendgrid via pivoxquant.com"}]
  }'
```
2. Gmail 받은편지함 도착 확인:
   - **From**: `PivoxQuant <noreply@pivoxquant.com>`
   - **메인 inbox** (스팸함 아님)
   - 메일 → "원본 보기" → `SPF=pass`, `DKIM=pass`, `DMARC=pass` 3줄 모두 PASS

### 3-4. mail-tester.com (선택, 권장)

1. https://www.mail-tester.com 접속 → 표시되는 임시 주소 (예: `test-abc123@mail-tester.com`) 복사
2. SendGrid cURL `to` 주소를 임시 주소로 바꿔 1통 발송
3. mail-tester.com 페이지 새로고침 → 점수 확인 — **9.0+** 목표
4. 9 미만이면: SPF/DKIM/DMARC 정합 / blacklist / 본문 spam trigger 확인

---

## §4. Vercel env 변수 (CEO 가 Vercel 대시보드에서 입력)

Vercel Dashboard → **pivoxquant** 프로젝트 → **Settings → Environment Variables**:

| Key | Value | Environment |
|-----|-------|-------------|
| `SENDGRID_API_KEY` | (§1-2 step 10 에서 복사한 키) | Production, Preview |
| `SENDGRID_FROM_EMAIL` | `noreply@pivoxquant.com` | Production, Preview |
| `SENDGRID_FROM_NAME` | `PivoxQuant` | Production, Preview |
| `BREVO_API_KEY` | (§1-4 step 6 에서 복사한 키) | Production, Preview |
| `BREVO_FROM_EMAIL` | `noreply@pivoxquant.com` (SendGrid 와 동일 — 1 sender) | Production, Preview |
| `BREVO_FROM_NAME` | `PivoxQuant` | Production, Preview |
| `BREVO_PROVIDER_PRIMARY` | `false` (기본 — SendGrid 우선, Brevo fallback). SendGrid 평판 저하 시 `true` 로 토글 | Production, Preview |
| `SUPPORT_EMAIL` | `support@pivoxquant.com` | Production, Preview |
| `LEGAL_EMAIL` | `legal@pivoxquant.com` | Production, Preview |

> **Railway env 도 동일 추가**: 백엔드(Flask)가 `services/email/sender.py` 에서 `os.environ.get("SENDGRID_API_KEY")` 직접 읽음. Railway Variables 탭에서 위 5개를 동일하게 추가.

**기존 `from_email` 디폴트와의 관계**: `services/email/sender.py` 의 17 artifact 호출부는 각자 `from_env_var=...FROM_EMAIL` 로 개별 env 키를 받음 (예: `WEEKLY_MEMO_FROM_EMAIL`). `SENDGRID_FROM_EMAIL` 은 새 `sendgrid_provider.py` 모듈의 **default sender** 로만 사용 — 기존 sender.py 우회 X.

저장 후 Vercel/Railway redeploy 트리거 (Vercel: empty commit; Railway: 자동).

---

## §5. 한도 + 모니터링

### 5-1. ImprovMX free tier

| 항목 | 한도 | 초과 시 |
|------|------|---------|
| Alias 개수 | 25 | Premium $9/mo (안 함 — `feedback_no_extra_cost`) |
| Forward 횟수 | **무제한** | — |
| Catch-all | 1 | — |
| Custom domain | 1 (pivoxquant.com) | — |

→ 25 alias 안쪽이면 영구 0원. 베타 100명 → 1000명 가도 변동 없음.

### 5-2. SendGrid + Brevo 결합 한도 (2026-05-18 갱신)

| Provider | Emails/day | API requests | Domain auth | 비용 |
|----------|------------|--------------|-------------|------|
| **SendGrid** (primary) | **100** | 무제한 | 1 도메인 | $0 |
| **Brevo** (fallback) | **300 영구** | 무제한 | 1 도메인 | $0 |
| **결합** | **400/day = 월 12,000** | — | 동일 도메인 | **$0** |

초과 시 (둘 다 429) → 다음날 00:00 UTC 까지 차단 (cost-monitor alert + SMTP fallback 동작 시 SMTP, 아니면 dev-mode log).

→ **17 artifact 매일 발송 시나리오** (결합 400/day 기준):
- 베타 단계 (사용자 5-10명): weekly_memo 1회/주 + earnings_prebrief 산발 = 일평균 10통 미만 ✅
- 100 사용자 시: 일평균 50통 (artifact 별 발송 빈도 합산) ✅ (SendGrid 단독으로도 OK)
- 500 사용자 시: 일평균 200-250통 → SendGrid 100 소진 후 Brevo 자동 fallback ✅
- 1000+ 사용자: 일평균 400+ → Brevo 도 한도 임박, 유료 검토 시점 (§6 트리거)
- **트리거**: SendGrid 일 80통 → cost-monitor alert (Brevo 자동 fallback 작동) / SendGrid + Brevo 합산 320통 → critical alert (유료 검토)

### 5-3. 모니터링 연계

| 메트릭 | 수집처 | Agent |
|--------|--------|-------|
| SendGrid 일일 사용량 | SendGrid Activity Feed API (`/v3/messages`) | cost-monitor (daily 04:00 KST) |
| Bounce / spam complaint | SendGrid Suppressions API + 본 시스템 `services/email/webhook.py` | email-deliverability |
| Domain authentication 만료 | SendGrid `/v3/whitelabel/domains/<id>` (DKIM rotation 30d) | cost-monitor |
| ImprovMX forward 누락 | Gmail 받은편지함 manual 점검 (자동화 어려움) | CEO weekly |

---

## §6. 향후 업그레이드 트리거

| 트리거 | 조치 | 비용 |
|--------|------|------|
| 베타 100명 → 500명 (일평균 100통 초과) | Resend free 1000/mo 병행 (provider fallback) | $0 |
| 사용자 1000명+ (일 300통+) | SendGrid Essentials $19.95/mo 또는 Postmark $15/mo | CEO 결정 |
| 통신판매업 신고 완료 | email-deliverability §5-A footer 의 `business_telecomm_number` env 채움 | $0 |
| 자체 inbox 필요 (reply 빈도 ↑) | Google Workspace $6/mo·user | CEO 결정 |
| DMARC `p=reject` 강화 | 본 가이드 §2 의 `_dmarc` TXT 만 수정 (6개월 운영 후) | $0 |

---

## §7. 롤백 (라우팅 깨지면)

### 7-1. 수신 (ImprovMX) 롤백
- 가비아 DNS 에서 MX 2개 + SPF 의 `include:spf.improvmx.com` 만 제거
- ImprovMX 대시보드에서 도메인 삭제
- 수신 자체 다시 NOT_CONFIGURED 로 복귀 (bounce)

### 7-2. 발송 (SendGrid) 롤백
- 가비아 DNS 에서 CNAME 3개 + SPF 의 `include:sendgrid.net` 만 제거
- Vercel/Railway env 에서 `SENDGRID_*` 5개 삭제
- 코드는 `services/email/sender.py` 의 SMTP fallback 자동 동작 (SMTP_HOST 설정 시) 또는 dev-mode 로그만 (transport 없음)

### 7-3. 가비아 DNS 전체 원복
- 가비아 DNS 콘솔에서 본 가이드 §2 의 7 레코드 모두 삭제
- 5-10분 후 `dig` 다시 empty 로 복귀

---

## §8. 메모리 룰 검증

- ✅ `feedback_no_extra_cost`: Workspace $96/년 거절, ImprovMX + SendGrid 모두 free tier. 추가 비용 **0원**.
- ✅ `feedback_official_data_only`: 본 작업은 데이터 sourcing 아님 (이메일 라우팅).
- ✅ `legal_compliance`: PIPA + 전자상거래법 §13 표시의무 충족 (실제 inbox 존재). 정통망법 §50 footer 는 별도 (email-deliverability §5-A).
- ✅ `feedback_no_extra_cost` 충돌 회피: Google Workspace path 명시적 거절.

---

## §9. CEO 작업 순서 요약 (체크리스트)

```
[ ] 1. ImprovMX 가입 + 도메인 + alias 4개 (5분)
[ ] 2. SendGrid 가입 + Domain Auth + API key (10분)
[ ] 3. 가비아 DNS §2 레코드 7개 입력 (10분)
[ ] 4. DNS 전파 30분-2시간 대기
[ ] 5. §3-1 dig 6개 명령어 모두 PASS 확인
[ ] 6. SendGrid 콘솔 "Verify" 클릭 → ✅
[ ] 7. §3-2 수신 테스트 4통 (support/legal/hello/seanbae)
[ ] 8. §3-3 발송 테스트 1통 (SPF/DKIM/DMARC pass 3줄 확인)
[ ] 9. §3-4 mail-tester 9.0+ 점수 (선택)
[ ] 10. §4 Vercel env 5개 추가 + redeploy
[ ] 11. §4 Railway env 5개 추가
[ ] 12. weekly_memo cron 일요일 08:00 KST 첫 발송 모니터링
[ ] 13. email-deliverability §3 "마지막 DNS 검토일" + 실측 결과 갱신
[ ] 14. qa_bug_log.md BUG-* "RESOLVED 2026-05-XX (ImprovMX + SendGrid)" 마킹
```

총 작업 시간: **20-30분** + DNS 전파 대기 30분-2시간.

---

## §10. 본 가이드 작성 근거 (감사 traceability)

- `services/email/sender.py:191-218` — `SENDGRID_API_KEY` env 직접 읽음 (Phase 7 통합 sender)
- `services/email/sender.py:72` — Reply-To 디폴트 `support@pivoxquant.com`
- `services/email/sendgrid_provider.py` (신규) — Direct v3 API path (사용자 facing transactional 이메일 전용, 17 artifact 와 분리)
- `requirements.txt:sendgrid>=6.12.5` — SDK 이미 pin됨
- `.claude/agents/email-deliverability.md` §3 — DNS 실측 NOT_CONFIGURED (본 가이드 완료 시 갱신)
- `memory/feedback_no_extra_cost.md` — Workspace 결제 거절 근거
- `memory/business_registration.md` — `legal@` alias 가 DMARC `rua` 수신지로 일치
- `docs/ops/email-setup.md` (이전 Cloudflare path) — 본 가이드가 superseded (CEO 2026-05-18 결정)
