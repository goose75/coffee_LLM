import dynamic from "next/dynamic";

const SearchPageClient = dynamic(() => import("./search-client"), { ssr: false });

export default function Page() {
  return <SearchPageClient />;
}
