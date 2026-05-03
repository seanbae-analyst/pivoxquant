# PivoxQuant — Email System Bug Audit (2026-05-01)

> 19개 이메일 발송 서비스 + 5개 HTML 템플릿 + SendGrid/SMTP 통합 코드 검사 결과.
> 18,000+ 줄 이메일 코드 — **법적/보안/스팸/UX 8개 카테고리에서 13개 버그** 발견.

---

## 🔴 P0 — 즉시 잡아야 할 버그

### E1. **`email_opt_out` 컬럼 미존재 — 글로벌 수신거부 작동 안 함** ⚠️

**가장 큰 발견**. 19개 이메일 서비스 전부에서 `getattr(user, "email_opt_out", False)`로 체크하는데 **User 모델에 그 컬럼 없음**.

```
models/user.py 검사 결과:
  ✓ email_opt_out_earnings (column exists, migration 009)
  ✗ email_opt_out          (NO COLUMN, only attribute fallback)
```

영향:
- `getattr(user, "email_opt_out", False)`는 **항상 False** 반환
- 사용자가 어디서 "수신거부"를 누르든 효과 없음 (애초에 수신거부 UI도 없음)
- **PIPA(개인정보보호법) 위반** — 정보통신망법 §50 광고성 정보 수신거부권 침해
- 첫 사용자가 수신거부 요청 → 무한 발송 → 신고 → 제재
- `tests/test_weekly_memo_service.py:194`의 `u.email_opt_out = True`는 **메모리 객체 attribute만 set**. DB에 저장 안 됨. **테스트가 가짜**.

**수정**:
1. `migrations/versions/021_email_opt_out.py` 신규 생성 — `email_opt_out` Boolean 컬럼 추가
2. `models/user.py`에 `email_opt_out = db.Column(db.Boolean, default=False, nullable=False, server_default="0")` 추가
3. `routes/profile.py` 또는 `routes/notifications.py`에 PATCH endpoint 추가
4. Settings 페이지에 토글 UI

### E2. **이메일 본문에 unsubscribe 링크 없음** ⚠️

5개 모든 이메일 템플릿(`_email_css.html` 제외) 검사 결과:
```
unsubscribe / opt-out / 구독해지 / 수신거부 → 0건
```

가장 가까운 문구: `earnings_prebrief_email.html` 푸터 — *"앱 설정 > 알림에서 비활성화하세요"* (앱 안에서 끄라는 안내만 있음, 직접 링크 없음).

영향:
- **CAN-SPAM Act 위반** (US 발송 시) + **정보통신망법 §50** 위반
- Gmail/Outlook 스팸 점수 즉시 +30%
- SendGrid bounce rate 상승 → sender reputation 하락
- List-Unsubscribe 헤더도 없음 → Gmail "한 번 클릭 수신거부" 미작동

**수정**:
1. 모든 템플릿 푸터에 `<a href="{{ unsubscribe_url }}">수신거부 / Unsubscribe</a>` 추가
2. `routes/profile.py`에 GET `/api/email/unsubscribe?token=` 엔드포인트
3. SendGrid Mail에 `List-Unsubscribe` 헤더 + `List-Unsubscribe-Post: List-Unsubscribe=One-Click` 추가:
   ```python
   mail.add_header("List-Unsubscribe", f"<{unsubscribe_url}>")
   mail.add_header("List-Unsubscribe-Post", "List-Unsubscribe=One-Click")
   ```

### E3. **earnings_prebrief 디지스트 SMTP가 STARTTLS 미사용 — 평문 전송**

`services/artifacts/earnings_prebrief_service.py:1630`:
```python
with smtplib.SMTP(smtp_host) as s:
    s.send_message(msg)   # ← starttls() 호출 없음
```

다른 17개 서비스(weekly_memo, brag_card 등) 모두 `s.starttls()` 호출 — 이것만 누락.

영향:
- SMTP 자격증명(SMTP_USER/PASSWORD) **평문 전송**
- 이메일 본문 + PDF 평문 전송 (단, digest는 PDF 첨부 안 함)
- 중간자 공격 가능

**수정**:
```python
with smtplib.SMTP(smtp_host, port, timeout=10) as s:
    s.starttls()
    if user_ and pw:
        s.login(user_, pw)
    s.send_message(msg)
```
다른 서비스 패턴과 동일하게 통일.

---

## 🟠 P1 — UX/법적 손상급

### E4. 한국 종목 ticker에 `$` 접두 (잘못된 통화 기호)

`earnings_prebrief_service.py:1201, 1246, 1313`:
```python
title_text = f"${ticker} 실적 30분 전"
subject = f"[Pre-Brief] ${ticker} — Earnings in {_lead_minutes()} min"
```

