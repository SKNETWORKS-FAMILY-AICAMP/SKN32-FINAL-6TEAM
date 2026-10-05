"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { ContactSync } from "@/components/contact-sync";
import { ServerNotConnected } from "@/components/server-not-connected";
import { ConsentGate } from "@/features/consent/consent-gate";
import { OnboardingProvider } from "@/features/onboarding/onboarding-state";
import { DATA_MODE } from "@/lib/data-mode";
import { useSettings } from "@/lib/settings";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false }, mutations: { retry: false } } }));
  const { language, theme } = useSettings();
  useEffect(() => { document.documentElement.lang = language; }, [language]);
  // The layout's script set the saved theme before the first paint; this follows a change made in the menu.
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  // ★`[2026-10-03 사용자 지시]` No server connection (`NEXT_PUBLIC_DATA_MODE=live` missing) → this one screen, never an imitation of the app.
  if (DATA_MODE !== "live") return <ServerNotConnected />;
  return <QueryClientProvider client={client}><OnboardingProvider><ContactSync /><ConsentGate>{children}</ConsentGate></OnboardingProvider></QueryClientProvider>;
}
