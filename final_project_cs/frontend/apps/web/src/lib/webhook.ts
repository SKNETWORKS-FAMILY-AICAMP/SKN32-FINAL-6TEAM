import { DATA_MODE } from "./data-mode";
import { translator, type Language } from "./i18n";
import { currentKey, LiveError } from "./live/client";
import { putProfile, type ServerProfile } from "./live/profile";

/**
 * The customer's Discord webhook for trip alerts (`PUT /v1/web/profile` `discord_webhook_url` — server 「고객 연락처」, 2026-10-01).
 *
 * ★A webhook address is a secret: whoever has it can post to that channel, and the server will later post to it. So it
 *   is never written to this browser's storage — the server keeps it encrypted and shows only a masked form.
 * ★Saving it before this browser has a user key (the first trip is not registered yet) would create a server user just
 *   for it. Typed on the start screen, it waits in this page's memory (`waiting`) and goes up as soon as the key exists
 *   (`syncDiscordWebhook`, run by `ContactSync`). A reload before that loses it — the start screen says so.
 * The server's second step — alerts about plan changes through the webhook — is not built yet; a test message is.
 */
let waiting: string | null = null;

export type WebhookSaved = { where: "server"; profile: ServerProfile } | { where: "waiting" };

/** Save (or with null/blank remove) the webhook. Rejects with the server's refusal (`invalid_webhook` …) or `live_only`. */
export async function saveDiscordWebhook(url: string | null, language: Language): Promise<WebhookSaved> {
  const value = url?.trim() || null;
  if (DATA_MODE !== "live") throw new LiveError("live_only", translator(language)("디스코드 웹훅은 실제 서버에 연결됐을 때만 저장할 수 있어요.", "A Discord webhook can be saved only when connected to the real server."));
  if (!currentKey()) {
    waiting = value;
    return { where: "waiting" };
  }
  const profile = await putProfile({ discordWebhookUrl: value }, language);
  waiting = null;
  return { where: "server", profile };
}

/** A webhook typed on the start screen is waiting for this browser's first user key. */
export function webhookWaiting(): boolean {
  return waiting !== null;
}

let sending: Promise<void> | null = null;

/**
 * Send a waiting webhook once there is a user key. Silent: a refused one is dropped, any other failure tries again at the
 * next key change. ★A new key announces itself twice (the key, then its notice) — calls meanwhile share one request.
 */
export function syncDiscordWebhook(language: Language): Promise<void> {
  if (DATA_MODE !== "live" || !currentKey() || waiting === null) return Promise.resolve();
  sending ??= (async () => {
    const value = waiting;
    try {
      await putProfile({ discordWebhookUrl: value }, language);
      if (waiting === value) waiting = null;
    } catch (error) {
      if (error instanceof LiveError && error.code === "invalid_webhook" && waiting === value) waiting = null;
    }
  })().finally(() => { sending = null; });
  return sending;
}
