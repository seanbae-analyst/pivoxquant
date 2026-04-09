"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  BellRing,
  Plus,
  Sparkles,
  ToggleLeft,
  ToggleRight,
  Trash2,
  Zap,
} from "lucide-react";

interface AlertItem {
  id: number;
  condition: string;
  createdAt: Date;
  status: "active" | "triggered";
  enabled: boolean;
}

const PRESETS = [
  "NVDA drops 5% in a day",
  "VIX goes above 30",
  "My portfolio drops below $5000",
  "Any BUY signal triggers",
];

let nextId = 1;

export default function AIAlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [input, setInput] = useState("");

  function addAlert(condition: string) {
    if (!condition.trim()) return;
    setAlerts((prev) => [
      {
        id: nextId++,
        condition: condition.trim(),
        createdAt: new Date(),
        status: "active",
        enabled: true,
      },
      ...prev,
    ]);
    setInput("");
  }

  function toggleAlert(id: number) {
    setAlerts((prev) =>
      prev.map((a) => (a.id === id ? { ...a, enabled: !a.enabled } : a)),
    );
  }

  function removeAlert(id: number) {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white">
              AI Natural Language Alerts
            </h1>
            <span className="rounded-md px-2.5 py-1 text-[9px] font-bold uppercase tracking-wider bg-purple-500/15 text-purple-400">
              Coming Soon
            </span>
          </div>
          <p className="mt-1 text-[13px] text-zinc-600">
            Describe alert conditions in plain English and let AI monitor them
            for you
          </p>
        </div>
        <Sparkles className="h-5 w-5 text-purple-400" />
      </div>

      {/* Add Alert Form */}
      <div className="glass-surface rounded-xl p-6">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
          <Zap className="h-4 w-4 text-cyan-400" />
          Create a new alert
        </div>
        <form
          className="mt-4 flex gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            addAlert(input);
          }}
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder='e.g. "Alert me when AAPL drops below $180"'
            className="h-11 flex-1 bg-white/[0.03] border-white/[0.06] text-white placeholder:text-zinc-700 focus:border-cyan-500/30 rounded-xl"
          />
          <Button
            type="submit"
            className="h-11 gap-2 bg-gradient-to-r from-cyan-500/10 to-emerald-500/10 text-cyan-400 border border-cyan-500/20 rounded-xl spring-transition"
          >
            <Plus className="h-4 w-4" />
            Add Alert
          </Button>
        </form>

        {/* Preset Suggestions */}
        <div className="mt-4 flex flex-wrap gap-2">
          {PRESETS.map((preset) => (
            <button
              key={preset}
              type="button"
              onClick={() => addAlert(preset)}
              className="rounded-md px-2.5 py-1 text-[9px] font-bold bg-white/[0.03] border border-white/[0.06] text-zinc-400 spring-transition transition-all duration-300 hover:border-cyan-500/30 hover:text-cyan-400"
            >
              {preset}
            </button>
          ))}
        </div>
      </div>

      {/* Alerts List */}
      {alerts.length === 0 ? (
        <div className="glass-surface rounded-2xl py-12 text-center">
          <BellRing className="mx-auto h-10 w-10 text-zinc-600" />
          <p className="mt-3 text-[13px] text-zinc-600">
            No alerts yet. Create one above or pick a preset.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={`flex items-center gap-4 glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)] ${
                !alert.enabled ? "opacity-50" : ""
              }`}
            >
              {/* Toggle */}
              <button
                type="button"
                onClick={() => toggleAlert(alert.id)}
                className="shrink-0 text-zinc-400 spring-transition hover:text-cyan-400"
                aria-label={alert.enabled ? "Disable alert" : "Enable alert"}
              >
                {alert.enabled ? (
                  <ToggleRight className="h-6 w-6 text-cyan-400" />
                ) : (
                  <ToggleLeft className="h-6 w-6" />
                )}
              </button>

              {/* Content */}
              <div className="flex-1">
                <p className="text-sm font-medium text-white">
                  {alert.condition}
                </p>
                <p className="mt-1 text-[13px] text-zinc-600">
                  Created{" "}
                  {alert.createdAt.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              </div>

              {/* Status Badge */}
              <span
                className={`shrink-0 rounded-md px-2.5 py-1 text-[9px] font-bold uppercase tracking-wider ${
                  alert.status === "active"
                    ? "bg-emerald-500/15 text-emerald-400"
                    : "bg-amber-500/15 text-amber-400"
                }`}
              >
                {alert.status}
              </span>

              {/* Delete */}
              <button
                type="button"
                onClick={() => removeAlert(alert.id)}
                className="shrink-0 text-zinc-600 spring-transition hover:text-red-400"
                aria-label="Delete alert"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
