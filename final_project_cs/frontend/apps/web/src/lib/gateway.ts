import type { TripGateway } from "../features/trip/model";
import { createLiveGateway } from "./live/gateway";
import { GatewayError } from "./gateway-errors";
import { DATA_MODE } from "./data-mode";
import { translator, type Language } from "./i18n";

export { GatewayError, isGatewayError } from "./gateway-errors";

// Production builds must explicitly opt into demo mode. An unavailable live
// adapter must never make fabricated successful responses by falling back.
export { DATA_MODE } from "./data-mode";

function unavailable(language: Language): Promise<never> {
  const t = translator(language);
  return Promise.reject(new GatewayError("DATA_MODE_UNAVAILABLE", t("실제 서버 연결이 설정되지 않았어요. .env.local 에 NEXT_PUBLIC_DATA_MODE=live 와 NEXT_PUBLIC_API_BASE 를 적고 다시 실행해 주세요.", "The real server is not configured. Set NEXT_PUBLIC_DATA_MODE=live and NEXT_PUBLIC_API_BASE in .env.local and restart.")));
}

const unavailableGateway: TripGateway = {
  createTrip: (_input, language) => unavailable(language),
  listTrips: (language) => unavailable(language),
  getTrip: (_tripId, language) => unavailable(language),
  retryVerification: (_tripId, language) => unavailable(language),
  startTrip: (_tripId, language) => unavailable(language),
  sendMessage: (_tripId, _message, language) => unavailable(language),
};

/**
 * ★`[2026-09-29 사용자 지시]` The real app must run without any test imitation code. The browser-local demo
 * (`lib/demo` — imitation data for the design team's screen tests) is loaded **only** when a build names
 * `NEXT_PUBLIC_DATA_MODE=demo`, as a separate chunk; a live build never downloads or runs it.
 */
function demoGateway(): TripGateway {
  let loaded: Promise<TripGateway> | null = null;
  const demo = () => (loaded ??= import("./demo").then((module) => module.createDemoGateway()));
  return {
    createTrip: (input, language) => demo().then((gateway) => gateway.createTrip(input, language)),
    listTrips: (language) => demo().then((gateway) => gateway.listTrips(language)),
    getTrip: (tripId, language) => demo().then((gateway) => gateway.getTrip(tripId, language)),
    retryVerification: (tripId, language) => demo().then((gateway) => gateway.retryVerification(tripId, language)),
    startTrip: (tripId, language) => demo().then((gateway) => gateway.startTrip(tripId, language)),
    sendMessage: (tripId, message, language, itemId) => demo().then((gateway) => gateway.sendMessage(tripId, message, language, itemId)),
    deleteTrip: (tripId, language) => demo().then((gateway) => gateway.deleteTrip!(tripId, language)),
  };
}

/** Example plans for the demo's "Load example" button — loaded only in a demo build, like the demo itself. */
export const loadSamplePlans = () => import("./demo/sample").then((module) => module.SAMPLE_PLANS);

// `live` talks to the triPilot server (`NEXT_PUBLIC_API_BASE`, `/v1/web/*`) with a per-user key.
export const tripGateway: TripGateway = DATA_MODE === "demo" ? demoGateway() : DATA_MODE === "live" ? createLiveGateway() : unavailableGateway;
export const tripKey = (tripId: string, language: Language) => ["trip", tripId, language] as const;
/** Prefix of one trip's query in every language; removed when the trip is deleted. */
export const tripKeyPrefix = (tripId: string) => ["trip", tripId] as const;
/** Prefix of the trip list query in every language; removed after a registration so the list is read again. */
export const tripsKey = ["trips"] as const;
