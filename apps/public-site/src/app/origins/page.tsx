import { Suspense } from "react";
import OriginsContent from "./origins-content";

export default function OriginsPage() {
  return (
    <Suspense fallback={<OriginsSkeleton />}>
      <OriginsContent />
    </Suspense>
  );
}

function OriginsSkeleton() {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", padding: "32px" }}>
      <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
        <div style={{ height: "40px", background: "var(--surface)", borderRadius: "8px", marginBottom: "32px", width: "50%" }} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "16px" }}>
          {[...Array(6)].map((_, i) => (
            <div key={i} style={{ height: "250px", background: "var(--surface)", borderRadius: "8px" }} />
          ))}
        </div>
      </div>
    </div>
  );
}
