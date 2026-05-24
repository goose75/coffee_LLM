import Link from "next/link";
import {
  getCoffee, getPriceHistory, getPriceStats,
  getTasteProfile, getSimilarCoffees,
  type BeanPriceHistory, type PriceSummaryStats,
  type TasteProfile, type SimilarCoffee, type Coffee,
} from "@/lib/api";
import CoffeeDetailTabs from "@/components/CoffeeDetailTabs";
import CompareButtonDetail from "@/components/CompareButtonDetail";

const PROCESS_COLORS: Record<string, string> = {
  washed: "#6b9e8c", natural: "#c4763a", honey: "#d4a03a",
  anaerobic: "#8b6bab", wet_hulled: "#5a7fa8", carbonic_maceration: "#a85a7f",
};

function TasteWheel({ profile }: { profile: TasteProfile }) {
  if (!profile.has_structured_tags || profile.families.length === 0) return <LegacyWheel notes={profile.raw_notes} />;
  const cx = 100, cy = 100, r = 68, n = profile.families.length;
  const maxW = Math.max(...profile.families.map(f => f.weight), 1);
  const segs = profile.families.map((f, i) => {
    const angle = (i * 360) / n, norm = f.weight / maxW;
    const radius = r * 0.25 + norm * r * 0.72;
    const rad = (angle - 90) * (Math.PI / 180);
    return { ...f, norm, x: cx + radius * Math.cos(rad), y: cy + radius * Math.sin(rad),
      lx: cx + (r + 16) * Math.cos(rad), ly: cy + (r + 16) * Math.sin(rad), angle };
  });
  return (
    <svg viewBox="0 0 200 200" className="w-full max-w-[220px] mx-auto">
      {[0.3,0.6,1].map(f=><circle key={f} cx={cx} cy={cy} r={r*f} fill="none" stroke="var(--border-light)" strokeWidth="0.5"/>)}
      {segs.map((s,i)=>{const rad=(s.angle-90)*Math.PI/180;return<line key={i} x1={cx} y1={cy} x2={cx+r*Math.cos(rad)} y2={cy+r*Math.sin(rad)} stroke="var(--border-light)" strokeWidth="0.5"/>;})}
      <polygon points={segs.map(s=>`${s.x.toFixed(1)},${s.y.toFixed(1)}`).join(" ")} fill="var(--accent)" fillOpacity="0.12" stroke="var(--accent)" strokeWidth="1.5"/>
      {segs.map((s,i)=><circle key={i} cx={s.x} cy={s.y} r={s.norm>0?3.5:1.5} fill={s.colour} fillOpacity={s.norm>0?0.9:0.3}/>)}
      {segs.map((s,i)=><text key={i} x={s.lx} y={s.ly} textAnchor="middle" dominantBaseline="middle" fontSize="5.5" fill={s.norm>0?"var(--text)":"var(--text-faint)"}>{s.family_label}</text>)}
    </svg>
  );
}

