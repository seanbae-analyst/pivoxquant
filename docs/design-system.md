# StockPilot Design System

> Documented 2026-04-09. Based on actual codebase usage, not aspirational.
> Design direction: "Clean Enterprise" (Cohere-inspired, white-first SaaS aesthetic).

---

## 1. Color Palette

### 1.1 CSS Custom Properties (Light Mode Only)

No dark mode is implemented. The system is light-only.

#### Core Semantic Tokens (`:root` in `globals.css`)

| Token                | Value     | Usage                        |
|----------------------|-----------|------------------------------|
| `--background`       | `#ffffff` | Page background              |
| `--foreground`       | `#0f172a` | Primary text (slate-900)     |
| `--card`             | `#ffffff` | Card background              |
| `--card-foreground`  | `#0f172a` | Card text                    |
| `--popover`          | `#ffffff` | Popover/dropdown background  |
| `--popover-foreground` | `#0f172a` | Popover text               |
| `--primary`          | `#059669` | Primary actions (emerald-600)|
| `--primary-foreground` | `#ffffff` | Text on primary             |
| `--secondary`        | `#f8fafc` | Secondary surfaces (slate-50)|
| `--secondary-foreground` | `#334155` | Secondary text (slate-700) |
| `--muted`            | `#f1f5f9` | Muted backgrounds (slate-100)|
| `--muted-foreground` | `#64748b` | Muted text (slate-500)      |
| `--accent`           | `#f1f5f9` | Accent backgrounds           |
| `--accent-foreground`| `#0f172a` | Accent text                  |
| `--destructive`      | `#dc2626` | Destructive/error actions    |
| `--border`           | `#e2e8f0` | Default borders (slate-200)  |
| `--input`            | `#e2e8f0` | Input borders                |
| `--ring`             | `#10b981` | Focus ring (emerald-500)     |
| `--radius`           | `0.625rem`| Base border radius (10px)    |

#### Status/Semantic Colors

| Token       | Value     | Usage                                 |
|-------------|-----------|---------------------------------------|
| `--success` | `#10b981` | Profit, BUY signal, positive PnL      |
| `--warning` | `#f59e0b` | HOLD signal, caution states           |
| `--info`    | `#0ea5e9` | Informational highlights              |
| `--gold`    | `#d97706` | Premium/gold accent                   |

#### Chart Colors

| Token      | Value     | Usage           |
|------------|-----------|-----------------|
| `--chart-1`| `#10b981` | Emerald (primary)|
| `--chart-2`| `#0ea5e9` | Sky blue        |
| `--chart-3`| `#f59e0b` | Amber           |
| `--chart-4`| `#8b5cf6` | Violet          |
| `--chart-5`| `#f43f5e` | Rose            |

#### Dashboard Surface Tokens

| Token               | Value                        | Usage                     |
|----------------------|------------------------------|---------------------------|
| `--db-bg`            | `#f8fafc`                    | Dashboard background      |
| `--db-surface`       | `#ffffff`                    | Card/panel surface        |
| `--db-surface-2`     | `#f8fafc`                    | Secondary surface         |
| `--db-surface-3`     | `#f1f5f9`                    | Tertiary surface          |
| `--db-border`        | `#e2e8f0`                    | Surface borders           |
| `--db-border-hover`  | `#cbd5e1`                    | Hover border enhancement  |
| `--db-glow-emerald`  | `rgba(16, 185, 129, 0.08)`   | Positive glow             |
| `--db-glow-red`      | `rgba(239, 68, 68, 0.08)`    | Negative glow             |
| `--db-glow-cyan`     | `rgba(14, 165, 233, 0.06)`   | Info glow                 |

#### Sidebar Tokens

| Token                         | Value     |
|-------------------------------|-----------|
| `--sidebar`                   | `#f8fafc` |
| `--sidebar-foreground`        | `#334155` |
| `--sidebar-primary`           | `#10b981` |
| `--sidebar-primary-foreground`| `#ffffff` |
| `--sidebar-accent`            | `#f1f5f9` |
| `--sidebar-accent-foreground` | `#0f172a` |
| `--sidebar-border`            | `#e2e8f0` |
| `--sidebar-ring`              | `#10b981` |

