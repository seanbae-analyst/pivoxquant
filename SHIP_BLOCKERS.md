# PivoxQuant SHIP_BLOCKERS.md

**SoT**: 출시를 막는 것들의 단일 목록.
**최근 갱신**: 2026-09-05 20:16 KST (ship_blockers_audit 자동 — RELEASE-BLOCKER 7건 / SHIP-AT-RISK 5건 / POST-LAUNCH 15건 / 변호사 큐 21건)

> ⚠️ **2026-09-01 전면 재작성.** 직전 갱신이 2026-06-20 이었고, 그 사이
> **Railway 계정이 삭제**되면서 이 파일의 상당수가 무효가 됐다. "Railway env
> 에서 토글" 류의 해제조건은 가리키는 대상이 없다. 아래는 **오늘 실제로 확인한
> 것만** 남기고, 확인 못 한 것은 그렇게 표시했다.
>
> **이번에 실측으로 뒤집힌 항목 5건** — 전부 "PENDING 인데 실은 이미 끝나 있던" 것:
> A1(MX) · A7(사업자정보 env) · A8(미푸시 커밋) · A9(Anthropic) · P13/P14/P15(Railway 의존).

상태 코드: BLOCKED(외부 대기) / IN_PROGRESS / PENDING(미착수) / RESOLVED

---

## 🔵 지금 진행 중 — 백엔드 재구축 (2026-09-01)

| # | 항목 | Owner | 상태 |
|---|---|---|---|
| B1 | Supabase Postgres 구축 | agent | ✅ **완료** — 43 테이블 + alembic `049` stamp + `/api/health` 200 + 로그인 이후 API E2E 통과 |
| B2 | Google OAuth | agent | ✅ **완료** — 9/1 삭제돼 있던 클라이언트 복원 + 브랜딩 채우고 **프로덕션 게시**(심사 불필요, 민감범위 0) |
| B3 | Kakao OAuth | agent | ✅ **확인 완료** — 앱 정상, 로그인 ON, Redirect URI 2개 정확 |
| B4 | Render 앱 배포 | CEO | ✅ **완료 2026-09-04 22:38 KST** — Blueprint `pivoxquant` (srv-dadcjiv10e5c73eb60vg, singapore, plan free) `main@c1f6180`. `https://pivoxquant-api.onrender.com/api/health` → 200 `db:ok, missing_required:0`. ⚠️ free 플랜 = 유휴 시 spin-down, 첫 요청 50s+ 지연·일시 502 (실측) |
| B5 | 남은 키 수집 | — | ✅ **불필요 — 2026-09-01 재실측으로 소멸.** `.secrets/RENDER_PASTE_VALUES.txt` 의 15개 키가 `render.yaml` 의 `sync:false` 15개와 정확히 일치하고 **빈 값이 0개**다. FMP·KIS×2 는 이미 로컬 `.env` 에 있었고(len 32/36/180), Brevo 는 `cee3d291` 이후 **필요 없다**(캐스케이드가 SendGrid→Brevo→SMTP 이고 SendGrid·SMTP 자격증명이 있음). B4 는 이 항목을 기다리지 않는다 |
| B6 | Vercel 재연결 | agent | ✅ **완료 2026-09-04** — `RAILWAY_BACKEND_URL` **와 `NEXT_PUBLIC_API_URL`(sensitive, 우선순위 높음 — 5번째 연결점, pull 로는 빈값으로 보여 함정)** 둘 다 Render URL 로 PATCH + 재빌드. `www.pivoxquant.com/api/health` → 200, `/api/auth/me` → 200 |
| B7 | 브라우저 E2E | agent | 🟡 **curl E2E 만 통과** — `/api/auth/google`·`/api/auth/kakao` → 302, redirect_uri=`https://www.pivoxquant.com/api/auth/*/callback` 정확. **브라우저 검증 NOT-TESTED**: pivoxquant.com 이 agent 브라우저(Chrome 확장·앱 내 브라우저 둘 다) 조직 정책으로 차단됨. CEO 가 직접 로그인 1회 확인 필요 |

