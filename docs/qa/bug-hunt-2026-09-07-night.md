# 버그헌팅 — 2026-09-07 밤 (자율 세션)

CEO 취침 중 자율 모드. 브랜치 `chore/email-flags-on`.
**전부 실측 후 수정 + 회귀 테스트.** 추정으로 적은 항목 없음.

---

## 🔴 P0 — 콜드스타트가 타임아웃보다 길다

| 측정 (prod, 09-07) | 값 |
|---|---|
| `/api/health` **콜드** | **43.9s** |
| `/api/health` **웜** | 0.52s (3회, ±0.02) |
| 프론트 `DEFAULT_TIMEOUT_MS` | **30s** |

30s 가 두 값 **사이**에 있다. Render 무료 플랜은 15분 유휴 후 스핀다운하므로,
유휴 뒤 들어오는 방문자는 첫 요청이 30초에 중단되고 `408` 을 본다 — 서버가
죽은 게 아니라 **부팅 중**인데도. 트래픽 없는 클로즈드 베타는 대부분 잠들어
있으니 사실상 **첫 로드가 거의 항상 실패**한다.

발견 경위: "웜" 이라고 이름 붙여 돌린 curl 이 43.9초에 돌아왔다.

**조치** `80f53a05` — 읽기 요청에 한해 타임아웃 시 **1회 재시도**.
첫 시도가 곧 서비스를 깨우는 요청이므로 재시도는 웜 서버에 착지한다.
경계를 좁게 잡았다: 우리 타임아웃일 때만 · 1회만 · GET/HEAD/OPTIONS 만
(타임아웃난 POST 는 서버가 이미 받았을 수 있어 중복 생성 위험) ·
호출자가 자기 `timeoutMs` 를 준 경우 제외 · 호출자 취소는 그대로 throw.

⚠️ **완치가 아니라 완화다.** 근본 해결은 서비스가 자지 않는 것 —
유료 인스턴스 또는 낮시간 keep-alive 핑.

---

## 🟠 P1 — 관리자 화면 전체가 모두를 차단하고 있었다

`admin/layout.tsx` 가 `/admin/*` 전체를 호출 1건의 성공 여부로 게이트하는데,
그 호출이 `/api/admin/artifacts/list` 였다. 8-31 prune 이 artifact 라우트를
전부 지웠고 **백엔드 url_map 에 `/artifact/` 매칭이 0건**(앱 부팅해
`iter_rules` 스캔으로 확인, grep 아님).

404 → "관리자 아님" → 소유자 포함 **전원 거부**. 고객문의를 읽는 유일한 화면인
`/admin/support` 가 그동안 접근 불가였다. 빈 not-found 로 **fail-closed** 라
정상 거부와 구분이 안 돼 아무도 눈치채지 못했다.

같은 트리의 죽은 길 2개도 prod 실측으로 확인:
- `admin/page.tsx` → `/admin/preview` 로 리다이렉트 (**prod 404**)
- 네비게이션에 `Artifact Preview` 링크 (같은 404)

**조치** `e1dc8e64` — 게이트를 살아있는 `/api/support/admin/inquiries`
(자체 ADMIN_EMAILS 게이트)로 교체, 인덱스는 `/admin/support` 로, 죽은 링크 제거.
`API.admin.artifacts*` 는 소비자 0(심볼로 확인) 이 되어 제거.

---

## 🟠 P1 — 거래 확인 푸시가 404 에 떨어진다

`push_service.py` 가 거래 확인 딥링크를 `/trades` 로 보냈다. prod **404**,
리디렉션도 없다. 푸시는 폰에서 누르는 링크라 **닿은 적 없는 페이지로
돌아갈 뒤로가기가 없다.** 거래내역은 `/portfolio` 의 `RecentTransactionsBlock`
에 있다.

같은 파일의 `/alerts` 는 308 로 `/mirror` 에 갔다 — 동작은 했지만 삭제된
라우트를 경유. 벨 알림은 모든 대시보드 화면의 상단바 드롭다운에 있으므로
`/mirror` 가 원래 목적지다.

**조치** `032fb7b2`

---

## 🟡 P2 — 로그인마다 리다이렉트 한 홉

`routes/auth._safe_next` 가 모든 OAuth 로그인을 `/home` 으로 보냈고, 프론트는
그걸 308 로 `/mirror` 에 넘긴다. 더 아픈 지점은 **이 함수의 존재 이유가 죽은
라우트를 살아있는 것으로 매핑하는 것**인데(docstring 에 그렇게 적혀 있다)
자기 fallback 이 죽은 라우트였다는 것. 2026-05-03 `/landing` → 404 P0 핫픽스가
같은 함수의 같은 유형이었다.

**이 함수는 테스트가 0개였다** (tests/ 전수 grep). open-redirect 방어인데.

