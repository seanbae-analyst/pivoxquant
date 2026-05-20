"use client";

/**
 * Zone3 DOSSIER — News, grouped by day with KR-convention sentiment chips.
 *
 * P0 resilience: owns its own loading / failure boundary. News failing does
 * not affect any other section.
 */

import { ExternalLink } from "lucide-react";
import { SectionHeading, EmptyNote, LoadFailure } from "./shared";
import { classifyNewsSentiment, bucketNewsByDay } from "./types";
import type { NewsItem } from "./types";

export function NewsFeed({
  news,
  loading,
  error,
  onRetry,
  retrying,
}: {
  news: NewsItem[] | undefined;
  loading: boolean;
  error: boolean;
  onRetry: () => void;
  retrying: boolean;
}) {
  const groups = news ? bucketNewsByDay(news.slice(0, 12)) : [];

  return (
    <section>
      <div className="mb-5">
        <SectionHeading eyebrow="Recent coverage" title="News feed" />
      </div>

      {error ? (
        <LoadFailure label="뉴스를 불러오지 못했습니다." onRetry={onRetry} retrying={retrying} />
      ) : loading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-16 rounded-sm pq-skeleton-dark" />
          ))}
        </div>
      ) : !groups.length ? (
        <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-8 rounded-sm text-center">
          <EmptyNote>
            No headlines observed in the last 14 days — re-checking every 2
            minutes.
          </EmptyNote>
        </div>
      ) : (
        <div className="space-y-6">
          {groups.map((group) => (
            <div key={group.label}>
              <div className="pq-news-date-header">{group.label}</div>
              <ul className="space-y-2">
                {group.items.map((n, i) => {
                  const sent = classifyNewsSentiment(n.title);
                  const chipClass =
                    sent === "pos"
                      ? "pq-sent-chip pq-sent-chip--pos"
                      : sent === "neg"
                        ? "pq-sent-chip pq-sent-chip--neg"
                        : "pq-sent-chip pq-sent-chip--neu";
                  const chipLabel =
                    sent === "pos" ? "Positive" : sent === "neg" ? "Negative" : "Neutral";
                  return (
                    <li key={`${group.label}-${i}`}>
                      <a
                        href={n.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group block bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-4 rounded-sm hover:border-[var(--pq-bronze)] hover:bg-[rgba(139,111,71,0.04)] transition-all"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0 flex-1">
                            <p className="font-serif text-pq-lead leading-snug text-[var(--pq-ivory)] group-hover:text-[var(--pq-bronze-light)] transition-colors line-clamp-2">
                              {n.title}
                            </p>
                            <div className="mt-2 flex items-center gap-2 flex-wrap">
                              <span className={chipClass}>{chipLabel}</span>
                              <span className="text-pq-mono-xs text-[var(--pq-ivory-faint)] font-sans tracking-tight">
                                {n.source}
                              </span>
                              <span className="text-pq-mono-xs text-[var(--pq-ivory-faint)]">
                                ·
                              </span>
                              <span className="text-pq-mono-xs text-[var(--pq-ivory-faint)] font-sans tabular-nums tracking-tight">
                                {n.published}
                              </span>
                            </div>
                          </div>
                          <ExternalLink className="h-3.5 w-3.5 shrink-0 mt-1 text-[var(--pq-ivory-faint)] group-hover:text-[var(--pq-bronze)]" />
                        </div>
                      </a>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