---

## 🟢 "무료 베타 출시" 에 실제로 걸리는 것 — **법무 블로커 아님**

CEO 가 이번 주 목표로 잡은 건 **무료** 배포다. 아래 R 목록이 위압적으로 보이지만,
**대부분 유상 거래를 전제로 성립하는 조항**이라 무료에는 걸리지 않는다.

| 블로커 | 무료 베타에 적용되나 | 왜 |
|---|---|---|
| R3 통신판매업 신고 | ❌ 아니오 | 전자상거래법상 **재화·용역의 판매**가 전제. 무료 제공은 통신판매가 아니다 |
| R4 Stripe 유료결제 | ❌ 아니오 | 애초에 게이트로 꺼져 있고, 무료면 켤 이유가 없다 |
| R1 변호사 의견서 | 🟡 성격이 달라짐 | 핵심 쟁점 §101 유사투자자문업은 **대가를 받고** 조언할 때 성립. 무료면 위험도가 크게 내려간다 |
| R7 KIS 시세 재배포 | 🟡 성격이 달라짐 | 문서 자체가 *"유료결제 활성화 시 상업 재배포 성립"* 이라고 적고 있다 |
| R5/R6 "변호사 검토 대기 중" 표기 | ❌ 아니오 | 표기를 **유지한 채** 운영하면 된다. 오히려 정직하다 |

**따라서 무료 클로즈드 베타를 막는 법적 블로커는 사실상 없다.** 지금 막고 있는 건
법무가 아니라 **B4 — Render 배포 하나뿐**이다. (B5 "키 수집"은 2026-09-01 재실측으로
소멸했다 — 위 표 참조. 값은 15칸 전부 준비돼 있다.)

⚠️ 단 이건 agent 판단이지 법률 자문이 아니다. R1 의견서를 받을 때 **"무료 운영은
§101 밖인가"** 를 질문 목록에 넣을 것. 순서는 **무료로 먼저 열고, 유료화 직전에
의견서**가 합리적이다.

---

## 🟥 RELEASE-BLOCKER (출시 전 해결 필수)

| # | 항목 | 카테고리 | Owner | ETA | 해제조건 | 상태 |
|---|---|---|---|---|---|---|
| R0 | ~~PIPA §28-8 국외이전 동의서가 사실과 다르다~~ → **문구 정정 완료** (2026-09-06, CEO 지시). Anthropic 제거 · Railway→Render · **Supabase(서울) 신규 행** 분리 · terms 제6조 §2 AI 면책 조항 · 온보딩 필수 동의까지. 잔여: **기존 가입자는 옛 문구로 동의한 상태** — 소급 재동의 여부는 변호사 판단 | legal | CEO + 변호사 | — | 변호사 §28-8 사인 (서울 리전이 국외이전 대상인지 포함) | 🟠 **부분 해소** |
| R1 | 변호사 일괄 의견서 Q1-Q15 + Q-S1/S3/S4 + Q-M1/M2/M3 (총 21건) | legal | CEO + 변호사 | 미정 (CEO 미팅 예약 전) | 금융규제·자본시장법 전문 변호사 사인. 예상 300-500만원 1회 의견서 | BLOCKED |
| R2 | Q-S1 정통망법 §50 분리 동의 framework 답변 | legal | 변호사 | 미정 | 환영 메일 + onboarding nudge + retention 메일 (B/C 분류) 발송 가능 여부 사인 | BLOCKED |
| R3 | 통신판매업 신고 (성동구청, 등록세 ~45,000원) | legal | CEO | 미정 | 신고 완료 → `PIVOX_COMMERCE_REGISTERED=true` 전환, Stripe Live 활성 가능 | PENDING |
| R4 | Stripe 유료결제 활성화 (require_business_registration 게이트) | billing | CEO | R3 + R1 후 | R3 신고 완료 + R1 Q-S3 (§101 ②월구독 충돌) 사인 | BLOCKED |
| R5 | terms-ko.md "변호사 검토 대기 중" 표기 제거 | legal | CEO | R1 후 | 변호사 사인 후 표기 제거 | BLOCKED |
| R6 | privacy-ko.md "변호사 검토 대기 중" 표기 제거 | legal | CEO | R1 후 | 변호사 사인 후 표기 제거 | BLOCKED |
| R7 | KIS 시세 재배포 라이선스 갭 — `kis_market_adapter.py`가 KIS Open API로 임의 KR 종목/지수 시세를 받아 전 유저 대시보드(/market)·PDF·시그널에 표출(fetcher "KR: KIS primary"). KIS 앱키 ≠ 상업 재배포 권한, KRX/KOSCOM 정보이용계약 필요(비제도권 핀테크 제휴 불가). 유료결제 활성화 시 상업 재배포 성립 | legal/data | CEO+변호사+엔지니어 | R1/R4 전 | (택1) FMP 상위플랜 업그레이드(⚠️실측 2026-06-03 현 Premium $29는 KR 미서빙·US만, KR fallback 배선도 없음) / 또는 금융위 공공데이터 T+1로 전환(무료·재배포OK but 실시간 아님) / 또는 KOSCOM 시세라이선스 체결(fintechdata@koscom.co.kr, 적격성 OPEN) / 또는 prod `KIS_USE_REAL=0`+KR 라우팅 제거(KR 실시간 시세 전면 중단). KIS는 본인계좌(표면1) 격리. **무료 드롭인 대체 없음** — 비용/품질/리스크 trade-off. Q-KIS1~4 변호사 사인 | BLOCKED |

