import dynamic from "next/dynamic";

const ComparePageClient = dynamic(() => import("./compare-client"), { ssr: false });

export default function Page() {
  return <ComparePageClient />;
}
