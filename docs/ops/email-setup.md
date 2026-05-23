# Email 인프라 셋업 가이드 — pivoxquant.com

> **상태 갱신: 2026-05-23 v51** — DNS 실측 후 전면 정정.
> 발신(SendGrid)은 **이미 설정 완료**, 남은 건 **수신(MX) 1건 + 발신 키 검증 1건**.
> 추가 비용 0원 (ImprovMX 무료 + SendGrid free 100/day + 가비아 도메인 기존).
> **작업 시간**: CEO 약 10분.

---

## 0. 실측된 현재 상태 (2026-05-23 `dig` 기준)

| 항목 | 레코드 | 상태 |
|------|--------|------|
| NS (DNS 호스트) | `ns1.gabia.co.kr` 등 | **가비아** (Cloudflare 이전 안 함) |
| A / CNAME | Vercel (216.198.79.1 / vercel-dns) | ✅ 라우팅 정상 |
| SPF (발신) | `v=spf1 include:sendgrid.net ~all` | ✅ 설정됨 |
| DKIM (발신) | `s1/s2._domainkey` → SendGrid (u91995806) | ✅ 설정됨 |
| DMARC | `v=DMARC1; p=none; rua=mailto:dmarc@pivoxquant.com` | ✅ 설정됨 (모니터링) |
| **MX (수신)** | 없음 | ❌ **미설정 — 이게 남은 갭** |

→ **나가는 메일**(`reports@`/`noreply@` 발송)은 DNS 인증이 다 돼서 스팸 안 걸리고 전달 가능.
→ **들어오는 메일**(`support@`·`reports@`·`dmarc@` reply/문의)은 MX가 없어 **전부 bounce**.

> ⚠️ 기존(v43) 가이드의 "Cloudflare Email Routing" 경로는 **폐기**. NS가 가비아에 그대로 있고
> SendGrid 인증도 가비아 콘솔에 박혀 있으므로, NS를 Cloudflare로 옮기면 오히려 기존 SendGrid 레코드까지
> 재설정해야 함. 가비아 DNS를 유지하면서 수신만 붙이는 **ImprovMX**가 최소 변경 경로.

---

## A. 수신(MX) 설정 — ImprovMX, 가비아 DNS 유지 (5분)

ImprovMX = 무료 이메일 포워딩. 들어온 메일을 개인 Gmail로 전달. NS 이전 불필요, MX 2개만 추가.

### A-1. ImprovMX 가입 + 도메인/별칭 등록 (2분)
1. https://improvmx.com → 무료 가입 (`seanbae1521@gmail.com`)
2. 도메인 입력: `pivoxquant.com`
3. Alias 추가 (각각 → `seanbae1521@gmail.com`):
   - `support@pivoxquant.com`
   - `reports@pivoxquant.com`
   - `hello@pivoxquant.com`
   - `dmarc@pivoxquant.com`  ← DMARC 리포트 수신용 (현재 rua가 이 주소)
   - (권장) catch-all `*@pivoxquant.com` → 오타도 잡음

### A-2. 가비아 DNS 콘솔에서 MX 2개 추가 (2분)
My가비아 → 도메인 통합 관리 → pivoxquant.com → **DNS 정보 → DNS 관리 → 레코드 추가**:

```
타입  호스트  값/위치                 우선순위  TTL
MX    @       mx1.improvmx.com         10       3600
MX    @       mx2.improvmx.com         20       3600
```

### A-3. SPF 병합 (1분) — ⚠️ 기존 레코드 수정, 추가 아님
현재 SPF: `v=spf1 include:sendgrid.net ~all`
→ ImprovMX include 를 **앞에 끼워** 같은 TXT 레코드를 **교체**:

```
타입  호스트  값
TXT   @       "v=spf1 include:spf.improvmx.com include:sendgrid.net ~all"
```
(SPF는 도메인당 1개만 유효 — 새로 추가하지 말고 기존 값을 위 문자열로 바꿀 것)