**출처**:
- R1: `legal_question_queue.md:9-148` (21건 누적, 2026-05-28 Q-S4 추가)
- R2: `legal_question_queue.md:40-65` (Wave D Sub-wave 2 BLOCKER, C-S1/S5/S2/R1/AC1 이메일 4종 OFF)
- R3: `business_registration.md:36` + `legal_question_queue.md:67-97` (Q-S3 §101 ② 상호작용 회색지대)
- R4: `MEMORY.md` Brand 섹션 + `session_2026-05-28.md:60` carry-over
- R5/R6: `autopilot_log.md:98` "Privacy-ko.md 변호사 검토 대기 중 — CEO must remove after lawyer review"

---

### R0 상세 — 가입 **필수** 동의가 없는 처리자를 명시한다

`(auth)/signup/page.tsx:599` 의 국외이전 동의는 **[필수]** 라 이게 틀리면
**가입 자체가 잘못된 고지 위에서 이뤄진다.** 현재 문구:

> PIPA §28-8 — Anthropic / Vercel / Railway / Google / SendGrid 외 …

세 가지가 사실과 다르다 (2026-09-02 실측):

1. **`Railway` — 계정이 삭제됐다.** 실제 백엔드는 Render, DB 는 **Supabase
   `ap-northeast-2`(서울)**. 서울 리전이면 그 부분은 애초에 "국외 이전" 이
   아닐 수 있다 — 즉 빼야 할 뿐 아니라 **분류 자체가 달라질 수 있다.**
   (`privacy-ko.md:26,167,252`)
2. **`Anthropic` — 더 이상 데이터가 가지 않는다.** `privacy-ko.md:169` 는
   "AI 기능 입력값·포트폴리오 요약" 이 Claude API 로 전송된다고 적지만,
   `services/ai/` 는 **2026-09-01 커밋 `e19f28c3` 에서 삭제**됐고 런타임에
   Anthropic 을 한 번도 부르지 않는다. **일어나지 않는 이전에 필수 동의를
   받고 있다.**
3. **`privacy-ko.md:195` 의 AI기본법 §31 고지가 반대로 틀렸다** — "본 서비스가
   인공지능에 기반하여 운용됨을 고지" 라고 적혀 있으나 AI 기능이 없다.
