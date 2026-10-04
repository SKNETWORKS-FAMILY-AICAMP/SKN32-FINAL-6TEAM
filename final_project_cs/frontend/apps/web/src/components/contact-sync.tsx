"use client";

import { useEffect } from "react";
import { SESSION_CHANGED_EVENT } from "@/lib/live/client";
import { syncDiscordWebhook } from "@/lib/webhook";
import { useSettings } from "@/lib/settings";

/**
 * Sends a Discord webhook typed on the start screen once this browser has a session (`lib/webhook.ts` — it waits in page
 * memory only, because a webhook is a secret): when the app opens, and whenever the session is made or changed (the first trip
 * gives it). Draws nothing.
 */
export function ContactSync() {
  const { language } = useSettings();
  useEffect(() => {
    void syncDiscordWebhook(language);
    const again = () => { void syncDiscordWebhook(language); };
    addEventListener(SESSION_CHANGED_EVENT, again);
    return () => removeEventListener(SESSION_CHANGED_EVENT, again);
  }, [language]);
  return null;
}