### 1.2 Hardcoded Tailwind Colors (Used Directly in Components)

These bypass CSS variables. They are the most frequently used direct colors:

| Tailwind Class         | Hex       | Usage Context                        |
|------------------------|-----------|--------------------------------------|
| `slate-900`            | `#0f172a` | Primary text in pages                |
| `slate-700`            | `#334155` | Secondary text                       |
| `slate-500`            | `#64748b` | Muted text, labels                   |
| `slate-400`            | `#94a3b8` | Placeholder, captions, section labels|
| `slate-200`            | `#e2e8f0` | Borders, dividers                    |
| `slate-100`            | `#f1f5f9` | Hover backgrounds                    |
| `slate-50`             | `#f8fafc` | Surface backgrounds, alternating rows|
| `emerald-700`          | `#047857` | Active nav text                      |
| `emerald-600`          | `#059669` | Primary button, links, BUY signal    |
| `emerald-500`          | `#10b981` | Live indicator dot, progress bars    |
| `emerald-200`          | `#a7f3d0` | Active nav border, signal borders    |
| `emerald-50`           | `#ecfdf5` | Active nav bg, BUY badge bg          |
| `red-600`              | `#dc2626` | SELL signal text, negative PnL       |
| `red-200`              | `#fecaca` | SELL signal border                   |
| `red-50`               | `#fef2f2` | SELL signal background               |
| `amber-600`            | `#d97706` | HOLD signal, warning text            |
| `amber-200`            | `#fde68a` | Warning borders                      |
| `amber-50`             | `#fffbeb` | Warning/HOLD background              |
| `cyan-500`             | `#06b6d4` | Stress test live indicator           |
| `violet-500`/`violet-600` | --    | AI Chat icon accent                  |
| `#0a1929`              | --        | Hero value text (custom near-black)  |
| `#003a70`              | --        | Portfolio card left border            |

### 1.3 Signal Color System (from `format.ts`)

```
BUY:  bg-success/15  text-success  border-success/30   (emerald family)
SELL: bg-destructive/15  text-destructive  border-destructive/30   (red family)
HOLD: bg-warning/15  text-warning  border-warning/30   (amber family)
```

PnL color logic:
```
positive  -> text-success
negative  -> text-destructive
zero      -> text-muted-foreground
```

Score color logic:
```
>= 70  -> bg-success
>= 45  -> bg-warning
< 45   -> bg-destructive
```

### 1.4 Chart-Specific Colors (Recharts)

- Positive area: `#34d399` (emerald-400)
- Negative area: `#f87171` (red-400)
- Grid: `rgba(0,0,0,0.06)`
- Axis tick text: `#52525b` (zinc-600)
- Tooltip bg: `#ffffff`, border: `#e2e8f0`, text: `#0f172a`

---

## 2. Typography

### 2.1 Font Stack

| Role          | Font                                       | CSS Variable             | Source        |
|---------------|--------------------------------------------|--------------------------|---------------|
| Body (ko/en)  | Pretendard Variable                        | Applied via inline style | External CDN  |
| Headings      | Geist                                      | `--font-geist-heading`   | next/font     |
| Monospace     | IBM Plex Mono (400, 500, 600)              | `--font-geist-mono`      | next/font     |

**Actual body font-family** (from `layout.tsx` inline style):
```
"Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif
```

**html element**: `font-sans` class (maps to `--font-sans` via Tailwind, but overridden by body inline style).

### 2.2 Font Size Scale (Actually Used)