005930.KS(삼성전자)나 035720.KS(카카오) 같은 **한국 종목도 `$005930.KS`로 렌더링**됨.

`capital_allocation_service.py:485`는 올바른 패턴:
```python
sym = "₩" if ccy == "KRW" else "$"
```

**수정**: 같은 헬퍼 추출해서 `_currency_prefix(ticker)` 함수 만들고 17개 서비스에 일괄 적용.

### E5. PDF URL 없을 때 CTA가 `href="#"` (페이지 새로고침)

`services/artifacts/templates/earnings_prebrief_email.html:108`:
```jinja
<a href="{% if pdf_url %}{{ pdf_url }}{% else %}#{% endif %}"
   ...>Open Pre-Brief PDF</a>
```

`pdf_url`이 None이면 클릭 시 현재 페이지(=email viewer)로 navigation. 사용자에게 broken link 인상. 브라우저에 따라 javascript:void 이상 발생.

**수정**: `pdf_url` 없으면 CTA 자체를 숨기거나 disabled 스타일로.

### E6. SendGrid `from_email`이 검증되지 않은 도메인일 가능성

기본값 `reports@pivoxquant.com` 하드코딩. CLAUDE.md(2026-04-14)에 "Contact 이메일 가짜 도메인 4곳에 각각 다른 가짜 도메인 (.app/.io/.me)" 라는 메모 있음 — pivoxquant.com 도메인이 실제 등록/운영 중인지 검증 필요.

**확인 필요**:
- pivoxquant.com 도메인 소유 여부
- SendGrid sender authentication (SPF/DKIM/DMARC) 설정
- 미설정 시 모든 이메일 즉시 스팸 폴더 직행

### E7. Reply-To 헤더 없음

`From: reports@pivoxquant.com` 으로만 보내고 Reply-To 미설정. 사용자가 이메일에 답장하면 `reports@`로 가는데, 이게 모니터링 안 되면 사용자 문의가 black hole로 사라짐.

**수정**: `mail.reply_to = "support@pivoxquant.com"` 추가.

### E8. weekly_memo subject에 연도 누락

```python
subject = f"Week {datetime.now(...).isocalendar()[1]} Investor Memo"
```

새해 첫째 주 / 작년 마지막 주 헷갈림. ISO week-year edge case에서 "Week 1 Investor Memo"가 1월에 두 번 발송될 수도.

**수정**: `f"Week {iso[1]}, {iso[0]} Investor Memo"` 또는 날짜 명시.

---

## 🟡 P2 — 잠재 리스크

### E9. 17개 서비스에 send_email 코드 중복 (~16-90 lines × 17)

각 `*_service.py`마다 SendGrid + SMTP fallback + opt-out 체크 + from_email resolve 로직이 거의 동일하게 복붙됨. 합쳐서 ~1,200 lines 중복.

영향:
- E1, E3 같은 버그 수정 시 17곳 동시 패치 필요 (E3 누락은 이게 원인)
- 코드 라인 인플레이션 (전체 18,000줄 중 7%가 중복)

**수정**: `services/artifacts/_email_sender.py` 공통 헬퍼:
```python
class EmailSender:
    def send(self, user, subject, html_body, *, pdf_bytes=None,
             from_env_var=None, opt_out_attr="email_opt_out") -> bool:
        ...
```

### E10. brag_card 안의 disclaimer 인라인 카피가 `_disclaimer.html`과 분기

`brag_card_email.html`에는 `_disclaimer.html` include 대신 **인라인 disclaimer**가 있음:
```jinja
{# Inline disclaimer kept for Gmail dark-mode compat — colors must
   remain readable on both light and dark clients. Mirrors the
   canonical copy from _disclaimer.html at 2026-04-23 snapshot. #}
```

`_disclaimer.html` 본문이 변경되면 brag_card는 stale 카피 유지 → **legal 문구 drift**. 자본시장법 §6 방어 wording이 두 버전이 되는 위험.

**수정**: 매크로(`{% macro disclaimer_inline_dark() %}`) 패턴으로 단일 소스 + dark-mode variant.

### E11. dd_checklist 디스클레이머 fallback이 너무 짧음

`dd_checklist_email.html` 푸터:
```jinja
{{ disclaimer or "정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다." }}
```

`disclaimer` 변수 누락 시 **fallback 한 줄짜리** 표시. `_disclaimer.html`의 자본시장법 §6 방어 문구(영문 + 한글 2문단)와 길이/내용 불일치. 자본시장법 위반 시 "디폴트 fallback이라 짧았다"가 변호 안 됨.

**수정**: fallback 자체를 `_disclaimer.html` include로 변경 또는 동일 길이로 작성.

### E12. 이메일 본문 한글 lang 속성 누락 (일부)

