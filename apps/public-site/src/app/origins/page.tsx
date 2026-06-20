import dynamic from "next/dynamic";

const OriginsPageClient = dynamic(() => import("./origins-client"), { ssr: false });

export default function Page() {
  return <OriginsPageClient />;
}