| Class/Value     | Rendered Size | Where Used                                    |
|-----------------|---------------|-----------------------------------------------|
| `text-[8px]`    | 8px           | Micro labels (1M, 3M period labels)           |
| `text-[9px]`    | 9px           | Section labels, signal badges, LIVE indicator  |
| `text-[10px]`   | 10px          | Ticker symbols, metric labels, section headers |
| `text-[11px]`   | 11px          | Sign Out, filter tabs, nav helper text         |
| `text-[12px]`   | 12px          | Nav links, loading messages                    |
| `text-xs`       | 12px          | Badge text, captions, sub-values               |
| `text-[13px]`   | 13px          | AI Chat subtitle (responsive)                  |
| `text-[14px]`   | 14px          | Logo "StockPilot" text                         |
| `text-sm`       | 14px          | Default body text, card descriptions           |
| `body`          | 15px          | Base body font-size (globals.css)              |
| `text-base`     | 16px          | Card titles, dialog titles                     |
| `text-lg`       | 18px          | Page subheadings                               |
| `text-xl`       | 20px          | Metric values, scanner scores                  |
| `text-2xl`      | 24px          | Large metric values (VIX, Treasury)            |
| `text-3xl`      | 30px          | Hero portfolio value                           |
| `text-4xl`      | 36px          | Hero portfolio value (md+ breakpoint)          |

### 2.3 Font Weight Usage

| Weight        | Class           | Where Used                                    |
|---------------|-----------------|-----------------------------------------------|
| 400 (regular) | `font-normal`   | Denominator text ("/100"), body               |
| 500 (medium)  | `font-medium`   | Nav links, section labels, item names          |
| 600 (semibold)| `font-semibold` | Card titles, metric labels, signal badges      |
| 700 (bold)    | `font-bold`     | Primary values, buttons, nav brand             |
| 800 (extrabold)| `font-extrabold`| Hero values, metric card numbers              |

### 2.4 Monospace Usage Pattern

`font-mono` (IBM Plex Mono) is used for:
- Financial data values (prices, percentages, scores)
- Ticker symbols
- Section header labels (uppercase + tracking-wide pattern)
- Market data in charts

Common monospace label pattern:
```
font-mono text-[10px] font-semibold uppercase tracking-[1.2px] text-slate-400
```

---

## 3. Spacing System

### 3.1 Base Unit

Tailwind default 4px grid (no custom spacing scale).

### 3.2 Common Padding Patterns

| Context                | Value           | Tailwind Class   |
|------------------------|-----------------|------------------|
| Card content (standard)| 20px            | `p-5`            |
| Card content (compact) | 12px            | `p-3`            |
| Card content (large)   | 24px / 32px     | `p-6` / `p-8`    |
| Main content area      | 12px / 16px     | `p-3 md:p-4`     |
| Nav horizontal padding | 16px            | `px-4`           |
| Nav item padding       | 12px H / 6px V  | `px-3 py-1.5`    |
| Button default         | 20px horizontal | `px-5`           |
| Dialog content         | 20px            | `p-5`            |

### 3.3 Common Gap Patterns

| Context              | Value    | Tailwind Class |
|----------------------|----------|----------------|
| Card internal gap    | 16px     | `gap-4`        |
| Metric card grid     | 12px     | `gap-3`        |
| Section spacing      | 16px     | `space-y-4`    |
| Nav items            | 2px      | `gap-0.5`      |
| Right-side items     | 12px     | `gap-3`        |
| Grid columns (large) | 16px     | `gap-4`        |

### 3.4 Margin Patterns

| Context                | Value          | Tailwind Class      |
|------------------------|----------------|---------------------|
| Section header bottom  | 12-20px        | `mb-3` to `mb-5`    |
| Metric value top       | 8px            | `mt-2`              |
| Section between blocks | 16px           | `mt-4`              |

---

## 4. Border Radius

