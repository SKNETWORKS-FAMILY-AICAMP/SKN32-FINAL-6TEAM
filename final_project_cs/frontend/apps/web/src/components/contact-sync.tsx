"use client";

import { useEffect } from "react";
import { syncRecoveryEmail } from "@/lib/contact";
import { KEY_CHANGED_EVENT } from "@/lib/live/client";
import { useSettings } from "@/lib/settings";

/**
 * Keeps the recovery email in step with the server (`lib/contact.ts`): once when the app opens, and again whenever this
 * browser gets or changes its user key — an email typed before the first trip was registered goes up as soon as the key exists.
 * Draws nothing.
 */
export function ContactSync() {
  const { language } = useSettings();
  useEffect(() => {
    void syncRecoveryEmail(language);
    const again = () => void syncRecoveryEmail(language);
    addEventListener(KEY_CHANGED_EVENT, again);
    return () => removeEventListener(KEY_CHANGED_EVENT, again);
  }, [language]);
  return null;
}