4. **저장소가 표에 없다 (2026-09-02 추가).** 처리위탁 표에 **`Supabase` 가
   한 번도 등장하지 않는다** (`grep -c Supabase privacy-ko.md` → **0**).
   실제 개인정보(users·portfolio·trade 43테이블)는 Supabase
   `ap-northeast-2`(서울) 에 있고 Render 는 앱만 돌린다. 그런데 표의 호스팅
   행은 "서비스 데이터 전반 … **데이터 저장**" 을 그 행에 귀속시킨다.
   → ①의 "Railway 를 뭘로 바꾸나" 는 **치환 문제가 아니다.** 행 하나를
   갈아끼우면 저장 위치를 틀리게 진술하게 된다. 최소 **행 분리**(앱 호스팅
   = Render/미국, 데이터 저장 = Supabase/서울)가 필요하고, 서울 저장분이
   §28-8 대상인지는 변호사 판단이다.
5. **온보딩 필수 동의에도 같은 AI 문구가 있다 (2026-09-02 추가).**
   `frontend/src/data/onboarding-questions.ts` 의 `ai_advisory` 항목이
   `required: true` 로 *"PivoxQuant은 AI 기반 분석 정보를 제공하며"* 를 받고
   있다. ②③ 과 같은 문제이고 signup 동의와 **함께** 고쳐야 문구가 갈라지지
   않는다.

⚠️ **에이전트가 단독 재작성하지 않는다.** ①의 올바른 처리자 목록은 Render 리전
확정 후에야 정해지고, ②③ 은 "빼면 되는" 것처럼 보여도 §28-8 필수 고지문이라
변호사 검토 전 개인정보처리방침 본문을 고쳐 쓰는 건 범위를 넘는다.

> 🔁 **2026-09-02 — 이 경고를 한 번 어겼고, 되돌렸다.** 커밋 `8f9e1670` 이
> Anthropic 행 제거 + Railway→Render 치환 + 동의 문구 정정을 단독으로 했다가
> `3464912b` 로 revert 됐다. 실패 원인이 위 ④ 그대로다 — 기계적 치환이
> **저장 위치를 틀리게 진술**했고, 부분적으로 맞는 고지문은 틀린 것보다 낫지
> 않다(정정한 외관 때문에 더 늦게 발견된다). ④⑤ 는 그때 얻은 소득이다.
> **다음 세션도 여기서 멈출 것.** 고칠 준비가 됐다는 신호는 두 가지다:
> Render 리전 확정 + 변호사 §28-8 사인.

~~**지금 노출은 없다**~~ → **2026-09-04 22:38 부터 노출된다.** 백엔드가 Render 에서 살아나 가입이 열렸다. CEO 가 "일단 무료로 배포" 지시로 알고 진행한 상태 — 변호사 사인 전까지 이 문구로 동의를 받는다는 사실을 기록한다.
그래서 이건 "지금 터진 사고" 가 아니라 **Render 가 살아나는 순간 터지는 것**이고,
따라서 **B4 배포와 같은 게이트에 묶어야 한다.** 배포 → 가입 재개 사이에 정정할 것.

출처: 2026-09-02 daily-sweep P0 (`AUTOPILOT_BACKLOG.md` 상단), 본 세션 재확인.

## 🟧 SHIP-AT-RISK (출시 가능하나 운영 리스크 큼)