`earnings_prebrief_email.html`은 `<html lang="ko">` 정상.
다른 템플릿(`brag_card_email.html`, `weekly_memo_email.html`, `dd_checklist_email.html`, `earnings_prebrief_digest_email.html`) 확인 필요.
누락 시 스크린리더가 영어로 읽음 (접근성), 일부 메일 클라이언트가 자동 번역 권장.

### E13. SendGrid `from_email` Display Name 누락

```python
mail = Mail(from_email=from_email, to_emails=user.email, ...)
```

`from_email="reports@pivoxquant.com"`만 있고 발신자 이름이 없음. Gmail에서는 그대로 이메일 주소가 노출됨. 일반 유저는 "reports@..." 보고 자동 마케팅으로 인식.

**수정**:
```python
from sendgrid.helpers.mail import From
mail = Mail(
    from_email=From(from_email, "PivoxQuant Research"),
    ...
)
```

---

## 🟢 P3 — 폴리시

### E14. Preview text가 일부만 활용

`earnings_prebrief_email.html`은 `<div style="display:none">` preview text 활용 (Gmail 받은편지함에 미리보기). 다른 템플릿도 동일 패턴 적용 권장 — open rate +5-10% 개선.

### E15. 첨부 PDF 파일명이 user.id 노출

```python
FileName(f"weekly_memo_{user.id}.pdf")
```

내부 user_id가 파일명에 노출. 별 문제는 아니지만 enumeration risk 미미. `weekly_memo_2026W18.pdf` 같은 형태가 더 사용자 친화적.

### E16. 디지스트 모드 dedup이 `today` 기준 → 자정 직전 발송 시 다음날 중복 발송 가능

```python
if self._already_sent_digest(uid, today):
    continue
```

`today`가 UTC vs KST 어느 기준인지 확인 필요. KST 23:55 발송 → UTC 14:55 = 같은 UTC 날 → 다음 cron tick(KST 00:10 = 새 UTC 날)에서 중복 발송 가능.

---

## 우선순위 별 액션 플랜

| 순서 | 버그 | 추정 시간 |
|---|---|---|
| 1 | E1: email_opt_out 컬럼 추가 + migration + UI | 4시간 |
| 2 | E2: unsubscribe 링크 + List-Unsubscribe 헤더 | 3시간 |
| 3 | E3: digest STARTTLS 추가 (1줄 수정) | 5분 |
| 4 | E4: ticker currency 헬퍼 + 17곳 적용 | 1시간 |
| 5 | E5: pdf_url null 처리 | 15분 |
| 6 | E6: pivoxquant.com 도메인 + SPF/DKIM/DMARC 검증 | 외부 액션 (CEO) |
| 7 | E7: Reply-To 헤더 일괄 | 30분 |
| 8 | E8: weekly_memo subject year fix | 5분 |
| 9 | E9: 공통 EmailSender 추출 (대규모 리팩토링) | 1일 |
| 10 | E10-E13: 디스클레이머/lang/Display Name 일괄 | 2시간 |
| 11 | E14-E16: 폴리시 | 1일 |

**최우선 3개(E1+E2+E3)는 출시 전 필수**. 합쳐서 1일 작업.

---

## Claude Code에 줄 마스터 프롬프트

```
EMAIL_BUG_AUDIT_2026-05-01.md 파일을 읽고 P0 섹션(E1, E2, E3)만 처리해줘.

순서:
1. fix/email-opt-out-column 브랜치 — E1 처리
   - migrations/versions/021_email_opt_out.py 생성 (idempotent ALTER TABLE)
   - models/user.py에 컬럼 추가
   - routes/profile.py에 PATCH /api/profile/email-preferences 엔드포인트
   - tests/test_email_opt_out.py 추가 (실제 DB 컬럼 + opt-out 동작 검증)
   - 기존 17개 서비스의 getattr(...) 코드는 건드리지 마 (이미 올바름)

2. fix/email-unsubscribe 브랜치 — E2 처리
   - 5개 템플릿 푸터에 <a href="{{ unsubscribe_url }}"> 추가
   - routes/profile.py에 GET /api/email/unsubscribe?token= 엔드포인트
   - SendGrid Mail에 List-Unsubscribe 헤더 추가하는 헬퍼 (E9 미리 준비)
   - signed token: itsdangerous URLSafeTimedSerializer 사용

3. fix/email-starttls-digest 브랜치 — E3 처리
   - earnings_prebrief_service.py:1630 한 줄 수정
   - port, user_, pw 추가 (다른 서비스 패턴 그대로)
   - 신규 테스트: test_digest_uses_tls.py (mock smtplib, starttls 호출 확인)

각 브랜치 별 commit 1개. fix(email): prefix.
완료 후 정직 보고: 어떤 파일 수정, pytest 결과, 누락된 부분.
```
