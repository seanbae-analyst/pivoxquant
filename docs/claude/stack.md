# 기술 스택 · 구조 — 상세

> CLAUDE.md 에서 옮겨 온 원문 (2026-09-11). CLAUDE.md 에는 한 줄 요약만 남겼다. 코드 주석의 "CLAUDE.md §기술" 은 이 문서를 가리킨다.

## 기술 스택

- **Backend**: Flask + SQLAlchemy + PostgreSQL(Supabase) / SQLite(local)
- **Frontend**: Next.js 16 + TypeScript + Tailwind 4 + SWR + motion/react
- **AI**: **없음 — 코드까지 삭제됨.** 2026-09-01 지원 챗봇 제거로
  `ANTHROPIC_API_KEY` 의 마지막 실사용처가 사라졌고, 같은 날 죽은 코드를
  **트리에서도 걷어냈다**: `services/ai/`(9개 공개 메서드 + 3개 모델 클래스),
  `services/ai_budget.py`, `container.ai` 싱글턴, `fetcher.score_news_sentiment`
  (+`_score_news_with_ai`/`_score_news_keywords`), `cache_service` 의
  `ai_result_cache_*`/`earnings_tone_*`. 전부 **호출처 0곳**임을 확인 후 삭제했고,
  삭제 전후 URL rule 120 / blueprint 23 이 동일하다. 런타임에 Claude API 를 한 번도
  부르지 않는다. 되살릴 거면 **소비자부터** 만들 것 (원본은 `git show cee3d291:services/ai/service.py`).
  ⚠️ `anthropic_usage_log` 테이블 + migration 042 + `scripts/nightly/
  anthropic_cost_estimate.py` 는 **남겼다** — `pipa_purge` 가 참조한다.
  🟥 **법적 후속 조치가 미완이다.** 개인정보처리방침이 아직 Anthropic 을
  국외 처리자로 명시하고(`privacy-ko.md:169`) 가입 **필수** 동의 문구에도
  들어 있다(`signup/page.tsx:599`). 코드가 사라졌으므로 **일어나지 않는
  이전에 동의를 받는 상태**다. `SHIP_BLOCKERS.md` R0 (컷오버 게이트) 참조 —
  Render 배포 전에 정정해야 한다.
- **Broker**: KIS 한국투자증권 (read-only — `services/kis/service.py` 의
  `KIS_READ_ONLY` 가드 3곳). Alpaca 는 데이터 fallback stub 만
  `ALPACA_ENABLED` 게이트(기본 OFF)로 잔존.
  **토스증권 Open API 는 운영자 본인 계좌 read-only 전용** (2026-09-10,
  `services/toss/` + `scripts/pivox_report.py`, GET allowlist 9개 · 주문 경로 0개).
  리포트는 `services/behavior/*_mirror` **함수를 그대로** 실계좌 이력에 댄다 —
  거울 로직을 두 벌 만들지 마라 (함정 §10 과 같은 이유).
  유저용 브로커 연동은 여전히 `BROKER_LINKING_AVAILABLE=false` — 토스 약관 §5②
  때문이고, 토스 토큰엔 scope 가 없어 조회 토큰으로 주문이 된다. 런북:
  `docs/ops/toss-personal-report.md`
- **Data**: FMP + KIS. ⚠️ **FMP 약관 §2.2.2 — 별도 Data Display Agreement 없이는
  유저에게 표시 금지.** *"complimentary or paid"* 를 명시하므로 **무료 서비스도
  해당된다.** R7(KIS 시세 재배포)의 미장 버전이며 **미해결**
- **Auth**: Google + Kakao OAuth (이메일+비번 없음)
- **Payment**: Stripe (게이트로 비활성)
- **Design**: v3 락-인 — Vantablack + Bronze + Playfair + KR 컨벤션

---

## 구조

### 백엔드 (2026-09-01 실측: blueprint 23 / URL rule 120)

```
app.py              # create_app() factory  ⚠️ L414 에서 db.create_all() 무조건 실행
config.py · extensions.py · security.py · run.py (5050)
models/ · migrations/   # alembic 리비전 전량 보존 — 삭제 금지
routes/   alerts · auth(+auth_alias) · behavior · billing · consents · data_status
          · dev_auth · email_preferences · feedback · health · inbox
          · market · mirror_home · notifications · portfolio · pre_trade
          · profile · push · realtime · sendgrid_webhook · support · trades
          (조건부·부팅 시 미등록: command_center=opt-in. 위 23 카운트에 없다.
           sim_onboard 은 2026-09-01 CAUS 와 함께 삭제 — 함정 §7)
services/ behavior · customer · data · email · inbox · kis · legal
          · marketing · observability · portfolio · pre_trade · profile
          · scheduler · support · tax
          (+ 루트 모듈 다수: cache_service · legal_filter · fx_service …)
          ⚠️ `broker/` `mock_data/` `trading/` 은 **디렉터리는 있어도 추적 파일
          0개**다 — 내용이 지워지고 껍데기만 남았다(로컬 `__pycache__` 뿐).
          import 하는 코드도 0곳. 2026-09-01 실측.
```

**`routes/market.py` 는 2026-09-01 에 18 → 4 라우트로 줄었다**
(`/search` · `/market/fx` · `/market/indices` · `/public/market-snapshot`).
나머지 14개는 8-31 prune 으로 사라진 화면의 잔재였고 **FMP 를 가장 많이 쓰던
것들**이다. 되살리지 마라.

**퀀트 코드는 없다.** `services/quant/` 는 2026-08-31 통째로 삭제됐다.
autotrade 는 2026-05-05 물리 삭제 (투자일임업 회피).

### 프론트엔드 (2026-09-01 실측: `page.tsx` 보유 디렉터리)

```
frontend/src/app/(dashboard)/
  mirror · portfolio · pre-trade · journal
  settings · support/contact · support/inbox(+/[id])
```
nav(`terminal-sidebar.tsx` / `bottom-nav.tsx`)에 있는 것 = 유저가 갈 수 있는 곳.
`/home` 은 삭제 → `/mirror` 로 308. `/profile`·`/settings/profile` 은 2026-09-12 삭제 → `/settings` 로 308.

⚠️ **프론트가 어떤 API 를 쓰는지 볼 땐 경로 문자열로 grep 하지 마라.**
컴포넌트는 `endpoints.ts` 의 **심볼**(`API.market.fx` 등)로 호출한다. 경로 리터럴
매칭은 실사용처를 전부 놓친다 — 2026-09-01 에 이걸로 틀린 결론을 냈다.
심볼을 먼저 찾고 그 심볼의 소비자를 추적할 것.
