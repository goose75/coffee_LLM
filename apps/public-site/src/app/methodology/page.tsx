export const metadata = { title: "Methodology" };

function Step({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <div className="grid md:grid-cols-[80px_1fr] gap-6 py-10" style={{ borderBottom: "1px solid var(--border-light)" }}>
      <div className="flex-shrink-0">
        <div className="text-4xl font-light" style={{ fontFamily: "var(--font-display)", color: "var(--accent)", opacity: 0.4 }}>{n}</div>
      </div>
      <div>
        <h3 className="text-xl font-medium mb-3" style={{ fontFamily: "var(--font-display)" }}>{title}</h3>
        <div className="text-sm leading-relaxed space-y-3" style={{ color: "var(--text-muted)" }}>
          {children}
        </div>
      </div>
    </div>
  );
}

function Callout({ children }: { children: React.ReactNode }) {
  return (
    <div className="my-4 pl-4 py-3 text-sm" style={{ borderLeft: "2px solid var(--accent)", color: "var(--text-muted)" }}>
      {children}
    </div>
  );
}

export default function MethodologyPage() {
  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="mb-14">
        <div className="text-xs uppercase tracking-widest mb-3" style={{ color: "var(--text-faint)" }}>Transparency</div>
        <h1 className="text-5xl font-light mb-5" style={{ fontFamily: "var(--font-display)" }}>
          How Grounds works
        </h1>
        <p className="text-lg leading-relaxed max-w-2xl" style={{ color: "var(--text-muted)", fontFamily: "var(--font-display)", fontStyle: "italic" }}>
          We believe coffee discovery should be transparent. Here's exactly how we collect, process, and present data.
        </p>
      </div>

      {/* Principles */}
      <div className="grid sm:grid-cols-3 gap-4 mb-14">
        {[
          ["Canonical-first", "We separate the coffee's identity from how any individual seller presents it."],
          ["Append-only history", "Prices are never overwritten. We preserve the full price history."],
          ["Confidence-aware", "Every match decision carries a confidence score. Uncertain matches are reviewed by humans."],
        ].map(([title, desc]) => (
          <div key={title} className="p-5 rounded-2xl" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
            <h3 className="font-medium mb-2" style={{ fontFamily: "var(--font-display)", fontSize: "1rem" }}>{title}</h3>
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>{desc}</p>
          </div>
        ))}
      </div>

      <div className="h-px mb-10" style={{ backgroundColor: "var(--border-light)" }} />

      {/* Steps */}
      <h2 className="text-3xl font-light mb-2" style={{ fontFamily: "var(--font-display)" }}>The pipeline</h2>
      <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>From roaster website to your screen in five stages.</p>

      <Step n="01" title="Source discovery">
        <p>We maintain a curated list of ~200 UK coffee roasters and specialty coffee shops. For each, we detect whether it runs Shopify (enabling structured product data access via <code className="text-xs bg-surface-raised px-1 py-0.5 rounded">/products.json</code>), uses schema.org Product markup, or requires HTML parsing.</p>
        <Callout>Shopify sources are the most reliable: structured JSON, paginated, stable variant IDs. We prioritise these.</Callout>
      </Step>

      <Step n="02" title="Ingestion">
        <p>Each source is crawled on a schedule (12–24 hours depending on activity). For Shopify stores, we fetch all products and variants. For other sources, we extract data from page HTML using a priority chain:</p>
        <ol className="list-decimal list-inside space-y-1 mt-2">
          <li>Shopify <code className="text-xs bg-surface-raised px-1 py-0.5 rounded">products.json</code> feed</li>
          <li>schema.org JSON-LD Product markup</li>
          <li>Deterministic HTML selectors</li>
          <li>LLM extraction fallback (Anthropic Claude, for messy pages only)</li>
        </ol>
        <p>Every raw payload is stored with a SHA-256 content hash. If nothing has changed since the last crawl, we skip reprocessing.</p>
      </Step>

      <Step n="03" title="Normalisation">
        <p>Raw text from sources ("Full City+", "Cafetière", "Natural Process") is mapped to our controlled vocabulary via a curated dictionary. We always preserve the original text alongside the normalised value — we never silently replace source data.</p>
        <p>Controlled vocabularies: roast level (light → dark), grind type (8 values), process (washed, natural, honey, anaerobic, wet-hulled, carbonic maceration, experimental). Country names are normalised to ISO standards.</p>
      </Step>

      <Step n="04" title="Entity resolution">
        <p>This is the hardest problem. A coffee sold as "Ethiopia Yirgacheffe Konga" at Square Mile and "Ethiopia Konga Natural" at Rave might be the same lot — or might not be. We use three signals in combination:</p>
        <ul className="list-disc list-inside space-y-1 mt-2">
          <li><strong>Exact fields</strong> (weight 45%): origin country, process, varietal, farm match</li>
          <li><strong>Fuzzy title similarity</strong> (weight 30%): rapidfuzz token_set_ratio on product names</li>
          <li><strong>Embedding similarity</strong> (weight 20%): cosine distance on 1536-dim description vectors</li>
          <li><strong>Harvest year agreement</strong> (weight 5%): same-farm different-year lots are different coffees</li>
        </ul>
        <Callout>
          Confidence ≥ 0.92: auto-linked. 0.75–0.91: queued for human review. Below 0.75: treated as a new canonical bean.
          Harvest year mismatch prevents auto-accept regardless of other signals.
        </Callout>
      </Step>

      <Step n="05" title="Serving">
        <p>Data is served via a FastAPI backend with PostgreSQL storage. Price history is append-only — we never overwrite a recorded price. Embeddings are stored in pgvector for approximate nearest-neighbour search.</p>
        <p>Prices shown are the latest recorded price. We recommend always verifying on the seller's site before purchasing, as prices may have changed.</p>
      </Step>

      {/* Limitations */}
      <div className="mt-12 p-6 rounded-2xl" style={{ backgroundColor: "var(--bg-warm)", border: "1px solid var(--border-light)" }}>
        <h3 className="text-xl font-medium mb-4" style={{ fontFamily: "var(--font-display)" }}>Known limitations</h3>
        <ul className="space-y-2 text-sm" style={{ color: "var(--text-muted)" }}>
          <li className="flex gap-3"><span style={{ color: "var(--accent)" }}>—</span>Some roasters block automated access. We respect robots.txt and don't access password-protected stores.</li>
          <li className="flex gap-3"><span style={{ color: "var(--accent)" }}>—</span>Entity resolution is imperfect. A coffee labelled the same way across two sites may or may not be the same lot. We show our confidence score.</li>
          <li className="flex gap-3"><span style={{ color: "var(--accent)" }}>—</span>Subscription coffees with rotating selections change faster than our crawl interval.</li>
          <li className="flex gap-3"><span style={{ color: "var(--accent)" }}>—</span>We don't sell coffee and have no commercial relationships with any roaster.</li>
        </ul>
      </div>

      {/* Contact */}
      <div className="mt-10 text-center py-10" style={{ borderTop: "1px solid var(--border-light)" }}>
        <p className="text-sm mb-2" style={{ color: "var(--text-muted)" }}>
          Roaster not listed? Data incorrect?
        </p>
        <p className="text-sm" style={{ color: "var(--text-faint)" }}>
          We're building this openly. Reach out via GitHub.
        </p>
      </div>
    </div>
  );
}
