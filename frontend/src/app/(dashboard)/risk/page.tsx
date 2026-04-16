"use client";

import useSWR from "swr";
import { API } from "@/lib/endpoints";
import { useAnalytics } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { fmtUsd, fmtPct } from "@/lib/format";
import { Skeleton, CardSkeleton } from "@/components/ui/loading-skeleton";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { usePortfolio } from "@/lib/hooks";
import {
  Shield,
  AlertTriangle,
  TrendingDown,
  Activity,
  CheckCircle,
  XCircle,
  BarChart3,
  Info,
  Lightbulb,
} from "lucide-react";

/* ── 7-Layer Risk Defense reference (canonical names + meanings + actions) ── */

interface LayerDefinition {
  no: number;
  key: string;        // matched against backend layer name (loose match)
  title: string;
  meaning: string;    // why this layer exists
  triggerAction: string; // what to do when triggered
}

const LAYER_DEFINITIONS: LayerDefinition[] = [
  {
    no: 1,
    key: "var",
    title: "VaR Layer — 일별 손실 한도",
    meaning: "95% 확률로 하루 손실 한도를 넘는지 감시.",
    triggerAction: "신규 매수 보류, 비중 큰 종목부터 부분 익절/손절 고려.",
  },
  {
    no: 2,
    key: "correlation",
    title: "Correlation Layer — 종목 간 상관관계",
    meaning: "포지션들이 너무 같은 방향으로 움직이는지(분산 효과 소실) 감시.",
    triggerAction: "다른 섹터/자산군(예: 채권 ETF, 금) 추가로 분산 강화.",
  },
  {
    no: 3,
    key: "vix",
    title: "VIX Layer — 시장 변동성",
    meaning: "VIX(공포지수)가 기준 위로 치솟으면 시장 전반 위험 국면.",
    triggerAction: "변동성 확대 국면 — 신규 매수 보류, 현금 비중 확대 권장.",
  },
  {
    no: 4,
    key: "tail",
    title: "Tail Layer — 극단 손실 위험",
    meaning: "정규 분포로는 설명 안 되는 꼬리 위험(블랙스완) 노출 측정.",
    triggerAction: "헤지 수단(인버스 ETF, 풋옵션) 검토 또는 위험자산 비중 축소.",
  },
  {
    no: 5,
    key: "daily",
    title: "Daily Layer — 일일 손실 누적",
    meaning: "오늘 하루 누적 손실이 일일 한도를 초과했는지.",
    triggerAction: "당일 추가 매매 중단, 다음날 시장 재평가 후 진입.",
  },
  {
    no: 6,
    key: "sector",
    title: "Sector Layer — 섹터 집중 리스크",
    meaning: "한 섹터에 비중이 과도하게 쏠려 있는지(예: 반도체 60%).",
    triggerAction: "초과 섹터 비중을 줄이고 다른 섹터로 재배분.",
  },
  {
    no: 7,
    key: "cash",
    title: "Cash Layer — 현금 비중",
    meaning: "현금 buffer가 너무 적어 급락 시 매수 여력/방어력이 없는지.",
    triggerAction: "일부 포지션 정리해 현금 비중을 권장 수준으로 회복.",
  },
];

function findLayerDefinition(name: string | undefined): LayerDefinition | undefined {
  if (!name) return undefined;
  const n = name.toLowerCase();
  return LAYER_DEFINITIONS.find((d) => n.includes(d.key));
}

/* ── Types ── */

interface VaRResponse {
  var_95?: number;
  var_99?: number;
  method?: string;
  confidence_level?: number;
  portfolio_value?: number;
}

interface DrawdownResponse {
  max_drawdown?: number;
  current_drawdown?: number;
  recovery_days?: number;
  drawdown_start?: string;
  drawdown_end?: string;
  peak_value?: number;
  trough_value?: number;
}

interface StressScenario {
  name?: string;
  impact_pct?: number;
  description?: string;
  portfolio_loss?: number;
}

interface StressTestResponse {
  scenarios?: StressScenario[];
}

interface ComponentESItem {
  ticker?: string;
  contribution_pct?: number;
  expected_shortfall?: number;
  weight_pct?: number;
}

