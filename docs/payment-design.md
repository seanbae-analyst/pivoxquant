# PivoxQuant 구독 결제 시스템 설계

> 작성일: 2026-04-09
> 최종 수정: 2026-04-10
> 상태: 설계 완료 / 구현 대기 (Stripe 계정 생성 후 진행)
> 설계자: 연동부 (Integrations Agent)

---

## 1. 현재 상태 분석

### 1.1 이미 구축된 것

백엔드와 프론트엔드에 Stripe 연동의 골격이 이미 존재한다.

**User 모델 (models/user.py)** -- 구독 필드 4개 존재:
- `subscription_tier` (String(10), default="free")
- `stripe_customer_id` (String(100), nullable)
- `stripe_subscription_id` (String(100), nullable)
- `subscription_status` (String(20), default="inactive")

**Billing 라우트 (routes/billing.py)** -- 4개 엔드포인트 구현 완료:
- `POST /api/billing/create-checkout` -- Stripe Checkout Session 생성
- `POST /api/billing/webhook` -- Stripe Webhook 수신 (3개 이벤트 처리)
- `GET /api/billing/subscription` -- 구독 상태 조회
- `POST /api/billing/portal` -- Stripe Customer Portal

**프론트엔드 (lib/endpoints.ts)** -- billing 엔드포인트 3개 등록 완료:
- `billing.createCheckout`, `billing.subscription`, `billing.portal`

**프론트엔드 타입 (lib/auth.tsx)** -- User 인터페이스에 `subscription_tier` 포함

### 1.2 누락된 것

| 영역 | 누락 항목 |
|------|-----------|
| Stripe 대시보드 | Product/Price 미생성, Webhook URL 미설정 |
| 환경변수 | STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_PRO, STRIPE_PRICE_ENTERPRISE 미설정 |
| 데이터 모델 | `subscription_end` (만료일), 결제 이력 테이블 없음 |
| 기능 제한 | `require_tier` 데코레이터 미구현 -- 모든 API가 Free 유저에게 열려 있음 |
| 프론트엔드 | 가격표 페이지 없음, 결제 플로우 UI 없음, 업그레이드 프롬프트 없음 |
| 가격 구조 | "enterprise" 로 되어 있으나 "premium" 이어야 함 |
| Webhook | invoice.payment_failed, invoice.paid 핸들러 미구현 |
| 환불 | 전자상거래법 제17조 청약 철회 자동화 미구현 |
| 모니터링 | Stripe 결제 성공/실패율 추적 없음 |

### 1.3 네이밍 불일치 -- 반드시 수정

현재 billing.py의 PLAN_PRICES/PLAN_TIERS에서 `enterprise`를 사용하지만,
이용약관(제6조)과 비즈니스 플랜은 `premium`을 사용한다.
**구현 시 "enterprise" -> "premium" 으로 통일 필요.**

변경 대상:
- `STRIPE_PRICE_ENTERPRISE` -> `STRIPE_PRICE_PREMIUM`
- `PLAN_PRICES["enterprise"]` -> `PLAN_PRICES["premium"]`
- `PLAN_TIERS["enterprise"]` -> `PLAN_TIERS["premium"]`

---

## 2. Stripe 대시보드 설정 (수동 작업)

### 2.1 Product/Price 구조

Stripe Dashboard에서 아래와 같이 생성한다.

```
Product: PivoxQuant Pro
  +-- Price: price_pro_monthly
  |   - 금액: 9,900 KRW / month
  |   - Recurring, interval: month
  |   - Currency: KRW
  +-- (Phase 2) Price: price_pro_yearly
      - 금액: 99,000 KRW / year (2개월 할인)

Product: PivoxQuant Premium
  +-- Price: price_premium_monthly
  |   - 금액: 19,900 KRW / month
  |   - Recurring, interval: month
  |   - Currency: KRW
  +-- (Phase 2) Price: price_premium_yearly
      - 금액: 199,000 KRW / year (2개월 할인)
```

**한국 결제 고려사항:**
- Currency는 반드시 KRW로 설정 (소수점 없음, 최소 단위 = 1원)
- Stripe Korea 수수료: 카드 결제 3.5% (해외 카드 +0.5%)
- 간편결제(네이버페이, 카카오페이)는 Stripe Checkout에서 자동 노출됨
  (Stripe 대시보드 > Settings > Payment methods에서 활성화)

### 2.2 Webhook 설정

Stripe Dashboard > Developers > Webhooks 에서:
- Endpoint URL: `https://{BACKEND_DOMAIN}/api/billing/webhook`
- Events to listen:
  1. `checkout.session.completed` -- 결제 완료
  2. `customer.subscription.updated` -- 구독 변경 (업/다운그레이드, 갱신)
  3. `customer.subscription.deleted` -- 구독 취소 확정
  4. `invoice.payment_failed` -- 결제 실패 (추가 필요)
  5. `invoice.paid` -- 결제 성공 (결제 이력용, 추가 필요)
  6. `customer.subscription.trial_will_end` -- 체험 종료 3일 전 (Phase 2)
  7. `charge.refunded` -- 환불 처리 완료 (Phase 2)

### 2.3 Customer Portal 설정

Stripe Dashboard > Settings > Billing > Customer portal:
- 구독 취소: 허용 (기간 만료 후 취소 -- cancel_at_period_end)
- 플랜 변경: Pro <-> Premium 전환 허용 (proration 자동 적용)
- 결제 수단 변경: 허용
- 인보이스 조회: 허용

### 2.4 환경변수

```bash
# .env (절대 프론트엔드에 노출 금지)
STRIPE_SECRET_KEY=sk_live_...        # 또는 sk_test_... (테스트용)
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRO=price_...           # Pro 월간 Price ID
STRIPE_PRICE_PREMIUM=price_...       # Premium 월간 Price ID
FRONTEND_URL=https://pivoxquant.com   # Checkout 성공/취소 리다이렉트 URL
```

**주의:** STRIPE_PUBLISHABLE_KEY는 불필요하다.
Stripe Checkout Session 방식은 server-side에서 URL을 생성하여 리다이렉트하므로
프론트엔드에 Stripe.js를 포함하지 않는다.

---

## 3. 데이터 모델 변경

### 3.1 User 모델 필드 추가

```python
# models/user.py -- 추가 필드
subscription_end = db.Column(db.DateTime, nullable=True)  # 현재 구독 기간 만료일
trial_end = db.Column(db.DateTime, nullable=True)          # 무료 체험 만료일 (Phase 2)
```

