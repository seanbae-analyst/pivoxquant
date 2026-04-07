"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/ui/logo";

export default function LoginPage() {
  const { login, signup } = useAuth();
  const router = useRouter();
  const [isSignup, setIsSignup] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (isSignup) {
        await signup(email, password, name || undefined);
      } else {
        await login(email, password);
      }
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-4">
      {/* Background gradient orbs */}
      <div className="pointer-events-none absolute -left-40 -top-40 h-80 w-80 rounded-full bg-primary/10 blur-[120px]" />
      <div className="pointer-events-none absolute -bottom-40 -right-40 h-80 w-80 rounded-full bg-[#a855f7]/10 blur-[120px]" />

      <div className="w-full max-w-sm">
        <div className="rounded-2xl border border-white/[.06] bg-card/80 p-8 shadow-2xl backdrop-blur-xl">
          {/* Logo */}
          <div className="flex flex-col items-center">
            <Logo size={48} />
            <h1 className="mt-3 text-lg font-bold tracking-tight text-foreground">
              StockPilot
            </h1>
            <p className="mt-1 font-mono text-[9px] tracking-[2px] text-muted-foreground/40">
              QUANT ENGINE v4
            </p>
          </div>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
            {isSignup && (
              <div className="space-y-1.5">
                <Label htmlFor="name" className="text-[10px] uppercase tracking-wider text-muted-foreground/50">
                  Name
                </Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  className="border-white/[.06] bg-white/[.03]"
                />
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-[10px] uppercase tracking-wider text-muted-foreground/50">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="border-white/[.06] bg-white/[.03]"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-[10px] uppercase tracking-wider text-muted-foreground/50">
                Password
              </Label>
              <Input
                id="password"
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min 6 characters"
                className="border-white/[.06] bg-white/[.03]"
              />
            </div>

            {error && (
              <p className="text-center text-xs text-destructive">{error}</p>
            )}

            <Button
              type="submit"
              className="w-full bg-gradient-to-r from-primary to-[#a855f7] font-semibold text-white hover:opacity-90"
              disabled={loading}
            >
              {loading ? "..." : isSignup ? "Create Account" : "Sign In"}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-muted-foreground/50">
            {isSignup ? "Already have an account?" : "Don't have an account?"}{" "}
            <button
              type="button"
              onClick={() => { setIsSignup(!isSignup); setError(""); }}
              className="text-primary/80 hover:text-primary hover:underline"
            >
              {isSignup ? "Sign In" : "Sign Up"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
