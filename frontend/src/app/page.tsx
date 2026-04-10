"use client";

import { useAuth } from "@/lib/auth";
import { Logo } from "@/components/ui/logo";
import { Terminal } from "@/components/terminal/terminal";
import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { Products } from "./components/Products";
import { Solutions } from "./components/Solutions";
import { Stats } from "./components/Stats";
import { CTA } from "./components/CTA";
import { Footer } from "./components/Footer";

export default function MainPage() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-white">
        <Logo size={48} />
      </div>
    );
  }

  // Logged in → Terminal mode
  if (user) {
    return <Terminal />;
  }

  // Not logged in → Landing page
  return (
    <div className="landing-dark min-h-[100dvh]">
      <Header />
      <main>
        <Hero />
        <Products />
        <Solutions />
        <Stats />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