### 3.2 결제 이력 모델 (신규 파일: models/payment.py)

```python
from datetime import datetime
from extensions import db


class PaymentHistory(db.Model):
    __tablename__ = "payment_history"
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    stripe_invoice_id = db.Column(db.String(100), unique=True, nullable=True)
    amount           = db.Column(db.Integer, nullable=False)  # KRW 단위 (원)
    currency         = db.Column(db.String(3), default="KRW")
    status           = db.Column(db.String(20), nullable=False)  # paid, failed, refunded
    plan             = db.Column(db.String(10), nullable=False)  # pro, premium
    period_start     = db.Column(db.DateTime, nullable=True)
    period_end       = db.Column(db.DateTime, nullable=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("payments", lazy=True))
```

### 3.3 Webhook 이벤트 멱등성 테이블 (프로덕션용)

```python
class ProcessedWebhookEvent(db.Model):
    __tablename__ = "processed_webhook_events"
    id         = db.Column(db.String(100), primary_key=True)  # Stripe event ID
    event_type = db.Column(db.String(50), nullable=False)
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
```

개발 환경에서는 in-memory set으로 충분하나,
프로덕션(Railway + PostgreSQL)에서는 DB 테이블 사용.

### 3.4 DB 마이그레이션

SQLite 개발 환경에서는 `db.create_all()` 로 충분하다.
프로덕션(PostgreSQL) 전환 시 Flask-Migrate(Alembic) 도입 필요.

---

## 4. API 엔드포인트 설계

### 4.1 기존 엔드포인트 수정

| 엔드포인트 | 변경 사항 |
|-----------|-----------|
| `POST /api/billing/create-checkout` | "enterprise" -> "premium" 으로 플랜명 변경 |
| `POST /api/billing/webhook` | `invoice.payment_failed`, `invoice.paid` 이벤트 추가 처리 |
| `GET /api/billing/subscription` | `subscription_end`, `plan_limits` 필드 추가 반환 |

### 4.2 신규 엔드포인트

| 엔드포인트 | Method | 인증 | 설명 |
|-----------|--------|------|------|
| `GET /api/billing/plans` | GET | 불필요 | 가격표 데이터 반환 (SSR용) |
| `GET /api/billing/history` | GET | api_auth | 결제 이력 목록 |
| `POST /api/billing/cancel` | POST | api_auth | 구독 취소 (기간 만료 후 해지) |
| `POST /api/billing/resume` | POST | api_auth | 취소 예약 철회 |

### 4.3 Plans 응답 스키마

```json
{
  "plans": [
    {
      "id": "free",
      "name": "Free",
      "name_kr": "무료",
      "price": 0,
      "currency": "KRW",
      "interval": "month",
      "features": [
        {"key": "portfolio_limit", "value": 3, "label": "Portfolio: 3 stocks", "label_kr": "포트폴리오 3종목"},
        {"key": "signal_frequency", "value": "daily", "label": "Daily signals", "label_kr": "일 1회 시그널"},
        {"key": "basic_analysis", "value": true, "label": "Basic Analysis", "label_kr": "기본 분석"}
      ],
      "cta": "Current Plan"
    },
    {
      "id": "pro",
      "name": "Pro",
      "name_kr": "프로",
      "price": 9900,
      "currency": "KRW",
      "interval": "month",
      "popular": true,
      "features": [
        {"key": "portfolio_limit", "value": -1, "label": "Unlimited Stocks", "label_kr": "무제한 종목"},
        {"key": "realtime_signals", "value": true, "label": "Real-time Signals", "label_kr": "실시간 시그널"},
        {"key": "ai_chat", "value": true, "label": "AI Chat", "label_kr": "AI 채팅"},
        {"key": "backtest", "value": true, "label": "Backtest", "label_kr": "백테스트"},
        {"key": "swot", "value": true, "label": "SWOT Analysis", "label_kr": "SWOT 분석"},
        {"key": "coaching", "value": true, "label": "AI Coaching", "label_kr": "AI 코칭"}
      ],
      "cta": "Upgrade to Pro"
    },
    {
      "id": "premium",
      "name": "Premium",
      "name_kr": "프리미엄",
      "price": 19900,
      "currency": "KRW",
      "interval": "month",
      "features": [
        {"key": "all_pro", "value": true, "label": "Everything in Pro", "label_kr": "Pro 전체 기능 포함"},
        {"key": "autotrade", "value": true, "label": "Auto Trading", "label_kr": "자동매매"},
        {"key": "advanced_quant", "value": true, "label": "Advanced Quant Models", "label_kr": "고급 퀀트 모델"},
        {"key": "push_alerts", "value": true, "label": "Push Alerts", "label_kr": "푸시 알림"},
        {"key": "api_access", "value": true, "label": "API Access", "label_kr": "API 접근"},
        {"key": "priority_support", "value": true, "label": "Priority Support", "label_kr": "우선 지원"}
      ],
      "cta": "Upgrade to Premium"
    }
  ]
}
```

### 4.4 Subscription 응답 스키마 (확장)

```json
{
  "subscription_tier": "pro",
  "subscription_status": "active",
  "has_active_subscription": true,
  "current_period_end": 1717200000,
  "cancel_at_period_end": false,
  "plan_limits": {
    "portfolio_limit": -1,
    "ai_chat": true,
    "backtest": true,
    "autotrade": false,
    "advanced_quant": false,
    "push_alerts": false,
    "realtime_signals": true
  }
}
```

### 4.5 Cancel/Resume 엔드포인트 상세

```python
# POST /api/billing/cancel
# 즉시 해지가 아닌 "기간 만료 후 해지" (cancel_at_period_end)
# 이용약관 제7조 2항 준수: 갱신일 전일까지 해지
@billing_bp.route("/cancel", methods=["POST"])
@api_auth
def cancel_subscription():
    if not current_user.stripe_subscription_id:
        return jsonify({"error": "No active subscription"}), 400
    try:
        stripe.Subscription.modify(
            current_user.stripe_subscription_id,
            cancel_at_period_end=True
        )
        return jsonify({"ok": True, "cancel_at_period_end": True})
    except stripe.StripeError as e:
        return jsonify({"error": str(e)}), 500


# POST /api/billing/resume -- 취소 예약 철회
@billing_bp.route("/resume", methods=["POST"])
@api_auth
def resume_subscription():
    if not current_user.stripe_subscription_id:
        return jsonify({"error": "No active subscription"}), 400
    try:
        stripe.Subscription.modify(
            current_user.stripe_subscription_id,
            cancel_at_period_end=False
        )
        return jsonify({"ok": True, "cancel_at_period_end": False})
    except stripe.StripeError as e:
        return jsonify({"error": str(e)}), 500
```