| Context               | Value    | CSS / Tailwind            |
|------------------------|---------|---------------------------|
| Buttons                | 9999px  | `rounded-full`            |
| Cards                  | 16px    | `rounded-2xl`             |
| Input fields           | 12px    | `rounded-xl`              |
| Dropdown menus         | 12px    | `rounded-xl`              |
| Nav link pills         | 8px     | `rounded-lg`              |
| Badges                 | 9999px  | `rounded-full`            |
| Filter pills           | 9999px  | `rounded-full`            |
| Progress bars          | 9999px  | `rounded-full`            |
| Status dots            | 50%     | `rounded-full`            |
| Data section items     | 12px    | `rounded-xl`              |
| Base `--radius`        | 10px    | shadcn computed scale      |

---

## 5. Component Inventory

### 5.1 shadcn/ui Components (Base UI primitives)

All sourced from shadcn v4 with `base-nova` style, using `@base-ui/react` primitives:

| Component       | File                 | Notes                                      |
|-----------------|----------------------|--------------------------------------------|
| Button          | `ui/button.tsx`      | 6 variants, 8 sizes, `rounded-full`        |
| Card            | `ui/card.tsx`        | 7 sub-components, `rounded-2xl`, two sizes |
| Badge           | `ui/badge.tsx`       | 6 variants via CVA                         |
| Input           | `ui/input.tsx`       | `rounded-xl`, emerald focus ring           |
| Dialog          | `ui/dialog.tsx`      | Full modal system with overlay + portal    |
| DropdownMenu    | `ui/dropdown-menu.tsx`| Complete menu system with sub-menus       |
| Label           | `ui/label.tsx`       | Basic form label                           |
| Avatar          | `ui/avatar.tsx`      | 3 sizes (sm/default/lg), with badge + group|
| Logo            | `ui/logo.tsx`        | Next/Image wrapper for `/logo-hero.jpeg`   |

### 5.2 Custom Animation Components (`ui/animated.tsx`)

| Component       | Purpose                                           |
|-----------------|---------------------------------------------------|
| PageTransition  | Framer Motion fade+slide-up (300ms)               |
| StaggerContainer| Parent for staggered child reveal (60ms interval) |
| StaggerItem     | Individual stagger child                          |
| CountUp         | Animated number counting (ease-out cubic, 1.2s)   |
| PriceTick       | Green/red flash on price change (800ms)           |
| PulseDot        | Animated live indicator dot                       |
| Skeleton        | Shimmer loading placeholder                       |
| GlowCard        | Hover glow effect card (Framer Motion)            |

### 5.3 3D Components (`ui/scene-3d.tsx`)

| Component       | Usage                            |
|-----------------|----------------------------------|
| Scene3D         | Landing page particle background |
| LoginScene      | Login page particle background   |

Dependencies: `@react-three/fiber`, `@react-three/drei`, `three`

### 5.4 Layout Components

| Component          | File                              | Purpose                   |
|--------------------|-----------------------------------|---------------------------|
| MarketTicker       | `layout/market-ticker.tsx`        | Scrolling market prices   |
| NotificationBell   | `layout/notification-bell.tsx`    | Alert notification UI     |
| Header             | `layout/header.tsx`               | Landing page header       |
| Sidebar            | `layout/sidebar.tsx`              | (Exists but not active)   |
| ConnectionBanner   | `realtime/connection-banner.tsx`  | WebSocket status banner   |

### 5.5 Dashboard Widgets

| Component            | File                              | Purpose                    |
|----------------------|-----------------------------------|----------------------------|
| SummaryCards         | `dashboard/summary-cards.tsx`     | Portfolio value + metrics  |
| PnlChart             | `dashboard/pnl-chart.tsx`        | Recharts area chart        |
| PnlChart3D           | `dashboard/pnl-chart-3d.tsx`     | Three.js 3D chart          |
| SectorPie            | `dashboard/sector-pie.tsx`       | Recharts pie chart         |
| PositionCard         | `dashboard/position-card.tsx`    | Individual stock card      |
| SignalsWidget        | `dashboard/signals-widget.tsx`   | BUY/SELL signal list       |
| TopMoversWidget      | `dashboard/top-movers-widget.tsx` | Daily top movers          |
| MarketWidget         | `dashboard/market-widget.tsx`    | Market overview mini       |
| VixWidget            | `dashboard/vix-widget.tsx`       | VIX gauge                  |
| CrossAssetWidget     | `dashboard/cross-asset-widget.tsx`| Multi-asset comparison    |
| DiscoverWidget       | `dashboard/discover-widget.tsx`  | AI discovery suggestions   |
| AiCoachingWidget     | `dashboard/ai-coaching-widget.tsx`| AI coaching card          |
| AnalyticsBar         | `dashboard/analytics-bar.tsx`    | Quick analytics strip      |
| ActionModals         | `dashboard/action-modals.tsx`    | Edit capital modal etc.    |

