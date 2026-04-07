"use client";

import useSWR from "swr";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { signalColor } from "@/lib/format";

interface Alert {
  id: number;
  ticker: string;
  message: string;
  signal: string;
  score: number;
  rec_shares: number;
  rec_investment: number;
  created_at: string;
  is_read: boolean;
}

const fetcher = (url: string) => fetch(url, { credentials: "include" }).then((r) => r.json());

export default function AlertsPage() {
  const { data } = useSWR<{ alerts: Alert[]; unread: number }>("/api/alerts", fetcher);

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
        <h1 className="text-lg font-semibold text-foreground">Alerts</h1>
        {data.unread > 0 && (
          <Badge className="bg-primary text-xs">{data.unread} unread</Badge>
        )}
      </div>

      {data.alerts.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">No alerts</p>
      ) : (
        <div className="space-y-2">
          {data.alerts.map((a) => (
            <Card
              key={a.id}
              className={`flex items-start gap-4 border-border p-4 ${!a.is_read ? "bg-primary/5" : "bg-card"}`}
            >
              <Badge variant="outline" className={`mt-0.5 shrink-0 text-[10px] font-semibold ${signalColor(a.signal)}`}>
                {a.signal}
              </Badge>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-foreground">{a.ticker}</span>
                  <span className="text-[10px] text-muted-foreground">
                    {new Date(a.created_at).toLocaleDateString()}
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{a.message}</p>
                {a.rec_shares > 0 && (
                  <p className="mt-1 text-[10px] text-success">
                    Rec: {a.rec_shares} shares (${a.rec_investment.toFixed(0)})
                  </p>
                )}
              </div>
              <span className="shrink-0 font-mono text-xs text-muted-foreground">{(a.score ?? 0).toFixed(0)}</span>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
