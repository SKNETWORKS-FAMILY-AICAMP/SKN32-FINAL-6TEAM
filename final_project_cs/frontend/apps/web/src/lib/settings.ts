"use client";

import { useMemo, useSyncExternalStore } from "react";
import { translator, type Language, type Translate } from "./i18n";

export type TripNavigation = "fixed" | "floating";

export interface Settings {
  language: Language;
  navigation: TripNavigation;
}

const storageKey = "tripilot.web.settings.v1";
const defaults: Settings = { language: "en", navigation: "fixed" };
const listeners = new Set<() => void>();
let current: Settings | null = null;

function read(): Settings {
  if (current) return current;
  current = defaults;
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey) ?? "null") as Partial<Settings> | null;
    current = {
      language: stored?.language === "ko" || stored?.language === "en" ? stored.language : defaults.language,
      navigation: stored?.navigation === "floating" || stored?.navigation === "fixed" ? stored.navigation : defaults.navigation,
    };
  } catch {
    // Settings are a per-browser convenience; unreadable storage keeps the defaults.
  }
  return current;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function updateSettings(next: Partial<Settings>) {
  current = { ...read(), ...next };
  try { localStorage.setItem(storageKey, JSON.stringify(current)); }
  catch { /* The choice still applies to this page when storage is unavailable. */ }
  listeners.forEach((listener) => listener());
}

/** Server rendering and hydration use the defaults; the saved choice applies right after. */
export function useSettings(): Settings {
  return useSyncExternalStore(subscribe, read, () => defaults);
}

export function useT(): Translate {
  const { language } = useSettings();
  return useMemo(() => translator(language), [language]);
}
