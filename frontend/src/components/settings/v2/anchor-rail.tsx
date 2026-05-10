"use client";

/**
 * <AnchorRail /> — sticky 2-col anchor rail for /settings v2.
 *
 * 5 sections (A·Identity / B·Brokers / C·Notifications / D·Subscription /
 * E·Privacy). Active state is computed via IntersectionObserver against the
 * `id` of each section so the rail stays in sync with scroll.
 */

import * as React from "react";

interface Item {
  id: string;
  letter: string;
  label: string;
}

const ITEMS: Item[] = [
  { id: "section-a", letter: "A", label: "Identity" },
  { id: "section-b", letter: "B", label: "Brokers" },
  { id: "section-c", letter: "C", label: "Notifications" },
  { id: "section-d", letter: "D", label: "Subscription" },
  { id: "section-e", letter: "E", label: "Privacy" },
];

export function AnchorRail() {
  const [activeId, setActiveId] = React.useState<string>(ITEMS[0]?.id ?? "");

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const els = ITEMS.map((it) => document.getElementById(it.id)).filter(
      (el): el is HTMLElement => Boolean(el),
    );
    if (els.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        // Pick the entry with the smallest top that is currently intersecting
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort(
            (a, b) =>
              a.boundingClientRect.top - b.boundingClientRect.top,
          );
        if (visible.length > 0 && visible[0]) {
          setActiveId(visible[0].target.id);
        }
      },
      { rootMargin: "-30% 0px -55% 0px", threshold: [0, 0.5, 1] },
    );

    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <aside
      style={{
        position: "sticky",
        top: 24,
        alignSelf: "flex-start",
      }}
      aria-label="Settings sections"
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: 12,
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 12,
        }}
      >
        Sections
      </div>
      {ITEMS.map((item) => {
        const isActive = activeId === item.id;
        return (
          <a
            key={item.id}
            href={`#${item.id}`}
            className="font-mono uppercase"
            style={{
              display: "block",
              padding: "10px 0 10px 14px",
              borderLeft: `1px solid ${isActive ? "var(--pq-bronze)" : "var(--pq-hairline, var(--pq-ivory-line))"}`,
              fontSize: 12,
              letterSpacing: "0.16em",
              color: isActive
                ? "var(--pq-bronze)"
                : "rgba(245,240,232,0.55)",
              textDecoration: "none",
              transition: "color 200ms, border-color 200ms",
            }}
          >
            <span
              style={{
                color: isActive
                  ? "var(--pq-bronze)"
                  : "rgba(245,240,232,0.55)",
                marginRight: 8,
              }}
            >
              {item.letter}
            </span>
            {item.label}
          </a>
        );
      })}
    </aside>
  );
}

export default AnchorRail;
