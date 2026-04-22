import Link from "next/link";
import type { ReactNode } from "react";

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description: string;
  action?: { label: string; href: string };
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-16 h-16 rounded-[2px] bg-[rgba(255,255,255,0.03)] border border-[rgba(245,240,232,0.1)] flex items-center justify-center mb-6 text-[var(--pq-bronze-light)]">
        {icon}
      </div>
      <h3 className="text-lg font-bold text-[var(--pq-ivory)] mb-2">{title}</h3>
      <p className="text-[rgba(245,240,232,0.6)] max-w-sm mb-6 text-sm">{description}</p>
      {action && (
        <Link
          href={action.href}
          className="px-6 py-3 rounded-[2px] bg-[var(--pq-bronze)] text-[var(--pq-ink)] text-sm font-semibold transition-all duration-200 hover:bg-[var(--pq-bronze-light)] active:scale-[0.97]"
        >
          {action.label}
        </Link>
      )}
    </div>
  );
}
