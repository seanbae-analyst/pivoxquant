# PivoxQuant Design System

> Last updated: 2026-04-10
> Source of truth: Extracted from actual codebase (`globals.css`, `layout.tsx`, `components/ui/*`, dashboard/market components).
> Design direction: **Clean Enterprise** -- white-first, Cohere-inspired SaaS aesthetic. Light mode only.

---

## 1. Color Palette

### 1.1 Semantic Design Tokens (CSS Custom Properties)

Defined in `:root` of `globals.css`. No dark mode (`.dark`) variant exists.

#### Core Tokens

| Token                    | Value     | Tailwind Utility       | Usage                          |
|--------------------------|-----------|------------------------|--------------------------------|
| `--background`           | `#ffffff` | `bg-background`        | Page background                |
| `--foreground`           | `#0f172a` | `text-foreground`      | Primary text (slate-900)       |
| `--card`                 | `#ffffff` | `bg-card`              | Card background                |
| `--card-foreground`      | `#0f172a` | `text-card-foreground` | Card text                      |
| `--popover`              | `#ffffff` | `bg-popover`           | Popover/dropdown background    |
| `--popover-foreground`   | `#0f172a` | `text-popover-foreground` | Popover text                |
| `--primary`              | `#059669` | `bg-primary`           | Primary actions (emerald-600)  |
| `--primary-foreground`   | `#ffffff` | `text-primary-foreground` | Text on primary             |
| `--secondary`            | `#f8fafc` | `bg-secondary`         | Secondary surfaces (slate-50)  |
| `--secondary-foreground` | `#334155` | `text-secondary-foreground` | Secondary text (slate-700)|
| `--muted`                | `#f1f5f9` | `bg-muted`             | Muted backgrounds (slate-100)  |
| `--muted-foreground`     | `#64748b` | `text-muted-foreground`| Muted text (slate-500)         |
| `--accent`               | `#f1f5f9` | `bg-accent`            | Accent backgrounds             |
| `--accent-foreground`    | `#0f172a` | `text-accent-foreground` | Accent text                  |
| `--destructive`          | `#dc2626` | `bg-destructive`       | Destructive/error (red-600)    |
| `--border`               | `#e2e8f0` | `border-border`        | Default borders (slate-200)    |
| `--input`                | `#e2e8f0` | `border-input`         | Input borders                  |
| `--ring`                 | `#10b981` | `ring-ring`            | Focus ring (emerald-500)       |
| `--radius`               | `0.625rem`| --                     | Base border radius (10px)      |

#### Status Colors

| Token       | Value     | Tailwind Utility  | Usage                             |
|-------------|-----------|-------------------|-----------------------------------|
| `--success` | `#10b981` | `text-success`    | Profit, BUY signal, positive PnL  |
| `--warning` | `#f59e0b` | `text-warning`    | HOLD signal, caution states       |
| `--info`    | `#0ea5e9` | `text-info`       | Informational highlights          |
| `--gold`    | `#d97706` | `text-gold`       | Premium/gold accent               |

#### Chart Colors

| Token        | Value     | Usage            |
|--------------|-----------|------------------|
| `--chart-1`  | `#10b981` | Emerald (primary)|
| `--chart-2`  | `#0ea5e9` | Sky blue         |
| `--chart-3`  | `#f59e0b` | Amber            |
| `--chart-4`  | `#8b5cf6` | Violet           |
| `--chart-5`  | `#f43f5e` | Rose             |

#### Dashboard Surface Tokens

| Token               | Value                        | Usage                     |
|----------------------|------------------------------|---------------------------|
| `--db-bg`            | `#f8fafc`                    | Dashboard page background |
| `--db-surface`       | `#ffffff`                    | Card/panel surface        |
| `--db-surface-2`     | `#f8fafc`                    | Secondary surface         |
| `--db-surface-3`     | `#f1f5f9`                    | Tertiary surface          |
| `--db-border`        | `#e2e8f0`                    | Surface borders           |
| `--db-border-hover`  | `#cbd5e1`                    | Hover border enhancement  |
| `--db-glow-emerald`  | `rgba(16, 185, 129, 0.08)`   | Positive glow             |
| `--db-glow-red`      | `rgba(239, 68, 68, 0.08)`    | Negative glow             |
| `--db-glow-cyan`     | `rgba(14, 165, 233, 0.06)`   | Info glow                 |

#### Sidebar Tokens