| # | 항목 | 카테고리 | Owner | ETA | 해제조건 | 상태 |
|---|---|---|---|---|---|---|
| A1 | ~~DNS MX 미설정~~ → **RESOLVED** | email | — | ✅ 2026-09-01 실측: `mx1/mx2.improvmx.com` 둘 다 등록, SPF=`v=spf1 include:spf.improvmx.com include:sendgrid.net ~all` | 가비아 MX **2줄**(mx1.improvmx.com 우선순위10 · mx2.improvmx.com 20) + catch-all `*@pivoxquant.com`(13 alias). ⚠️정정 2026-06-09: "MX 1줄+alias 4개"는 부정확. `project_email_infra.md:28` 2026-06-04 로그상 MX 2줄 active → **확인만 필요(RESOLVED 추정)** | ✅ RESOLVED (9-01 실측: MX 2줄 + SPF 정상) |
| A2 | Brevo fallback API key 미설정 | email | CEO | 미정 | Brevo 가입 + API key 발급 → **Railway** env `BREVO_API_KEY` / `BREVO_FROM_EMAIL` / `BREVO_FROM_NAME`. ⚠️정정 2026-06-09: 소비처가 백엔드(`services/email/brevo_provider.py`)라 Vercel 아닌 **Railway**. 베타 규모 비차단(출시 후 OK) | ✅ RESOLVED (Brevo 6-30 라이브 — CLAUDE.md 참조). 단 **Render env 에 재입력 필요** |
| A3 | SENDGRID_WEBHOOK_PUBLIC_KEY 미설정 (이벤트 추적 OFF) | email | CEO | 미정 | SendGrid Event Webhook 서명 키 입력 → `/api/webhooks/sendgrid` 503 해제. 발송과 무관, 추적만 OFF | PENDING |
| A4 | `~/.pivoxquant-env` 8개 변수 — **건너뛰기 권장** | env | CEO | — | ⚠️정정 2026-06-09: 랩탑 crontab/launchd 2026-05-28 RETIRED. 8변수 전부 타 항목 중복/무가치(SLACK=A5, SENDGRID=완료, STRIPE=R4, DATABASE_URL=Railway 자동, GPG·SENTRY 3종=죽은 로컬). Sentry 발신은 SENTRY_DSN 으로 이미 라이브 → **입력 불필요** | SKIP |
| A5 | Slack webhook URL 미설정 (모든 alert silent) | env | CEO | 미정 | Slack incoming webhook 발급 → Railway env `SLACK_WEBHOOK_URL` + `~/.pivoxquant-env` | PENDING — 단 해제조건이 'Railway env' 라 **Render 로 읽을 것** |
| A6 | Naver News API key 미설정 (`.KS` News empty) | data | CEO | 미정 | Naver Developers 등록 → Railway env 입력 | PENDING — 해제조건 'Railway env' → **Render** |
| A7 | Vercel 사업자정보 footer env 6개 미입력 (전자상거래법 §13) | env | CEO | 미정 | Vercel env(canonical, `business-info.ts` SoT): NEXT_PUBLIC_BUSINESS_NAME / _REPRESENTATIVE / _REGISTRATION_NUMBER / _ADDRESS / _TYPE / **_SUBTYPE**. ⚠️정정 2026-06-09: 기존 목록 5개로 `_SUBTYPE` 누락 → **6개가 맞음**. 상세 `docs/ops/ceo_env_checklist_2026-06-09.md` | ✅ RESOLVED (9-01 실측: Vercel prod 에 BUSINESS_* 6종 전부 존재) |
| A8 | 로컬 **16 commit** push 안 됨 (v59~v62) | infra | CEO | go 대기 | reconcile 후 push (feedback_push_workflow). ⚠️정정 2026-06-09: 14→**16 commit**, canonical=`~/Desktop/취준/pivoxquant`(~/dev 아님). 실측 `git cherry`로 **push 무유실 확정** + 전수테스트 **3868 passed/0 fail(exit0)** → 랜딩 안전, CEO go 만 남음 | ✅ RESOLVED (9-01 실측: `38beb633` 은 origin 에 있음 — 미푸시가 아니라 미머지였음) |
| A9 | Anthropic 크레딧 0 → 챗봇 LLM OFF, FAQ 즉답만 작동 | infra | CEO | 미정 | 크레딧 충전 시 `SUPPORT_CHAT_LLM_ENABLED=1` 전환. 미충전 시 FAQ 검색만 (0원 운영) | ✅ **무효화** — 9-01 지원 챗봇 제거로 Anthropic 소비자 0. 크레딧과 무관해짐 |
| A10 | VAPID env 미설정 (push 알림 OFF) | env | CEO | 미정 | ⚠️정정 2026-06-09: "Vercel만" 아니라 **2곳 분리** — 공개키 `NEXT_PUBLIC_VAPID_PUBLIC_KEY`=**Vercel**, 비밀키 `VAPID_PRIVATE_KEY`+`VAPID_EMAIL`=**Railway**. `npx web-push generate-vapid-keys` 1회로 쌍 생성 | 부분 RESOLVED — 공개키는 Vercel 에 존재(9-01 실측). **비밀키는 Render 에 재입력 필요** |
| A11 | 변호사 미팅 자료 준비 (사업자등록증 PDF, terms/privacy, regulatory 자료, Q-S1 KISA 가이드) | legal | CEO | R1 전 | 자료 패킷 완성 → 변호사 컨택. ⚠️갱신 2026-06-09: 상담A 의뢰서 마감(Q-A10 만14세·A11 §50분리동의·A12 업태·A13 §17환불 추가 + 국외수탁자 6→8 정정 + 별첨 라이브경로). md+html 갱신, **PDF 재export 필요(weasyprint 환경 미비)** | IN_PROGRESS |
| A12 | `dd_checklist_email.html` 면책 §6 verbatim + §101 footer 미포함 (`_disclaimer.html` include 없음, 단문 1줄만) | legal | CEO+변호사 | R1/Q-S1 후 | 변호사 사인 후 `_disclaimer.html` include 전환 또는 §6+§101 문구 수동 추가 (코드 주석 NEEDS_CONFIG.md §11) | BLOCKED |
| A13 | `brag_card_email.html` 인라인 면책에 §101 "미신고 면제 트랙" footer 누락 + `_disclaimer.html` 동기화 단절 | legal | CEO | R1/Q-S1 후 | §101 footer 문구 수동 추가 또는 `_disclaimer.html` include 전환 (이메일 CSS 호환 확인) | PENDING |

