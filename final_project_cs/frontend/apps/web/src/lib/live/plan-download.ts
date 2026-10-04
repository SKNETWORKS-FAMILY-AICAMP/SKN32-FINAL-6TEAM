/**
 * `[2026-10-04 사용자 결정 · 서버]` 계획서 내려받기: the trip plan link (`plan_url`, `GET /plan/{id}?t=…`) with `download=1` added is the same page sent as a file
 * (`Content-Disposition: attachment`, `triPilot-<제목>.html`, one HTML file that opens alone, no login). A guest's server data is deleted after some hours and the session
 * ends with the window, so this is how a guest keeps the plan.
 */
export function planDownloadUrl(planUrl: string): string | null {
  try {
    const url = new URL(planUrl);
    if (url.protocol !== "https:" && url.protocol !== "http:") return null;
    url.searchParams.set("download", "1");
    return url.toString();
  } catch {
    return null;
  }
}