| Token                          | Value     |
|--------------------------------|-----------|
| `--sidebar`                    | `#f8fafc` |
| `--sidebar-foreground`         | `#334155` |
| `--sidebar-primary`            | `#10b981` |
| `--sidebar-primary-foreground` | `#ffffff` |
| `--sidebar-accent`             | `#f1f5f9` |
| `--sidebar-accent-foreground`  | `#0f172a` |
| `--sidebar-border`             | `#e2e8f0` |
| `--sidebar-ring`               | `#10b981` |

### 1.2 Hardcoded Tailwind Colors (Direct Usage in Components)

These bypass CSS variables and are the most frequently used direct color classes:

| Tailwind Class     | Hex       | Usage Context                          |
|--------------------|-----------|----------------------------------------|
| `slate-900`        | `#0f172a` | Primary text in dashboard pages        |
| `slate-700`        | `#334155` | Secondary text, market ticker prices   |
| `slate-500`        | `#64748b` | Muted text, labels                     |
| `slate-400`        | `#94a3b8` | Placeholders, section labels, captions |
| `slate-200`        | `#e2e8f0` | Borders, dividers, separators          |
| `slate-100`        | `#f1f5f9` | Hover backgrounds                      |
| `slate-50`         | `#f8fafc` | Surface backgrounds, dashboard bg      |
| `emerald-700`      | `#047857` | Active nav text                        |
| `emerald-600`      | `#059669` | Primary button default, links          |
| `emerald-500`      | `#10b981` | Live indicator, progress bars, ring    |
| `emerald-200`      | `#a7f3d0` | Active nav border, signal borders      |
| `emerald-50`       | `#ecfdf5` | Active nav bg, BUY badge bg            |
| `red-600`          | `#dc2626` | SELL signal text, negative PnL         |
| `red-400`          | `#f87171` | Chart negative area fill               |
| `red-200`          | `#fecaca` | SELL signal border                     |
| `red-50`           | `#fef2f2` | SELL signal background                 |
| `amber-600`        | `#d97706` | HOLD signal, warning text              |
| `amber-200`        | `#fde68a` | Warning borders                        |
| `amber-50`         | `#fffbeb` | Warning/HOLD background                |
| `cyan-500`         | `#06b6d4` | Avatar gradient endpoint               |
| `zinc-500`         | `#71717a` | Notification bell icon                 |
| `white` / `#ffffff`| --        | Card backgrounds, nav backgrounds      |

#### One-off Custom Colors (Not Tokenized)

| Value     | Where Used                      | Note                               |
|-----------|---------------------------------|------------------------------------|
| `#0a1929` | `summary-cards.tsx` hero text   | Custom near-black, not a token     |
| `#003a70` | `summary-cards.tsx` left border | Portfolio card accent, not a token |
| `#0d0d12` | `notification-bell.tsx` dropdown| Dark dropdown bg (dark-mode relic) |

### 1.3 Signal Color System (`format.ts`)

Used consistently across position-card, scanner-tab, intraday-tab:

```
BUY:  bg-success/15  text-success  border-success/30   (emerald family)
SELL: bg-destructive/15  text-destructive  border-destructive/30   (red family)
HOLD: bg-warning/15  text-warning  border-warning/30   (amber family)
```

PnL color logic (`pnlColor`):
```
positive  -> text-success
negative  -> text-destructive
zero      -> text-muted-foreground
```

Score color logic (`scoreColor`):
```
>= 70  -> bg-success
>= 45  -> bg-warning
< 45   -> bg-destructive
```

### 1.4 Chart-Specific Colors (Recharts)

| Purpose         | Value                  |
|-----------------|------------------------|
| Positive area   | `#34d399` (emerald-400)|
| Negative area   | `#f87171` (red-400)    |
| Grid lines      | `rgba(0,0,0,0.06)`    |
| Axis tick text  | `#52525b` (zinc-600)   |
| Tooltip bg      | `#ffffff`              |
| Tooltip border  | `#e2e8f0`              |
| Tooltip text    | `#0f172a`              |

---

## 2. Typography

### 2.1 Font Stack

| Role         | Font Family                    | CSS Variable / Mechanism     | Source          |
|--------------|--------------------------------|------------------------------|-----------------|
| Body (ko/en) | Pretendard Variable            | Inline style on `<body>`     | External CDN    |
| Headings     | Geist                          | `--font-geist-heading`       | `next/font`     |
| Monospace    | IBM Plex Mono (400, 500, 600)  | `--font-geist-mono`          | `next/font`     |

Actual body `font-family` (from `layout.tsx` inline style):
```
"Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif
```

The `html` element gets `font-sans` class, but the `<body>` inline style overrides this with Pretendard.

