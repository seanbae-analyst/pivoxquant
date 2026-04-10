# StockPilot 구독 결제 시스템 설계

> 작성일: 2026-04-09
> 상태: 설계 완료 / 구현 대기 (Stripe 계정 생성 후 진행)
> 설계자: 연동부 (Integrations Agent)

---

## 1. 현재 상태 분석

### 1.1 이미 구축된 것

백엔드와 프론트엔드에 Stripe 연동의 골격이 이미 존재한다.

**User 모델 (models/user.py)** -- 구독 필드 3개 존재:
- `subscription_tier` (String(10), default="free")
- `stripe_customer_id` (String(100), nullable)
- `stripe_subscription_id` (String(100), nullable)
- `subscription_status` (String(20), default="inactive")

**Billing 라우트 (routes/billing.py)** -- 3개 엔드포인트 구현 완료:
- `POST /api/billing/create-checkout` -- Stripe Checkout Session 생성
- `POST /api/billing/webhook` -- Stripe Webhook 수신 (3개 이벤트 처리)
- `GET /api/billing/subscription` -- 구독 상태 조회
- `POST /api/billing/portal` -- Stripe Customer Portal

**프론트엔드 (lib/endpoints.ts)** -- billing 엔드포인트 등록 완료:
- `billing.createCheckout`, `billing.subscription`, `billing.portal`

### 1.2 누락된 것

| 영역 | 누락 항목 |
|------|-----------|
| Stripe 대시보드 | Product/Price 미생성, Webhook URL 미설정 |
| 환경변수 | STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_PRO, STRIPE_PRICE_ENTERPRISE 미설정 |
| 데이터 모델 | `subscription_end` (만료일), 결제 이력 테이블 없음 |
| 기능 제한 | `require_tier` 데코레이터 미구현 -- 모든 API가 Free 유저에게 열려 있음 |
| 프론트엔드 | 가격표 페이지 없음, 결제 플로우 UI 없음, 업그레이드 프롬프트 없음 |
| 가격 구조 | "enterprise" 로 되어 있으나 "premium" 이어야 함 |
| 보안 | Webhook 서명 검증 구현됨, 하지만 테스트 미완 |

### 1.3 네이밍 불일치 -- 반드시 수정

현재 billing.py의 PLAN_PRICES/PLAN_TIERS에서 `enterprise`를 사용하지만,
이용약관(제6조)과 비즈니스 플랜은 `premium`을 사용한다.
**구현 시 "enterprise" -> "premium" 으로 통일 필요.**

---

## 2. Stripe 대시보드 설정 (수동 작업)

### 2.1 Product/Price 구조

Stripe Dashboard에서 아래와 같이 생성한다.

```
Product: StockPilot Pro
  ├── Price: price_pro_monthly
  │   - 금액: 9,900 KRW / month
  │   - Recurring, interval: month
  │   - Currency: KRW
  └── (추후) Price: price_pro_yearly
      - 금액: 99,000 KRW / year (2개월 할인)

Product: StockPilot Premium
  ├── Price: price_premium_monthly
  │   - 금액: 19,900 KRW / month
  │   - Recurring, interval: month
  │   - Currency: KRW
  └── (추후) Price: price_premium_yearly
      - 금액: 199,000 KRW / year (2개월 할인)
```

### 2.2 Webhook 설정

Stripe Dashboard > Developers > Webhooks 에서:
- Endpoint URL: `https://{BACKEND_DOMAIN}/api/billing/webhook`
- Events to listen:
  1. `checkout.session.completed` -- 결제 완료
  2. `customer.subscription.updated` -- 구독 변경 (업/다운그레이드, 갱신)
  3. `customer.subscription.deleted` -- 구독 취소 확정
  4. `invoice.payment_failed` -- 결제 실패 (추가 필요)
  5. `invoice.paid` -- 결제 성공 (결제 이력용, 추가 필요)
  6. `customer.subscription.trial_will_end` -- 체험 종료 3일 전 (추후)