### 4.6 History 엔드포인트 상세

```python
# GET /api/billing/history
@billing_bp.route("/history")
@api_auth
def payment_history():
    payments = PaymentHistory.query.filter_by(user_id=current_user.id)\
        .order_by(PaymentHistory.created_at.desc())\
        .limit(50).all()
    return jsonify({
        "history": [{
            "id": p.id,
            "amount": p.amount,
            "currency": p.currency,
            "status": p.status,
            "plan": p.plan,
            "period_start": p.period_start.isoformat() if p.period_start else None,
            "period_end": p.period_end.isoformat() if p.period_end else None,
            "created_at": p.created_at.isoformat(),
        } for p in payments]
    })
```

---

## 5. 기능 제한 (Tier Gating) 설계

### 5.1 require_tier 데코레이터

`routes/decorators.py` 에 추가할 데코레이터.

```python
def require_tier(*allowed_tiers):
    """Restrict endpoint to specific subscription tiers.

    Usage:
        @require_tier("pro", "premium")  # Pro 이상만 접근
        @require_tier("premium")          # Premium만 접근
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*a, **kw):
            if not current_user.is_authenticated:
                return jsonify({"error": "Login required"}), 401
            user_tier = getattr(current_user, "subscription_tier", "free") or "free"
            if user_tier not in allowed_tiers:
                return jsonify({
                    "error": "Upgrade required",
                    "required_tier": allowed_tiers[0],
                    "current_tier": user_tier,
                    "upgrade_url": "/pricing"
                }), 403
            return f(*a, **kw)
        return wrapped
    return decorator
```

### 5.2 라우트별 Tier 매핑

기존 `@api_auth` 데코레이터 바로 아래에 `@require_tier` 를 추가하는 방식.

```
# ===== FREE (모든 유저) =====
GET  /api/portfolio              -- 3종목 제한 (로직에서 처리)
GET  /api/signals                -- 일 1회 제한 (로직에서 처리)
GET  /api/market/overview        -- 제한 없음
GET  /api/discover               -- 제한 없음
GET  /api/alerts                 -- 제한 없음
POST /api/auth/*                 -- 제한 없음
GET  /api/billing/*              -- 제한 없음

# ===== PRO 이상 (pro, premium) =====
POST /api/ai/chat                -- @require_tier("pro", "premium")
POST /api/ai/swot                -- @require_tier("pro", "premium")
POST /api/ai/competitor          -- @require_tier("pro", "premium")
POST /api/ai/sector-trend        -- @require_tier("pro", "premium")
POST /api/ai/commentary          -- @require_tier("pro", "premium")
POST /api/ai/morning-summary     -- @require_tier("pro", "premium")
POST /api/ai/coaching            -- @require_tier("pro", "premium")
GET  /api/backtest/<ticker>      -- @require_tier("pro", "premium")
GET  /api/signals/refresh        -- 무제한 갱신 (Free는 일 1회 제한)
GET  /api/realtime/stream        -- @require_tier("pro", "premium")

# ===== PREMIUM만 (premium) =====
POST /api/autotrade/start        -- @require_tier("premium")
POST /api/autotrade/stop         -- @require_tier("premium")
POST /api/autotrade/sell-all     -- @require_tier("premium")
GET  /api/autotrade/status       -- @require_tier("premium")
GET  /api/vix-strategy           -- @require_tier("premium")
GET  /api/cross-asset            -- @require_tier("premium")
POST /api/push/subscribe         -- @require_tier("premium")
```

### 5.3 Free 유저 종목 수 제한 로직

포트폴리오 추가 시 제한 (routes/portfolio.py 수정):

```python
# POST /api/portfolio/position -- 기존 @api_auth 뒤에 추가
tier = current_user.subscription_tier or "free"
if tier == "free":
    count = Position.query.filter_by(user_id=current_user.id).count()
    if count >= 3:
        return jsonify({
            "error": "Free plan limited to 3 stocks. Upgrade to Pro for unlimited.",
            "upgrade_url": "/pricing",
            "current_count": count,
            "limit": 3
        }), 403
```

### 5.4 Free 유저 시그널 빈도 제한 로직

```python
# GET /api/signals/refresh 또는 시그널 생성 시
# Free 유저: 마지막 갱신으로부터 24시간 경과 필요
from datetime import datetime, timedelta

tier = current_user.subscription_tier or "free"
if tier == "free":
    last_refresh = SignalCache.query.filter_by(user_id=current_user.id)\
        .order_by(SignalCache.updated_at.desc()).first()
    if last_refresh and last_refresh.updated_at > datetime.utcnow() - timedelta(hours=24):
        return jsonify({
            "error": "Free plan: 1 signal refresh per day. Upgrade for real-time.",
            "next_refresh": (last_refresh.updated_at + timedelta(hours=24)).isoformat()
        }), 429
```

### 5.5 Tier 제한 상수 (중앙 관리)

```python
# config.py 또는 별도 tier_config.py
TIER_LIMITS = {
    "free": {
        "portfolio_limit": 3,
        "signal_refresh_hours": 24,
        "ai_chat": False,
        "backtest": False,
        "autotrade": False,
        "advanced_quant": False,
        "push_alerts": False,
        "realtime_signals": False,
    },
    "pro": {
        "portfolio_limit": -1,  # unlimited
        "signal_refresh_hours": 0,  # no limit
        "ai_chat": True,
        "backtest": True,
        "autotrade": False,
        "advanced_quant": False,
        "push_alerts": False,
        "realtime_signals": True,
    },
    "premium": {
        "portfolio_limit": -1,
        "signal_refresh_hours": 0,
        "ai_chat": True,
        "backtest": True,
        "autotrade": True,
        "advanced_quant": True,
        "push_alerts": True,
        "realtime_signals": True,
    },
}
```

---

## 6. Webhook 이벤트 처리 상세

### 6.1 현재 구현 상태 (billing.py)

| 이벤트 | 상태 | 처리 내용 |
|--------|------|-----------|
| checkout.session.completed | 구현됨 | tier 활성화, subscription_id 저장 |
| customer.subscription.updated | 구현됨 | status/tier 갱신 |
| customer.subscription.deleted | 구현됨 | free 복귀 |
| invoice.payment_failed | 미구현 | 추가 필요 |
| invoice.paid | 미구현 | 추가 필요 |

