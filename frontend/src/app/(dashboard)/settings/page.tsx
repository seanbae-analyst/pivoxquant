"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Settings, Bell, Monitor, User, Trash2 } from "lucide-react";
import {
  isPushSupported,
  subscribeToPush,
  unsubscribeFromPush,
  getPushSubscription,
} from "@/lib/push";

export default function SettingsPage() {
  const { user } = useAuth();

  /* Notifications */
  const [emailAlerts, setEmailAlerts] = useState(true);
  const [pushNotifs, setPushNotifs] = useState(false);
  const [pushLoading, setPushLoading] = useState(false);
  const [pushSupported, setPushSupported] = useState(true);
  const [alertFreq, setAlertFreq] = useState("realtime");

  // Check current push subscription status on mount
  useEffect(() => {
    if (!isPushSupported()) {
      setPushSupported(false);
      return;
    }
    getPushSubscription().then((sub) => {
      setPushNotifs(!!sub);
    });
  }, []);

  const handlePushToggle = useCallback(async () => {
    setPushLoading(true);
    try {
      if (pushNotifs) {
        const ok = await unsubscribeFromPush();
        if (ok) setPushNotifs(false);
      } else {
        const sub = await subscribeToPush();
        setPushNotifs(!!sub);
      }
    } catch {
      // Permission denied or error
    } finally {
      setPushLoading(false);
    }
  }, [pushNotifs]);

  /* Display */
  const [theme, setTheme] = useState("dark");
  const [language, setLanguage] = useState("en");

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Settings
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Manage your preferences
        </p>
      </div>

      {/* Notifications */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6">
        <div className="flex items-center gap-2 mb-5">
          <Bell size={18} className="text-emerald-600" />
          <h2 className="text-lg font-semibold text-slate-900">
            Notifications
          </h2>
        </div>
        <div className="space-y-5">
          {/* Email alerts */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-700">
                Email Alerts
              </p>
              <p className="text-xs text-slate-500">
                Receive trading signals via email
              </p>
            </div>
            <button
              onClick={() => setEmailAlerts(!emailAlerts)}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ${
                emailAlerts ? "bg-emerald-500" : "bg-slate-300"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform duration-200 ${
                  emailAlerts ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* Push notifications */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-700">
                Push Notifications
              </p>
              <p className="text-xs text-slate-500">
                {!pushSupported
                  ? "Not supported in this browser"
                  : "Browser push notifications for alerts"}
              </p>
            </div>
            <button
              onClick={handlePushToggle}
              disabled={pushLoading || !pushSupported}
              className={`relative inline-flex h-6 w-11 shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 ${
                !pushSupported
                  ? "cursor-not-allowed bg-slate-200 opacity-50"
                  : pushLoading
                    ? "cursor-wait bg-slate-400"
                    : pushNotifs
                      ? "cursor-pointer bg-emerald-500"
                      : "cursor-pointer bg-slate-300"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform duration-200 ${
                  pushNotifs ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* Alert frequency */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-700">
                Alert Frequency
              </p>
              <p className="text-xs text-slate-500">
                How often to send notifications
              </p>
            </div>
            <select
              value={alertFreq}
              onChange={(e) => setAlertFreq(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 outline-none focus:border-emerald-500/50"
            >
              <option value="realtime">Real-time</option>
              <option value="hourly">Hourly</option>
              <option value="daily">Daily Digest</option>
              <option value="weekly">Weekly Summary</option>
            </select>
          </div>
        </div>
      </section>

      {/* Display */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6">
        <div className="flex items-center gap-2 mb-5">
          <Monitor size={18} className="text-emerald-600" />
          <h2 className="text-lg font-semibold text-slate-900">Display</h2>
        </div>
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-700">Theme</p>
              <p className="text-xs text-slate-500">
                Application color scheme
              </p>
            </div>
            <select
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 outline-none focus:border-emerald-500/50"
            >
              <option value="dark">Dark</option>
            </select>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-700">
                Language
              </p>
              <p className="text-xs text-slate-500">
                Interface language
              </p>
            </div>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 outline-none focus:border-emerald-500/50"
            >
              <option value="en">English</option>
            </select>
          </div>
        </div>
      </section>

      {/* Account */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6">
        <div className="flex items-center gap-2 mb-5">
          <User size={18} className="text-emerald-600" />
          <h2 className="text-lg font-semibold text-slate-900">Account</h2>
        </div>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Name</span>
            <span className="text-sm font-medium text-slate-700">
              {user?.name ?? "—"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Email</span>
            <span className="text-sm font-medium text-slate-700">
              {user?.email ?? "—"}
            </span>
          </div>

          <div className="mt-6 border-t border-slate-200 pt-5">
            <h3 className="text-sm font-semibold text-red-600">
              Danger Zone
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              Permanently delete your account and all data. This action
              cannot be undone.
            </p>
            <Button
              disabled
              className="mt-3 gap-2 border border-red-500/30 bg-red-500/10 text-red-600 cursor-not-allowed opacity-50"
            >
              <Trash2 size={14} />
              Delete Account
            </Button>
          </div>
        </div>
      </section>

      {/* About */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6">
        <div className="flex items-center gap-2 mb-5">
          <Settings size={18} className="text-emerald-600" />
          <h2 className="text-lg font-semibold text-slate-900">About</h2>
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Version</span>
            <span className="text-sm font-mono font-medium text-slate-700">
              v2.0
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Documentation</span>
            <a
              href="#"
              className="text-sm text-emerald-600 hover:text-emerald-700 transition-colors"
            >
              View Docs
            </a>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Support</span>
            <a
              href="#"
              className="text-sm text-emerald-600 hover:text-emerald-700 transition-colors"
            >
              Contact Support
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}
