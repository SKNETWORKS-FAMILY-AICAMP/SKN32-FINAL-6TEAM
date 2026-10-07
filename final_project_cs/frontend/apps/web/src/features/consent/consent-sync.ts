import { hasSession } from "@/lib/live/client";
import type { Language } from "@/lib/i18n";
import { getServerConsents, isConsentsUnsupported, isTermsVersionChanged, postServerConsents, type ConsentChoice, type ServerConsents } from "@/lib/live/consents";
import { CONSENT_CODES, noConsents, requiredAgreed, type ConsentMap } from "./consent-model";
import { consentedAt, consentsSynced, markConsentsSynced, readConsents, replaceConsents } from "./consent-store";
import { loadLiveTerms, termsDocs, termsVersion } from "./terms-live";
import { docHash, sha256Hex } from "./terms-text";

/**
 * `[2026-10-05 사용자 지시]` 이 브라우저의 동의 사본과 서버의 동의 기록을 맞춘다. 서버가 정본이다.
 *   - `sendConsents`: 고객이 고른 것을 서버에 기록한다(세션이 없으면 이때 게스트 세션이 만들어진다 - 고객이 동의한 뒤라 만들어도 되는 때다).
 *   - `reconcileConsents`: 앱이 열릴 때·서버가 `consent_required` 라고 할 때·로그인한 뒤에 서버 기록을 읽어 사본을 맞춘다.
 * 서버가 동의 기록을 모르는 옛 서버면(404) 이 브라우저의 사본만 쓴다(`local_only`).
 */
export type SendResult = "recorded" | "local_only" | "outdated" | "failed";
export type ReconcileResult = "ok" | "needs" | "local_only" | "outdated" | "failed";

const hashes = new Map<string, Promise<string>>();

/** 동의할 때 보여 준 한국어 전문의 지문. 약관 글이 아직 없는 항목은 빈 글의 지문. 버전마다 따로 센다 — 보관 기간 문장이 바뀌면 글도 바뀐다. */
function hashOf(code: string): Promise<string> {
  const key = `${termsVersion()}|${code}`;
  let found = hashes.get(key);
  if (!found) {
    const doc = termsDocs().find((entry) => entry.code === code);
    found = doc ? docHash(doc) : sha256Hex("");
    hashes.set(key, found);
  }
  return found;
}

export async function choicesOf(map: ConsentMap): Promise<ConsentChoice[]> {
  return Promise.all(CONSENT_CODES.map(async (code) => ({ code, agreed: map[code], textSha256: await hashOf(code) })));
}

/** 서버가 이 약관 버전에 대해 갖고 있는 동의로 이 브라우저의 사본을 바꾼다(서버가 이긴다). */
export function adoptServer(server: ServerConsents): ConsentMap {
  const map = noConsents();
  let at: string | null = null;
  for (const item of server.items) {
    if (item.version !== termsVersion()) continue;
    map[item.code] = item.agreed;
    if (item.agreedAt && (!at || item.agreedAt > at)) at = item.agreedAt;
  }
  replaceConsents(map, at ?? new Date().toISOString(), true);
  return map;
}

/**
 * 맞춤 작업은 한 줄로 선다 - 읽어 온 서버 기록이 방금 고른 동의를 덮어쓰거나, 같은 동의가 두 번 기록되는 일(기록은 추가만 한다)이 없게.
 */
let queue: Promise<unknown> = Promise.resolve();
function serial<T>(job: () => Promise<T>): Promise<T> {
  const run = queue.then(job, job);
  queue = run.catch(() => undefined);
  return run;
}

/** 지금 사본(`readConsents`)을 서버에 기록한다. 실패해도 사본은 남아 있고 `synced` 가 false 라 다음에 다시 보낸다. */
export function sendConsents(language: Language): Promise<SendResult> {
  return serial(() => sendNow(language));
}

async function sendNow(language: Language): Promise<SendResult> {
  await loadLiveTerms(language);
  const map = readConsents();
  const version = termsVersion();
  try {
    const server = await postServerConsents(version, await choicesOf(map), language);
    if (server.items.some((item) => item.version === version)) adoptServer(server);
    else markConsentsSynced();
    return "recorded";
  } catch (error) {
    if (isConsentsUnsupported(error)) { markConsentsSynced(); return "local_only"; }
    if (isTermsVersionChanged(error)) { await loadLiveTerms(language, true); return "outdated"; }   // 그사이 관리자가 보관 기간을 고쳤다: 새 약관을 읽어 다시 동의 받는다
    return "failed";
  }
}

/** 고객이 동의를 바꿨다(처음 동의, 또는 선택 항목을 켜고 끔): 사본을 바꾸고 서버에 기록한다. */
export function saveConsents(next: ConsentMap, language: Language): Promise<SendResult> {
  replaceConsents(next, new Date().toISOString(), false);                       // 화면은 바로 따라간다
  return serial(async () => {
    replaceConsents(next, new Date().toISOString(), false);                     // 앞서 돌던 맞춤이 서버의 옛 값으로 덮었더라도 방금 고른 것이 이긴다
    return sendNow(language);
  });
}

/**
 * 서버 기록을 읽어 사본을 맞춘다.
 *   - 이 브라우저에 세션이 없으면 서버에 물을 사람이 없다(묻기만 해도 사용자가 만들어진다): 사본이 정한다.
 *   - 서버에 **지금 버전의** 기록이 하나라도 있으면 서버가 이긴다(다른 기기에서 철회했을 수 있다).
 *   - 없으면 사본이 정한다: 필수가 모두 있으면 보낸다(오프라인에서 고르고 온 경우), 없으면 약관 화면이 필요하다.
 */
export function reconcileConsents(language: Language): Promise<ReconcileResult> {
  return serial(() => reconcileNow(language));
}

async function reconcileNow(language: Language): Promise<ReconcileResult> {
  await loadLiveTerms(language);
  const local = readConsents();
  const localAgreed = requiredAgreed(local);
  try {
    if (!await hasSession(language)) return localAgreed ? "ok" : "needs";
    const server = await getServerConsents(language);
    if (server.currentVersion && server.currentVersion !== termsVersion()) {
      await loadLiveTerms(language, true);                                      // 버전이 바뀐 줄 모르고 있었다: 서버 약관을 다시 읽는다
      if (server.currentVersion !== termsVersion()) return "outdated";
    }
    if (server.items.some((item) => item.version === termsVersion())) {
      adoptServer(server);
      return server.ok ? "ok" : "needs";
    }
    if (!localAgreed) return "needs";
    const sent = await sendNow(language);
    return sent === "recorded" ? "ok" : sent === "local_only" ? "local_only" : sent === "outdated" ? "outdated" : "failed";
  } catch (error) {
    if (isConsentsUnsupported(error)) return localAgreed ? "local_only" : "needs";
    return localAgreed ? "failed" : "needs";
  }
}

/** 서버에 아직 보내지 못한 동의가 있나(보내야 하는데 안 보낸 것). */
export function consentsUnsent(): boolean {
  return requiredAgreed(readConsents()) && !consentsSynced();
}

export { consentedAt };
