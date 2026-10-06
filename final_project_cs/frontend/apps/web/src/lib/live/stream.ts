import { translator, type Language, type Translate } from "../i18n";
import { API_BASE, answerWithin, LiveError, refusal, sessionChecked, sessionInit } from "./client";
import { eventStreamParser } from "./events";
import { beginWait, TASK_STEPS } from "./waiting";

/**
 * Live progress of the server's long tasks (`[2026-10-02]` server `op_stream.py`, REST spec 「웹 실시간 진행 (SSE)」).
 *
 * The chat (`POST …/messages`) and 「plan it for me」 (`POST …/trip-intakes/{id}/plan`) answer as a stream when asked with
 * `Accept: text/event-stream`: `accepted` → `stage` / `beat` (every 3 s, even while the server waits on the model) →
 * `result` (the same body as the JSON answer) | `error`. Reading an intake has its own stream (`watchIntake`).
 *
 * What the screen does with it (the server only gives the material):
 *   - shows the stage the server says it is in, and how long it has taken; `slow` → 「the model is slow」;
 *   - ★no event for two beats → the line or the server is down: 「reconnecting」, and the same request goes again —
 *     the server knows its `request_id` and does not act twice (chat answers `duplicate` with the earlier answer,
 *     planning returns the trip it already registered);
 *   - `error` → the server's reason; a refusal before the stream opens is the usual JSON error.
 * A server without streams answers the request once in JSON, as before — this reads both.
 */

export interface OpProgress {
  /** The stage the server says it is in (`received`, `understanding`, `planning` …), or null before it says one. */
  stage: string | null;
  /** Seconds since the server took the request, by the server's clock. */
  elapsed: number;
  /** The server waits on the model or a place lookup longer than usual (`beat.slow`). */
  slow: boolean;
  /** No sign of life for two beats: the line or the server is down, and the request is being sent again. */
  lost: boolean;
}

export interface StreamTiming {
  /** No event for this long = lost. The server beats every 3 s, so two beats and a margin. */
  watchdogMs: number;
  /** Waits before each reconnect; when they run out the call fails with `connection_lost`. */
  reconnectMs: readonly number[];
}

export const STREAM_TIMING: StreamTiming = { watchdogMs: 7_000, reconnectMs: [1_000, 2_000, 4_000] };

type Body = Record<string, unknown>;

function parse(data: string): Body {
  try {
    const value: unknown = data ? JSON.parse(data) : {};
    return value && typeof value === "object" && !Array.isArray(value) ? value as Body : {};
  } catch {
    return {};
  }
}

const seconds = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value : null;

/** The server's `error` event → the same kind of error a refused JSON call gives (its code, sentence and body). */
function streamError(body: Body, t: Translate): LiveError {
  const code = typeof body.code === "string" && body.code ? body.code : "error";
  const message = typeof body.message === "string" && body.message ? body.message : t("요청을 처리하지 못했어요.", "The request failed.");
  return new LiveError(code, message, body);
}

type Attempt<T> = { kind: "done"; value: T } | { kind: "lost" };

