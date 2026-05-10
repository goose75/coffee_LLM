import type { Metadata, Viewport } from "next";
import { Cormorant_Garamond, DM_Sans } from "next/font/google";
import "./globals.css";
import AppBar from "@/components/AppBar";
import BottomTabBar from "@/components/BottomTabBar";
import AssistantPanel from "@/components/AssistantPanel";
import { CompareProvider } from "@/components/CompareContext";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["300", "400", "500", "600"],
  style: ["normal", "italic"],
  display: "swap",
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["300", "400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Grounds — UK Specialty Coffee", template: "%s | Grounds" },
  description: "Browse and compare specialty coffees from 200+ UK roasters. Track prices, discover new releases, explore origins.",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "Grounds" },
  formatDetection: { telephone: false },
  openGraph: {
    type: "website", siteName: "Grounds",
    title: "Grounds — UK Specialty Coffee",
    description: "Browse and compare specialty coffees from 200+ UK roasters.",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f5f0" },
    { media: "(prefers-color-scheme: dark)", color: "#0f0e0c" },
  ],
  width: "device-width", initialScale: 1, maximumScale: 1,
  userScalable: false, viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${cormorant.variable} ${dmSans.variable}`} suppressHydrationWarning>
      <head>
        <link rel="apple-touch-icon" href="/icon-192.png" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        <meta name="apple-mobile-web-app-title" content="Grounds" />
      </head>
      <body className="flex flex-col transition-colors duration-200"
        style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}>
        <CompareProvider>
          <AppBar />
          <main className="flex-1 fade-in">{children}</main>
          <AssistantPanel />
          <BottomTabBar />
        </CompareProvider>
        <script dangerouslySetInnerHTML={{
          __html: `(function(){try{var t=localStorage.getItem('theme');if(t==='dark'||(!t&&matchMedia('(prefers-color-scheme:dark)').matches)){document.documentElement.classList.add('dark')}}catch(e){}})();`,
        }} />
      </body>
    </html>
  );
}