interface ComponentESResponse {
  components?: ComponentESItem[];
  total_es?: number;
  insufficientPositions?: boolean;
}

interface DefenseLayer {
  name?: string;
  status?: "pass" | "warning" | "fail";
  message?: string;
  value?: number;
  threshold?: number;
  layer?: number;
}

interface DefenseStatusResponse {
  layers?: DefenseLayer[];
  overall_status?: "safe" | "warning" | "danger";
  timestamp?: string;
}

/* ── Fetcher ── */

const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

/* ── Backend raw shapes (as returned by routes/quant.py) ── */

interface RawVarMethod {
  var_95?: number;
  var_99?: number;
}

interface RawVarResponse {
  portfolio_value?: number;
  parametric?: RawVarMethod;
  historical?: RawVarMethod;
  methodology?: string;
  confidence_level?: number;
}

interface RawDrawdownResponse {
  max_drawdown_pct?: number;
  current_drawdown?: {
    pct?: number;
    start_date?: string;
    duration_days?: number;
    is_in_drawdown?: boolean;
  };
  recovery?: {
    longest_days?: number;
    average_days?: number;
  };
  top_drawdowns?: Array<{
    start?: string;
    end?: string;
    pct?: number;
  }>;
  ulcer_index?: number;
  calmar_ratio?: number;
  peak_value?: number;
  trough_value?: number;
}

interface RawStressScenario {
  name?: string;
  description?: string;
  portfolio_impact_pct?: number;
  portfolio_impact_usd?: number;
}

interface RawStressTestResponse {
  scenarios?: RawStressScenario[];
}

interface RawComponentESPosition {
  ticker?: string;
  weight_pct?: number;
  component_es_pct?: number;
  risk_contribution_pct?: number;
}

interface RawComponentESResponse {
  positions?: RawComponentESPosition[];
  portfolio_es_pct?: number;
  error?: string;
}

interface RawDefenseLayerItem {
  name?: string;
  message?: string;
  status?: string;
  value?: number;
  threshold?: number;
  layer?: number;
}

interface RawDefenseStatusResponse {
  defense_score?: number;
  status?: "GREEN" | "YELLOW" | "RED" | string;
  layers_triggered?: Array<RawDefenseLayerItem | string>;
  warnings?: Array<RawDefenseLayerItem | string>;
  risk_exposure?: number;
  regime_risk_level?: string;
  halt_trading?: boolean;
  timestamp?: string;
}

/* ── Adapters: raw backend shape → frontend shape ── */

function normalizeVar(raw: RawVarResponse | undefined): VaRResponse | undefined {
  if (!raw) return raw;
  const hist = raw.historical ?? {};
  const param = raw.parametric ?? {};
  return {
    var_95: hist.var_95 ?? param.var_95,
    var_99: hist.var_99 ?? param.var_99,
    method: raw.methodology,
    confidence_level: raw.confidence_level,
    portfolio_value: raw.portfolio_value,
  };
}

function normalizeDrawdown(
  raw: RawDrawdownResponse | undefined,
): DrawdownResponse | undefined {
  if (!raw) return raw;
  const current = raw.current_drawdown ?? {};
  const recovery = raw.recovery ?? {};
  const topEnd = raw.top_drawdowns?.[0]?.end;

  return {
    max_drawdown: raw.max_drawdown_pct,
    current_drawdown: current.pct,
    recovery_days: recovery.average_days ?? recovery.longest_days,
    drawdown_start: current.start_date,
    drawdown_end: topEnd,
    peak_value: raw.peak_value,
    trough_value: raw.trough_value,
  };
}

function normalizeStressTest(
  raw: RawStressTestResponse | undefined,
): StressTestResponse | undefined {
  if (!raw) return raw;
  return {
    scenarios: (raw.scenarios ?? []).map((s) => ({
      name: s.name,
      description: s.description,
      impact_pct: s.portfolio_impact_pct,
      portfolio_loss: s.portfolio_impact_usd,
    })),
  };
}

