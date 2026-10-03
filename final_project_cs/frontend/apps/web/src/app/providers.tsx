"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { ContactSync } from "@/components/contact-sync";
import { OnboardingProvider } from "@/features/onboarding/onboarding-state";
import { useSettings } from "@/lib/settings";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false }, mutations: { retry: false } } }));
  const { language, theme } = useSettings();
  useEffect(() => { document.documentElement.lang = language; }, [language]);
  // The layout's script set the saved theme before the first paint; this follows a change made in the menu.
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  return <QueryClientProvider client={client}><OnboardingProvider><ContactSync />{children}</OnboardingProvider></QueryClientProvider>;
}
