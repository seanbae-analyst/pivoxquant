"use client";

import useSWR from "swr";

interface MarketStatus {
  status: "regular" | "pre_market" | "after_hours" | "closed";
  label: string;
  next_event: string;
  next_event_kst: string;
  tradable: boolean;
}

interface StatusResponse {
  us: MarketStatus;
  kr: MarketStatus;
}

const fetcher = (url: string): Promise<StatusResponse> =>
  fetch(url, { credentials: "include" }).then((r) => r.json());

const COLORS: Record<MarketStatus["status"], string> = {
  regular: "bg-emerald-100 text-emerald-700 border-emerald-200",
  pre_market: "bg-amber-100 text-amber-700 border-amber-200",
  after_hours: "bg-amber-100 text-amber-700 border-amber-200",
  closed: "bg-slate-100 text-slate-500 border-slate-200",
};

const DOTS: Record<MarketStatus["status"], string> = {
  regular: "bg-emerald-500",
  pre_market: "bg-amber-500",
  after_hours: "bg-amber-500",
  closed: "bg-slate-400",
};

export function MarketStatusBadge() {
  const { data } = useSWR<StatusResponse>("/api/market/status", fetcher, {
    refreshInterval: 60000,
    revalidateOnFocus: false,
  });

  if (!data) return null;

  return (
    <div className="flex flex-wrap items-center gap-3">
      <SingleBadge name="🇺🇸 미국장" s={data.us} />
      <SingleBadge name="🇰🇷 한국장" s={data.kr} />
    </div>
  );
}

function SingleBadge({ name, s }: { name: string; s: MarketStatus }) {
  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${COLORS[s.status]}`}
    >
      <span className={`h-2 w-2 rounded-full ${DOTS[s.status]}`} />
      <span>{name}</span>
      <span className="font-bold">{s.label}</span>
      <span className="text-slate-400">·</span>
      <span className="font-normal">
        {s.next_event} {s.next_event_kst} KST
      </span>
    </div>
  );
}
