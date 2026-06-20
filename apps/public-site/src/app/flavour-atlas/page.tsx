import dynamic from "next/dynamic";

const FlavourAtlasClient = dynamic(() => import("./flavour-atlas-client"), { ssr: false });

export default function Page() {
  return <FlavourAtlasClient />;
}
