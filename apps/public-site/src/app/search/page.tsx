import { Suspense } from "react";
import SearchPageContent from "./search-content";

export const dynamic = 'force-dynamic';

export default function SearchPage() {
  return (
    <Suspense fallback={<SearchPageSkeleton />}>
      <SearchPageContent />
    </Suspense>
  );
}

function SearchPageSkeleton() {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", padding: "0 32px" }}>
      <div style={{ maxWidth: "880px", margin: "0 auto", paddingTop: "48px" }}>
        <div style={{ height: "20px", background: "var(--surface)", borderRadius: "8px", marginBottom: "16px", width: "60%" }} />
        <div style={{ height: "40px", background: "var(--surface)", borderRadius: "8px", marginBottom: "16px" }} />
        <div style={{ height: "80px", background: "var(--surface)", borderRadius: "12px", marginBottom: "24px" }} />
      </div>
    </div>
  );
}