### 5.6 Terminal Components

| Component          | File                              | Purpose                      |
|--------------------|-----------------------------------|------------------------------|
| Terminal           | `terminal/terminal.tsx`           | Bloomberg-style main view    |
| TerminalNav        | `terminal/terminal-nav.tsx`       | Terminal header navigation   |
| TerminalChart      | `terminal/terminal-chart.tsx`     | Recharts + TradingView chart |
| TerminalTabs       | `terminal/terminal-tabs.tsx`      | Bottom data tabs             |
| TerminalMetrics    | `terminal/terminal-metrics.tsx`   | Metrics strip                |
| RightPanel         | `terminal/right-panel.tsx`        | Watchlist/signals panel      |

### 5.7 Market Components

| Component      | File                        | Purpose               |
|----------------|-----------------------------|-----------------------|
| OverviewTab    | `market/overview-tab.tsx`   | Market overview data  |
| IntradayTab    | `market/intraday-tab.tsx`   | Intraday scanner      |
| ScannerTab     | `market/scanner-tab.tsx`    | Stock scanner         |

### 5.8 PWA Components

| Component          | File                          | Purpose                    |
|--------------------|-------------------------------|----------------------------|
| SwInit             | `pwa/sw-init.tsx`            | Service worker registration|
| InstallPrompt      | `pwa/install-prompt.tsx`     | PWA install banner         |
| InAppBrowserGuard  | `pwa/in-app-browser-guard.tsx`| In-app browser detection  |

---

## 6. CSS Utility Classes (Custom)

Defined in `globals.css`:

| Class               | Purpose                                          |
|----------------------|--------------------------------------------------|
| `.spring-transition` | `cubic-bezier(0.16, 1, 0.3, 1)` easing          |
| `.glass-surface`     | White with backdrop blur + border                |
| `.bezel-card`        | Double-bezel card (outer border + inner fill)    |
| `.bezel-card-inner`  | Inner content of bezel card                      |
| `.glass-card`        | Elevated card with shadow + hover                |
| `.metric-card`       | Metric display card                              |
| `.gradient-mesh`     | Background gradient (currently just slate-50 bg) |
| `.text-gradient`     | Emerald-to-cyan text gradient                    |
| `.text-gradient-gold`| Amber-to-gold text gradient                      |
| `.table-row`         | Table row with hover highlight                   |
| `.filter-pill`       | Pill-shaped filter toggle                        |
| `.signal-buy`        | BUY signal badge style                           |
| `.signal-sell`       | SELL signal badge style                          |
| `.signal-hold`       | HOLD signal badge style                          |
| `.status-dot`        | 8px animated status indicator                    |
| `.scrollbar-hide`    | Hide scrollbar completely                        |
| `.scrollbar-thin`    | 4px thin scrollbar                               |
| `.landing-divider`   | Gradient horizontal rule                         |
| `.landing-dark`      | Landing page scope (light theme, despite name)   |

---

## 7. Animation System

### 7.1 CSS Animations (globals.css)

