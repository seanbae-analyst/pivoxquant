"use client";

import useSWR from "swr";
import { API } from "@/lib/endpoints";
import { Newspaper, TrendingUp, TrendingDown, ExternalLink } from "lucide-react";

interface Story { title: string; summary: string; source: string; link: string; published: string; sentiment: string; }
interface MorningBrief { date: string; market_mood: string; mood_color: string; bull_count: number; bear_count: number; stories: Story[]; gs_view: { bias: string; bias_note: string; themes: string[] }; }
const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function MorningBriefPage() {
  const { data } = useSWR<MorningBrief>(API.market.morningBrief, fetcher);
  if (!data) return <div className="flex items-center justify-center py-20"><span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" /><span className="text-zinc-600 text-[12px]">Loading...</span></div>;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div><h1 className="text-2xl font-bold tracking-tight text-white">Morning Brief</h1><p className="mt-1 text-[13px] text-zinc-600">{data.date}</p></div>
        <span className="glass-surface rounded-full px-4 py-1.5 text-sm font-semibold text-zinc-300">{data.market_mood}</span>
      </div>

      {/* GS View Hero — bezel card */}
      <div className="bezel-card">
        <div className="bezel-card-inner">
          <div className="flex items-center gap-3 mb-4">
            <span className={`rounded-md px-3 py-1.5 text-[10px] font-bold ${data.gs_view.bias === "BULLISH" ? "bg-emerald-500/15 text-emerald-400" : data.gs_view.bias === "BEARISH" ? "bg-red-500/15 text-red-400" : "bg-amber-500/15 text-amber-400"}`}>{data.gs_view.bias}</span>
          </div>
          <p className="text-[15px] text-zinc-300 leading-relaxed">{data.gs_view.bias_note}</p>
          <div className="mt-6 flex gap-6">
            <div className="flex items-center gap-2"><TrendingUp size={16} className="text-emerald-400" /><span className="text-sm font-semibold text-emerald-400">{data.bull_count} Bullish</span></div>
            <div className="flex items-center gap-2"><TrendingDown size={16} className="text-red-400" /><span className="text-sm font-semibold text-red-400">{data.bear_count} Bearish</span></div>
          </div>
        </div>
      </div>

      <div>
        <h2 className="mb-4 text-lg font-bold text-white">Top Stories</h2>
        {data.stories.length === 0 ? (
          <div className="glass-surface rounded-2xl py-16 text-center"><Newspaper className="mx-auto h-10 w-10 text-zinc-700" /><p className="mt-3 text-[13px] text-zinc-600">No stories available</p></div>
        ) : (
          <div className="space-y-2">
            {data.stories.map((s, i) => (
              <a key={i} href={s.link} target="_blank" rel="noopener noreferrer" className="group flex items-start gap-5 glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
                <div className="flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-semibold text-white group-hover:text-cyan-400 spring-transition transition-colors duration-300">{s.title}</p>
                    <ExternalLink size={14} className="mt-0.5 shrink-0 text-zinc-700 group-hover:text-cyan-400 spring-transition transition-colors duration-300" />
                  </div>
                  <p className="mt-2 text-[13px] leading-relaxed text-zinc-400 line-clamp-2">{s.summary}</p>
                  <div className="mt-3 flex items-center gap-3">
                    <span className="text-[11px] font-medium text-zinc-500">{s.source}</span>
                    <span className="text-[11px] text-zinc-700">{new Date(s.published).toLocaleDateString()}</span>
                    <span className={`rounded-md px-2 py-0.5 text-[9px] font-bold ${s.sentiment === "bullish" ? "bg-emerald-500/15 text-emerald-400" : s.sentiment === "bearish" ? "bg-red-500/15 text-red-400" : "bg-white/5 text-zinc-500"}`}>{s.sentiment}</span>
                  </div>
                </div>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
