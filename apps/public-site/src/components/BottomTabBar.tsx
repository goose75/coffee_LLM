"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// ── Icons — custom SVGs in the Grounds style ──────────────────────────────────

function HomeIcon({ filled }: { filled: boolean }) {
  return filled ? (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
      <path d="M10.707 2.293a1 1 0 0 1 1.414 0l7.5 7.5A1 1 0 0 1 19 11.5V20a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-4h-2v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-8.5a1 1 0 0 1 .293-.707l5.414-5.5Z" />
    </svg>
  ) : (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12L12 3l9 9" />
      <path d="M9 21V12h6v9" />
      <path d="M5 10v11h14V10" />
    </svg>
  );
}

function GridIcon({ filled }: { filled: boolean }) {
  return filled ? (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
      <rect x="3" y="3" width="8" height="8" rx="1.5" />
      <rect x="13" y="3" width="8" height="8" rx="1.5" />
      <rect x="3" y="13" width="8" height="8" rx="1.5" />
      <rect x="13" y="13" width="8" height="8" rx="1.5" />
    </svg>
  ) : (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <rect x="3" y="3" width="8" height="8" rx="1.5" />
      <rect x="13" y="3" width="8" height="8" rx="1.5" />
      <rect x="3" y="13" width="8" height="8" rx="1.5" />
      <rect x="13" y="13" width="8" height="8" rx="1.5" />
    </svg>
  );
}

function SparkleIcon({ filled }: { filled: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={filled ? 0 : 1.6} strokeLinecap="round" strokeLinejoin="round">
      {filled ? (
        <>
          <path d="M12 2c0 0-.5 4-3.5 6.5S2 12 2 12s4 .5 6.5 3.5S12 22 12 22s.5-4 3.5-6.5S22 12 22 12s-4-.5-6.5-3.5S12 2 12 2Z" />
        </>
      ) : (
        <>
          <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
          <path d="M12 8c0 0-1 2-4 4 3 2 4 4 4 4s1-2 4-4c-3-2-4-4-4-4Z" />
        </>
      )}
    </svg>
  );
}

function ShopIcon({ filled }: { filled: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={filled ? 0 : 1.6} strokeLinecap="round" strokeLinejoin="round">
      {filled ? (
        <path d="M19 3H5a2 2 0 0 0-2 2v2.5a2 2 0 0 0 1 1.73V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9.23A2 2 0 0 0 21 7.5V5a2 2 0 0 0-2-2ZM9 13a3 3 0 0 0 6 0" />
      ) : (
        <>
          <path d="M3 7.5V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2.5" />
          <path d="M3 7.5a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2" />
          <path d="M5 9.5V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9.5" />
          <path d="M9 13a3 3 0 0 0 6 0" />
        </>
      )}
    </svg>
  );
}

function SearchIcon({ filled }: { filled: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={filled ? 2.2 : 1.6} strokeLinecap="round">
      <circle cx="11" cy="11" r="7" />
      <line x1="16.5" y1="16.5" x2="21" y2="21" />
    </svg>
  );
}

// ── Tab configuration ─────────────────────────────────────────────────────────

function AtlasIcon({ filled }: { filled: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={filled ? 0 : 1.6} strokeLinecap="round" strokeLinejoin="round">
      {filled ? (
        <>
          <circle cx="12" cy="12" r="2.5" fill="currentColor" />
          <circle cx="12" cy="4"  r="1.5" fill="currentColor" opacity=".7" />
          <circle cx="19" cy="8"  r="1.5" fill="currentColor" opacity=".7" />
          <circle cx="19" cy="16" r="1.5" fill="currentColor" opacity=".7" />
          <circle cx="12" cy="20" r="1.5" fill="currentColor" opacity=".7" />
          <circle cx="5"  cy="16" r="1.5" fill="currentColor" opacity=".7" />
          <circle cx="5"  cy="8"  r="1.5" fill="currentColor" opacity=".7" />
        </>
      ) : (
        <>
          <circle cx="12" cy="12" r="2.5" />
          <circle cx="12" cy="4"  r="1.5" />
          <circle cx="19" cy="8"  r="1.5" />
          <circle cx="19" cy="16" r="1.5" />
          <circle cx="12" cy="20" r="1.5" />
          <circle cx="5"  cy="16" r="1.5" />
          <circle cx="5"  cy="8"  r="1.5" />
        </>
      )}
    </svg>
  );
}


const TABS = [
  { href: "/",               label: "Home",    Icon: HomeIcon    },
  { href: "/coffees",        label: "Browse",  Icon: GridIcon    },
  { href: "/flavour-atlas",  label: "Atlas",   Icon: AtlasIcon   },
  { href: "/roasters",       label: "Roasters",Icon: ShopIcon    },
  { href: "/search",         label: "Search",  Icon: SearchIcon  },
] as const;

// ── Component ─────────────────────────────────────────────────────────────────

export default function BottomTabBar() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50"
      style={{
        backgroundColor: "var(--surface)",
        borderTop: "1px solid var(--border-light)",
        paddingBottom: "var(--safe-bottom)",
        height: "calc(var(--tab-h) + var(--safe-bottom))",
        // Frosted glass effect
        backdropFilter: "blur(20px) saturate(180%)",
        WebkitBackdropFilter: "blur(20px) saturate(180%)",
      }}
    >
      <div className="flex h-16 items-stretch">
        {TABS.map(({ href, label, Icon }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              className="flex-1 flex flex-col items-center justify-center gap-0.5 press-active"
              style={{
                color: active ? "var(--accent)" : "var(--text-faint)",
                minWidth: 0,
              }}
            >
              <div
                className="transition-all duration-200"
                style={{
                  transform: active ? "scale(1.08)" : "scale(1)",
                }}
              >
                <Icon filled={active} />
              </div>
              <span
                className="text-[10px] leading-none tracking-wide font-medium"
                style={{
                  opacity: active ? 1 : 0.7,
                  fontFamily: "var(--font-body)",
                }}
              >
                {label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