**출처**:
- A1: `project_email_infra.md:28` "ImprovMX 수신(MX 레코드 + alias) 미설정"
- A2: `project_email_infra.md:140-161` Brevo 설정 + `session_2026-05-28.md:40` "Brevo 키 부재"
- A3: `project_email_infra.md:18` "SENDGRID_WEBHOOK_PUBLIC_KEY 단 하나 누락"
- A4: `project_automation_v2.md:118-129, 143-149` 8개 env 변수 carry-over
- A5: `project_automation_v2.md:121` SLACK_WEBHOOK_URL carry-over
- A6: `autopilot_log.md:99` "Naver News API key Railway env var missing"
- A7: `business_registration.md:37-43` Vercel env 6개 footer
- A8: `session_2026-05-28.md:14, 60` "push 안 함" + `session_2026-05-26.md:38, 41` push reconcile carry-over
- A9: `session_2026-05-26.md:41` "Anthropic 크레딧 충전 시 SUPPORT_CHAT_LLM_ENABLED=1"
- A10: `MEMORY.md` v49.1/.2 "VAPID env 근본수정" + `session_2026-05-22-v49.md:24` "VAPID env 미설정(CEO Vercel)"
- A11: `legal_question_queue.md:171-183` CEO 액션 + `MEMORY.md` v45 컨택 가이드
- A12/A13: `docs/qa/legal-advisory-audit-2026-06-03.md` §2 M2 (compliance-gatekeeper 면책 매트릭스 — 23 템플릿 중 2건만 §6/§101 누락, 나머지 21건 완비)

---

## 🟨 POST-LAUNCH (출시 후 처리 가능)

