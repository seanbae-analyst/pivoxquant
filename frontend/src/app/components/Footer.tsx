"use client";

import { Logo } from "@/components/ui/logo";
import Link from "next/link";

const links = {
  Products: ["Quant Engine", "Auto Trading", "AI Insights", "Scanner"],
  Company: ["About", "Blog", "Careers"],
  Resources: ["Docs", "API", "Support", "Status"],
};

export function Footer() {
  return (
    <footer className="border-t border-[var(--ld-border)] py-16 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="grid md:grid-cols-5 gap-10 mb-12">
          <div className="md:col-span-2">
            <Link href="/" className="flex items-center gap-2.5 mb-4">
              <Logo size={28} />
              <span className="font-semibold text-[15px] text-white">StockPilot</span>
            </Link>
            <p className="text-[13px] text-zinc-500 leading-relaxed max-w-xs">
              Next-generation personal investment advisor powered by AI and quant analysis.
            </p>
          </div>
          {Object.entries(links).map(([category, items]) => (
            <div key={category}>
              <h4 className="text-[13px] font-medium text-zinc-300 mb-4">{category}</h4>
              <ul className="space-y-2.5">
                {items.map((item) => (
                  <li key={item}>
                    <a href="#" className="text-[13px] text-zinc-500 hover:text-zinc-300 transition-colors duration-300">
                      {item}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <hr className="landing-divider mb-8" />
        <div className="flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-[12px] text-zinc-600">
            &copy; 2026 StockPilot. All rights reserved.
          </p>
          <div className="flex gap-6 text-[12px] text-zinc-600">
            <a href="#" className="hover:text-zinc-400 transition-colors">Privacy Policy</a>
            <a href="#" className="hover:text-zinc-400 transition-colors">Terms of Service</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
