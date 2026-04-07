"use client";

import useSWR from "swr";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface Story {
  title: string;
  summary: string;
  source: string;
  link: string;
  published: string;
  sentiment: string;
}

interface MorningBrief {
  date: string;
  market_mood: string;
  mood_color: string;
  bull_count: number;
  bear_count: number;
  stories: Story[];
  gs_view: { bias: string; bias_note: string; themes: string[] };
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function MorningBriefPage() {
  const { data } = useSWR<MorningBrief>("/api/morning-brief", fetcher);

  if (!data) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Morning Brief</h1>
          <p className="text-sm text-muted-foreground">{data.date}</p>
        </div>
        <Badge variant="outline" className="text-sm">{data.market_mood}</Badge>
      </div>

      {/* GS View */}
      <Card className="border-border bg-card p-5">
        <div className="flex items-center gap-3">
          <Badge
            variant="outline"
            className={`text-xs font-semibold ${
              data.gs_view.bias === "BULLISH"
                ? "border-success/30 bg-success/10 text-success"
                : data.gs_view.bias === "BEARISH"
                  ? "border-destructive/30 bg-destructive/10 text-destructive"
                  : "border-warning/30 bg-warning/10 text-warning"
            }`}
          >
            {data.gs_view.bias}
          </Badge>
          <p className="text-sm text-muted-foreground">{data.gs_view.bias_note}</p>
        </div>
      </Card>

      {/* Sentiment summary */}
      <div className="flex gap-4 text-sm">
        <span className="text-success">{data.bull_count} Bullish</span>
        <span className="text-destructive">{data.bear_count} Bearish</span>
      </div>

      {/* Stories */}
      <div className="space-y-3">
        {data.stories.map((s, i) => (
          <Card key={i} className="border-border bg-card p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <p className="text-sm font-medium text-foreground">{s.title}</p>
                <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{s.summary}</p>
                <div className="mt-2 flex items-center gap-2 text-[10px] text-muted-foreground">
                  <span>{s.source}</span>
                  <span>{new Date(s.published).toLocaleDateString()}</span>
                </div>
              </div>
              <Badge
                variant="outline"
                className={`shrink-0 text-[9px] ${
                  s.sentiment === "bullish"
                    ? "border-success/30 text-success"
                    : s.sentiment === "bearish"
                      ? "border-destructive/30 text-destructive"
                      : "border-border text-muted-foreground"
                }`}
              >
                {s.sentiment}
              </Badge>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
