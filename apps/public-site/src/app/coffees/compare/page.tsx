import { Suspense } from "react";
import ComparePageContent from "./compare-content";

export default function ComparePage() {
  return (
    <Suspense fallback={<ComparePageSkeleton />}>
      <ComparePageContent />
    </Suspense>
  );
}

function ComparePageSkeleton() {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "32px" }}>
        <div style={{ height: "20px", background: "var(--surface)", borderRadius: "8px", marginBottom: "16px", width: "40%" }} />
        <div style={{ height: "40px", background: "var(--surface)", borderRadius: "8px", marginBottom: "32px" }} />
        <div style={{ height: "300px", background: "var(--surface)", borderRadius: "8px" }} />
      </div>
    </div>
  );
}