### 2.2 Font Size Scale (All Sizes Actually Used)

| Class / Value   | Rendered Size | Where Used                                      |
|-----------------|---------------|-------------------------------------------------|
| `text-[8px]`    | 8px           | Micro labels (1M/3M period labels, QUANT badge) |
| `text-[9px]`    | 9px           | Section labels, signal badges, LIVE indicator, nav sub-brand |
| `text-[10px]`   | 10px          | Ticker symbols, metric labels, section headers, market ticker change |
| `text-[11px]`   | 11px          | Sign Out button, filter tabs, market ticker prices, notification text |
| `text-[12px]`   | 12px          | Nav links, loading messages, notification titles |
| `text-xs`       | 12px          | Badge text, captions, sub-values (Tailwind)      |
| `text-[13px]`   | 13px          | Sidebar items, notification header               |
| `text-[14px]`   | 14px          | Logo "PivoxQuant" text                           |
| `text-sm`       | 14px          | Default body text, card descriptions (Tailwind)  |
| body base       | 15px          | Base body font-size (`globals.css`)              |
| `text-base`     | 16px          | Card titles, dialog titles                       |
| `text-lg`       | 18px          | Position card price/PnL values                   |
| `text-xl`       | 20px          | Metric values, scanner scores                    |
| `text-2xl`      | 24px          | Large metric values (VIX, Treasury)              |
| `text-3xl`      | 30px          | Hero portfolio value (mobile)                    |
| `text-4xl`      | 36px          | Hero portfolio value (md+ breakpoint)            |

### 2.3 Font Weight Usage

| Weight          | Class            | Where Used                                     |
|-----------------|------------------|-------------------------------------------------|
| 400 (regular)   | `font-normal`    | Denominator text ("/100"), body                 |
| 500 (medium)    | `font-medium`    | Nav links, section labels, item names           |
| 600 (semibold)  | `font-semibold`  | Card titles, metric labels, signal badges, nav  |
| 700 (bold)      | `font-bold`      | Primary values, buttons, nav brand, badges      |
| 800 (extrabold) | `font-extrabold` | Hero values, metric card hero numbers           |

### 2.4 Monospace Usage (`font-mono` / IBM Plex Mono)

Applied to:
- Financial data values (prices, percentages, scores)
- Ticker symbols (e.g., AAPL, TSLA)
- Section header labels (uppercase + tracking-wide pattern)
- Market ticker data
- Version/system labels ("QUANT ENGINE v4")

Canonical monospace label pattern (repeated heavily in market/dashboard components):
```
font-mono text-[10px] font-semibold uppercase tracking-[1.2px] text-slate-400
```

Alternate label pattern (narrower tracking):
```
font-mono text-[9px] font-semibold uppercase tracking-[1.5px] text-slate-400
```

### 2.5 Heading Font (`font-heading` / Geist)

Used only on:
- `CardTitle` component: `font-heading text-base leading-snug font-semibold tracking-tight`
- `DialogTitle` component: `font-heading text-base leading-none font-semibold`
- Dashboard nav brand: `var(--font-geist-heading)` inline style

All other "headings" use the body font (Pretendard) with increased weight (`font-bold` / `font-extrabold`).

---

## 3. Spacing System

### 3.1 Base Unit

Tailwind 4px grid (default, no custom spacing scale).

### 3.2 Common Padding Patterns

| Context                 | Value           | Tailwind Class    |
|-------------------------|-----------------|-------------------|
| Card content (standard) | 20px            | `p-5`             |
| Card content (compact)  | 12px            | `p-3`             |
| Card content (hero)     | 24px / 32px     | `p-6` / `p-8`     |
| Main content area       | 12px / 16px     | `p-3 md:p-4`      |
| Nav horizontal padding  | 16px            | `px-4`            |
| Nav item padding        | 12px H / 6px V  | `px-3 py-1.5`     |
| Button default          | 20px horizontal | `px-5`            |
| Dialog content          | 20px            | `p-5`             |
| Card footer             | 16px            | `p-4`             |

### 3.3 Common Gap Patterns

| Context               | Value   | Tailwind Class |
|-----------------------|---------|----------------|
| Card internal gap     | 16px    | `gap-4`        |
| Metric card grid      | 12px    | `gap-3`        |
| Section spacing       | 16px    | `space-y-4`    |
| Nav items             | 2px     | `gap-0.5`      |
| Right-side items      | 12px    | `gap-3`        |
| Grid columns (large)  | 16px    | `gap-4`        |
| Market ticker items   | 32px    | `gap-8`        |
| Position data grid    | 12px Y  | `gap-y-3`      |

