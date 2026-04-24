// Footer
export default function Footer() {
  return (
    <footer className="mt-20 border-t" style={{ borderColor: "var(--border)" }}>
      <div className="max-w-6xl mx-auto px-5 sm:px-8 py-10">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div>
            <div className="text-lg font-medium mb-3 text-display" style={{ fontFamily: "var(--font-display)", color: "var(--accent)" }}>Grounds</div>
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-faint)" }}>
              Tracking specialty coffee across UK roasters. Data collected ethically, updated daily.
            </p>
          </div>
          {[
            { title: "Discover", links: [["Browse coffees", "/coffees"], ["New releases", "/new-releases"], ["Roasters", "/roasters"]] },
            { title: "Learn", links: [["Methodology", "/methodology"], ["About", "/methodology#about"]] },
          ].map(({ title, links }) => (
            <div key={title}>
              <div className="text-xs uppercase tracking-widest mb-3 font-medium" style={{ color: "var(--text-faint)" }}>{title}</div>
              <div className="space-y-2">
                {links.map(([label, href]) => (
                  <a key={href} href={href} className="block text-sm transition-opacity hover:opacity-70" style={{ color: "var(--text-muted)" }}>{label}</a>
                ))}
              </div>
            </div>
          ))}
          <div>
            <div className="text-xs uppercase tracking-widest mb-3 font-medium" style={{ color: "var(--text-faint)" }}>Data</div>
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-faint)" }}>
              ~200 UK sources · Updated daily · Prices may vary
            </p>
          </div>
        </div>
        <div className="mt-8 pt-6 border-t flex items-center justify-between" style={{ borderColor: "var(--border-light)" }}>
          <span className="text-xs" style={{ color: "var(--text-faint)" }}>© 2025 Grounds. For coffee lovers.</span>
          <span className="text-xs" style={{ color: "var(--text-faint)" }}>Not affiliated with any roaster.</span>
        </div>
      </div>
    </footer>
  );
}