function normalizeComponentES(
  raw: RawComponentESResponse | undefined,
): ComponentESResponse | undefined {
  if (!raw) return raw;
  const positions = raw.positions ?? [];
  // Backend returns 400 with error if positions < 2, but in case it slips through
  const insufficientPositions = positions.length < 2;
  return {
    components: positions.map((p) => ({
      ticker: p.ticker,
      contribution_pct: p.risk_contribution_pct,
      weight_pct: p.weight_pct,
      expected_shortfall: p.component_es_pct,
    })),
    total_es: raw.portfolio_es_pct,
    insufficientPositions,
  };
}

function normalizeDefenseStatus(
  raw: RawDefenseStatusResponse | undefined,
): DefenseStatusResponse | undefined {
  if (!raw) return raw;

  const overall_status: "safe" | "warning" | "danger" =
    raw.status === "GREEN"
      ? "safe"
      : raw.status === "YELLOW"
        ? "warning"
        : raw.status === "RED"
          ? "danger"
          : "safe";

  const triggered = (raw.layers_triggered ?? []).map(
    (l): DefenseLayer => {
      if (typeof l === "string") {
        return { name: l, status: "fail", message: "" };
      }
      return {
        name: l.name ?? `Layer ${l.layer ?? "?"}`,
        status: "fail",
        message: l.message ?? "",
        value: l.value,
        threshold: l.threshold,
        layer: l.layer,
      };
    },
  );

  const warn = (raw.warnings ?? []).map(
    (w): DefenseLayer => {
      if (typeof w === "string") {
        return { name: "Warning", status: "warning", message: w };
      }
      return {
        name: w.name ?? "Warning",
        status: "warning",
        message: w.message ?? "",
        value: w.value,
        threshold: w.threshold,
        layer: w.layer,
      };
    },
  );

  return {
    layers: [...triggered, ...warn],
    overall_status,
    timestamp: raw.timestamp,
  };
}

/* ── Sub-components ── */

function MetricCard({
  label,
  value,
  icon,
  variant = "default",
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  variant?: "default" | "positive" | "negative" | "warning";
}) {
  const colorMap = {
    default: "text-slate-900",
    positive: "text-emerald-600",
    negative: "text-red-500",
    warning: "text-amber-500",
  };

  return (
    <div className="sp-card p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-slate-400">{icon}</span>
        <span className="text-xs font-medium text-slate-500">{label}</span>
      </div>
      <span className={cn("text-lg font-bold tabular-nums", colorMap[variant])}>
        {value}
      </span>
    </div>
  );
}

function SectionHeader({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-3">
      <h2 className="text-base font-bold text-slate-900">{title}</h2>
      {subtitle && (
        <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
      )}
    </div>
  );
}

