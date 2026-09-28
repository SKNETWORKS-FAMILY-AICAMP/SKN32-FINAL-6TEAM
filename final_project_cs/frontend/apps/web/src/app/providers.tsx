"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { OnboardingProvider } from "@/features/onboarding/onboarding-state";
import { useSettings } from "@/lib/settings";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false }, mutations: { retry: false } } }));
  const { language } = useSettings();
  useEffect(() => { document.documentElement.lang = language; }, [language]);
  return <QueryClientProvider client={client}><OnboardingProvider>{children}</OnboardingProvider></QueryClientProvider>;
}