### 6.2 추가 구현 필요 -- invoice.payment_failed

```python
def _handle_payment_failed(invoice):
    """결제 실패 처리. Stripe가 자동 재시도하지만, 유저에게 알림."""
    customer_id = invoice.get("customer")
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return

    user.subscription_status = "past_due"
    db.session.commit()

    # 알림 생성 (기존 Alert 모델 활용)
    alert = Alert(
        user_id=user.id,
        type="payment_failed",
        title="Payment Failed",
        message="Your subscription payment failed. Please update your payment method.",
        severity="critical"
    )
    db.session.add(alert)
    db.session.commit()
```

### 6.3 추가 구현 필요 -- invoice.paid

```python
def _handle_invoice_paid(invoice):
    """결제 성공 시 이력 기록."""
    customer_id = invoice.get("customer")
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return

    # 중복 방지: stripe_invoice_id로 이미 기록된 건 skip
    existing = PaymentHistory.query.filter_by(
        stripe_invoice_id=invoice.get("id")
    ).first()
    if existing:
        return

    payment = PaymentHistory(
        user_id=user.id,
        stripe_invoice_id=invoice.get("id"),
        amount=invoice.get("amount_paid", 0),
        currency=invoice.get("currency", "krw").upper(),
        status="paid",
        plan=user.subscription_tier,
        period_start=datetime.fromtimestamp(invoice["period_start"]) if invoice.get("period_start") else None,
        period_end=datetime.fromtimestamp(invoice["period_end"]) if invoice.get("period_end") else None,
    )
    db.session.add(payment)

    # subscription_end 갱신
    if invoice.get("period_end"):
        user.subscription_end = datetime.fromtimestamp(invoice["period_end"])

    db.session.commit()
```

### 6.4 Webhook 이벤트 흐름도

```
Stripe Event
    |
    v
POST /api/billing/webhook
    |
    +-- Signature 검증 (stripe.Webhook.construct_event)
    |       |-- 실패 -> 400 Invalid signature
    |       +-- 성공 -> 계속
    |
    +-- 멱등성 체크 (event.id)
    |       |-- 이미 처리됨 -> 200 OK (skip)
    |       +-- 미처리 -> 계속
    |
    +-- 이벤트 분기
            |
            +-- checkout.session.completed
            |       -> _handle_checkout_completed
            |       -> user.subscription_tier = plan
            |       -> user.subscription_status = "active"
            |       -> user.stripe_subscription_id = sub_id
            |
            +-- customer.subscription.updated
            |       -> _handle_subscription_updated
            |       -> status/tier 갱신
            |       -> 업/다운그레이드 반영
            |
            +-- customer.subscription.deleted
            |       -> _handle_subscription_deleted
            |       -> user.subscription_tier = "free"
            |       -> user.subscription_status = "inactive"
            |
            +-- invoice.paid
            |       -> _handle_invoice_paid
            |       -> PaymentHistory 기록
            |       -> user.subscription_end 갱신
            |
            +-- invoice.payment_failed
                    -> _handle_payment_failed
                    -> user.subscription_status = "past_due"
                    -> Alert 생성 (결제 실패 알림)
```

---

## 7. 결제 플로우 설계

### 7.1 신규 구독 플로우

```
[유저] 가격표 페이지 (/pricing)
  |
  +-- "Pro 시작하기" 클릭
  |     v
  |   POST /api/billing/create-checkout {plan: "pro"}
  |     v
  |   백엔드: Stripe Customer 생성/조회 -> Checkout Session 생성
  |     v
  |   프론트: Stripe Checkout 페이지로 리다이렉트 (session.url)
  |     v
  |   [Stripe Hosted Checkout]
  |   - 카드 정보 입력 (또는 네이버페이/카카오페이)
  |   - 결제 처리
  |     v
  |   성공: /home?billing=success 로 리다이렉트
  |   취소: /home?billing=cancelled 로 리다이렉트
  |     v
  |   (비동기) Webhook: checkout.session.completed
  |     v
  |   백엔드: user.subscription_tier = "pro"
  |           user.subscription_status = "active"
  |
  +-- 완료: 프론트에서 /api/billing/subscription 재조회 -> UI 갱신
```

### 7.2 구독 관리 플로우

```
[유저] 설정 페이지 (/settings)
  |
  +-- "구독 관리" 클릭
  |     v
  |   POST /api/billing/portal
  |     v
  |   Stripe Customer Portal로 리다이렉트
  |   - 결제 수단 변경
  |   - 플랜 업/다운그레이드
  |   - 구독 취소
  |   - 인보이스 조회
  |     v
  |   Portal에서 변경 시 Webhook으로 자동 반영
  |
  +-- 또는 앱 내 취소 버튼 -> POST /api/billing/cancel
      -> Stripe API: subscription.cancel_at_period_end = true
      -> 기간 만료까지 서비스 유지, 만료 후 free 전환
```

### 7.3 결제 실패 복구 플로우

```
Webhook: invoice.payment_failed
  v
백엔드: user.subscription_status = "past_due"
  v
프론트: 배너 표시 "결제 실패 - 결제 수단을 업데이트해 주세요"
  v
Stripe 자동 재시도 (Smart Retries: 1주 내 최대 4회)
  v
  +-- 재시도 성공: invoice.paid -> status = "active"
  +-- 재시도 실패: customer.subscription.deleted -> tier = "free"
```

### 7.4 플랜 업/다운그레이드 플로우

```
[Pro 유저] -> "Premium 업그레이드" 클릭
  v
POST /api/billing/create-checkout {plan: "premium"}
  v
Stripe Checkout (비례배분 proration 자동 적용)
  - Pro 잔여 기간 크레딧 차감
  - Premium 금액에서 차감 후 차액 결제
  v
Webhook: customer.subscription.updated
  -> user.subscription_tier = "premium"

[Premium 유저] -> Stripe Portal에서 Pro 다운그레이드
  v
Webhook: customer.subscription.updated
  -> 현재 기간 종료 후 Pro로 전환 (proration 정책에 따라)
```

주의: 업그레이드는 create-checkout으로 새 세션 생성하고,
다운그레이드는 Customer Portal에서만 허용하여 UX를 통제한다.

---

## 8. 프론트엔드 설계

### 8.1 신규 페이지: /pricing

경로: `frontend/src/app/(dashboard)/pricing/page.tsx`

