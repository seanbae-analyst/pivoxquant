"use client";

import { AuthProvider } from "@/lib/auth";
import { RealtimeProvider } from "@/lib/realtime";
import { LocaleProvider } from "@/lib/locale";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <LocaleProvider>
      <AuthProvider>
        <RealtimeProvider>{children}</RealtimeProvider>
      </AuthProvider>
    </LocaleProvider>
  );
}