### 3.4 Margin Patterns

| Context                 | Value     | Tailwind Class    |
|-------------------------|-----------|-------------------|
| Section header bottom   | 12-20px   | `mb-3` to `mb-5`  |
| Metric value top        | 8px       | `mt-2`            |
| Section between blocks  | 16px      | `mt-4`            |
| Metric value subtitle   | 4px       | `mt-1`            |

---

## 4. Border Radius

| Context               | Value    | CSS / Tailwind             |
|-----------------------|---------|----------------------------|
| Buttons               | 9999px  | `rounded-full`             |
| Cards                 | 16px    | `rounded-2xl`              |
| Input fields          | 12px    | `rounded-xl`               |
| Dropdown menus        | 12px    | `rounded-xl` / `rounded-lg`|
| Nav link pills        | 8px     | `rounded-lg`               |
| Badges                | 9999px  | `rounded-full`             |
| Filter pills          | 9999px  | `rounded-full`             |
| Progress bars         | 9999px  | `rounded-full`             |
| Status dots           | 50%     | `rounded-full`             |
| Bezel cards           | 16px    | `border-radius: 16px`      |
| Bezel card inner      | 13px    | `border-radius: 13px`      |
| Glass cards           | 12px    | `border-radius: 12px`      |
| Base `--radius`       | 10px    | shadcn computed scale       |

Computed radius scale (from `--radius: 0.625rem`):
```
--radius-sm: 6px   (0.6x)
--radius-md: 8px   (0.8x)
--radius-lg: 10px  (1.0x)
--radius-xl: 14px  (1.4x)
--radius-2xl: 18px (1.8x)
--radius-3xl: 22px (2.2x)
--radius-4xl: 26px (2.6x)
```

---

## 5. Component Inventory

### 5.1 shadcn/ui Base Components

All sourced from shadcn v4 with `base-nova` style, using `@base-ui/react` primitives:

| Component       | File                   | Variants / Notes                               |
|-----------------|------------------------|-------------------------------------------------|
| Button          | `ui/button.tsx`        | 6 variants (default/outline/secondary/ghost/destructive/link), 8 sizes (default/xs/sm/lg/icon/icon-xs/icon-sm/icon-lg), `rounded-full`, spring easing |
| Card            | `ui/card.tsx`          | 7 sub-components (Card, CardHeader, CardTitle, CardAction, CardDescription, CardContent, CardFooter), `rounded-2xl`, size="default"/"sm", uses `--db-surface` vars |
| Badge           | `ui/badge.tsx`         | 6 variants via CVA (default/secondary/destructive/outline/ghost/link), `rounded-full`, height 20px |
| Input           | `ui/input.tsx`         | `rounded-xl`, emerald focus ring, height 40px, spring easing |
| Dialog          | `ui/dialog.tsx`        | Full modal system (overlay + portal + popup), `rounded-2xl`, `sm:max-w-sm`, blur backdrop, close button with XIcon |
| DropdownMenu    | `ui/dropdown-menu.tsx` | Full menu system with sub-menus, checkbox items, radio items, separator, `rounded-lg` |
| Label           | `ui/label.tsx`         | Basic form label, `text-sm font-medium` |
| Avatar          | `ui/avatar.tsx`        | 3 sizes (sm: 24px, default: 32px, lg: 40px), fallback + image + badge + group |
| Logo            | `ui/logo.tsx`          | Next/Image wrapper for `/logo-hero.jpeg`, `rounded-lg` |

### 5.2 Custom Animation Components (`ui/animated.tsx`)

Uses `framer-motion` for orchestrated animations:

| Component        | Purpose                                              | Duration / Config               |
|------------------|------------------------------------------------------|---------------------------------|
| `PageTransition` | Fade + slide-up page entrance                        | 300ms, easeOut                  |
| `StaggerContainer` | Parent for staggered child reveal                  | 60ms stagger interval           |
| `StaggerItem`    | Individual stagger child (fade + slide-up + scale)   | 350ms per item                  |
| `CountUp`        | Animated number counting                             | 1200ms, ease-out cubic          |
| `PriceTick`      | Green/red flash on price change with scale pulse     | 800ms flash, 300ms scale        |
| `PulseDot`       | Animated live indicator dot with ping effect         | CSS `animate-ping`              |
| `Skeleton`       | Shimmer loading placeholder                          | CSS `animate-pulse`             |
| `GlowCard`       | Hover glow effect card (blue glow)                   | Framer Motion `whileHover`      |

### 5.3 3D Components (`ui/scene-3d.tsx`)