와이어프레임:
```
+--------------------------------------------------------------+
|  Choose Your Plan                                             |
|  "월간" / "연간 (17% 할인)" 토글 (Phase 2)                       |
|                                                               |
|  +----------+   +--------------+   +--------------+           |
|  |  Free     |   |  Pro  BEST   |   |  Premium     |          |
|  |           |   |              |   |              |          |
|  |  0원/월   |   |  9,900원/월  |   |  19,900원/월 |          |
|  |           |   |              |   |              |          |
|  | * 3종목   |   | * 무제한종목 |   | * Pro 전체   |          |
|  | * 기본분석|   | * 실시간     |   | * 자동매매   |          |
|  | * 일1회   |   | * AI 채팅    |   | * 고급퀀트   |          |
|  |           |   | * 백테스트   |   | * 알림       |          |
|  |           |   | * SWOT       |   | * API접근    |          |
|  |           |   | * AI코칭     |   |              |          |
|  |           |   |              |   |              |          |
|  | [현재]    |   | [시작하기]   |   | [시작하기]   |          |
|  +----------+   +--------------+   +--------------+           |
|                                                               |
|  FAQ 섹션                                                     |
|  Q: 언제든지 취소할 수 있나요?                                    |
|  Q: 환불 정책은?                                                |
|  Q: 결제 수단은?                                                |
+--------------------------------------------------------------+
```