**조치** `032fb7b2` — 기본값 `/mirror`, 그리고 보안 절반부터 고정하는 테스트:
scheme-relative · 절대 URL · `javascript:` · 비문자열 · 쿼리스트링 뒤에 숨긴
스킴 전부 fallback, 그리고 "fallback 자신이 삭제된 라우트가 아닐 것".

---

## 🟡 P2 — 나가는 메일 5통 전부 CTA 가 삭제된 라우트

welcome · d3_guide · d7_summary · d30_summary · inactive_nudge **전부**
주 버튼이 `/home`. 넛지 기본값 기준 실측 체인:
`pivoxquant.com/home` → 307 → `www` → 308 → `/mirror`. **2홉.**

`_dashboard_url()` 이 **3벌**이었고 이미 갈라져 있었다 — 온보딩·리텐션은
`FRONTEND_URL` 에서 유도, 넛지만 apex 하드코딩(추가 홉의 출처).
CLAUDE.md §10 이 기록한 바로 그 실패 유형.

**조치** `0146e51f` — `services/email/urls.py` 하나로 통합, 목적지 `/mirror`,
fallback 호스트를 `www` 로(apex 는 307 만 할 뿐이고 render.yaml 도 www 다).

---

## 🟢 수정 — 컴플라이언스 체크가 네트워크 문제를 법 위반으로 오보

`email_compliance_check.py` 가 `ssl.create_default_context()` 를 CA 번들 없이
만들어, 이 맥에서 SendGrid POST 와 opt-out GET 이 **둘 다** 인증서 오류로
죽고 "§50 위배 가능성 FAIL 2건" 을 보고했다. `certifi` 는 이미
`requirements.txt:29` 에 있고 28번 줄 주석이 "다른 야간 스크립트는 이미
certifi 를 명시적으로 쓴다"고 적고 있다 — 이 파일만 빠져 있었다.

**조치** `c9665e9f`. 그리고 SSL 가림막을 걷자 진짜 상태가 드러났다 —
**SendGrid 401 `Maximum credits exceeded`**.

---

## 확인했으나 문제 없던 것 (측정 범위 기록)

- naive/aware datetime 혼용 — 실사용 0 (주석뿐)
- 나눗셈·statistics 분모 가드 — 전부 있음
- `except: pass` / bare except — 0건
- FX 다통화 합산 — `fx_service.cost_basis_krw` 로 정규화, 주석에 버그 이력까지
- i18n — 235키 사용, ko/en 양쪽 누락 0, 로케일 간 차이 0
- 온보딩 v3 법적 확인 항목 — 프론트/백엔드 5개 정확히 일치
- 알림 매트릭스 — `NOTIFICATION_EVENT_IDS` 2종과 UI 일치, 테스트도 있음
- `d7_pro_nudge` 내부 편집 노트 — `PIVOX_PAID_PLANS_ENABLED` 가드 정상 작동
- `sw.js` 의 죽은 `/api/*` 경로들 — `PRECACHE_ASSETS = [OFFLINE_URL]` 뿐이라
  설치가 깨지지 않는다. 매칭 안 되는 캐시 전략 설정일 뿐 = **버그 아님**.
  (SW 는 캐시 생명주기 위험이 있어 손대지 않았다.)
- `manifest.ts` · `robots.ts` 경로 — 전부 살아있는 라우트

---

## 관통하는 한 가지

5건 중 4건이 **같은 유형**이다 — *8-31 prune 이 화면을 지웠는데 그걸 가리키는
링크는 남았다.* next.config.ts 의 리디렉션이 대부분을 덮어줘서 브라우저에서는
안 보이고, 그래서 테스트로만 잡힌다. 오늘 `/portfolio` 죽은 행 클릭까지 세면
5건이다.

리디렉션이 없는 곳(`/trades`, `/admin/preview`)만 404 로 드러났다.

---

## 검증

pytest **2063 passed / 0 failed** (18 skip, 1 xfail) — 세션 시작 2021 대비 +42 신규
vitest **382 passed** (372 + 10 신규) · tsc 0 · eslint 0 · next build exit 0
부팅 `rules 121 / bp 23`

신규 테스트 3파일 전부 **공허하지 않음 확인** — 각각 이전 리비전에 대고 돌려
실패하는 것을 봤다 (email 17개 중 6개 실패 / routing 전량 / api 재시도 2개).

## CEO 확인 필요

1. **Brevo 키** (앞서 안내한 4단계) — 없으면 무료 플랜에서 메일이 못 나간다
2. **낮시간 keep-alive 핑** — P0 의 근본 해결. 08:00–21:00 KST 만 5분 간격이면
   월 ~403h 로 무료 750h 안에 넉넉히 들어간다
3. `chore/email-flags-on` 머지 — 발송 경로 확인 후가 맞다