| Component    | Usage                              |
|--------------|------------------------------------|
| `Scene3D`    | Landing page particle background   |
| `LoginScene` | Login page particle background     |

Dependencies: `@react-three/fiber`, `@react-three/drei`, `three`

### 5.4 Layout Components

| Component          | File                              | Purpose                          |
|--------------------|-----------------------------------|----------------------------------|
| Dashboard Layout   | `app/(dashboard)/layout.tsx`      | Top nav + ticker + content area  |
| MarketTicker       | `layout/market-ticker.tsx`        | Scrolling market prices (Framer Motion, 35s loop) |
| NotificationBell   | `layout/notification-bell.tsx`    | Alert notification dropdown      |
| Header             | `layout/header.tsx`               | Landing page header (alt layout) |
| Sidebar            | `layout/sidebar.tsx`              | Desktop sidebar + MobileNav (exists but inactive in current layout) |
| ConnectionBanner   | `realtime/connection-banner.tsx`  | SSE connection status banner     |

### 5.5 Dashboard Widgets

| Component            | File                               | Purpose                     |
|----------------------|------------------------------------|-----------------------------|
| SummaryCards         | `dashboard/summary-cards.tsx`      | Portfolio value + 4 metric cards |
| PositionCard         | `dashboard/position-card.tsx`      | Individual stock position card |
| PnlChart             | `dashboard/pnl-chart.tsx`         | Recharts area chart          |
| PnlChart3D           | `dashboard/pnl-chart-3d.tsx`      | Three.js 3D chart            |
| SectorPie            | `dashboard/sector-pie.tsx`        | Recharts pie chart           |
| SignalsWidget        | `dashboard/signals-widget.tsx`    | BUY/SELL signal list         |
| TopMoversWidget      | `dashboard/top-movers-widget.tsx` | Daily top movers             |
| MarketWidget         | `dashboard/market-widget.tsx`     | Market overview mini         |
| VixWidget            | `dashboard/vix-widget.tsx`        | VIX gauge                    |
| CrossAssetWidget     | `dashboard/cross-asset-widget.tsx`| Multi-asset comparison       |
| DiscoverWidget       | `dashboard/discover-widget.tsx`   | AI discovery suggestions     |
| AiCoachingWidget     | `dashboard/ai-coaching-widget.tsx`| AI coaching card             |
| AnalyticsBar         | `dashboard/analytics-bar.tsx`     | Quick analytics strip        |
| ActionModals         | `dashboard/action-modals.tsx`     | QuickBuy, QuickSell, BuyNew, EditCapital, EditPosition, DeletePosition modals |

### 5.6 Terminal Components (Bloomberg-style view)

| Component        | File                            | Purpose                      |
|------------------|---------------------------------|------------------------------|
| Terminal         | `terminal/terminal.tsx`         | Bloomberg-style main view    |
| TerminalNav      | `terminal/terminal-nav.tsx`     | Terminal header navigation   |
| TerminalChart    | `terminal/terminal-chart.tsx`   | Recharts + TradingView chart |
| TerminalTabs     | `terminal/terminal-tabs.tsx`    | Bottom data tabs             |
| TerminalMetrics  | `terminal/terminal-metrics.tsx` | Metrics strip                |
| RightPanel       | `terminal/right-panel.tsx`      | Watchlist/signals panel      |

### 5.7 Market Components

| Component    | File                       | Purpose              |
|--------------|----------------------------|----------------------|
| OverviewTab  | `market/overview-tab.tsx`  | Market overview data |
| IntradayTab  | `market/intraday-tab.tsx`  | Intraday scanner     |
| ScannerTab   | `market/scanner-tab.tsx`   | Stock scanner        |

### 5.8 Agents Components

| Component          | File                              | Purpose                    |
|--------------------|-----------------------------------|----------------------------|
| AgentDetailPanel   | `agents/agent-detail-panel.tsx`   | Agent detail drawer        |
| AgentDirectory     | `agents/agent-directory.tsx`      | Agent list/table view      |
| AgentNode          | `agents/agent-node.tsx`           | React Flow node            |
| OrgChartView       | `agents/org-chart-view.tsx`       | Org chart layout           |
| PdcaFlowView       | `agents/pdca-flow-view.tsx`       | PDCA flow diagram          |

### 5.9 PWA Components

| Component          | File                            | Purpose                    |
|--------------------|---------------------------------|----------------------------|
| SwInit             | `pwa/sw-init.tsx`               | Service worker registration|
| InstallPrompt      | `pwa/install-prompt.tsx`        | PWA install banner         |
| InAppBrowserGuard  | `pwa/in-app-browser-guard.tsx`  | In-app browser detection   |

