import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Providers } from "./providers";
import "./globals.css";

// No static title: each screen sets it in the chosen language (useDocumentTitle), and a
// streamed metadata title would overwrite that after hydration.
export const metadata: Metadata = {
  description: "Add your travel plan, review the check results and follow your itinerary.",
  robots: { index: false, follow: false },
  // Without an icon every page asks for /favicon.ico and gets a 404, which shows up as a console error on all screens.
  icons: { icon: "/images/tripilot-traveler-icon.svg" },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="en"><body><Providers>{children}</Providers></body></html>;
}