function LegacyWheel({ notes }: { notes: string[] }) {
  const CATS = [
    {label:"Floral",col:"#c084c0",kw:["jasmine","rose","elderflower","hibiscus","floral","lavender"]},
    {label:"Fruity",col:"#e05c3a",kw:["lemon","bergamot","citrus","grapefruit","orange","tropical","mango","passionfruit","cherry","peach","strawberry","blackcurrant","red fruit"]},
    {label:"Sweet",col:"#d4a84b",kw:["honey","caramel","vanilla","brown sugar","candy","toffee","maple"]},
    {label:"Choc.",col:"#7c4b2a",kw:["dark chocolate","milk chocolate","cocoa","cacao","mocha"]},
    {label:"Nutty",col:"#a07850",kw:["almond","hazelnut","walnut","peanut"]},
    {label:"Spice",col:"#c47820",kw:["cinnamon","clove","cardamom","black pepper","nutmeg"]},
    {label:"Earthy",col:"#6b7c4a",kw:["earthy","tobacco","cedar","oak","green tea","black tea","herbal"]},
    {label:"Ferm.",col:"#8b6bab",kw:["wine","whisky","vinegar","yoghurt","funky"]},
  ];
  const cx=100,cy=100,r=68;
  const segs=CATS.map((c,i)=>{
    const angle=(i*360)/CATS.length;
    const mc=c.kw.filter(k=>notes.some(n=>n.includes(k)||k.includes(n))).length;
    const hasM=mc>0;
    const radius=hasM?r*0.35+(mc/c.kw.length)*r*0.62:r*0.18;
    const rad=(angle-90)*Math.PI/180;
    return{...c,hasM,x:cx+radius*Math.cos(rad),y:cy+radius*Math.sin(rad),
      lx:cx+(r+16)*Math.cos(rad),ly:cy+(r+16)*Math.sin(rad),angle};
  });
  return(
    <svg viewBox="0 0 200 200" className="w-full max-w-[220px] mx-auto">
      {[0.3,0.6,1].map(f=><circle key={f} cx={cx} cy={cy} r={r*f} fill="none" stroke="var(--border-light)" strokeWidth="0.5"/>)}
      {segs.map((s,i)=>{const rad=(s.angle-90)*Math.PI/180;return<line key={i} x1={cx} y1={cy} x2={cx+r*Math.cos(rad)} y2={cy+r*Math.sin(rad)} stroke="var(--border-light)" strokeWidth="0.5"/>;})}
      <polygon points={segs.map(s=>`${s.x.toFixed(1)},${s.y.toFixed(1)}`).join(" ")} fill="var(--accent)" fillOpacity="0.13" stroke="var(--accent)" strokeWidth="1.5"/>
      {segs.map((s,i)=><circle key={i} cx={s.x} cy={s.y} r={s.hasM?3.5:1.5} fill={s.hasM?s.col:"var(--text-faint)"} fillOpacity={s.hasM?0.9:0.3}/>)}
      {segs.map((s,i)=><text key={i} x={s.lx} y={s.ly} textAnchor="middle" dominantBaseline="middle" fontSize="5.5" fill={s.hasM?"var(--text)":"var(--text-faint)"}>{s.label}</text>)}
    </svg>
  );
}

function RoastBar({ level }: { level: string | null }) {
  const levels = ["light","medium_light","medium","medium_dark","dark"];
  const idx = level ? levels.indexOf(level) : -1;
  return (
    <div className="flex items-center gap-1">
      {levels.map((l,i) => <div key={l} className="h-1.5 flex-1 rounded-full" style={{backgroundColor: i<=idx?"var(--accent)":"var(--border)"}}/>)}
    </div>
  );
}

export async function generateMetadata({ params }: { params: { id: string } }) {
  try { const c = await getCoffee(params.id); return { title: c.canonical_name }; }
  catch { return { title: "Coffee" }; }
}

