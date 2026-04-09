"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Logo } from "@/components/ui/logo";
import { PulseDot } from "@/components/ui/animated";

export function Header() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <header className="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-border bg-white/80 px-4 backdrop-blur-2xl backdrop-saturate-150">
      {/* Logo */}
      <Link href="/dashboard" className="flex items-center gap-2.5">
        <Logo size={30} />
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-bold tracking-tight text-foreground">
            StockPilot
          </span>
          <span className="hidden font-mono text-[9px] tracking-[1.5px] text-muted-foreground/40 sm:inline">
            QUANT ENGINE
          </span>
        </div>
      </Link>

      {/* Right */}
      <div className="flex items-center gap-3">
        {/* Live indicator */}
        <div className="flex items-center gap-1.5 rounded-full border border-success/15 bg-success/5 px-3 py-1">
          <PulseDot color="bg-success" />
          <span className="font-mono text-[10px] font-medium tracking-wider text-success/80">
            LIVE
          </span>
        </div>

        {/* Search placeholder */}
        <button className="hidden items-center gap-2 rounded-lg border border-border/60 bg-muted/30 px-3 py-1.5 text-xs text-muted-foreground/50 transition hover:border-border hover:text-muted-foreground md:flex">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
          </svg>
          <span>Search ticker...</span>
          <kbd className="ml-4 rounded border border-border/60 bg-muted/50 px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground/40">
            /
          </kbd>
        </button>

        {user && (
          <DropdownMenu>
            <DropdownMenuTrigger className="flex items-center gap-2 rounded-full border border-border bg-muted/30 px-3 py-1 text-sm text-muted-foreground transition hover:border-border hover:bg-muted/60 hover:text-foreground">
              <Avatar className="h-6 w-6">
                <AvatarFallback className="bg-gradient-to-br from-primary to-[#60a5fa] text-[9px] font-bold text-white">
                  {user.name?.charAt(0).toUpperCase() ?? "?"}
                </AvatarFallback>
              </Avatar>
              <span className="hidden text-xs sm:inline">{user.name}</span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40 border-border bg-white">
              <DropdownMenuItem onClick={handleLogout} className="text-destructive focus:text-destructive">
                Sign Out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </header>
  );
}