### 2.3 Customer Portal 설정

Stripe Dashboard > Settings > Billing > Customer portal:
- 구독 취소: 허용 (즉시 취소 or 기간 만료 후 취소)
- 플랜 변경: Pro <-> Premium 전환 허용
- 결제 수단 변경: 허용
- 인보이스 조회: 허용

### 2.4 환경변수

```bash
# .env (절대 프론트엔드에 노출 금지)
STRIPE_SECRET_KEY=sk_live_...        # 또는 sk_test_... (테스트용)
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRO=price_...           # Pro 월간 Price ID
STRIPE_PRICE_PREMIUM=price_...       # Premium 월간 Price ID
STRIPE_PUBLISHABLE_KEY=pk_live_...   # 프론트엔드용 (Checkout 리다이렉트 불필요시 사용 안 함)
FRONTEND_URL=https://stockpilot.kr   # Checkout 성공/취소 리다이렉트 URL
```

---

## 3. 데이터 모델 변경

### 3.1 User 모델 필드 추가

```python
# models/user.py -- 추가 필드
subscription_end = db.Column(db.DateTime, nullable=True)  # 현재 구독 기간 만료일
trial_end = db.Column(db.DateTime, nullable=True)          # 무료 체험 만료일 (추후)
```

### 3.2 결제 이력 모델 (신규 파일: models/payment.py)

```python
class PaymentHistory(db.Model):
    __tablename__ = "payment_history"
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    stripe_invoice_id = db.Column(db.String(100), nullable=True)
    amount           = db.Column(db.Integer, nullable=False)  # KRW 단위 (원)
    currency         = db.Column(db.String(3), default="KRW")
    status           = db.Column(db.String(20), nullable=False)  # paid, failed, refunded
    plan             = db.Column(db.String(10), nullable=False)  # pro, premium
    period_start     = db.Column(db.DateTime, nullable=True)
    period_end       = db.Column(db.DateTime, nullable=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("payments", lazy=True))
```

### 3.3 DB 마이그레이션

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
        {"key": "portfolio_limit", "value": 3, "label": "포트폴리오 종목", "label_kr": "포트폴리오 3종목"},
        {"key": "signal_frequency", "value": "daily", "label": "Signals", "label_kr": "일 1회 시그널"},
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

---

## 7. 결제 플로우 설계

### 7.1 신규 구독 플로우

```
[유저] 가격표 페이지 (/pricing)
  │
  ├── "Pro 시작하기" 클릭
  │     ↓
  │   POST /api/billing/create-checkout {plan: "pro"}
  │     ↓
  │   백엔드: Stripe Customer 생성/조회 → Checkout Session 생성
  │     ↓
  │   프론트: Stripe Checkout 페이지로 리다이렉트 (session.url)
  │     ↓
  │   [Stripe Hosted Checkout]
  │   - 카드 정보 입력
  │   - 결제 처리
  │     ↓
  │   성공: /home?billing=success 로 리다이렉트
  │   취소: /home?billing=cancelled 로 리다이렉트
  │     ↓
  │   (비동기) Webhook: checkout.session.completed
  │     ↓
  │   백엔드: user.subscription_tier = "pro"
  │           user.subscription_status = "active"
  │
  └── 완료: 프론트에서 /api/billing/subscription 재조회 → UI 갱신
```

### 7.2 구독 관리 플로우

```
[유저] 설정 페이지 (/settings)
  │
  ├── "구독 관리" 클릭
  │     ↓
  │   POST /api/billing/portal
  │     ↓
  │   Stripe Customer Portal로 리다이렉트
  │   - 결제 수단 변경
  │   - 플랜 업/다운그레이드
  │   - 구독 취소
  │   - 인보이스 조회
  │     ↓
  │   Portal에서 변경 시 Webhook으로 자동 반영
  │
  └── 또는 앱 내 취소 버튼 → POST /api/billing/cancel
      → Stripe API: subscription.cancel_at_period_end = true
      → 기간 만료까지 서비스 유지, 만료 후 free 전환
```