| Name              | Duration/Easing                           | Usage                    |
|-------------------|-------------------------------------------|--------------------------|
| `pulse-dot`       | 2s ease-in-out infinite                   | Status dot pulse         |
| `fade-up`         | 0.6s cubic-bezier(0.16, 1, 0.3, 1)       | Page element entrance    |
| `shimmer`         | Background position shift                 | Skeleton loading         |
| `float`           | translateY bounce                         | Floating decorations     |
| `marquee`         | 30s linear infinite                       | Market ticker scroll     |
| `shine`           | Background position shift                 | Shine effect             |
| `price-flash`     | 1.5s ease-out                             | Generic price flash      |
| `price-flash-up`  | 1.5s ease-out (emerald tint)              | Price increase flash     |
| `price-flash-down`| 1.5s ease-out (red tint)                  | Price decrease flash     |

### 7.2 Framer Motion Animations (animated.tsx)

| Pattern         | Duration | Easing     |
|-----------------|----------|------------|
| Page enter      | 300ms    | easeOut    |
| Stagger delay   | 60ms     | --         |
| Stagger child   | 350ms    | default    |
| CountUp         | 1200ms   | ease-out cubic |
| Price flash     | 300ms    | default    |

### 7.3 Transition Timing

Most components use the spring easing curve inline:
```css
transition-timing-function: cubic-bezier(0.16, 1, 0.3, 1);
```

Standard transition durations: `duration-200`, `duration-300`, `duration-400`.

---

## 8. Responsive Breakpoints

Using Tailwind v4 defaults (no custom breakpoints configured):

| Prefix | Min-Width | Usage Frequency | Layout Behavior                    |
|--------|-----------|-----------------|-------------------------------------|
| `sm`   | 640px     | High            | Show/hide nav elements, 2-col grids|
| `md`   | 768px     | Medium          | Content padding, text scaling       |
| `lg`   | 1024px    | High            | 3-4 column grids, panel layouts    |
| `xl`   | 1280px    | Rare            | Not commonly used                   |
| `2xl`  | 1536px    | Not used        | --                                  |

### Common Responsive Grid Patterns

```
grid-cols-1 sm:grid-cols-2 lg:grid-cols-4    -- Metric cards
grid-cols-1 sm:grid-cols-2 lg:grid-cols-3    -- Content cards
grid-cols-2 gap-3 lg:grid-cols-4             -- Summary cards
grid-cols-1 gap-4 lg:grid-cols-2             -- Two-panel layouts
```

### Responsive Content Padding
```
p-3 md:p-4    -- Main content area
p-5           -- Card standard (no responsive scaling)
p-6 md:p-8   -- Hero card
```

---

## 9. Icon Library (Lucide React v1.7.0)

All icons from `lucide-react`. Complete usage inventory:

### Navigation/UI
`XIcon`, `ChevronRightIcon`, `CheckIcon`, `ArrowLeft`, `ArrowRight`, `ArrowUpRight`, `ArrowDownRight`, `ExternalLink`

### Finance/Trading
`TrendingUp`, `TrendingDown`, `DollarSign`, `Wallet`, `Receipt`, `Calculator`

### Status/Alert
`Bell`, `AlertTriangle`, `AlertCircle`, `Shield`, `Zap`

### Data/Analytics
`BarChart3`, `PieChart`, `Activity`, `Target`, `Scale`, `Grid3X3`, `Layers`, `Hash`

### AI/Tech
`Bot`, `Sparkles`, `Brain`, `Cpu`, `MessageSquare`, `Send`

### Action/Utility
`Search`, `Play`, `Power`, `RotateCcw`, `RefreshCw`, `Trash2`, `Settings`, `Monitor`, `Link2`, `Eye`, `X`, `Info`, `Loader2`

### Category/Domain
`Globe`, `Users`, `Star`, `Trophy`, `Calendar`, `Clock`, `Newspaper`, `History`, `FlaskConical`, `Gem`, `Briefcase`

### Onboarding-Specific
`Flag`, `Hand`, `Coffee`, `CheckCircle2`, `Leaf`, `Heart`, `Landmark`, `Flame`, `ShoppingBag`, `Factory`

### Toggle
`ToggleLeft`, `ToggleRight`