function DefenseLayerCard({ layer }: { layer: DefenseLayer }) {
  const status = layer.status ?? "pass";
  const StatusIcon = status === "pass" ? CheckCircle : XCircle;
  const def = findLayerDefinition(layer.name);
  const displayTitle = def?.title ?? layer.name ?? `Layer ${layer.layer ?? "?"}`;

  return (
    <div className="sp-card p-4 flex items-start gap-3">
      <div
        className={cn(
          "mt-0.5 shrink-0",
          status === "pass" && "text-emerald-500",
          status === "warning" && "text-amber-500",
          status === "fail" && "text-red-500",
        )}
      >
        {status === "warning" ? (
          <AlertTriangle className="h-5 w-5" />
        ) : (
          <StatusIcon className="h-5 w-5" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-900 truncate">
            {displayTitle}
          </span>
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold shrink-0",
              status === "pass" && "signal-positive",
              status === "warning" && "signal-neutral",
              status === "fail" && "signal-negative",
            )}
          >
            {status === "pass" ? "통과" : status === "warning" ? "경고" : "트리거"}
          </span>
        </div>
        {def?.meaning && (
          <p className="text-xs text-slate-500 mt-1 leading-relaxed">
            {def.meaning}
          </p>
        )}
        {layer.message && (
          <p className="text-xs text-slate-600 mt-1 leading-relaxed">
            {layer.message}
          </p>
        )}
        {layer.value != null && layer.threshold != null && (
          <div className="flex items-center gap-3 mt-2">
            <span className="text-[11px] text-slate-400">
              현재값:{" "}
              <span className="font-medium tabular-nums text-slate-600">
                {typeof layer.value === "number" ? layer.value.toFixed(2) : layer.value}
              </span>
            </span>
            <span className="text-[11px] text-slate-400">
              기준값:{" "}
              <span className="font-medium tabular-nums text-slate-600">
                {typeof layer.threshold === "number" ? layer.threshold.toFixed(2) : layer.threshold}
              </span>
            </span>
          </div>
        )}
        {(status === "fail" || status === "warning") && def?.triggerAction && (
          <div className="mt-2 flex items-start gap-1.5 rounded-md bg-amber-50 border border-amber-100 px-2 py-1.5">
            <Lightbulb className="h-3.5 w-3.5 text-amber-600 mt-0.5 shrink-0" />
            <p className="text-[11px] leading-relaxed text-amber-800">
              <span className="font-semibold">권장 행동: </span>
              {def.triggerAction}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Reusable guide block: explains a metric's meaning + how to act ── */

function MetricGuide({
  why,
  how,
}: {
  why: string;
  how: string;
}) {
  return (
    <div className="mt-3 rounded-lg bg-slate-50 border border-slate-100 px-3 py-2 space-y-1">
      <p className="text-[11px] leading-relaxed text-slate-600">
        <span className="font-semibold text-slate-700">왜? </span>
        {why}
      </p>
      <p className="text-[11px] leading-relaxed text-slate-600">
        <span className="font-semibold text-slate-700">어떻게? </span>
        {how}
      </p>
    </div>
  );
}

function OverallStatusBadge({
  status,
}: {
  status: "safe" | "warning" | "danger";
}) {
  const config = {
    safe: {
      label: "모든 방어 레이어 정상",
      bg: "bg-emerald-50",
      border: "border-emerald-200",
      text: "text-emerald-700",
      icon: <CheckCircle className="h-4 w-4" />,
    },
    warning: {
      label: "경고 감지됨",
      bg: "bg-amber-50",
      border: "border-amber-200",
      text: "text-amber-700",
      icon: <AlertTriangle className="h-4 w-4" />,
    },
    danger: {
      label: "리스크 한도 초과",
      bg: "bg-red-50",
      border: "border-red-200",
      text: "text-red-700",
      icon: <XCircle className="h-4 w-4" />,
    },
  };

  const c = config[status] ?? config.safe;

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1.5",
        c.bg,
        c.border,
        c.text,
      )}
    >
      {c.icon}
      <span className="text-xs font-semibold">{c.label}</span>
    </div>
  );
}

/* ── Stress Test Bar ── */

function StressBar({ scenario }: { scenario: StressScenario }) {
  const impact = scenario.impact_pct ?? 0;
  const absImpact = Math.abs(impact);
  const barWidth = Math.min(absImpact * 4, 100);

  return (
    <div className="py-3 first:pt-0 last:pb-0">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm font-medium text-slate-700 truncate pr-3">
          {scenario.name ?? "알 수 없는 시나리오"}
        </span>
        <span
          className={cn(
            "text-sm font-bold tabular-nums shrink-0",
            impact <= -10
              ? "text-red-500"
              : impact < 0
                ? "text-amber-500"
                : "text-emerald-600",
          )}
        >
          {fmtPct(impact)}
        </span>
      </div>
      <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500",
            impact <= -10
              ? "bg-red-400"
              : impact < 0
                ? "bg-amber-400"
                : "bg-emerald-400",
          )}
          style={{ width: `${barWidth}%` }}
        />
      </div>
      {scenario.description && (
        <p className="text-[11px] text-slate-400 mt-1">{scenario.description}</p>
      )}
    </div>
  );
}

/* ── Component ES Row ── */

function ESRow({ item }: { item: ComponentESItem }) {
  const contribution = item.contribution_pct ?? 0;
  const barWidth = Math.min(Math.abs(contribution) * 5, 100);

  return (
    <div className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
      <span className="text-sm font-bold text-slate-900 w-16 shrink-0 tabular-nums">
        {item.ticker ?? "???"}
      </span>
      <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
        <div
          className="h-full rounded-full bg-red-400 transition-all duration-500"
          style={{ width: `${barWidth}%` }}
        />
      </div>
      <span className="text-sm font-semibold text-red-500 tabular-nums w-16 text-right shrink-0">
        {fmtPct(contribution)}
      </span>
    </div>
  );
}

