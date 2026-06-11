import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const jb = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: { default: "Coffee Platform Admin", template: "%s | Admin" },
  description: "Internal operations dashboard for the Coffee Intelligence Platform",
};

const NAV = [
  { href: "/control-tower",   label: "Control Tower",   icon: "⚡" },
  { href: "/sources",         label: "Sources",         icon: "◈" },
  { href: "/llm-assist",      label: "LLM Assist",      icon: "🤖" },
  { href: "/ingestion-runs",  label: "Ingestion Runs",  icon: "↻" },
  { href: "/review/matches",  label: "Matches",         icon: "⊕" },
  { href: "/beans",           label: "Beans",           icon: "◉" },
  { href: "/prices",          label: "Prices",          icon: "£" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jb.variable}`}>
      <body className="bg-neutral-950 text-neutral-200 font-sans antialiased min-h-screen flex">
        <aside className="w-52 shrink-0 border-r border-neutral-800/80 flex flex-col sticky top-0 h-screen bg-neutral-950 z-20">
          <div className="px-4 py-4 border-b border-neutral-800/80">
            <div className="text-[9px] tracking-[0.2em] text-neutral-600 uppercase mb-1">Coffee Platform</div>
            <div className="text-amber-400 font-semibold text-sm tracking-wide">Admin Console</div>
          </div>
          <nav className="flex-1 py-2 overflow-y-auto">
            {NAV.map((item) => (
              <Link key={item.href} href={item.href}
                className="flex items-center gap-2.5 px-4 py-2.5 text-[13px] text-neutral-500 hover:text-neutral-100 hover:bg-white/[0.04] transition-colors group">
                <span className="text-[10px] text-neutral-700 group-hover:text-neutral-500 w-3 text-center">{item.icon}</span>
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="px-4 py-3 border-t border-neutral-800/80 space-y-1">
            <div className="text-[10px] text-neutral-700">v0.4.0 — Phase 4</div>
            <div className="text-[10px] text-neutral-700">coffee-platform.local</div>
          </div>
        </aside>
        <main className="flex-1 min-w-0 overflow-auto">{children}</main>
      </body>
    </html>
  );
}
