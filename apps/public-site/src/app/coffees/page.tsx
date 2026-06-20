import dynamic from "next/dynamic";

const BrowsePageClient = dynamic(() => import("./coffees-client"), { ssr: false });

export default function Page() {
  return <BrowsePageClient />;
}