/* ── Page ── */

export default function RiskPage() {
  /* ── Data hooks ── */
  const { data: portfolio, isLoading: loadingPortfolio } = usePortfolio();
  const { data: analytics, isLoading: loadingAnalytics } = useAnalytics();

  const { data: rawVarData, isLoading: loadingVar } = useSWR<RawVarResponse>(
    API.risk.var,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 120_000 },
  );

  const { data: rawDrawdownData, isLoading: loadingDrawdown } =
    useSWR<RawDrawdownResponse>(API.risk.drawdown, fetcher, {
      revalidateOnFocus: false,
      dedupingInterval: 120_000,
    });

  const { data: rawStressData, isLoading: loadingStress } =
    useSWR<RawStressTestResponse>(API.risk.stressTest, fetcher, {
      revalidateOnFocus: false,
      dedupingInterval: 300_000,
    });

  const { data: rawEsData, isLoading: loadingES, error: esError } =
    useSWR<RawComponentESResponse>(API.risk.componentEs, fetcher, {
      revalidateOnFocus: false,
      dedupingInterval: 120_000,
    });

  const { data: rawDefenseData, isLoading: loadingDefense } =
    useSWR<RawDefenseStatusResponse>(API.risk.defenseStatus, fetcher, {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
    });

  /* ── Normalize backend responses to frontend shape ── */
  const varData = normalizeVar(rawVarData);
  const drawdownData = normalizeDrawdown(rawDrawdownData);
  const stressData = normalizeStressTest(rawStressData);
  const esData = normalizeComponentES(rawEsData);
  const defenseData = normalizeDefenseStatus(rawDefenseData);

  // Backend returns 400 when positions < 2 for component-es → esError will be set
  const esInsufficientPositions =
    esError != null || esData?.insufficientPositions === true;

  /* ── Derived values ── */
  const sharpe = analytics?.sharpe_ratio;
  const maxDD = analytics?.max_drawdown_pct;
  const annVol = analytics?.ann_vol_pct;

  const passCount =
    defenseData?.layers?.filter((l) => l.status === "pass").length ?? 0;
  const totalLayers = defenseData?.layers?.length ?? 7;

  const positionCount = portfolio?.positions?.length ?? 0;
  const showEmpty = !loadingPortfolio && positionCount === 0;

  return (
    <ErrorBoundary>
      <div className="mx-auto max-w-3xl space-y-6">
        {/* ── Header ── */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900">
              리스크 대시보드
            </h1>
            <p className="text-sm text-slate-500 mt-0.5">
              포트폴리오 리스크 지표 및 방어 상태
            </p>
          </div>
          {!showEmpty && !loadingDefense && defenseData?.overall_status && (
            <OverallStatusBadge status={defenseData.overall_status} />
          )}
        </div>

        {/* ── Empty state: no positions ── */}
        {showEmpty ? (
          <EmptyState
            icon={<Shield className="h-8 w-8" />}
            title="분석할 포지션이 없습니다"
            description="포지션을 추가하면 리스크 지표, VaR, 최대 낙폭, 7단계 방어 상태를 확인할 수 있습니다."
            action={{ label: "포지션 추가", href: "/portfolio" }}
          />
        ) : (
          <>
        {/* ── Disclaimer ── */}
        <DisclaimerBanner type="signal" />

        {/* ── About Risk Analysis (header guide) ── */}
        <div className="sp-card p-5 border-l-4 border-l-blue-500">
          <div className="flex items-start gap-3">
            <Info className="h-5 w-5 text-blue-600 shrink-0 mt-0.5" />
            <div className="space-y-2">
              <h2 className="text-sm font-bold text-slate-900">
                리스크 분석이란?
              </h2>
              <p className="text-xs text-slate-600 leading-relaxed">
                PivoxQuant는 골드만삭스 PM이 사용하는 7가지 리스크 지표로
                포트폴리오의 잠재 손실을 정량 측정합니다. 각 지표가 위험 수준이면
                <span className="font-semibold text-slate-800"> 포지션 비중 조정 / 헤지 / 손절 시점</span>을
                직접 판단하는 데 활용하세요.
              </p>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                미국·한국 종목의 시가는 모두 KRW로 환산해 비중을 계산하므로,
                양 시장 종목이 동일 기준으로 비교됩니다.
              </p>
            </div>
          </div>
        </div>

        {/* ── Portfolio Risk Summary (from analytics) ── */}
        {loadingAnalytics ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MetricCard
              label="샤프 비율"
              value={sharpe != null ? sharpe.toFixed(2) : "\u2014"}
              icon={<BarChart3 className="h-4 w-4" />}
              variant={
                sharpe == null
                  ? "default"
                  : sharpe >= 1
                    ? "positive"
                    : sharpe >= 0.5
                      ? "warning"
                      : "negative"
              }
            />
            <MetricCard
              label="최대 낙폭"
              value={maxDD != null ? fmtPct(-Math.abs(maxDD)) : "\u2014"}
              icon={<TrendingDown className="h-4 w-4" />}
              variant={
                maxDD == null
                  ? "default"
                  : Math.abs(maxDD) <= 10
                    ? "positive"
                    : Math.abs(maxDD) <= 20
                      ? "warning"
                      : "negative"
              }
            />
            <MetricCard
              label="연환산 변동성"
              value={annVol != null ? fmtPct(annVol) : "\u2014"}
              icon={<Activity className="h-4 w-4" />}
              variant={
                annVol == null
                  ? "default"
                  : annVol <= 15
                    ? "positive"
                    : annVol <= 25
                      ? "warning"
                      : "negative"
              }
            />
            <MetricCard
              label="방어"
              value={`${passCount}/${totalLayers}`}
              icon={<Shield className="h-4 w-4" />}
              variant={
                passCount === totalLayers
                  ? "positive"
                  : passCount >= totalLayers * 0.7
                    ? "warning"
                    : "negative"
              }
            />
          </div>
        )}

        {/* ── Value at Risk (VaR) ── */}
        <div className="sp-card p-5">
          <SectionHeader
            title="Value at Risk (VaR)"
            subtitle={
              varData?.method
                ? `방법론: ${varData.method}`
                : "예상 최대 손실 (95%/99% 신뢰구간)"
            }
          />

          {loadingVar ? (
            <div className="grid grid-cols-2 gap-3">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : varData?.var_95 == null && varData?.var_99 == null ? (
            <p className="text-sm text-slate-400 py-2">
              VaR 데이터 없음. 포지션을 추가하면 리스크 추정값을 확인할 수 있습니다.
            </p>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-slate-50 border border-slate-100 p-4">
                <p className="text-xs font-medium text-slate-500 mb-1">
                  VaR (95%)
                </p>
                <p className="text-xl font-bold tabular-nums text-red-500">
                  {varData?.var_95 != null
                    ? fmtUsd(Math.abs(varData.var_95))
                    : "\u2014"}
                </p>
                <p className="text-[11px] text-slate-400 mt-1">
                  1-day potential loss
                </p>
              </div>
              <div className="rounded-xl bg-slate-50 border border-slate-100 p-4">
                <p className="text-xs font-medium text-slate-500 mb-1">
                  VaR (99%)
                </p>
                <p className="text-xl font-bold tabular-nums text-red-500">
                  {varData?.var_99 != null
                    ? fmtUsd(Math.abs(varData.var_99))
                    : "\u2014"}
                </p>
                <p className="text-[11px] text-slate-400 mt-1">
                  1-day extreme loss
                </p>
              </div>
            </div>
          )}
          <MetricGuide
            why="95% 확률로 하루 최대 이 금액까지 손실이 날 수 있다는 의미입니다. 나머지 5% 확률의 극단 상황에는 더 클 수 있음."
            how="이 금액이 감당 가능한 수준보다 크면 비중을 줄이거나 변동성이 낮은 종목으로 리밸런싱을 고려하세요."
          />
        </div>

        {/* ── Drawdown Analysis ── */}
        <div className="sp-card p-5">
          <SectionHeader
            title="최대 낙폭 분석"
            subtitle="고점 대비 최대 하락 지표"
          />

          {loadingDrawdown ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          ) : drawdownData?.max_drawdown == null &&
            drawdownData?.current_drawdown == null ? (
            <p className="text-sm text-slate-400 py-2">
              Drawdown data is not available.
            </p>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div className="rounded-xl bg-slate-50 border border-slate-100 p-4">
                <p className="text-xs font-medium text-slate-500 mb-1">
                  Max Drawdown
                </p>
                <p
                  className={cn(
                    "text-xl font-bold tabular-nums",
                    Math.abs(drawdownData?.max_drawdown ?? 0) > 20
                      ? "text-red-500"
                      : "text-amber-500",
                  )}
                >
                  {drawdownData?.max_drawdown != null
                    ? fmtPct(-Math.abs(drawdownData.max_drawdown))
                    : "\u2014"}
                </p>
              </div>
              <div className="rounded-xl bg-slate-50 border border-slate-100 p-4">
                <p className="text-xs font-medium text-slate-500 mb-1">
                  Current Drawdown
                </p>
                <p
                  className={cn(
                    "text-xl font-bold tabular-nums",
                    Math.abs(drawdownData?.current_drawdown ?? 0) > 10
                      ? "text-red-500"
                      : Math.abs(drawdownData?.current_drawdown ?? 0) > 5
                        ? "text-amber-500"
                        : "text-emerald-600",
                  )}
                >
                  {drawdownData?.current_drawdown != null
                    ? fmtPct(-Math.abs(drawdownData.current_drawdown))
                    : "\u2014"}
                </p>
              </div>
              <div className="rounded-xl bg-slate-50 border border-slate-100 p-4 col-span-2 sm:col-span-1">
                <p className="text-xs font-medium text-slate-500 mb-1">
                  Recovery Days
                </p>
                <p className="text-xl font-bold tabular-nums text-slate-900">
                  {drawdownData?.recovery_days != null
                    ? `${drawdownData.recovery_days}d`
                    : "\u2014"}
                </p>
                {drawdownData?.recovery_days != null &&
                  drawdownData.recovery_days > 0 && (
                    <p className="text-[11px] text-slate-400 mt-1">
                      Days to recover from trough
                    </p>
                  )}
              </div>
            </div>
          )}
          <MetricGuide
            why="지금 고점 대비 얼마나 빠진 상태인지 보여줍니다. 큰 낙폭은 회복까지 오랜 시간이 걸려 복리 수익률을 갉아먹습니다."
            how="현재 낙폭이 크다면 추가 매수 시점일 수도, 손절 시점일 수도 있습니다. 종목 펀더멘털을 다시 점검하세요."
          />
        </div>

        {/* ── Stress Test Results ── */}
        <div className="sp-card p-5">
          <SectionHeader
            title="스트레스 테스트 시나리오"
            subtitle="주요 시나리오별 포트폴리오 예상 영향"
          />

          {loadingStress ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !stressData?.scenarios?.length ? (
            <p className="text-sm text-slate-400 py-2">
              No stress test scenarios available.
            </p>
          ) : (
            <div className="divide-y divide-slate-50">
              {stressData.scenarios.map((scenario, idx) => (
                <StressBar key={scenario.name ?? idx} scenario={scenario} />
              ))}
            </div>
          )}
          <MetricGuide
            why="과거 위기(2008 금융위기, 2020 코로나, 금리 +1% 등) 시나리오가 다시 와도 포트폴리오가 얼마나 손실 볼지 시뮬레이션."
            how="감당하기 힘든 시나리오 손실이 보이면 해당 위기 유형에 약한 종목 비중을 줄이고 헤지 자산(달러, 금)을 추가하세요."
          />
        </div>

        {/* ── Component Expected Shortfall ── */}
        <div className="sp-card p-5">
          <SectionHeader
            title="종목별 예상 손실 기여도"
            subtitle="포트폴리오 꼬리 리스크에 대한 종목별 기여도"
          />

          {loadingES ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : esInsufficientPositions ? (
            <p className="text-sm text-slate-400 py-2">
              포지션 2개 이상 필요. 리스크 기여도 분석은 분산 효과 측정을 위해 최소 2개 포지션이 필요합니다.
            </p>
          ) : !esData?.components?.length ? (
            <p className="text-sm text-slate-400 py-2">
              기여도 데이터가 없습니다. 여러 포지션을 추가하면 리스크 기여도를 확인할 수 있습니다.
            </p>
          ) : (
            <>
              {esData.total_es != null && (
                <div className="mb-4 flex items-center gap-2">
                  <span className="text-xs font-medium text-slate-500">
                    포트폴리오 ES:
                  </span>
                  <span className="text-sm font-bold tabular-nums text-red-500">
                    {fmtUsd(Math.abs(esData.total_es))}
                  </span>
                </div>
              )}
              <div className="divide-y divide-slate-50">
                {[...esData.components]
                  .sort(
                    (a, b) =>
                      Math.abs(b.contribution_pct ?? 0) -
                      Math.abs(a.contribution_pct ?? 0),
                  )
                  .map((item, idx) => (
                    <ESRow key={item.ticker ?? idx} item={item} />
                  ))}
              </div>
            </>
          )}
          <MetricGuide
            why="포트폴리오 꼬리 손실(극단 시장 상황 손실) 중 어떤 종목이 가장 많이 기여하는지 분해. 비중 큰 종목 ≠ 위험 큰 종목."
            how="기여도 1·2위 종목이 비중 1·2위와 다르면 비중 조정 우선 후보. 한 종목이 전체 위험의 30% 이상이면 분산이 부족한 상태."
          />
        </div>

        {/* ── 7-Layer Risk Defense Status ── */}
        <div>
          <SectionHeader
            title="7단계 리스크 방어 상태"
            subtitle="자동화된 리스크 관리 방어 레이어"
          />

          {/* Layer catalog — always shown so users know what defenses exist */}
          <div className="sp-card p-5 mb-3 bg-slate-50/50">
            <div className="flex items-start gap-2 mb-3">
              <Info className="h-4 w-4 text-slate-500 shrink-0 mt-0.5" />
              <p className="text-xs text-slate-600 leading-relaxed">
                <span className="font-semibold text-slate-700">7개 방어 레이어란? </span>
                포트폴리오를 위협하는 7가지 위험 요인을 실시간 감시.
                트리거된 레이어가 있으면 아래 권장 행동을 참고해 직접 대응 결정을 내리세요.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {LAYER_DEFINITIONS.map((d) => (
                <div
                  key={d.no}
                  className="flex items-start gap-2 rounded-md bg-white border border-slate-100 px-3 py-2"
                >
                  <span className="text-[10px] font-bold text-slate-400 tabular-nums shrink-0 mt-0.5">
                    {String(d.no).padStart(2, "0")}
                  </span>
                  <div className="min-w-0">
                    <p className="text-[11px] font-semibold text-slate-800 leading-snug">
                      {d.title}
                    </p>
                    <p className="text-[10px] text-slate-500 leading-snug mt-0.5">
                      {d.meaning}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {loadingDefense ? (
            <div className="space-y-3">
              {Array.from({ length: 7 }).map((_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          ) : !defenseData?.layers?.length ? (
            <div className="sp-card p-5 bg-emerald-50/40 border-emerald-100">
              <div className="flex items-start gap-2">
                <CheckCircle className="h-5 w-5 text-emerald-500 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-emerald-800">
                    트리거된 방어 레이어 없음
                  </p>
                  <p className="text-xs text-emerald-700 mt-1 leading-relaxed">
                    현재 7개 방어 레이어 모두 정상 범위입니다. 위 카탈로그의 각 레이어 설명을 참고해
                    어떤 위험을 감시하고 있는지 확인하세요. 위험 신호가 감지되면 이 영역에 자동 표시됩니다.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2">
                <p className="text-xs text-amber-900 leading-relaxed">
                  <span className="font-semibold">{defenseData.layers.length}개 레이어가 트리거</span>되었습니다.
                  각 카드의 권장 행동을 참고해 비중 조정·헤지·매매 보류 등을 직접 결정하세요.
                  PivoxQuant는 자동 매매를 실행하지 않습니다 (read-only).
                </p>
              </div>
              {defenseData.layers.map((layer, idx) => (
                <DefenseLayerCard
                  key={layer.name ?? idx}
                  layer={{ ...layer, layer: layer.layer ?? idx + 1 }}
                />
              ))}
            </div>
          )}
        </div>
          </>
        )}
      </div>
    </ErrorBoundary>
  );
}