### 7.3 결제 실패 복구 플로우

```
Webhook: invoice.payment_failed
  ↓
백엔드: user.subscription_status = "past_due"
  ↓
프론트: 배너 표시 "결제 실패 - 결제 수단을 업데이트해 주세요"
  ↓
Stripe 자동 재시도 (3회, 1/3/5일 간격)
  ↓
├── 재시도 성공: invoice.paid → status = "active"
└── 재시도 실패: customer.subscription.deleted → tier = "free"
```

---

## 8. 프론트엔드 설계

### 8.1 신규 페이지: /pricing

경로: `frontend/src/app/(dashboard)/pricing/page.tsx`

와이어프레임:
```
┌──────────────────────────────────────────────────────────────┐
│  Choose Your Plan                                            │
│  월간 / 연간 토글                                              │
│                                                              │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────┐         │
│  │  Free     │   │  Pro  BEST   │   │  Premium     │         │
│  │           │   │              │   │              │         │
│  │  0원/월   │   │  9,900원/월  │   │  19,900원/월 │         │
│  │           │   │              │   │              │         │
│  │ - 3종목   │   │ - 무제한종목 │   │ - Pro 전체   │         │
│  │ - 기본분석│   │ - 실시간     │   │ - 자동매매   │         │
│  │ - 일1회   │   │ - AI 채팅    │   │ - 고급퀀트   │         │
│  │           │   │ - 백테스트   │   │ - 알림       │         │
│  │           │   │ - SWOT       │   │ - API접근    │         │
│  │           │   │ - AI코칭     │   │              │         │
│  │           │   │              │   │              │         │
│  │ [현재]    │   │ [시작하기]   │   │ [시작하기]   │         │
│  └──────────┘   └──────────────┘   └──────────────┘         │
│                                                              │
│  FAQ 섹션                                                    │
│  - 언제든지 취소할 수 있나요?                                    │
│  - 환불 정책은?                                                │
│  - 결제 수단은?                                                │
└──────────────────────────────────────────────────────────────┘
```

### 8.2 업그레이드 프롬프트 컴포넌트

Free 유저가 Pro/Premium 기능에 접근할 때 표시되는 공통 컴포넌트.

경로: `frontend/src/components/billing/upgrade-prompt.tsx`

```
┌─────────────────────────────────────────┐
│  [자물쇠] Pro Plan Required              │
│                                         │
│  AI 채팅은 Pro 이상 구독에서             │
│  이용 가능합니다.                        │
│                                         │
│  [Pro 시작하기]    [가격표 보기]          │
└─────────────────────────────────────────┘
```

### 8.3 구독 상태 배너

`frontend/src/components/billing/subscription-banner.tsx`

상태별 배너:
- `past_due`: "결제가 실패했습니다. 결제 수단을 업데이트해 주세요." (빨간색)
- `cancel_at_period_end`: "구독이 {날짜}에 해지됩니다." (노란색)
- `billing=success` (URL param): "구독이 활성화되었습니다!" (초록색, 5초 후 사라짐)

### 8.4 설정 페이지 구독 섹션 추가

`frontend/src/app/(dashboard)/settings/page.tsx` 에 구독 관리 섹션 추가:

```
┌─────────────────────────────────────────┐
│  [카드] Subscription                     │
│                                         │
│  현재 플랜: Pro                          │
│  상태: Active                            │
│  다음 결제일: 2026-05-09                 │
│  금액: 9,900원/월                        │
│                                         │
│  [구독 관리]  [플랜 변경]  [취소]          │
└─────────────────────────────────────────┘
```

### 8.5 프론트엔드 endpoints.ts 추가

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