---

## 6. CSS Utility Classes (Custom)

Defined in `globals.css`:

### Surface Classes

| Class               | Purpose                                          |
|---------------------|--------------------------------------------------|
| `.glass-surface`    | White semi-transparent with backdrop blur + border (`rgba(255,255,255,0.92)`, `blur(24px)`) |
| `.bezel-card`       | Double-bezel card -- outer border + 3px padding + inner content area, 16px radius |
| `.bezel-card-inner` | Inner content of bezel card (`--db-surface-2`, 13px radius, `1.25rem` padding) |
| `.glass-card`       | Elevated card with shadow + hover effect (12px radius) |
| `.metric-card`      | Metric display card (12px radius, `1.25rem` padding) |
| `.gradient-mesh`    | Background (currently just `--db-bg`) |

### Text Effect Classes

| Class                 | Purpose                                     |
|-----------------------|---------------------------------------------|
| `.text-gradient`      | Emerald-to-cyan text gradient (`#10b981` to `#0ea5e9`) |
| `.text-gradient-gold` | Amber-to-gold text gradient (`#d97706` to `#f59e0b`) |
| `.text-glow-emerald`  | Disabled (text-shadow: none)                |
| `.text-glow-cyan`     | Disabled (text-shadow: none)                |

### Interactive Classes

| Class               | Purpose                                          |
|---------------------|--------------------------------------------------|
| `.spring-transition` | `cubic-bezier(0.16, 1, 0.3, 1)` easing function |
| `.table-row`         | Table row with hover highlight (`#f8fafc`)       |
| `.filter-pill`       | Pill-shaped filter toggle (active: emerald bg, inactive: slate border) |

### Signal Badge Classes

| Class          | Background | Border       | Text Color |
|----------------|------------|--------------|------------|
| `.signal-buy`  | `#ecfdf5`  | `#a7f3d0`    | `#059669`  |
| `.signal-sell` | `#fef2f2`  | `#fecaca`    | `#dc2626`  |
| `.signal-hold` | `#fffbeb`  | `#fde68a`    | `#d97706`  |

### Status & Scroll Classes

| Class               | Purpose                                    |
|---------------------|--------------------------------------------|
| `.status-dot`       | 8px animated dot (active/inactive/warning/danger variants) |
| `.scrollbar-hide`   | Hide scrollbar completely                  |
| `.scrollbar-thin`   | 4px thin scrollbar with slate-300 thumb    |
| `.landing-divider`  | Gradient horizontal rule (`transparent` to `#e2e8f0` to `transparent`) |

### Landing Page Classes

| Class                  | Purpose                                        |
|------------------------|------------------------------------------------|
| `.landing-dark`        | Landing page scope (misleading name -- applies LIGHT theme) |
| `.landing-section-dark`| Dark contrast sections within landing (bg: `#0b1120`) |

---

## 7. Animation System

### 7.1 CSS Keyframe Animations (`globals.css`)

| Name               | Duration / Easing                          | Usage                    |
|--------------------|---------------------------------------------|--------------------------|
| `pulse-dot`        | 2s ease-in-out infinite                     | Status dot pulse         |
| `fade-up`          | 0.6s cubic-bezier(0.16, 1, 0.3, 1)         | Page element entrance    |
| `shimmer`          | Background position shift                   | Skeleton loading         |
| `float`            | translateY bounce                            | Floating decorations     |
| `marquee`          | 30s linear infinite                          | Market ticker scroll     |
| `shine`            | Background position shift                    | Shine effect             |
| `price-flash`      | 1.5s ease-out                                | Generic price flash      |
| `price-flash-up`   | 1.5s ease-out (emerald tint)                 | Price increase flash     |
| `price-flash-down` | 1.5s ease-out (red tint)                     | Price decrease flash     |

### 7.2 Framer Motion Animations (`animated.tsx`)

| Pattern          | Duration | Easing         |
|------------------|----------|----------------|
| Page enter       | 300ms    | easeOut        |
| Stagger delay    | 60ms     | --             |
| Stagger child    | 350ms    | default        |
| CountUp          | 1200ms   | ease-out cubic |
| Price flash      | 300ms    | default        |
| Market ticker    | 35s      | linear, infinite |

### 7.3 Transition Timing

Most interactive components use the spring easing curve via `.spring-transition` class or inline style:
```css
transition-timing-function: cubic-bezier(0.16, 1, 0.3, 1);
```

Standard transition durations used: `duration-200`, `duration-300`, `duration-400`.

