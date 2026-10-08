"use client";

import { useQuery } from "@tanstack/react-query";
import { getAuthProviders } from "@/lib/live/auth";
import { useSettings } from "@/lib/settings";

/**
 * Which social sign-in methods the server has set up (`GET /v1/web/auth/providers`). Asked once and kept for five minutes; no key is
 * needed (and none is created by asking). An error — most often an older server answering 404 — is kept as the error: the screen
 * tells "the server is not ready" from "no provider is set up" (an empty list).
 */
export function useAuthProviders(enabled = true) {
  const { language } = useSettings();
  return useQuery({ queryKey: ["auth-providers", language], queryFn: () => getAuthProviders(language), enabled, retry: false, staleTime: 5 * 60_000 });
}