| # | 항목 | 카테고리 | Owner | ETA | 해제조건 | 상태 |
|---|---|---|---|---|---|---|
| P1 | NPS baseline 수집 (분석 시스템 가동) | data | agent | 출시 +30일 | 가입자 ≥50 후 첫 NPS 설문 | PENDING |
| P2 | PIPA §28-8 국외이전 신고 (SendGrid/Brevo + Stripe + Vercel + **Render** + **Supabase** 이전 — ⚠️ 수탁자 목록이 바뀌었다. Anthropic 은 챗봇 제거로 빠짐) | regulatory | CEO + 변호사 | R1 사인 후 | 변호사 사인 → 신고서 제출 | BLOCKED |
| P3 | 세무 고문 계약 (월 ~100,000원, 6월부터 권고) | finance | CEO | 출시 후 | 세무사 컨택 | PENDING |
| P4 | 법인카드 발급 | finance | CEO | 출시 후 | 은행 신청 | PENDING |
| P5 | 출시 +7일 후: `PIVOX_FUNNEL_ALERT_MODE=alert` + `PIVOX_ERROR_RATE_MODE=alert` 전환 | env | CEO | 출시 +7일 | **Render** env 토글 | PENDING |
| P6 | 출시 +7일 후: `PIVOX_H4_MODE=enforce` + `PIVOX_H9_MODE=enforce` 전환 | env | CEO | 출시 +7일 | **Render** env 토글 | PENDING |
| P7 | 정통망법 §50 시행령 재스캔 (매출 6% 과징금 + 야간 22-08 시간대 별도 동의 + 2년 주기 재확인 자동화) | regulatory | agent | 2026-08-15 | 시행령 공포 후 6개월 추적, 재스캔 자동 | PENDING |
| P8 | DMARC 정책 `p=none` → `p=quarantine` 검토 | email | CEO | 출시 +30일 | 모니터링 리포트 검토 후 강제 모드 전환 | PENDING |
| P9 | Q-S4 영문 레짐 신호 (engine.py "avoid new longs"/"momentum favors longs") KR/EN 비대칭 정리 | legal | 변호사 → agent | R1 후 | 변호사 사인 후 (a) engine.py 영문 중립화 or (b) legal_filter 영문 패턴 추가 or (c) 현 구조 유지 결정 | BLOCKED |
| P10 | persona 이중 매핑 (PDF taxonomy vs 피어 코호트 taxonomy) blind 통합 검토 | data | persona-quant-domain agent | 출시 후 | 도메인 판단 필요 (의도적 별개 가능성) | PENDING |
| P11 | DEFERRED 기존 carry-over: regime Sharpe rf / VARCHAR(10) / email_category flag / SSE Vercel proxy / agent_worker | infra | agent | 출시 후 | 개별 도메인 판단 | PENDING |
| P12 | DEFERRED owner 판단 항목: 알림 prefs 6 event wiring / past_due 강등 정책 / refund 부분환불 §17 / DCA XIRR / backtester lookahead / Composer synthetic backtest / KR 52w KIS range / SSE 테스트 인프라 / worktree 20 locked | infra | agent + CEO | 출시 후 | 개별 결정 | PENDING |
| P13 | ~~merry-abundance Railway 프로젝트~~ | infra | — | — | ✅ **무효** — Railway 계정 자체가 삭제됨(2026-08-30). 과금 대상 없음 | RESOLVED |
| P14 | ~~구 Desktop 트리 삭제~~ | infra | — | — | ✅ **무효 (방향이 반대였음)** — canonical 은 `~/dev` 가 아니라 **`~/Desktop/취준/pivoxquant`** 다. 지우면 안 되는 트리였다 | RESOLVED |
| P15 | section101 fix prod 배포 | regulatory | CEO | B4 후 | ⚠️ 해제조건이 'Railway auto-deploy' 였다 → **Render 첫 배포 시 자동 반영**으로 대체 | PENDING |