### A-4. 검증 (1분, propagation 후 ~10분~1h)
ImprovMX 대시보드가 MX/SPF 초록불이 되면 OK. 그 후:
```
다른 메일에서 → support@pivoxquant.com 으로 "test" 발송
→ seanbae1521@gmail.com 에 도착하면 수신 성공
```
또는 터미널:
```bash
dig +short MX pivoxquant.com   # mx1/mx2.improvmx.com 두 줄 나오면 성공
```

---

## B. 발신 실제 작동 검증 — SENDGRID_API_KEY (CEO 액션, 3분)

발신 DNS(SPF/DKIM/DMARC)는 됐지만, **Railway에 `SENDGRID_API_KEY`가 실제로 들어있어야** 발송됨.
전송 우선순위(`services/email/sender.py`): **SendGrid → Brevo → SMTP → (없으면 log 후 silent drop)**.

`/api/health` 는 `missing_recommended: 1` 만 알려주고 어느 키인지는 가리지 않음(보안). 후보는
`SENDGRID_API_KEY` 또는 `SENDGRID_WEBHOOK_PUBLIC_KEY` 둘 중 하나 (나머지 7개 recommended는
동작 증거로 SET 확정). 둘의 차이가 결정적:
- **SENDGRID_API_KEY 가 빠진 거면 → 17개 아티팩트 메일 전부 silent drop (발신 불능)**
- SENDGRID_WEBHOOK_PUBLIC_KEY 만 빠진 거면 → 발신 정상, open/click/unsubscribe 웹훅만 깨짐

### B-1. 어느 키가 빠졌는지 확정 (택1)

**방법 1 — Railway Deploy Logs (가장 빠름)**
Railway 대시보드 → web 서비스 → Deployments → 최신 → **Deploy Logs** →
부팅 로그에서 `LAUNCH_PREP env-missing [RECOMMENDED]` 줄 검색.
거기 적힌 키 이름이 빠진 것. `SENDGRID_API_KEY` 가 거기 있으면 발신 불능 확정.

**방법 2 — Railway Variables 탭에서 직접 확인**
web 서비스 → **Variables** → `SENDGRID_API_KEY` 존재 + 값 있는지 눈으로 확인.

### B-2. 없으면 추가
1. SendGrid 콘솔 → Settings → API Keys → **Create API Key** (Full Access 또는 Mail Send) → 키 복사
2. Railway → web 서비스 → Variables → **New Variable**: `SENDGRID_API_KEY` = (붙여넣기) → 저장(자동 재배포)

### B-3. End-to-end 발신 검증
Railway env 반영 후, 본인 명의 weekly_memo 1통 수동 trigger(또는 일요일 08:00 KST cron 대기):
- Gmail 받은편지함에 `reports@pivoxquant.com` 발신 도착 + 스팸함 X
- SendGrid 콘솔 → **Activity Feed** 에 Delivered 이벤트 확인

---

## 메모리 룰 검증
- ✅ `feedback_no_extra_cost`: ImprovMX Free + SendGrid Free 100/day → 추가 비용 0원
- ✅ `feedback_official_data_only`: 이메일 라우팅 (데이터 sourcing 아님)
- ✅ `legal_compliance`: PIPA + 전자상거래법 §13 표시의무 (support@ inbox 실존), 정통망법 §50 (List-Unsubscribe 헤더는 sender.py 이미 처리)

## 작성 근거 (traceability, 2026-05-23 실측)
- `dig MX/TXT/CNAME/NS pivoxquant.com` — 위 표의 모든 레코드 실측값
- `services/email/sender.py:327-342` — SendGrid→Brevo→SMTP 캐스케이드
- `services/launch_prep.py:89-158` — recommended env 인벤토리 9개
- `services/email/brevo_provider.py:95-97` — from `noreply@`, support `support@`
- memory `project_email_infra.md` (ImprovMX 0원 path) — Cloudflare 대신 채택 근거
