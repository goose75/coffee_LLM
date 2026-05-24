import { Suspense } from "react";
import FlavourAtlasContent from "./flavour-atlas-content";

export const dynamic = 'force-dynamic';

export default function FlavourAtlasPage() {
  return (
    <Suspense fallback={<FlavourAtlasSkeleton />}>
      <FlavourAtlasContent />
    </Suspense>
  );
}

function FlavourAtlasSkeleton() {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", padding: "32px" }}>
      <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
        <div style={{ height: "40px", background: "var(--surface)", borderRadius: "8px", marginBottom: "32px", width: "60%" }} />
        <div style={{ height: "300px", background: "var(--surface)", borderRadius: "8px" }} />
      </div>
    </div>
  );
}