### Profile
`User`

---

## 10. Dependencies

| Package                | Version   | Purpose                          |
|------------------------|-----------|----------------------------------|
| `shadcn`               | 4.1.2     | Component generation CLI         |
| `@base-ui/react`       | 1.3.0     | Headless UI primitives (shadcn)  |
| `class-variance-authority` | 0.7.1 | Component variant management     |
| `tailwind-merge`       | 3.5.0     | Tailwind class deduplication     |
| `clsx`                 | 2.1.1     | Conditional class joining        |
| `lucide-react`         | 1.7.0     | Icon library                     |
| `recharts`             | 3.8.1     | Charts (Area, Pie, Bar, Line)    |
| `lightweight-charts`   | 5.1.0     | TradingView candlestick chart    |
| `framer-motion`        | 12.38.0   | Animation library                |
| `@react-three/fiber`   | 9.5.0     | React Three.js renderer          |
| `@react-three/drei`    | 10.7.7    | Three.js helpers                 |
| `three`                | 0.183.2   | 3D graphics engine               |
| `tw-animate-css`       | 1.4.0     | Tailwind animation utilities     |
| `swr`                  | 2.4.1     | Data fetching/caching            |
| `tailwindcss`          | 4.x       | CSS framework                    |
| `next`                 | 16.2.2    | React framework                  |

---

## 11. Known Issues and Inconsistencies

### Color Inconsistencies
1. **Badge component uses dark-mode colors** (`text-emerald-400`, `bg-zinc-300`, `rgba(255,255,255,0.06)`) while the app is light-mode only. These will appear incorrect on the white background.
2. **Mixed color referencing**: Some components use CSS variables (`text-success`, `bg-destructive`), others use hardcoded Tailwind classes (`text-emerald-600`, `bg-red-50`). No single source of truth.
3. **Notification bell** uses dark-theme opacity patterns (`bg-emerald-500/[0.02]`) that are nearly invisible on white.
4. **`#0a1929`** is used as a hero text color in summary-cards but is not defined as a design token.
5. **`#003a70`** is used as a card left-border accent in summary-cards but is not part of any token system.

### Typography Inconsistencies
1. **Arbitrary font sizes dominate**: `text-[8px]` through `text-[14px]` are used extensively instead of Tailwind's standard scale. This makes the type scale unpredictable.
2. **Body font override**: The `font-sans` CSS variable mapping is overridden by an inline style on `<body>`, creating a disconnect between Tailwind's `font-sans` utility and the actual rendered font.
3. **`--font-geist-heading`** is mapped to the Geist font but used via the `font-heading` Tailwind class only in Card titles and Dialog titles. Most headings just use bold weight on the body font.

### Architecture Issues
1. **`.landing-dark` class name is misleading**: It applies a light/white theme, not dark.
2. **No dark mode implemented**: Despite CSS variable infrastructure that could support it (`:root` / `.dark` pattern), only light values are defined.
3. **`glass-surface` assumes white**: `rgba(255, 255, 255, 0.92)` is hardcoded.
4. **Sidebar component exists** (`layout/sidebar.tsx`) but is not used in any layout.
5. **`scene-3d.tsx`** brings in heavy Three.js dependencies (three + fiber + drei) for a purely decorative landing page effect.

### Spacing Issues
1. **Card padding is inconsistent**: Some cards use `p-5`, others `p-3`, `p-4`, or `p-6`, without clear size-based rules.

---

## 12. File Reference

| File                            | Role                              |
|---------------------------------|-----------------------------------|
| `src/app/globals.css`           | All CSS variables + utility classes|
| `src/app/layout.tsx`            | Font loading, root HTML structure |
| `src/app/(dashboard)/layout.tsx`| Dashboard nav, ticker, content    |
| `components.json`              | shadcn configuration              |
| `src/components/ui/*`          | Base UI component library         |
| `src/lib/format.ts`            | Color utility functions           |
| `package.json`                 | Dependency versions               |
