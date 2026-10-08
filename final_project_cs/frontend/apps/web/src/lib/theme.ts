/**
 * The colour theme: green (the default) or white (`data-theme="neutral"` on <html>). Both themes define the same roles in
 * `styles/tokens.css`. Not a client module: the root layout (a server component) needs the script below as a string.
 */
export type Theme = "green" | "neutral";
export const themes: readonly Theme[] = ["green", "neutral"];

/** Where `lib/settings.ts` keeps the menu choices, `theme` among them. */
export const settingsStorageKey = "tripilot.web.settings.v1";

/** Runs while the HTML is parsed: puts the saved theme on <html> before the first paint, so white does not flash green. */
export const themeScript = `(function(){try{var s=JSON.parse(localStorage.getItem(${JSON.stringify(settingsStorageKey)})||"null");if(s&&s.theme==="neutral")document.documentElement.dataset.theme="neutral"}catch(e){}})()`;
