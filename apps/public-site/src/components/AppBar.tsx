"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect } from "react";

// Page title map
const PAGE_TITLES: Record<string, string> = {
  "/": "Grounds",
  "/coffees": "Browse",
  "/new-releases": "New Releases",
  "/roasters": "Roasters",
  "/roasters-map": "Roaster Map",
  "/methodology": "Methodology",
  "/search": "Search",
};

function DarkToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try { localStorage.setItem("theme", next ? "dark" : "light"); } catch {}
  };

  return (
    <button
      onClick={toggle}
      className="w-9 h-9 flex items-center justify-center rounded-full press-active"
      style={{ color: "var(--text-muted)" }}
      aria-label="Toggle theme"
    >
      {dark ? (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
          <circle cx="12" cy="12" r="4" />
          <line x1="12" y1="2" x2="12" y2="4" />
          <line x1="12" y1="20" x2="12" y2="22" />
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
          <line x1="2" y1="12" x2="4" y2="12" />
          <line x1="20" y1="12" x2="22" y2="12" />
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      )}
    </button>
  );
}

export default function AppBar() {
  const pathname = usePathname();
  const router = useRouter();

  // Determine if this is a detail page (has dynamic segments)
  const isDetailPage = pathname.split("/").length > 2;
  const isRoot = pathname === "/";

  // Get page title
  const staticTitle = PAGE_TITLES[pathname];
  const title = staticTitle ?? (isDetailPage ? "" : "Grounds");

  return (
    <header
      className="sticky top-0 z-40"
      style={{
        backgroundColor: "color-mix(in srgb, var(--bg) 85%, transparent)",
        borderBottom: "1px solid var(--border-light)",
        backdropFilter: "blur(20px) saturate(180%)",
        WebkitBackdropFilter: "blur(20px) saturate(180%)",
        paddingTop: "var(--safe-top)",
      }}
    >
      <div className="flex items-center h-12 px-4 gap-2">
        {/* Back button on detail pages */}
        {isDetailPage ? (
          <button
            onClick={() => router.back()}
            className="w-9 h-9 flex items-center justify-center rounded-full press-active -ml-1 flex-shrink-0"
            style={{ color: "var(--accent)" }}
            aria-label="Go back"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
        ) : (
          /* Grounds wordmark on root pages */
          isRoot ? (
            <span
              className="text-xl font-semibold tracking-tight"
              style={{ fontFamily: "var(--font-display)", color: "var(--accent)" }}
            >
              Grounds
            </span>
          ) : (
            <div className="w-9 flex-shrink-0" />
          )
        )}

        {/* Centred page title for non-root non-detail pages */}
        {!isRoot && (
          <span
            className="flex-1 text-center text-[15px] font-medium truncate"
            style={{ fontFamily: "var(--font-body)", color: "var(--text)" }}
          >
            {title}
          </span>
        )}

        {isRoot && <span className="flex-1" />}

        {/* Right action: theme toggle */}
        <div className="flex-shrink-0">
          <DarkToggle />
        </div>
      </div>
    </header>
  );
}
