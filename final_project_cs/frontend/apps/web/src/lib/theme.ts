/**
 * The colour theme: green or dark (`data-theme="dark"` on <html>). `[2026-10-17 사용자 결정 · ST4F-610]` Dark took the white theme's place, and
 * by default ("system") the device's light/dark setting picks between the two; the menu's theme card can fix one. Both themes define the same
 * roles in `styles/tokens.css`. Not a client module: the root layout (a server component) needs the script below as a string.
 */
export type Theme = "system" | "green" | "dark";
export type AppliedTheme = Exclude<Theme, "system">;
export const themes: readonly Theme[] = ["system", "green", "dark"];

/** The device asks for dark. */
export const darkQuery = "(prefers-color-scheme: dark)";
export const appliedTheme = (theme: Theme, deviceDark: boolean): AppliedTheme => (theme === "system" ? (deviceDark ? "dark" : "green") : theme);

/** Where `lib/settings.ts` keeps the menu choices, `theme` among them. */
export const settingsStorageKey = "tripilot.web.settings.v1";

/**
 * Runs while the HTML is parsed: puts the theme on <html> before the first paint, so dark does not flash green. No choice — or the white
 * theme saved before 2026-10-17 (`neutral`) — follows the device, like `appliedTheme`.
 */
export const themeScript = `(function(){var t;try{t=(JSON.parse(localStorage.getItem(${JSON.stringify(settingsStorageKey)})||"null")||{}).theme}catch(e){}if(t!=="green"&&t!=="dark")t=window.matchMedia&&matchMedia(${JSON.stringify(darkQuery)}).matches?"dark":"green";document.documentElement.dataset.theme=t})()`;
