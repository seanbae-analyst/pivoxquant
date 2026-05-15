# Email 인프라 셋업 가이드 — pivoxquant.com

> **출시 BLOCKER 클래스.** 추가 비용 0원 (Cloudflare 무료 + SendGrid free 100/day + 가비아 도메인 기존).
> **작업 시간**: CEO 10–15분.
> **마지막 갱신**: 2026-05-15 v43 autonomous wave (PR #397에서 `support@pivoxquant.com` 메시지 추가됐는데 inbox 없으면 빈말 되므로 즉시 setup 필요).

---

## 왜 필요한가 (1줄씩)

1. **들어오는 방향**: 사용자가 PDF 이메일 받고 `reports@`에 reply → 현재 MX 없어서 **bounce**. weekly_memo cron은 매주 일요일 08:00 KST에 발송 시작 예정 → 그때부터 매주 reply 손실.
2. **법규 표시 의무**: 이용약관 / 개인정보처리방침 / 결제 페이지에 `support@pivoxquant.com` 표시 (총 14곳, terms-ko.md / privacy-ko.md / settings / login / pricing 등). inbox 없으면 PIPA / 전자상거래법 §13 표시의무 위반 risk.
3. **사용자 신뢰**: PR #397 결제 503 메시지 "support@pivoxquant.com 으로 문의해 주세요" — inbox 없으면 빈말.
4. **나가는 방향 (SendGrid)**: 도메인 인증(SPF + DKIM) 안 하면 사용자 inbox로 **스팸 처리** 또는 거부됨. Cloudflare DNS 위임 후 SendGrid 콘솔에서 TXT 레코드 추가 1회.

---

## Step-by-Step (Cloudflare 처음 사용 가정)

### 0. 사전 준비
- 가비아 (pivoxquant.com 도메인 등록처) 로그인 가능해야 함
- 개인 Gmail: `seanbae1521@gmail.com` (포워딩 대상)
- 작업 중 도메인 다운타임: **없음** (NS 변경은 propagation 후 cutover, MX는 점진 등록)

### 1. Cloudflare 무료 계정 가입 + 도메인 추가 (3분)

1. https://dash.cloudflare.com/sign-up 접속 → 이메일로 가입 (`seanbae1521@gmail.com` 권장)
2. 대시보드 → **+ Add a site** → `pivoxquant.com` 입력
3. **Free** plan 선택 ($0/월)
4. Cloudflare가 현재 가비아 DNS 레코드를 자동 스캔 → 기존 A/CNAME/TXT 그대로 import (Vercel/Railway 라우팅 끊기지 않음)
5. Cloudflare가 보여주는 두 개의 **Nameserver** 메모 (예: `xxx.ns.cloudflare.com`, `yyy.ns.cloudflare.com`)

### 2. 가비아 → Cloudflare NS 변경 (5분, propagation 1-24h)

1. 가비아 My가비아 → 도메인 통합 관리 툴 → **pivoxquant.com** 선택 → **네임서버 설정**
2. **기타 네임서버 입력** 라디오 선택
3. 1차 / 2차 네임서버에 Step 1에서 메모한 Cloudflare NS 입력 → 저장
4. **propagation 대기**: 보통 1–6시간, 최대 24시간 (Cloudflare 대시보드가 활성화되면 완료)
5. ⚠️ 이 단계에서 **www.pivoxquant.com (Vercel) + web-production-7b484b.up.railway.app (Railway)** 라우팅이 끊기면 안 됨 — Cloudflare가 import한 A/CNAME이 동일한 IP 가리키는지 확인 (자동 import 보통 정확)

### 3. Cloudflare Email Routing 활성화 (2분)

1. Cloudflare 대시보드 → **pivoxquant.com** 선택 → **Email** 탭
2. **Get started** → **Enable Email Routing** 클릭
3. Cloudflare가 자동으로 다음 DNS 레코드 추가:
   - MX × 3개 (Cloudflare 메일 서버)
   - SPF TXT (`v=spf1 include:_spf.mx.cloudflare.net ~all`)
4. **Routing rules** 탭 → **Create address** ×3:
   - `support@pivoxquant.com` → `seanbae1521@gmail.com`
   - `reports@pivoxquant.com` → `seanbae1521@gmail.com`
   - `hello@pivoxquant.com` → `seanbae1521@gmail.com`
5. (선택) **Catch-all address** → `seanbae1521@gmail.com` 도 활성 (오타 들어와도 잡힘)
6. Gmail 받은편지함 가서 Cloudflare 인증 메일 클릭 (`seanbae1521@gmail.com` 소유권 확인)

### 4. 테스트 (2분)

다른 Gmail 또는 휴대폰 메일 앱에서:
```
받는사람: support@pivoxquant.com
제목: test
본문: 테스트
```
→ `seanbae1521@gmail.com` 으로 1분 안에 도착하면 성공.

`reports@` 와 `hello@` 도 동일 테스트.

### 5. SendGrid 도메인 인증 (나가는 방향, 5분)

> 전제: Railway env에 `SENDGRID_API_KEY` 가 이미 있다고 가정 (없으면 SendGrid 무료 계정 가입 후 키 발급 → Railway Variables tab에 추가).

1. SendGrid 콘솔 → **Settings → Sender Authentication → Authenticate Your Domain**
2. DNS host: **Cloudflare** 선택
3. 도메인: `pivoxquant.com`
4. **Next** → SendGrid가 3개의 CNAME 레코드 제공 (예: `em1234.pivoxquant.com → u123.wl456.sendgrid.net`, DKIM `s1._domainkey.pivoxquant.com → ...`, `s2._domainkey.pivoxquant.com → ...`)
5. Cloudflare 대시보드 → **pivoxquant.com → DNS** 탭 → **Add record** ×3로 추가 (Type: CNAME, Proxy status: **DNS only** ⚠️ 회색 구름 아이콘, orange 구름 X)
6. SendGrid 콘솔로 돌아가서 **Verify** 클릭 → 즉시 ~5분 안에 ✅ 활성화
7. SendGrid 콘솔 → **Settings → Sender Authentication → Single Sender Verification** 비활성화 (도메인 인증으로 대체)

### 6. End-to-end 검증 (2분)

CEO 본인 명의로 weekly_memo 한 번 수동 trigger 또는 다음 일요일 08:00 KST cron 대기.
- Gmail 받은편지함에 `reports@pivoxquant.com` 발신 → 스팸함 X → 메인 inbox 도착
- 그 메일에 reply → Cloudflare Routing → `seanbae1521@gmail.com` 도착

---

## DNS 레코드 최종 상태 (Cloudflare 자동 + 수동 합쳐서)

```
# 기본 A/CNAME (Vercel + Railway 라우팅, 가비아에서 import됨)
A     pivoxquant.com        76.x.x.x       (Vercel IP)
CNAME www.pivoxquant.com    cname.vercel-dns.com.

# Cloudflare Email Routing (Step 3 자동)
MX    pivoxquant.com        route1.mx.cloudflare.net   (priority 1)
MX    pivoxquant.com        route2.mx.cloudflare.net   (priority 2)
MX    pivoxquant.com        route3.mx.cloudflare.net   (priority 3)
TXT   pivoxquant.com        "v=spf1 include:_spf.mx.cloudflare.net ~all"

# SendGrid 도메인 인증 (Step 5 수동)
CNAME em1234.pivoxquant.com         u123.wl456.sendgrid.net
CNAME s1._domainkey.pivoxquant.com  s1.domainkey.uXXX.wl.sendgrid.net
CNAME s2._domainkey.pivoxquant.com  s2.domainkey.uXXX.wl.sendgrid.net
```

⚠️ **Cloudflare SPF + SendGrid 충돌 주의**: SendGrid가 SPF 추가하라고 안내해도 무시 (Cloudflare가 자동 추가한 `include:_spf.mx.cloudflare.net` 안에 SendGrid include 불가). 대신 SendGrid는 **DKIM만**으로 인증 성공. Cloudflare가 SPF의 `~all` (soft fail) 정책으로 SendGrid도 통과시킴.

만약 메일이 스팸함 가면 → SPF를 수동 갱신:
```
TXT   pivoxquant.com   "v=spf1 include:_spf.mx.cloudflare.net include:sendgrid.net ~all"
```

---

## 롤백 방법 (혹시 라우팅 깨지면)

### NS 롤백 (가비아 원복)
1. 가비아 → 도메인 통합 관리 → **네임서버 설정**
2. **가비아 네임서버 사용** 라디오 선택 → 저장
3. 1–6시간 후 가비아 DNS 다시 활성
4. 기존 A/CNAME (Vercel + Railway) 그대로 작동

### 비용 가비아 → Cloudflare 전환 후 발생 비용 0원
- Cloudflare Free plan: 무제한 도메인, 무제한 DNS query, 무제한 Email Routing 포워딩
- 도메인 등록비는 여전히 가비아 (Cloudflare는 DNS만 위임)

---

## 메모리 룰 검증

- ✅ `feedback_no_extra_cost`: Max + 도메인 + Railway 외 신규 비용 0원. Cloudflare Free + SendGrid 무료 100/day → 0원 추가
- ✅ `feedback_official_data_only`: 본 작업은 데이터 sourcing 아님 (이메일 라우팅)
- ✅ `legal_compliance`: PIPA + 전자상거래법 §13 표시의무 충족 (실제 inbox 존재)

---

## 다음 액션 (CEO 복귀 후)

1. **Step 1-4** (Cloudflare + Email Routing): 10분
2. **테스트 발송 1통**: 1분
3. **Step 5-6** (SendGrid DKIM): 5분
4. **첫 주 일요일 weekly_memo cron 결과 모니터링**: Sentry / Slack 확인
5. (선택) `qa_bug_log.md` BUG-001 entry → "RESOLVED 2026-05-XX (Cloudflare Email Routing)" 마킹

총 작업 시간: 15–20분. 도메인 propagation 1–6시간 (기다리는 시간).

---

## 본 가이드 작성 근거 (감사 traceability)

- 코드 `services/email/sender.py:33-50` — SendGrid → SMTP cascade + Reply-To `support@pivoxquant.com` 명시
- `services/email/sender.py:75` — `reports@pivoxquant.com` from 디폴트
- `frontend/src/content/terms-ko.md:259` + `privacy-ko.md:292` — 법규 표시 의무
- `feedback_no_extra_cost` memory: Cloudflare Free + SendGrid Free
- `session_2026-04-29.md:9`: 원래 "100명+ 후" 지연 결정 — 본 가이드는 **출시 전 필요로 우선순위 재조정** (PDF cron 발송 시작 + 결제 503 메시지 inbox 의존 명시)