디자인 가이드:
- 카드 배경: 기존 디자인 시스템 (#ffffff, border-slate-200, rounded-2xl)
- Pro 카드: `border-primary` (#1b4dff) 또는 `border-emerald-500` 강조
- "BEST" 뱃지: 기존 Badge 컴포넌트 사용
- 가격: text-3xl font-bold + text-slate-500 "원/월"
- CTA 버튼: 기존 Button 컴포넌트 (variant="default" for upgrade, variant="outline" for current)

### 8.2 업그레이드 프롬프트 컴포넌트

경로: `frontend/src/components/billing/upgrade-prompt.tsx`

403 응답을 받았을 때 각 페이지에서 표시하는 공통 컴포넌트.

```
+------------------------------------------+
|  [Lock icon] Pro Plan Required            |
|                                           |
|  AI 채팅은 Pro 이상 구독에서              |
|  이용 가능합니다.                         |
|                                           |
|  [Pro 시작하기]    [가격표 보기]            |
+------------------------------------------+
```

Props 인터페이스:
```typescript
interface UpgradePromptProps {
    requiredTier: "pro" | "premium";
    featureName: string;        // "AI Chat"
    featureNameKr: string;      // "AI 채팅"
    onUpgrade?: () => void;     // 직접 checkout 트리거
}
```

### 8.3 구독 상태 배너

`frontend/src/components/billing/subscription-banner.tsx`

상태별 배너 (대시보드 레이아웃 상단에 조건부 렌더링):
- `past_due`: "결제가 실패했습니다. 결제 수단을 업데이트해 주세요." (빨간색, destructive)
- `cancel_at_period_end`: "구독이 {날짜}에 해지됩니다." (노란색, warning)
- `billing=success` (URL param): "구독이 활성화되었습니다!" (초록색, 5초 후 fade out)
- `billing=cancelled` (URL param): 아무것도 표시하지 않음 (유저가 자발적 취소)

### 8.4 설정 페이지 구독 섹션 추가

`frontend/src/app/(dashboard)/settings/page.tsx` 에 구독 관리 섹션 추가:

```
+-----------------------------------------+
|  [CreditCard] Subscription               |
|                                          |
|  현재 플랜: Pro                           |
|  상태: Active                             |
|  다음 결제일: 2026-05-09                  |
|  금액: 9,900원/월                         |
|                                          |
|  [구독 관리]  [플랜 변경]  [취소]           |
+-----------------------------------------+
```

Free 유저일 경우:
```
+-----------------------------------------+
|  [CreditCard] Subscription               |
|                                          |
|  현재 플랜: Free                          |
|                                          |
|  Pro로 업그레이드하고 무제한 종목,          |
|  AI 채팅, 백테스트를 이용하세요.            |
|                                          |
|  [Pro 시작하기]  [가격표 보기]              |
+-----------------------------------------+
```

### 8.5 403 인터셉터 (SWR 미들웨어)

기존 `lib/api.ts`의 `apiFetch` 또는 SWR 미들웨어에서
403 응답의 `error === "Upgrade required"` 를 감지하여 처리.

```typescript
// lib/api.ts -- apiFetch 수정 또는 래퍼
export async function apiFetch<T>(url: string, opts?: RequestInit): Promise<T> {
    const res = await fetch(url, { credentials: "include", ...opts });

    if (res.status === 403) {
        const body = await res.json();
        if (body.error === "Upgrade required") {
            // 커스텀 이벤트 발행 -> UpgradePrompt 자동 표시
            window.dispatchEvent(new CustomEvent("upgrade-required", {
                detail: {
                    requiredTier: body.required_tier,
                    currentTier: body.current_tier,
                    upgradeUrl: body.upgrade_url,
                }
            }));
            throw new UpgradeRequiredError(body);
        }
    }

    if (!res.ok) throw new Error(`API Error: ${res.status}`);
    return res.json();
}
```

### 8.6 프론트엔드 endpoints.ts 추가

```typescript
billing: {
    createCheckout: "/api/billing/create-checkout",
    subscription: "/api/billing/subscription",
    portal: "/api/billing/portal",
    plans: "/api/billing/plans",      // 추가
    history: "/api/billing/history",  // 추가
    cancel: "/api/billing/cancel",    // 추가
    resume: "/api/billing/resume",    // 추가
},
```

### 8.7 프론트엔드 타입 추가 (types.ts)

```typescript
export interface PlanFeature {
    key: string;
    value: boolean | number | string;
    label: string;
    label_kr: string;
}

export interface Plan {
    id: "free" | "pro" | "premium";
    name: string;
    name_kr: string;
    price: number;
    currency: string;
    interval: string;
    popular?: boolean;
    features: PlanFeature[];
    cta: string;
}

export interface PlansResponse {
    plans: Plan[];
}

export interface SubscriptionResponse {
    subscription_tier: string;
    subscription_status: string;
    has_active_subscription: boolean;
    current_period_end?: number;
    cancel_at_period_end?: boolean;
    plan_limits: Record<string, boolean | number>;
}

export interface PaymentHistoryItem {
    id: number;
    amount: number;
    currency: string;
    status: string;
    plan: string;
    period_start: string;
    period_end: string;
    created_at: string;
}
```

### 8.8 SWR 훅 추가 (hooks.ts)

```typescript
export function useSubscription() {
    return useSWR<SubscriptionResponse>(
        API.billing.subscription,
        (url) => apiFetch(url),
        { revalidateOnFocus: true }
    );
}

export function usePlans() {
    return useSWR<PlansResponse>(
        API.billing.plans,
        (url) => apiFetch(url),
        { revalidateOnFocus: false }  // 가격은 자주 변하지 않음
    );
}
```

---

## 9. 신뢰성 패턴 (Reliability)

### 9.1 Stripe API 호출 표준

```
요청 -> Stripe API 호출 -> 성공 -> 응답 반환
                |  실패
          StripeError 분기:
          +-- CardError        -> 유저에게 카드 문제 안내 (400)
          +-- RateLimitError   -> 5초 후 1회 재시도
          +-- InvalidRequestError -> 로깅 + 500 에러
          +-- AuthenticationError -> 로깅 + 운영 알림 (API 키 문제)
          +-- APIConnectionError -> 로깅 + "일시적 오류" 안내 (503)
```

### 9.2 Webhook 멱등성

동일한 Webhook 이벤트가 중복 전달될 수 있다. 이미 처리된 이벤트 재처리 방지:

```python
# 개발 환경: in-memory set
_processed_events = set()

# 프로덕션 환경: DB 테이블 사용
def _is_event_processed(event_id):
    """Check if webhook event already processed. Return True if duplicate."""
    existing = ProcessedWebhookEvent.query.get(event_id)
    if existing:
        return True
    db.session.add(ProcessedWebhookEvent(
        id=event_id,
        event_type=event.get("type", "unknown")
    ))
    db.session.commit()
    return False
```

### 9.3 Timeout 설정

```python
# app.py 또는 billing.py 상단에 추가
stripe.max_network_retries = 2  # 자동 재시도 2회
# Stripe Python SDK의 기본 timeout은 80초.
# 요청별로 timeout을 설정하려면:
# stripe.Subscription.retrieve(sub_id, request_timeout=10)
```

### 9.4 Webhook Signature 검증 (이미 구현됨)

billing.py의 `stripe.Webhook.construct_event()` 에서 서명 검증이 이루어지고 있다.
이 부분은 수정 불필요.

### 9.5 Circuit Breaker (Stripe API)

Stripe API가 지속적으로 실패하는 경우 (네트워크 문제 등) 프론트엔드에
"결제 시스템 점검 중" 메시지를 표시해야 한다.

```python
# 간단한 circuit breaker (billing.py)
import time

_stripe_failures = 0
_stripe_circuit_open_until = 0

def _check_stripe_circuit():
    """Return True if Stripe is believed to be healthy."""
    global _stripe_failures, _stripe_circuit_open_until
    if time.time() < _stripe_circuit_open_until:
        return False  # circuit open
    return True

def _record_stripe_failure():
    global _stripe_failures, _stripe_circuit_open_until
    _stripe_failures += 1
    if _stripe_failures >= 5:
        _stripe_circuit_open_until = time.time() + 60  # 60초간 차단
        _stripe_failures = 0

def _record_stripe_success():
    global _stripe_failures
    _stripe_failures = 0
```

---

## 10. 보안 고려사항

### 10.1 API 키 관리

| 키 | 저장 위치 | 접근 |
|----|-----------|------|
| STRIPE_SECRET_KEY | 환경변수 (Railway) | 백엔드만 |
| STRIPE_WEBHOOK_SECRET | 환경변수 (Railway) | 백엔드만 |
| STRIPE_PUBLISHABLE_KEY | 사용 안 함 | N/A |

Stripe Checkout Session 방식은 server-side에서 URL을 생성하므로
프론트엔드에 publishable key가 필요 없다. (Stripe.js embed 방식이 아님)

### 10.2 Webhook 보안

- Signature 검증: 구현 완료 (billing.py)
- Raw body 사용: `request.get_data()` 로 raw payload 사용 (JSON 파싱 전에 서명 검증)
- CSRF 불필요: Webhook은 Stripe -> 서버 직접 호출이므로 세션 쿠키 없음

### 10.3 Rate Limiting

기존 security.py의 Rate Limiting이 billing 엔드포인트에도 적용됨.
추가로 create-checkout에 대해 더 엄격한 제한 고려:

```python
# security.py에서 엔드포인트별 rate limit 조정
# /api/billing/create-checkout: 분당 5회 (브루트포스 방지)
# /api/billing/webhook: 제한 없음 (Stripe에서 호출)
```

### 10.4 결제 정보 비저장

PivoxQuant은 카드 번호를 직접 수집하거나 저장하지 않는다.
Stripe Checkout/Customer Portal에서 모든 결제 정보를 처리한다.
PCI DSS 준수 불필요 (SAQ A 수준).

---

## 11. 한국 전자상거래법 준수

### 11.1 청약 철회 (제7조 3항 대응)

이용약관 제7조 3항: 결제일로부터 7일 이내 청약 철회 가능.

```python
# POST /api/billing/refund (Phase 2 -- 수동 환불 먼저, 추후 자동화)
@billing_bp.route("/refund", methods=["POST"])
@api_auth
def request_refund():
    """이용약관 제7조 기준 환불 처리."""
    if not current_user.stripe_subscription_id:
        return jsonify({"error": "No active subscription"}), 400

    # 최근 결제 조회
    latest_payment = PaymentHistory.query.filter_by(
        user_id=current_user.id, status="paid"
    ).order_by(PaymentHistory.created_at.desc()).first()

    if not latest_payment:
        return jsonify({"error": "No payment found"}), 400

    days_since_payment = (datetime.utcnow() - latest_payment.created_at).days

    if days_since_payment > 7:
        # 7일 초과: 잔여 기간 일할 계산 (위약금 10% 공제)
        # Phase 2에서 자동화, 현재는 안내 메시지
        return jsonify({
            "error": "7-day withdrawal period expired. Contact support for pro-rated refund.",
            "days_since_payment": days_since_payment,
            "support_email": "support@pivoxquant.com"
        }), 400

    # 7일 이내: 환불 처리
    # 서비스 이용 여부에 따라 일할 공제
    # Phase 1에서는 수동 처리 (관리자 확인 후 Stripe Dashboard에서 환불)
    return jsonify({
        "ok": True,
        "message": "Refund request received. Will be processed within 3 business days.",
        "days_since_payment": days_since_payment
    })
```

### 11.2 환불 기준 정리

| 조건 | 환불 금액 | 처리 방법 |
|------|-----------|-----------|
| 7일 이내 + 서비스 미이용 | 전액 | Stripe Refund API (자동) |
| 7일 이내 + 서비스 이용 | 일할 공제 후 환불 | 수동 계산 후 Stripe Refund |
| 7일 초과 | 잔여 기간 일할 - 위약금 10% | 수동 처리 |

### 11.3 필수 고지사항 (프론트엔드)

결제 전 반드시 표시:
- 월 자동 갱신 고지
- 해지 방법 안내
- 환불 정책 링크 (/terms#section-7)
- 유료 서비스 내용 명시

---

## 12. 비용 분석

### 12.1 Stripe 수수료

| 항목 | 비율 |
|------|------|
| 한국 카드 결제 | 3.5% |
| 해외 카드 결제 | 3.5% + 0.5% (환전) |
| 분쟁/차지백 | 건당 $15 |

### 12.2 플랜별 순수익 (Stripe 수수료 차감 후)

| 플랜 | 월 가격 | 수수료 (3.5%) | 순수익 |
|------|---------|---------------|--------|
| Pro | 9,900원 | 347원 | 9,553원 |
| Premium | 19,900원 | 697원 | 19,203원 |

### 12.3 손익분기점 (BEP)

월 고정비 약 14만원 (Railway $12 + Claude API 약 5만원 + 도메인 0.3만원) 기준:
- Pro만: 15명 x 9,553원 = 143,295원 (BEP)
- 혼합 (Pro 80%, Premium 20%): 13명 x 평균 11,483원 = 149,279원 (BEP)

---

## 13. 모니터링 및 알림

### 13.1 결제 메트릭 (로깅)

```python
# billing.py에 로깅 강화
logger.info(f"[BILLING] checkout_created user={user.id} plan={plan}")
logger.info(f"[BILLING] subscription_activated user={user.id} tier={tier}")
logger.warning(f"[BILLING] payment_failed user={user.id} customer={customer_id}")
logger.info(f"[BILLING] subscription_cancelled user={user.id}")
```

### 13.2 추적해야 할 핵심 지표

| 메트릭 | 계산 방법 | 목표 |
|--------|-----------|------|
| MRR (Monthly Recurring Revenue) | SUM(active_pro * 9900 + active_premium * 19900) | 성장 추세 |
| Churn Rate | 월 해지 수 / 전월 구독자 수 | < 5% |
| Payment Failure Rate | 실패 건 / 전체 청구 건 | < 3% |
| Checkout Conversion | 완료 / 세션 생성 | > 60% |
| ARPU | MRR / 총 유료 구독자 | 모니터링 |

### 13.3 운영 알림 (Phase 2)

Critical 알림 (즉시 대응):
- Stripe Webhook signature 검증 실패 5회 이상
- 결제 실패율 10% 초과
- Stripe API connection 장애 (circuit breaker open)

Warning 알림 (일 1회 확인):
- 신규 구독 0건 (3일 연속)
- 해지율 급증 (전주 대비 2배)

---

## 14. 구현 순서 (Stripe 계정 생성 후)

### Phase A: 핵심 결제 (1일)

1. Stripe 대시보드에서 Product/Price 생성
2. 환경변수 설정 (.env, Railway)
3. billing.py 의 "enterprise" -> "premium" 변경
4. `STRIPE_PRICE_ENTERPRISE` -> `STRIPE_PRICE_PREMIUM` 환경변수명 변경
5. Webhook URL 등록, invoice 이벤트 추가
6. `models/payment.py` 생성, DB 마이그레이션
7. invoice.payment_failed, invoice.paid 핸들러 추가
8. Stripe CLI로 로컬 Webhook 테스트

### Phase B: 기능 제한 (1일)

1. `routes/decorators.py` 에 `require_tier` 데코레이터 추가
2. 각 라우트에 `@require_tier` 적용 (섹션 5.2 참조)
3. TIER_LIMITS 상수 정의
4. 포트폴리오 종목 수 제한 로직 추가
5. 시그널 빈도 제한 로직 추가
6. 403 응답 통일 테스트

### Phase C: 프론트엔드 (1일)

1. `/pricing` 페이지 생성
2. `upgrade-prompt.tsx` 컴포넌트 생성
3. `subscription-banner.tsx` 컴포넌트 생성
4. Settings 페이지에 구독 관리 섹션 추가
5. 403 응답 인터셉터 (apiFetch 수정) -- 업그레이드 프롬프트 자동 표시
6. endpoints.ts, types.ts, hooks.ts 업데이트

### Phase D: 안정화 (1일)

1. Stripe 테스트 모드에서 전체 플로우 테스트
2. Webhook 중복 처리 검증
3. 결제 실패 -> past_due -> 복구 플로우 테스트
4. 환불 처리 테스트 (이용약관 제7조 준수)
5. 라이브 모드 전환 전 체크리스트

### Phase E: 후속 (별도 일정)

1. 연간 구독 Price 추가 + 프론트 토글
2. 무료 체험 (trial_days) 설정
3. 환불 자동화 (Stripe Refund API 연동)
4. 결제 메트릭 대시보드 (관리자용)
5. 네이버페이/카카오페이 활성화 확인

---

## 15. 테스트 체크리스트

### 15.1 Stripe CLI 로컬 테스트

```bash
# Stripe CLI 설치 후
stripe listen --forward-to localhost:5050/api/billing/webhook

# 테스트 이벤트 전송
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
stripe trigger customer.subscription.deleted
stripe trigger invoice.payment_failed
stripe trigger invoice.paid
```

### 15.2 수동 테스트 시나리오

| # | 시나리오 | 예상 결과 |
|---|---------|-----------|
| 1 | Free 유저가 Pro 결제 | tier=pro, status=active |
| 2 | Pro 유저가 Premium 업그레이드 | tier=premium (비례배분) |
| 3 | Premium 유저가 구독 취소 | cancel_at_period_end=true, 기간 만료 후 free |
| 4 | 취소 예약 유저가 취소 철회 | cancel_at_period_end=false |
| 5 | 결제 실패 (테스트 카드 4000000000000341) | status=past_due, 알림 생성 |
| 6 | 결제 실패 후 카드 변경하여 재시도 성공 | status=active |
| 7 | Free 유저가 AI 채팅 접근 | 403 + 업그레이드 프롬프트 |
| 8 | Free 유저가 4번째 종목 추가 | 403 + 종목 제한 메시지 |
| 9 | Pro 유저가 자동매매 접근 | 403 + Premium 업그레이드 프롬프트 |
| 10 | Webhook 중복 전송 | 두 번째는 무시 (멱등성) |
| 11 | Free 유저가 시그널 refresh 2회 연속 | 429 + 다음 갱신 시간 표시 |
| 12 | 비로그인 유저가 /pricing 접근 | 가격표 정상 표시 (인증 불필요) |

### 15.3 Stripe 테스트 카드

| 카드 번호 | 시나리오 |
|-----------|---------|
| 4242 4242 4242 4242 | 성공 |
| 4000 0000 0000 0341 | 첫 결제 실패 후 재시도 성공 |
| 4000 0000 0000 9995 | 항상 실패 |
| 4000 0025 0000 3155 | 3D Secure 인증 필요 |

---

## 16. 이용약관 정합성

이용약관 제6조, 제7조와의 정합성 확인:

| 약관 항목 | 시스템 대응 | 상태 |
|-----------|-------------|------|
| 제6조: Free/Pro/Premium 3티어 | 모델 + 가격표 반영 | 설계 완료 |
| 제7조 1항: 결제 수단 | Stripe (카드/간편결제) | 설계 완료 |
| 제7조 2항: 월 자동 갱신 | Stripe Subscription 자동 갱신 | 기존 구현 |
| 제7조 3항: 7일 이내 청약 철회 | 수동 환불 -> Phase 2 자동화 | 설계 완료 |
| 제7조 4항: 환불 기준 (일할 공제) | Stripe 비례배분 (proration) | Stripe 기본 지원 |
| 제7조 5항: 3영업일 이내 환불 | Stripe Refund API | Phase 2 |
| 제7조 6항: 무료 체험 자동 전환 | trial_end 필드 + Stripe Trial | Phase 2 |

---

## 17. integrations_map.md 업데이트 내용

구현 시 아래 내용을 integrations_map.md에 추가:

```markdown
| Stripe | 구독 결제/관리 | 설계 완료 | 3.5% 수수료 |
```

연동 스펙:
- Endpoint: https://api.stripe.com/v1/
- Auth: Bearer Token (STRIPE_SECRET_KEY)
- Rate Limit: 100 req/sec (Stripe 기본)
- SLA: 99.99% uptime
- Timeout: 10초
- Retry: SDK 내장 2회 재시도
- Fallback: "결제 시스템 점검 중" 메시지

---

## 부록 A: 파일 변경 목록 (구현 시)

| 파일 | 변경 유형 | 설명 |
|------|-----------|------|
| `models/user.py` | 수정 | subscription_end, trial_end 필드 추가 |
| `models/payment.py` | 신규 | PaymentHistory 모델 |
| `models/__init__.py` | 수정 | PaymentHistory import 추가 |
| `routes/decorators.py` | 수정 | require_tier 데코레이터 추가 |
| `routes/billing.py` | 수정 | enterprise->premium, 신규 이벤트 핸들러, plans/history/cancel/resume 엔드포인트 |
| `routes/ai.py` | 수정 | @require_tier("pro", "premium") 추가 |
| `routes/autotrade.py` | 수정 | @require_tier("premium") 추가 |
| `routes/backtest.py` | 수정 | @require_tier("pro", "premium") 추가 |
| `routes/quant.py` | 수정 | @require_tier("premium") 추가 |
| `routes/realtime.py` | 수정 | stream에 @require_tier("pro", "premium") 추가 |
| `routes/push.py` | 수정 | subscribe에 @require_tier("premium") 추가 |
| `routes/portfolio.py` | 수정 | 종목 수 제한 로직 추가 |
| `frontend/src/app/(dashboard)/pricing/page.tsx` | 신규 | 가격표 페이지 |
| `frontend/src/components/billing/upgrade-prompt.tsx` | 신규 | 업그레이드 프롬프트 |
| `frontend/src/components/billing/subscription-banner.tsx` | 신규 | 구독 상태 배너 |
| `frontend/src/app/(dashboard)/settings/page.tsx` | 수정 | 구독 관리 섹션 추가 |
| `frontend/src/lib/endpoints.ts` | 수정 | billing 엔드포인트 4개 추가 |
| `frontend/src/lib/types.ts` | 수정 | Plan, Subscription 타입 추가 |
| `frontend/src/lib/hooks.ts` | 수정 | useSubscription, usePlans 훅 추가 |
| `frontend/src/lib/api.ts` | 수정 | 403 인터셉터 추가 |

## 부록 B: 연간 구독 설계 (Phase 2)

### B.1 가격 구조

| 플랜 | 월간 | 연간 | 연간 할인율 |
|------|------|------|------------|
| Pro | 9,900원/월 | 99,000원/년 (8,250원/월) | 17% (2개월 무료) |
| Premium | 19,900원/월 | 199,000원/년 (16,583원/월) | 17% (2개월 무료) |

### B.2 프론트엔드 토글

가격표 페이지 상단에 "월간 / 연간" 토글 추가.
연간 선택 시 카드에 "연 99,000원 (월 8,250원)" 표시 + "2개월 무료" 뱃지.

### B.3 환경변수 추가

```bash
STRIPE_PRICE_PRO_YEARLY=price_...
STRIPE_PRICE_PREMIUM_YEARLY=price_...
```

### B.4 create-checkout 수정

```python
PLAN_PRICES = {
    "pro": STRIPE_PRICE_PRO,
    "pro_yearly": STRIPE_PRICE_PRO_YEARLY,
    "premium": STRIPE_PRICE_PREMIUM,
    "premium_yearly": STRIPE_PRICE_PREMIUM_YEARLY,
}
```

---

## 부록 C: 프로덕션 체크리스트 (라이브 전환 전)

- [ ] Stripe 라이브 키로 환경변수 교체
- [ ] Webhook 엔드포인트 URL을 프로덕션 도메인으로 변경
- [ ] Customer Portal 설정 최종 확인
- [ ] 테스트 모드 데이터 삭제 (Stripe Dashboard)
- [ ] SSL 인증서 확인 (Webhook은 HTTPS 필수)
- [ ] Rate limiting 최종 확인 (/api/billing/* 엔드포인트)
- [ ] 에러 로깅 확인 (Railway 로그에서 [BILLING] 태그)
- [ ] 이용약관 시행일 확정 및 공시
- [ ] 개인정보처리방침에 Stripe 위탁 업체 추가
- [ ] 한국 전자상거래법 청약 철회 프로세스 확인
