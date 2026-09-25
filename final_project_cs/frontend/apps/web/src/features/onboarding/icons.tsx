import type { CSSProperties } from "react";

/** The check that draws itself when an option is chosen. */
export function DrawnCheck({ className = "" }: { className?: string }) {
  return <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path pathLength={1} d="m3 8 3 3 7-7" /></svg>;
}

const paths: Record<string, string> = {
  down: "m4 6 4 4 4-4",
  arrow: "M3 8h10M9 4l4 4-4 4",
  lock: "M5 7V5a3 3 0 0 1 6 0v2M5 7h6a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z",
  leaf: "M13 2C5 1 1 5 3 11c5 4 10 0 10-9ZM2 14l8-9",
  food: "M4 2v5m-2-5v3c0 3 4 3 4 0V2M4 8v6M11 2v12M11 2c-3 1-4 6 0 6",
  nature: "m1 13 5-9 4 9H1Zm7 0 4-6 3 6H8ZM12 2a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z",
  culture: "m2 5 6-3 6 3H2Zm1 3v4m5-4v4m5-4v4M1 14h14",
  activity: "m2 13 4-6 3 3 5-8M10 2h4v4",
  shopping: "M3 6h10l1 8H2l1-8ZM5 6V4a3 3 0 0 1 6 0v2",
  local: "m1 7 7-5 7 5M3 6v8h10V6M6 14v-4h4v4",
  public: "M6 1h4a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V4a3 3 0 0 1 3-3ZM3 7h10M5 13l-1 2m7-2 1 2M6 10h0m4 0h0",
  walk: "M9 1a1 1 0 1 0 0 2 1 1 0 0 0 0-2ZM5 7l3-3 2 3 3 1M8 5l-2 5-3 4m4-4 4 4",
  car: "m2 7 2-4h8l2 4M2 7h12v6H2V7Zm2 6v2m8-2v2M4 10h1m6 0h1",
  taxi: "m2 7 2-4h8l2 4M2 7h12v6H2V7Zm2 6v2m8-2v2M6 1h4M4 10h1m6 0h1",
};

/** Line icons of the onboarding mockup; unknown names use the leaf, as in the mockup. */
export function OnboardingIcon({ name, size = 16, style }: { name: string; size?: number; style?: CSSProperties }) {
  return <svg width={size} height={size} style={style} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] ?? paths.leaf} /></svg>;
}