export default async function CoffeeDetailPage({ params }: { params: { id: string } }) {
  const id = params.id;
  const [coffee, priceHistory, priceStats, tasteProfile, similar] = await Promise.allSettled([
    getCoffee(id), getPriceHistory(id, 60), getPriceStats(id), getTasteProfile(id), getSimilarCoffees(id, 4),
  ]);

  if (coffee.status === "rejected") {
    return (
      <div className="px-4 py-20 text-center">
        <div className="text-3xl font-light mb-3" style={{ fontFamily: "var(--font-display)" }}>Not found</div>
        <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>This coffee may not exist yet.</p>
        <Link href="/coffees" style={{ color: "var(--accent)" }} className="text-sm">← Browse coffees</Link>
      </div>
    );
  }

  const c: Coffee = coffee.value;
  const history = priceHistory.status === "fulfilled" ? priceHistory.value : null;
  const stats = priceStats.status === "fulfilled" ? priceStats.value : [];
  const taste = tasteProfile.status === "fulfilled" ? tasteProfile.value : null;
  const similarCoffees = similar.status === "fulfilled" ? similar.value : [];

  const processColor = PROCESS_COLORS[c.process ?? ""] ?? "var(--border)";
  const bestPer100g = stats.flatMap(s => s.min_per_100g != null ? [s.min_per_100g] : []);
  const bestP100 = bestPer100g.length > 0 ? Math.min(...bestPer100g) : null;

  const tasteWheelJsx = taste ? <TasteWheel profile={taste} /> : <LegacyWheel notes={c.flavour_notes} />;

  return (
    <div>
      {/* Process colour strip */}
      <div className="h-1.5 w-full" style={{ backgroundColor: processColor }} />

      {/* Hero */}
      <div className="px-4 pt-6 pb-5" style={{ borderBottom: "1px solid var(--border-light)" }}>
        <div className="text-sm uppercase tracking-widest mb-3" style={{ color: "var(--text)" }}>
          {[c.origin_country, c.origin_region].filter(Boolean).join(" · ")}
        </div>

        <h1 className="text-4xl font-light leading-tight mb-2" style={{ fontFamily: "var(--font-display)" }}>
          {c.canonical_name}
        </h1>

        {c.farm_or_estate && (
          <p className="text-base italic mb-4" style={{ fontFamily: "var(--font-display)", color: "var(--text)" }}>
            {c.farm_or_estate}
          </p>
        )}

        {/* Brew badges */}
        <div className="flex items-center gap-2 mb-5">
          {c.espresso_suitable_flag && (
            <span className="text-xs px-3 py-2 rounded-full font-medium"
              style={{ backgroundColor: "var(--accent-dim)", color: "var(--accent)", border: "1px solid var(--accent)" }}>
              ☕ Espresso
            </span>
          )}
          {c.filter_suitable_flag && (
            <span className="text-xs px-3 py-2 rounded-full"
              style={{ backgroundColor: "var(--bg-warm)", color: "var(--text)", border: "1px solid var(--border)" }}>
              🫗 Filter
            </span>
          )}
          {c.decaf_flag && (
            <span className="text-xs px-3 py-2 rounded-full"
              style={{ backgroundColor: "var(--bg-warm)", color: "var(--text)" }}>Decaf</span>
          )}
          <CompareButtonDetail coffeeId={c.id} coffeeName={c.canonical_name} />
        </div>

        {/* Price + roast bar */}
        <div className="flex items-end justify-between gap-4">
          <div>
            {c.min_price_gbp != null ? (
              <>
                <span className="text-3xl font-light" style={{ fontFamily: "var(--font-display)", color: "var(--accent)" }}>
                  £{c.min_price_gbp.toFixed(2)}
                </span>
                <span className="text-sm ml-2" style={{ color: "var(--text)" }}>
                  from · {c.store_count ?? 0} {(c.store_count ?? 0) === 1 ? "store" : "stores"}
                </span>
                {bestP100 && <div className="text-sm mt-1" style={{ color: "var(--text)" }}>Best £{bestP100.toFixed(2)}/100g</div>}
              </>
            ) : (
              <span className="text-base" style={{ color: "var(--text)" }}>Price unavailable</span>
            )}
          </div>
          {c.roast_level && (
            <div className="w-32 flex-shrink-0">
              <div className="text-sm uppercase tracking-wider mb-2 text-right font-semibold" style={{ color: "var(--text)" }}>
                {c.roast_level.replace(/_/g, " ")}
              </div>
              <RoastBar level={c.roast_level} />
            </div>
          )}
        </div>
      </div>

      {/* Tabbed detail sections */}
      <CoffeeDetailTabs
        coffee={c}
        history={history}
        stats={stats}
        taste={taste}
        similar={similarCoffees}
        tasteWheelJsx={tasteWheelJsx}
      />
    </div>
  );
}
