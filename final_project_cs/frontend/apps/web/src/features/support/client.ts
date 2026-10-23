import { api, API_BASE, refusal } from "@/lib/live/client";
import type { Language } from "@/lib/i18n";

export interface Inquiry {
  id: string; title: string; body: string; language: string; receivedAt: string; status: string;
  replies: { body: string; operator: string; at: string }[];
}
export interface ServiceNotice {
  id: string; kind: string; title: string; body: string; titleEn?: string; bodyEn?: string;
  startsAt?: string | null; endsAt?: string | null;
}
export interface ServiceStatus {
  notices: ServiceNotice[];
  maintenance: { enabled: boolean; message: string; messageEn?: string; endsAt?: string | null };
}
export const inquiries = (language: Language, before?: string) => api<{ inquiries: Inquiry[]; next?: string | null }>(`/v1/web/support/inquiries${before ? `?before=${encodeURIComponent(before)}` : ""}`, language);
export const createInquiry = (language: Language, draft: { title: string; body: string; requestId: string }) =>
  api<{ inquiry: Inquiry }>("/v1/web/support/inquiries", language, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...draft, language }) });

/** Public notices never create a guest session or send account credentials. */
export async function serviceStatus(language: Language): Promise<ServiceStatus> {
  const response = await fetch(`${API_BASE}/v1/web/support/notices`, { credentials: "omit", signal: AbortSignal.timeout(15_000) });
  if (!response.ok) throw await refusal(response, language);
  return response.json() as Promise<ServiceStatus>;
}

/** A notice on the board: posted now or ended (the server leaves out the scheduled ones and the operator's name). Times are Korean time as the admin app writes them. */
export interface BoardNotice extends ServiceNotice { startsAt: string; endsAt: string; status: "posted" | "ended" }

/**
 * `[2026-10-17 사용자 결정 — ST4F-604]` 공지사항 게시판 (`GET /v1/web/support/notices/board`) — posted first, then ended, each newest first (the server orders them).
 * `null`: an older server without it (404/405) — the board says it is not ready, never an empty list.
 */
export async function noticeBoard(language: Language): Promise<BoardNotice[] | null> {
  const response = await fetch(`${API_BASE}/v1/web/support/notices/board`, { credentials: "omit", signal: AbortSignal.timeout(15_000) });
  if (response.status === 404 || response.status === 405) return null;
  if (!response.ok) throw await refusal(response, language);
  return ((await response.json()) as { notices: BoardNotice[] }).notices;
}

/** Keep the same request identity after an uncertain response; a changed draft is a new inquiry. */
export function requestIdentity(previous: { fingerprint: string; requestId: string } | null, title: string, body: string, language: string,
  newId: () => string = () => crypto.randomUUID()) {
  const fingerprint = JSON.stringify([title.trim(), body.trim(), language]);
  return previous?.fingerprint === fingerprint ? previous : { fingerprint, requestId: newId() };
}
