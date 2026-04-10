"use client";

import useSWR from "swr";
import { API } from "@/lib/endpoints";
import { Newspaper, TrendingUp, TrendingDown, ExternalLink } from "lucide-react";

interface Story { title: string; summary: string; source: string; link: string; published: string; sentiment: string; }
interface MorningBrief { date: string; market_mood: string; mood_color: string; bull_count: number; bear_count: number; stories: Story[]; gs_view: { bias: string; bias_note: string; themes: string[] }; }
const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function MorningBriefPage() {
  const { data } = useSWR<MorningBrief>(API.market.morningBrief, fetcher);
  if (!data) return <div className="flex items-center justify-center py-20"><span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" /><span className="text-slate-500 text-[12px]">Loading...</span></div>;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div><h1 className="text-2xl font-bold tracking-tight text-slate-900">Morning Brief</h1><p className="mt-1 text-[13px] text-slate-500">{data.date}</p></div>
        <span className="glass-surface rounded-full px-4 py-1.5 text-sm font-semibold text-slate-700">{data.market_mood}</span>
      </div>

      {/* GS View Hero — bezel card */}
      <div className="bezel-card">
        <div className="bezel-card-inner">
          <div className="flex items-center gap-3 mb-4">
            <span className={`rounded-md px-3 py-1.5 text-[10px] font-bold ${data.gs_view.bias === "BULLISH" ? "bg-emerald-500/15 text-emerald-600" : data.gs_view.bias === "BEARISH" ? "bg-red-500/15 text-red-600" : "bg-amber-500/15 text-amber-600"}`}>{data.gs_view.bias}</span>
          </div>
          <p className="text-[15px] text-slate-700 leading-relaxed">{data.gs_view.bias_note}</p>
          <div className="mt-6 flex gap-6">
            <div className="flex items-center gap-2"><TrendingUp size={16} className="text-emerald-600" /><span className="text-sm font-semibold text-emerald-600">{data.bull_count} Bullish</span></div>
            <div className="flex items-center gap-2"><TrendingDown size={16} className="text-red-600" /><span className="text-sm font-semibold text-red-600">{data.bear_count} Bearish</span></div>
          </div>
        </div>
      </div>

      <div>
        <h2 className="mb-4 text-lg font-bold text-slate-900">Top Stories</h2>
        {data.stories.length === 0 ? (
          <div className="glass-surface rounded-2xl py-16 text-center"><Newspaper className="mx-auto h-10 w-10 text-slate-300" /><p className="mt-3 text-[13px] text-slate-500">No stories available</p></div>
        ) : (
          <div className="space-y-2">
            {data.stories.map((s, i) => (
              <a key={i} href={s.link} target="_blank" rel="noopener noreferrer" className="group flex items-start gap-5 glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
                <div className="flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900 group-hover:text-cyan-600 spring-transition transition-colors duration-300">{s.title}</p>
                    <ExternalLink size={14} className="mt-0.5 shrink-0 text-slate-400 group-hover:text-cyan-600 spring-transition transition-colors duration-300" />
                  </div>
                  <p className="mt-2 text-[13px] leading-relaxed text-slate-500 line-clamp-2">{s.summary}</p>
                  <div className="mt-3 flex items-center gap-3">
                    <span className="text-[11px] font-medium text-slate-500">{s.source}</span>
                    <span className="text-[11px] text-slate-400">{new Date(s.published).toLocaleDateString()}</span>
                    <span className={`rounded-md px-2 py-0.5 text-[9px] font-bold ${s.sentiment === "bullish" ? "bg-emerald-500/15 text-emerald-600" : s.sentiment === "bearish" ? "bg-red-500/15 text-red-600" : "bg-slate-100 text-slate-500"}`}>{s.sentiment}</span>
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
