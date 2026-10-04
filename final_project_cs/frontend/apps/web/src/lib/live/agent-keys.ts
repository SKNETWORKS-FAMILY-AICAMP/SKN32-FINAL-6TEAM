import type { Language } from "../i18n";
import { api, LiveError } from "./client";

/**
 * `[2026-10-04 사용자 결정 · 서버 D-CS-012]` Agent keys (`/v1/web/agent-keys*`): the door a member opens for a personal AI (MCP, the user API) so it can work on THEIR trips only.
 *   - Only a signed-in member makes one, from the browser (cookie session + CSRF): a guest is refused (`403 member_only`, `login_required`), a call that is not the browser's
 *     is refused (`403 cookie_required`).
 *   - The key itself (`acop_a_…`) comes back ONCE, in the answer that makes it — the server keeps only a hash. So this side holds it in page memory for as long as the screen shows
 *     it and never writes it anywhere (no storage, no query cache).
 *   - A key lasts 1–90 days (default 90), reads only (`read`) or also writes (`write`), is revoked one by one, and at most ten are active at once (`409 agent_key_limit`).
 */
export type AgentScope = "read" | "write";
export type AgentKeyStatus = "active" | "expired" | "revoked";

export interface AgentKey {
  id: string;
  name: string;
  scope: AgentScope;
  createdAt: string | null;
  expiresAt: string | null;
  lastUsedAt: string | null;
  status: AgentKeyStatus;
}

/** The answer to making a key: the key once, and the server own sentence about keeping it. */
export interface CreatedAgentKey extends AgentKey { key: string; notice: string | null }

const text = (value: unknown): string | null => (typeof value === "string" && value.trim() ? value : null);
const STATUSES: readonly AgentKeyStatus[] = ["active", "expired", "revoked"];

export function agentKeyOf(entry: unknown): AgentKey | null {
  const row = (entry ?? {}) as Record<string, unknown>;
  const id = text(row.key_id), name = text(row.name);
  if (!id || !name) return null;
  return {
    id, name, scope: row.scope === "write" ? "write" : "read",
    createdAt: text(row.created_at), expiresAt: text(row.expires_at), lastUsedAt: text(row.last_used_at),
    // a status it does not know is treated as unusable, never as active
    status: STATUSES.find((value) => value === row.status) ?? "expired",
  };
}

export async function listAgentKeys(language: Language): Promise<AgentKey[]> {
  const body = await api<{ keys?: unknown }>("/v1/web/agent-keys", language);
  return (Array.isArray(body.keys) ? body.keys : []).map(agentKeyOf).filter((key): key is AgentKey => key !== null);
}

export async function createAgentKey(input: { name: string; scope: AgentScope; expiresDays?: number }, language: Language): Promise<CreatedAgentKey> {
  const body = await api<Record<string, unknown>>("/v1/web/agent-keys", language, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: input.name.trim(), scope: input.scope, ...(input.expiresDays ? { expires_days: input.expiresDays } : {}) }),
  });
  const key = text(body.key), summary = agentKeyOf(body);
  // A key the server did not hand over cannot be shown again: say so instead of showing an empty box.
  if (!key || !summary) throw new LiveError("bad_agent_key", "서버가 키를 주지 않았어요. 목록을 새로 읽어 보세요.");
  return { ...summary, status: "active", key, notice: text(body.notice) };
}

export async function revokeAgentKey(id: string, language: Language): Promise<void> {
  await api<unknown>(`/v1/web/agent-keys/${encodeURIComponent(id)}`, language, { method: "DELETE" });
}

/** The server has no such route yet (an older server: FastAPI 404 `{detail}` or 405) — the screen then says it is being prepared. */
export function isAgentKeysUnsupported(error: unknown): boolean {
  return error instanceof LiveError && ["HTTP_404", "HTTP_405", "method_not_allowed"].includes(error.code);
}

/** A guest asked for a member's door (`403 member_only`, `login_required: true`). */
export function isMemberOnly(error: unknown): boolean {
  return error instanceof LiveError && error.code === "member_only";
}

/**
 * The line that connects Claude Code to this server: the key goes in a header, never in the address (`claude mcp add --transport http …`).
 * `base` is the server address the page itself talks to.
 */
export function connectCommand(base: string, key: string): string {
  return `claude mcp add --transport http tripilot ${base.replace(/\/$/, "")}/mcp/ --header "Authorization: Bearer ${key}"`;
}
