"use client";

import { Component, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { useT } from "@/lib/locale";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/* Functional fallback UI that can use hooks. Dark themed for Vantablack dashboard. */
function ErrorFallback({ onRetry }: { onRetry: () => void }) {
  const t = useT();
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] text-center p-8">
      <div className="w-14 h-14 rounded-[2px] bg-[rgba(139,111,71,0.12)] border border-[rgba(139,111,71,0.3)] flex items-center justify-center mb-5">
        <AlertTriangle className="w-6 h-6 text-[var(--pq-bronze-light)]" />
      </div>
      <div className="text-[9px] tracking-[0.22em] uppercase text-[var(--pq-bronze-light)] mb-2">
        Error
      </div>
      <h2 className="text-xl font-bold text-[var(--pq-ivory)] mb-2">
        {t("errorBoundary.title")}
      </h2>
      <p className="text-[rgba(245,240,232,0.6)] mb-6 max-w-sm text-sm">
        {t("errorBoundary.description")}
      </p>
      <button
        onClick={onRetry}
        className="px-5 py-2.5 rounded-[2px] bg-[var(--pq-bronze)] text-[var(--pq-ink)] text-sm font-semibold transition-all duration-200 hover:bg-[var(--pq-bronze-light)] active:scale-[0.97]"
      >
        {t("errorBoundary.retry")}
      </button>
    </div>
  );
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <ErrorFallback onRetry={() => this.setState({ hasError: false })} />
        )
      );
    }

    return this.props.children;
  }
}
