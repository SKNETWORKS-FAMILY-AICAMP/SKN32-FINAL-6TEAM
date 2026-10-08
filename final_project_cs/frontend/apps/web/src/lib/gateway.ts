import type { TripGateway } from "../features/trip/model";
import { createLiveGateway } from "./live/gateway";
import { GatewayError } from "./gateway-errors";
import { DATA_MODE } from "./data-mode";
import { translator, type Language } from "./i18n";

export { GatewayError, isGatewayError } from "./gateway-errors";

// An unavailable live adapter must never make fabricated successful responses by falling back.
function unavailable(language: Language): Promise<never> {
  const t = translator(language);
  return Promise.reject(new GatewayError("DATA_MODE_UNAVAILABLE", t("실제 서버 연결이 설정되지 않았어요. .env.local 에 NEXT_PUBLIC_DATA_MODE=live 와 NEXT_PUBLIC_API_BASE 를 적고 다시 실행해 주세요.", "The real server is not configured. Set NEXT_PUBLIC_DATA_MODE=live and NEXT_PUBLIC_API_BASE in .env.local and restart.")));
}

const unavailableGateway: TripGateway = {
  listTrips: (language) => unavailable(language),
  getTrip: (_tripId, language) => unavailable(language),
  sendMessage: (_tripId, _message, language) => unavailable(language),
  deleteTrip: (_tripId, language) => unavailable(language),
};

// ★`[2026-10-03 사용자 지시]` There is no imitation gateway any more. `live` talks to the triPilot server
//   (`NEXT_PUBLIC_API_BASE`, `/v1/web/*`) with a per-user key; any other build says the server is not connected.
export const tripGateway: TripGateway = DATA_MODE === "live" ? createLiveGateway() : unavailableGateway;
export const tripKey = (tripId: string, language: Language) => ["trip", tripId, language] as const;
/** Prefix of one trip's query in every language; removed when the trip is deleted. */
export const tripKeyPrefix = (tripId: string) => ["trip", tripId] as const;
/** Prefix of the trip list query in every language; removed after a registration so the list is read again. */
export const tripsKey = ["trips"] as const;