**출처**:
- P1: `analytics_metrics.md` (메모리 인덱스)
- P2: `legal_question_queue.md:18-21` Q6 cross_border + `project_email_infra.md:265-266`
- P3/P4: `business_registration.md:44-45`
- P5/P6: `project_automation_v2.md:147-149`
- P7: `legal_question_queue.md:161-165` Q12 정통망법 §50 시행령 추적
- P8: `project_email_infra.md:105` "출시 후 p=quarantine 검토"
- P9: `legal_question_queue.md:142-147` Q-S4 + `session_2026-05-28.md:55`
- P10: `session_2026-05-28.md:50` DEFERRED persona-quant-domain
- P11: `session_2026-05-24.md:80` 기존 carry-over
- P12: `session_2026-05-22-v49.md:42` DEFERRED owner 판단 + `MEMORY.md` v49~v51
- P13: `session_2026-05-27.md:16` merry-abundance 정체불명
- P14: `session_2026-05-26.md:41` 구 Desktop 11G 삭제
- P15: `project_automation_v2.md:31` "미배포: fix는 로컬 working tree만"

---

## 부록 — RESOLVED (참고용, 최근 해결)

| # | 항목 | 해결 일자 | 출처 |
|---|---|---|---|
| ✅ | **베타 게이트 폐기** — CEO "일단 무료로 배포, 베타비번 폐기". `/beta-gate`·`/api/beta-auth`·middleware 게이트·`BETA_PASSWORD`/`BETA_SIGNING_SECRET`(코드+Vercel env) 전부 삭제. prod 는 06-25 부터 이미 게이트 OFF 였음 | 2026-09-04 | 커밋 `chore(beta)` / `MEMORY.md` Brand |
| ✅ | BETA_PASSWORD rotate 영구 해결 (`<BETA_PASSWORD>` 평문 고정값 + Vercel REST API, literal은 MEMORY.md/Vercel env 만) | 2026-05-26 | `MEMORY.md` Brand 섹션 |
| ✅ | OAuth provisioning_failed P0 hotfix (alembic 035 prod 미적용 → _do_migrations runtime ADD COLUMN) | 2026-05-17 v44.7 | `MEMORY.md` |
| ✅ | Railway PG too-many-clients (pool 3/2 + self-heal 가드 7개) | 2026-05-20 v46 | `MEMORY.md` Brand 섹션 |
| ✅ | SendGrid Domain Authentication 완료 (SPF+DKIM+DMARC) | 2026-05-20 | `project_email_infra.md:23-27` |
| ✅ | PDF 이메일 END-TO-END 실발송 검증 (admin diag 엔드포인트) | 2026-05-20 v46.2 | `project_email_infra.md:10-12` |
| ✅ | Sentry prod ingest 라이브 확정 (event id be776584 검증) | 2026-05-26 | `project_automation_v2.md:33-37` |
| ✅ | Vercel V2 플래그 9개 모두 true (LOGIN/SIGNUP/HOME/PORTFOLIO/SIGNALS/REPORTS/RISK/SETTINGS/PROFILE) | 2026-05-20 v45.8 | `autopilot_log.md:31` |
| ✅ | section101 §101 요건3 prod BLIND 버그 fix (artifacts.content → data_json) | 2026-05-26 | `project_automation_v2.md:27-31` (로컬만, prod 배포는 P15) |
| ✅ | 사업자등록 발급 (459-01-03808, 피복스퀀트(PivoxQuant)) | 2026-05-08 | `business_registration.md` |
| ✅ | i18n 한글화 (온보딩 + 컴포넌트 + 페르소나 8종) | 2026-05-28 | `session_2026-05-28.md:26` commit 3198edc1+2cd797d4 |

---

## 운영 메모

- **CEO만 가능한 작업**: 변호사 컨택 / DNS 가비아 콘솔 / Vercel env 입력 / 신고서 제출 / 결제 활성화 / push reconcile (canonical=~/dev/pivoxquant)
- **agent 가능**: 코드 변경 / 테스트 작성 / 메모리 갱신 / 외부 액션 진행 시 follow-up 자동 수행
- **본 매트릭스 갱신 트리거**: (a) 매일 06:27 morning-briefing prepend (b) CEO/변호사 답변 수령 시 즉시 (c) prod env 변경 시 즉시
- **신규 BLOCKER 발견 시**: 본 파일 PR로 갱신, 추측·날조 항목 절대 금지 — 메모리 file:line 출처 인용 필수