### 8.6 프론트엔드 타입 추가 (types.ts)

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

---

## 9. 신뢰성 패턴 (Reliability)

### 9.1 Stripe API 호출 표준

```
요청 → Stripe API 호출 → 성공 → 응답 반환
                ↓ 실패
          StripeError 분기:
          ├── CardError        → 유저에게 카드 문제 안내
          ├── RateLimitError   → 5초 후 1회 재시도
          ├── InvalidRequestError → 로깅 + 500 에러
          ├── AuthenticationError → 로깅 + 알림 (API 키 문제)
          └── APIConnectionError → 로깅 + "일시적 오류" 안내
```

### 9.2 Webhook 멱등성

동일한 Webhook 이벤트가 중복 전달될 수 있다. 이미 처리된 이벤트 재처리 방지:

```python
# 간단한 방식: event.id 기반 중복 체크
import hashlib

_processed_events = set()  # 프로덕션에서는 Redis 또는 DB 사용

def stripe_webhook():
    ...
    event_id = event.get("id")
    if event_id in _processed_events:
        return jsonify({"ok": True, "duplicate": True})
    _processed_events.add(event_id)
    # 이벤트 처리
    ...
```

프로덕션 환경에서는 `processed_webhook_events` DB 테이블 또는 Redis SET을 사용한다.

### 9.3 Timeout 설정

```python
# Stripe API 호출 timeout
stripe.max_network_retries = 2  # 자동 재시도 2회
stripe.default_http_client = stripe.http_client.RequestsClient(
    timeout=10  # 10초 timeout
)
```

### 9.4 Webhook Signature 검증 (이미 구현됨)

billing.py의 `stripe.Webhook.construct_event()` 에서 서명 검증이 이루어지고 있다.
이 부분은 수정 불필요.

---

## 10. 보안 고려사항

### 10.1 API 키 관리

| 키 | 저장 위치 | 접근 |
|----|-----------|------|
| STRIPE_SECRET_KEY | 환경변수 (Railway) | 백엔드만 |
| STRIPE_WEBHOOK_SECRET | 환경변수 (Railway) | 백엔드만 |
| STRIPE_PUBLISHABLE_KEY | 프론트엔드 불필요* | 사용 안 함 |

*Stripe Checkout Session 방식은 server-side에서 URL을 생성하므로
프론트엔드에 publishable key가 필요 없다. (Stripe.js embed 방식이 아님)

### 10.2 Webhook 보안

- Signature 검증: 구현 완료 (billing.py)
- IP 화이트리스트: Stripe의 Webhook IP 대역만 허용 (Railway/Vercel 설정)
- Raw body 사용: `request.get_data()` 로 raw payload 사용 (JSON 파싱 전에 서명 검증)

### 10.3 CSRF 방지

- Checkout/Portal 엔드포인트는 POST 메서드 + `@api_auth` (세션 쿠키 기반)
- Webhook은 서명 검증으로 CSRF 불필요

### 10.4 결제 정보 비저장

StockPilot은 카드 번호를 직접 수집하거나 저장하지 않는다.
Stripe Checkout/Customer Portal에서 모든 결제 정보를 처리한다.
PCI DSS 준수 불필요 (SAQ A 수준).

---

## 11. 비용 분석

### 11.1 Stripe 수수료

| 항목 | 비율 |
|------|------|
| 한국 카드 결제 | 3.5% + 없음 (Stripe Korea) |
| 해외 카드 결제 | 3.5% + 0.5% (환전) |
| 분쟁/차지백 | 건당 $15 |

### 11.2 플랜별 순수익 (Stripe 수수료 차감 후)

| 플랜 | 월 가격 | 수수료 (3.5%) | 순수익 |
|------|---------|---------------|--------|
| Pro | 9,900원 | 347원 | 9,553원 |
| Premium | 19,900원 | 697원 | 19,203원 |

