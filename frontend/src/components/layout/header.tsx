"use client";

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
    <header className="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-white/[.04] bg-[#0a0e18]/95 px-4 backdrop-blur-xl">
      {/* Logo */}
      <div className="flex items-center gap-2.5">
        <Logo size={32} />
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-bold tracking-tight text-foreground">
            StockPilot
          </span>
          <span className="hidden font-mono text-[9px] tracking-[1.5px] text-muted-foreground/60 sm:inline">
            QUANT v4
          </span>
        </div>
      </div>

      {/* Right */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 rounded-full border border-success/20 bg-success/5 px-3 py-1">
          <PulseDot color="bg-success" />
          <span className="font-mono text-[10px] font-medium tracking-wider text-success">
            LIVE
          </span>
        </div>

        {user && (
          <DropdownMenu>
            <DropdownMenuTrigger className="flex items-center gap-2 rounded-full border border-white/[.06] bg-white/[.03] px-3 py-1 text-sm text-muted-foreground transition hover:border-white/[.12] hover:bg-white/[.06] hover:text-foreground">
              <Avatar className="h-6 w-6">
                <AvatarFallback className="bg-gradient-to-br from-primary to-[#9c6cff] text-[9px] font-bold text-white">
                  {user.name?.charAt(0).toUpperCase() ?? "?"}
                </AvatarFallback>
              </Avatar>
              <span className="hidden text-xs sm:inline">{user.name}</span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40 border-border bg-[#0c1018]">
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
