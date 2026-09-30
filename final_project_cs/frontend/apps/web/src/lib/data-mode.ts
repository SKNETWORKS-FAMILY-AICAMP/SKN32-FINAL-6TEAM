// ★`[2026-09-29 사용자 지시]` The web app runs on the real server. A missing setting no longer falls back to the
//   browser-local demo (it used to in development) — it says the server is not connected. The demo runs only when
//   a build asks for it by name (`NEXT_PUBLIC_DATA_MODE=demo`, used by the design team's screen tests).
export const DATA_MODE = process.env.NEXT_PUBLIC_DATA_MODE ?? "unconfigured";
