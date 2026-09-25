import type { TripGateway } from "../features/trip/model";
import { createDemoGateway } from "./demo";
import { GatewayError } from "./demo/errors";
import { DATA_MODE } from "./data-mode";
import { translator, type Language } from "./i18n";

export { GatewayError, isGatewayError } from "./demo/errors";
export { SAMPLE_PLANS } from "./demo/sample";

// Production builds must explicitly opt into demo mode. An unavailable live
// adapter must never make fabricated successful responses by falling back.
export { DATA_MODE } from "./data-mode";

function unavailable(language: Language): Promise<never> {
  const t = translator(language);
  return Promise.reject(new GatewayError("DATA_MODE_UNAVAILABLE", t("실제 에이전트 API 연결이 아직 설정되지 않았어요. 개발용 시연은 NEXT_PUBLIC_DATA_MODE=demo로 실행해 주세요.", "The live agent API is not connected yet. For a development preview, run with NEXT_PUBLIC_DATA_MODE=demo.")));
}

const unavailableGateway: TripGateway = {
  createTrip: (_input, language) => unavailable(language),
  getTrip: (_tripId, language) => unavailable(language),
  retryVerification: (_tripId, language) => unavailable(language),
  startTrip: (_tripId, language) => unavailable(language),
  sendMessage: (_tripId, _message, language) => unavailable(language),
};

export const tripGateway: TripGateway = DATA_MODE === "demo" ? createDemoGateway() : unavailableGateway;
export const tripKey = (tripId: string, language: Language) => ["trip", tripId, language] as const;
