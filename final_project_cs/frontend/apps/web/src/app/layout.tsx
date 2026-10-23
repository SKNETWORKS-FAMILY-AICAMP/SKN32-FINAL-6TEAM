import type { Metadata } from "next";
import type { ReactNode } from "react";
import { themeScript } from "@/lib/theme";
import { Providers } from "./providers";
import { ServiceNotices } from "@/features/support/service-notices";
import "./globals.css";

// No static title: each screen sets it in the chosen language (useDocumentTitle), and a
// streamed metadata title would overwrite that after hydration.
export const metadata: Metadata = {
  description: "Add your travel plan, review the check results and follow your itinerary.",
  robots: { index: false, follow: false },
  // Without an icon every page asks for /favicon.ico and gets a 404, which shows up as a console error on all screens.
  // `[2026-10-17 ST4F-610]` 구구루트 아이콘 — 탭은 작은 크기용 굵은 판(SVG), 휴대폰 홈 화면은 180px PNG(모서리는 휴대폰이 둥글린다).
  icons: { icon: "/images/guguroute-mark.svg", apple: "/images/guguroute-apple-touch-icon.png" },
};

// `suppressHydrationWarning`: the theme script may change `data-theme` on <html> before React hydrates it.
export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="ko" data-theme="green" suppressHydrationWarning>
    <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
    <body><Providers>{children}<ServiceNotices /></Providers></body>
  </html>;
}