### 11.3 손익분기점 (BEP)

월 고정비 약 14만원 (Railway $12 + Claude API 약 5만원 + 도메인 0.3만원) 기준:
- Pro만: 15명 x 9,553원 = 143,295원 (BEP)
- 혼합 (Pro 80%, Premium 20%): 13명 x 평균 11,483원 = 149,279원 (BEP)

---

## 12. 구현 순서 (Stripe 계정 생성 후)

### Phase A: 핵심 결제 (1일)

1. Stripe 대시보드에서 Product/Price 생성
2. 환경변수 설정 (.env, Railway)
3. billing.py 의 "enterprise" -> "premium" 변경
4. `STRIPE_PRICE_ENTERPRISE` -> `STRIPE_PRICE_PREMIUM` 환경변수명 변경
5. Webhook URL 등록, invoice 이벤트 추가
6. `models/payment.py` 생성, DB 마이그레이션
7. Stripe CLI로 로컬 Webhook 테스트

### Phase B: 기능 제한 (1일)

1. `routes/decorators.py` 에 `require_tier` 데코레이터 추가
2. 각 라우트에 `@require_tier` 적용 (섹션 5.2 참조)
3. 포트폴리오 종목 수 제한 로직 추가
4. 시그널 빈도 제한 로직 추가
5. 403 응답 통일 테스트

### Phase C: 프론트엔드 (1일)

1. `/pricing` 페이지 생성
2. `upgrade-prompt.tsx` 컴포넌트 생성
3. `subscription-banner.tsx` 컴포넌트 생성
4. Settings 페이지에 구독 관리 섹션 추가
5. 403 응답 인터셉터 (SWR 미들웨어) -- 업그레이드 프롬프트 자동 표시
6. endpoints.ts, types.ts 업데이트

### Phase D: 안정화 (1일)

1. Stripe 테스트 모드에서 전체 플로우 테스트
2. Webhook 중복 처리 검증
3. 결제 실패 -> past_due -> 복구 플로우 테스트
4. 환불 처리 테스트 (이용약관 제7조 준수)
5. 라이브 모드 전환 전 체크리스트

---

## 13. 테스트 체크리스트

### 13.1 Stripe CLI 로컬 테스트

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

### 13.2 수동 테스트 시나리오

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

### 13.3 Stripe 테스트 카드

| 카드 번호 | 시나리오 |
|-----------|---------|
| 4242 4242 4242 4242 | 성공 |
| 4000 0000 0000 0341 | 첫 결제 실패 후 재시도 성공 |
| 4000 0000 0000 9995 | 항상 실패 |
| 4000 0025 0000 3155 | 3D Secure 인증 필요 |

---

## 14. 이용약관 정합성

이용약관 제6조, 제7조와의 정합성 확인:

| 약관 항목 | 시스템 대응 | 상태 |
|-----------|-------------|------|
| 제6조: Free/Pro/Premium 3티어 | 모델 + 가격표 반영 | 설계 완료 |
| 제7조 1항: 결제 수단 | Stripe (카드/간편결제) | 설계 완료 |
| 제7조 2항: 월 자동 갱신 | Stripe Subscription 자동 갱신 | 기존 구현 |
| 제7조 3항: 7일 이내 청약 철회 | Customer Portal + 수동 환불 | 추후 자동화 |
| 제7조 4항: 환불 기준 (일할 공제) | Stripe 비례배분 (proration) | Stripe 기본 지원 |
| 제7조 5항: 3영업일 이내 환불 | Stripe Refund API | 추후 구현 |
| 제7조 6항: 무료 체험 자동 전환 | trial_end 필드 + Stripe Trial | 추후 구현 |

---

## 15. integrations_map.md 업데이트 내용

구현 시 아래 내용을 integrations_map.md에 추가:

```markdown
| Stripe | 구독 결제/관리 | 설계 완료 | 3.5% 수수료 |
```

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