---

## 8. Responsive Breakpoints

Using Tailwind v4 defaults (no custom breakpoints):

| Prefix | Min-Width | Usage Frequency | Layout Behavior                       |
|--------|-----------|-----------------|---------------------------------------|
| `sm`   | 640px     | High            | Show/hide nav elements, 2-col grids, dialog widths |
| `md`   | 768px     | High            | Content padding, right panel visibility, sidebar breakpoint |
| `lg`   | 1024px    | High            | 3-4 column grids, expanded layouts    |
| `xl`   | 1280px    | Low             | Scanner 4-col grid                    |
| `2xl`  | 1536px    | Not used        | --                                    |

### Common Responsive Grid Patterns

```
grid-cols-2 gap-3 lg:grid-cols-4          -- Summary metric cards
grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 -- Market overview metrics
grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 -- Content cards
grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-5 -- Intraday items
grid-cols-2 md:grid-cols-4                -- Stats grid, terminal metrics
grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4   -- Sector grid
```

### Responsive Content Padding
```
p-3 md:p-4    -- Main content area
p-5           -- Card standard (no responsive scaling)
p-6 md:p-8   -- Hero card
```

### Responsive Visibility
```
hidden sm:inline       -- Desktop-only text (nav brand subtitle, username)
hidden sm:block        -- Desktop-only dividers, sign out button
hidden sm:flex         -- Desktop-only groups
hidden md:flex         -- Tablet+ right panel, search bar
hidden md:table-cell   -- Tablet+ table columns
md:hidden              -- Mobile-only bottom nav
```

---

## 9. Icon Library -- Lucide React

All icons sourced from `lucide-react`. Complete inventory organized by category:

### Navigation / UI
`XIcon`, `X`, `ChevronRightIcon`, `ChevronRight`, `CheckIcon`, `ArrowLeft`, `ArrowRight`, `ArrowUpRight`, `ArrowDownRight`, `ExternalLink`, `Search`, `Eye`, `List`, `Plus`

### Finance / Trading
`TrendingUp`, `TrendingDown`, `DollarSign`, `Wallet`, `Receipt`, `Calculator`, `Briefcase`

### Status / Alert
`Bell`, `BellRing`, `AlertTriangle`, `AlertCircle`, `Shield`, `ShieldCheck`, `Zap`

### Data / Analytics
`BarChart3`, `PieChart`, `Activity`, `Target`, `Scale`, `Grid3X3`, `Layers`, `Hash`

### AI / Tech
`Bot`, `Sparkles`, `Brain`, `Cpu`, `MessageSquare`, `Send`, `Network`, `GitBranch`

### Action / Utility
`Play`, `Power`, `RotateCcw`, `RefreshCw`, `Trash2`, `Settings`, `Monitor`, `Link2`, `Info`, `Loader2`, `ToggleLeft`, `ToggleRight`

### Category / Domain
`Globe`, `Users`, `User`, `Star`, `Trophy`, `Calendar`, `Clock`, `Newspaper`, `History`, `FlaskConical`, `Gem`

### Onboarding-Specific
`Flag`, `Hand`, `Coffee`, `CheckCircle2`, `Leaf`, `Heart`, `Landmark`, `Flame`, `ShoppingBag`, `Factory`, `Sprout`, `TreePine`, `Mountain`, `Rocket`, `ThumbsDown`, `MinusCircle`, `Pause`, `ShoppingCart`

### Custom SVG Icons (sidebar.tsx)
The sidebar uses hand-crafted 18x18 SVG icons instead of Lucide:
`IconChart`, `IconBell`, `IconList`, `IconGlobe`, `IconNews`, `IconStar`, `IconBot`, `IconBook`, `IconMore`

---

## 10. Dependencies

| Package                     | Version   | Purpose                           |
|-----------------------------|-----------|-----------------------------------|
| `next`                      | 16.2.2    | React framework                   |
| `tailwindcss`               | 4.x       | CSS framework                     |
| `shadcn`                    | 4.1.2     | Component generation CLI          |
| `@base-ui/react`            | 1.3.0     | Headless UI primitives (shadcn)   |
| `class-variance-authority`  | 0.7.1     | Component variant management      |
| `tailwind-merge`            | 3.5.0     | Tailwind class deduplication      |
| `clsx`                      | 2.1.1     | Conditional class joining         |
| `lucide-react`              | 1.7.0     | Icon library                      |
| `recharts`                  | 3.8.1     | Charts (Area, Pie, Bar, Line)     |
| `lightweight-charts`        | 5.1.0     | TradingView candlestick chart     |
| `framer-motion`             | 12.38.0   | Animation library                 |
| `@react-three/fiber`        | 9.5.0     | React Three.js renderer           |
| `@react-three/drei`         | 10.7.7    | Three.js helpers                  |
| `three`                     | 0.183.2   | 3D graphics engine                |
| `tw-animate-css`            | 1.4.0     | Tailwind animation utilities      |
| `swr`                       | 2.4.1     | Data fetching/caching             |
| `sonner`                    | --        | Toast notifications               |