async function attempt<T>(path: string, language: Language, init: RequestInit, timing: StreamTiming,
  report: (next: Partial<OpProgress>) => void): Promise<Attempt<T>> {
  const t = translator(language);
  const sent = await sessionInit(language, { ...init, headers: { ...(init.headers as Record<string, string> | undefined), Accept: "text/event-stream" } });
  const url = `${API_BASE}${path}`;
  const controller = new AbortController();
  // ★Until the answer starts, the usual limit holds — a server without streams answers once, after the whole task.
  let headerTimeout = false;
  const headerLimit = setTimeout(() => { headerTimeout = true; controller.abort(); }, answerWithin(url));
  let response: Response;
  try {
    response = await fetch(url, { ...sent, cache: "no-store", signal: controller.signal });
  } catch {
    clearTimeout(headerLimit);
    if (headerTimeout) throw new LiveError("timeout", t("서버가 응답하지 않아요. 잠시 뒤 다시 시도해 주세요.", "The server is not answering. Please try again shortly."));
    return { kind: "lost" };
  }
  clearTimeout(headerLimit);
  if (!response.ok) throw sessionChecked(await refusal(response, language), language);
  if (!(response.headers.get("content-type") ?? "").includes("text/event-stream") || !response.body) {
    return { kind: "done", value: await response.json() as T };
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  const end: { event: { name: "result" | "error"; body: Body } | null } = { event: null };
  let watchdog: ReturnType<typeof setTimeout> | undefined;
  const arm = () => {
    clearTimeout(watchdog);
    watchdog = setTimeout(() => { controller.abort(); void reader.cancel().catch(() => undefined); }, timing.watchdogMs);
  };
  const feed = eventStreamParser((name, data) => {
    arm();
    const body = parse(data);
    if (name === "accepted") report({ lost: false });
    else if (name === "stage") report({ stage: typeof body.stage === "string" ? body.stage : null, elapsed: seconds(body.elapsed) ?? 0, slow: false, lost: false });
    else if (name === "beat") report({ ...(typeof body.stage === "string" ? { stage: body.stage } : {}), elapsed: seconds(body.elapsed) ?? 0, slow: body.slow === true, lost: false });
    else if (name === "result" || name === "error") end.event = { name, body };
  });
  arm();
  try {
    while (!end.event) {
      const { value, done } = await reader.read();
      if (done) break;
      feed(value);
    }
  } catch {
    // the watchdog cut a silent line, or the line dropped: the same request goes again
  } finally {
    clearTimeout(watchdog);
    if (end.event) void reader.cancel().catch(() => undefined);
  }
  if (end.event?.name === "result") return { kind: "done", value: end.event.body as T };
  if (end.event?.name === "error") throw streamError(end.event.body, t);
  return { kind: "lost" };
}

/**
 * A long request with live progress. Resolves with the server's result (the same body as its JSON answer); rejects with
 * the server's refusal or `error` event, or `connection_lost` when the reconnects run out. `init` is sent again unchanged
 * on a reconnect — it must carry the request's own id (or the server must derive one) so nothing runs twice.
 */
export async function streamApi<T>(path: string, language: Language, init: RequestInit, onProgress?: (progress: OpProgress) => void,
  timing: StreamTiming = STREAM_TIMING): Promise<T> {
  let progress: OpProgress = { stage: null, elapsed: 0, slow: false, lost: false };
  // ★`[2026-10-06 사용자 지적]` A task that shows no new stage for long is told to the customer (`waiting.ts`): a heartbeat alone does not start the count over.
  const wait = beginWait(TASK_STEPS);
  const report = (next: Partial<OpProgress>) => {
    if ((next.stage !== undefined && next.stage !== progress.stage) || (next.lost !== undefined && next.lost !== progress.lost)) wait.touch();
    progress = { ...progress, ...next };
    onProgress?.(progress);
  };
  try {
    for (let tries = 0; ; tries += 1) {
      const outcome = await attempt<T>(path, language, init, timing, report);
      if (outcome.kind === "done") return outcome.value;
      if (tries >= timing.reconnectMs.length) {
        const t = translator(language);
        throw new LiveError("connection_lost", t("서버와 연결이 끊겼어요. 다시 보내면 같은 요청으로 이어서 확인해요.", "The connection to the server was lost. Sending again continues the same request."));
      }
      report({ lost: true });
      await new Promise((resolve) => setTimeout(resolve, timing.reconnectMs[tries]));
    }
  } finally { wait.end(); }
}

/** The server's stage names (`op_stream.STAGES` and the intake's) in the customer's language. Unknown names show as they are. */
const STAGES: Record<string, [string, string]> = {
  received: ["요청을 받았어요", "Request received"],
  reading: ["여행 일정을 읽는 중이에요", "Reading your trip"],
  understanding: ["요청을 이해하는 중이에요", "Understanding your request"],
  classifying: ["요청 종류를 가려내는 중이에요", "Sorting out your request"],
  extracting: ["요청 내용을 정리하는 중이에요", "Organizing your request"],
  looking_up: ["장소 정보를 확인하는 중이에요", "Checking place details"],
  planning: ["일정을 짜는 중이에요", "Planning your days"],
  checking: ["조건을 확인하는 중이에요", "Checking the conditions"],
  applying: ["일정에 반영하는 중이에요", "Updating your plan"],
  registering: ["여행으로 등록하는 중이에요", "Registering your trip"],
  writing: ["답을 정리하는 중이에요", "Writing the reply"],
};

/** One line for the waiting screen: what the server is doing and for how long, or that the line is being restored. */
export function progressText(progress: OpProgress | null, t: Translate, waiting: [string, string]): string {
  if (progress?.lost) return t("서버와 연결이 끊겼어요 — 다시 연결하는 중이에요…", "Lost the connection to the server — reconnecting…");
  if (!progress?.stage) return t(...waiting);
  const [ko, en] = STAGES[progress.stage] ?? [progress.stage, progress.stage];
  const elapsed = Math.round(progress.elapsed);
  if (progress.slow) return t(`${ko} · 응답이 느려요 (${elapsed}초째)`, `${en} · the reply is slow (${elapsed} s)`);
  return elapsed >= 1 ? t(`${ko}… (${elapsed}초)`, `${en}… (${elapsed} s)`) : t(`${ko}…`, `${en}…`);
}

export type IntakeWatchEvent = { type: "progress"; stage: string | null; elapsed: number; slow: boolean } | { type: "done" };
/**
 * How a watch of an intake's reading ended: `done` (read — review, confirmed or fatal), `stalled` (the server says the
 * reading stopped: its worker died), `gone` (no such intake), `unsupported` (no stream here: 404/405, or the per-user
 * stream limit — the screen re-reads on a timer instead), `lost` (silent or dropped: reconnect), `closed` (we stopped).
 */
export type IntakeWatchEnd = "done" | "stalled" | "gone" | "unsupported" | "lost" | "closed";

/**
 * The events that carry what the server has checked so far (`line` · `item` · `check` · `move` · `progress` · `done`, copies of state —
 * `intake-events.ts` reads them). They are handed on as they come; this function only follows the stage.
 */
export const INTAKE_CONTENT_EVENTS: ReadonlySet<string> = new Set(["line", "item", "check", "move", "progress", "done"]);
export type IntakeContentHandler = (name: string, data: string) => void;

/**
 * Follow an intake while the server reads it (`GET /v1/web/trip-intakes/{id}/events`). The stage events tell the screen to
 * read the intake again with the GET it already has; the content events (`onContent`) carry the checks that are not in
 * that GET until the check is done. Never throws.
 */
export async function watchIntake(intakeId: string, language: Language, onEvent: (event: IntakeWatchEvent) => void, signal: AbortSignal,
  timing: StreamTiming = STREAM_TIMING, onContent?: IntakeContentHandler): Promise<IntakeWatchEnd> {
  const controller = new AbortController();
  const stop = () => controller.abort();
  signal.addEventListener("abort", stop, { once: true });
  let watchdog: ReturnType<typeof setTimeout> | undefined;
  try {
    let response: Response;
    try {
      response = await fetch(`${API_BASE}/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/events`, await sessionInit(language, {
        headers: { Accept: "text/event-stream" }, cache: "no-store", signal: controller.signal,
      }));
    } catch {
      return signal.aborted ? "closed" : "lost";
    }
    if (!response.ok || !response.body || !(response.headers.get("content-type") ?? "").includes("text/event-stream")) return "unsupported";
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
    const end: { value: IntakeWatchEnd | null } = { value: null };
    const arm = () => { clearTimeout(watchdog); watchdog = setTimeout(() => { stop(); void reader.cancel().catch(() => undefined); }, timing.watchdogMs); };
    const feed = eventStreamParser((name, data) => {
      arm();
      const body = parse(data);
      const state = body.state && typeof body.state === "object" ? body.state as Body : {};
      const stage = typeof body.stage === "string" ? body.stage : typeof state.stage === "string" ? state.stage : null;
      if (name === "accepted" || name === "stage" || name === "beat") onEvent({ type: "progress", stage, elapsed: seconds(body.elapsed) ?? 0, slow: body.slow === true });
      else if (name === "result") { onEvent({ type: "done" }); end.value = "done"; }
      else if (INTAKE_CONTENT_EVENTS.has(name)) onContent?.(name, data);
      else if (name === "error") end.value = body.code === "stalled" ? "stalled" : body.code === "not_found" ? "gone" : "lost";
    });
    arm();
    try {
      while (!end.value) {
        const { value, done } = await reader.read();
        if (done) break;
        feed(value);
      }
    } catch { /* cut by the watchdog or by `signal`, or the line dropped */ }
    void reader.cancel().catch(() => undefined);
    return end.value ?? (signal.aborted ? "closed" : "lost");
  } finally {
    clearTimeout(watchdog);
    signal.removeEventListener("abort", stop);
  }
}
