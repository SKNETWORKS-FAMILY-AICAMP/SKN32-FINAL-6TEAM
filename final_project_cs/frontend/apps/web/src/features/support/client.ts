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
export const inquiries = (language: Language) => api<{ inquiries: Inquiry[] }>("/v1/web/support/inquiries", language);
export const createInquiry = (language: Language, draft: { title: string; body: string; requestId: string }) =>
  api<{ inquiry: Inquiry }>("/v1/web/support/inquiries", language, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...draft, language }) });

/** Public notices never create a guest session or send account credentials. */
export async function serviceStatus(language: Language): Promise<ServiceStatus> {
  const response = await fetch(`${API_BASE}/v1/web/support/notices`, { credentials: "omit", signal: AbortSignal.timeout(15_000) });
  if (!response.ok) throw await refusal(response, language);
  return response.json() as Promise<ServiceStatus>;
}

/** Keep the same request identity after an uncertain response; a changed draft is a new inquiry. */
export function requestIdentity(previous: { fingerprint: string; requestId: string } | null, title: string, body: string, language: string,
  newId: () => string = () => crypto.randomUUID()) {
  const fingerprint = JSON.stringify([title.trim(), body.trim(), language]);
  return previous?.fingerprint === fingerprint ? previous : { fingerprint, requestId: newId() };
}