---

## 11. Known Issues and Inconsistencies

### COLOR ISSUES

1. **Badge component uses dark-mode colors**: The `badge.tsx` default variant uses `text-emerald-400`, `bg-zinc-300`, `rgba(255,255,255,0.06)` which are dark-theme values. On the white background of this light-mode-only app, these will render poorly (near-invisible backgrounds, washed-out text).

2. **Notification bell uses dark-theme styling**: The `notification-bell.tsx` dropdown uses `bg-[#0d0d12]` (near-black) and `rgba(255,255,255,0.06)` hover states. This creates a jarring dark popup in an otherwise all-white UI. The bell icon hover also uses `rgba(255,255,255,0.06)` which is invisible on white.

3. **Mixed color referencing**: Some components use CSS variable utilities (`text-success`, `bg-destructive`) while others use hardcoded Tailwind classes (`text-emerald-600`, `bg-red-50`). No single source of truth. This makes theme changes require touching dozens of files.

4. **Un-tokenized custom colors**: `#0a1929` (hero text) and `#003a70` (card border accent) in `summary-cards.tsx` are not part of any token system. Changes require finding hardcoded values.

### TYPOGRAPHY ISSUES

1. **Arbitrary font sizes dominate**: `text-[8px]` through `text-[14px]` are used extensively instead of Tailwind's standard scale (`text-xs`, `text-sm`, etc.). This makes the type scale unpredictable and difficult to maintain.

2. **Body font override conflict**: The `font-sans` CSS variable is mapped in `globals.css`, but the `<body>` inline style overrides it with Pretendard. Tailwind's `font-sans` utility and the actual rendered font are disconnected.

3. **Heading font underused**: `--font-geist-heading` is loaded but only used on `CardTitle` and `DialogTitle`. Most page headings just use body font with increased weight, creating inconsistency.

### ARCHITECTURE ISSUES

1. **`.landing-dark` class is misleading**: The name suggests dark theme but applies a light/white theme. Confusing for any developer.

2. **No dark mode**: Despite CSS variable infrastructure that could support `:root` / `.dark` toggling, only light values are defined. The `@custom-variant dark (&:is(.dark *))` rule in globals.css is set up but unused.

3. **Hardcoded glass-surface**: `rgba(255, 255, 255, 0.92)` prevents future dark mode adoption.

4. **Sidebar component unused**: `layout/sidebar.tsx` with full desktop + mobile nav exists but is not imported in the active dashboard layout. The dashboard layout has its own inline navigation.

5. **Heavy 3D dependencies**: `scene-3d.tsx` imports three + fiber + drei (significant bundle size) for a purely decorative landing page particle effect.

### SPACING ISSUES

1. **Card padding inconsistency**: Cards use `p-3`, `p-4`, `p-5`, `p-6`, or `p-8` without clear rules tied to card size or context. The Card component has a `size` prop ("default"/"sm") that controls header/content padding (`px-5` vs `px-3`), but individual pages override this freely.

---

## 12. File Reference

| File                                 | Role                                   |
|--------------------------------------|----------------------------------------|
| `src/app/globals.css`                | All CSS variables + utility classes    |
| `src/app/layout.tsx`                 | Font loading, root HTML structure      |
| `src/app/(dashboard)/layout.tsx`     | Dashboard nav, ticker, content area    |
| `src/components/ui/*`               | Base UI component library (9 files)   |
| `src/components/dashboard/*`        | Dashboard widget components (14 files)|
| `src/components/layout/*`           | Layout components (4 files)           |
| `src/components/market/*`           | Market tab components (3 files)       |
| `src/components/terminal/*`         | Terminal components (6 files)         |
| `src/components/agents/*`           | Agent components (5 files)            |
| `src/components/pwa/*`              | PWA components (3 files)              |
| `src/components/realtime/*`         | Realtime components (1 file)          |
| `src/lib/format.ts`                 | Color utility functions (pnlColor, signalColor, scoreColor) |
| `src/lib/utils.ts`                  | `cn()` classname merge utility        |
