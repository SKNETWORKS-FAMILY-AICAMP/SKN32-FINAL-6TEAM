import type { TripGateway } from "../features/trip/model";
import { createDemoGateway } from "./demo";
import { GatewayError } from "./demo/errors";
import { DATA_MODE } from "./data-mode";

export { GatewayError, isGatewayError } from "./demo/errors";
export { SAMPLE_PLAN } from "./demo/sample";

// Production builds must explicitly opt into demo mode. An unavailable live
// adapter must never make fabricated successful responses by falling back.
export { DATA_MODE } from "./data-mode";

function unavailable(): Promise<never> {
  return Promise.reject(new GatewayError("DATA_MODE_UNAVAILABLE", "실제 에이전트 API 연결이 아직 설정되지 않았어요. 개발용 시연은 NEXT_PUBLIC_DATA_MODE=demo로 실행해 주세요."));
}

const unavailableGateway: TripGateway = {
  createTrip: unavailable,
  getTrip: unavailable,
  retryVerification: unavailable,
  startTrip: unavailable,
  sendMessage: unavailable,
};

export const tripGateway: TripGateway = DATA_MODE === "demo" ? createDemoGateway() : unavailableGateway;
export const tripKey = (tripId: string) => ["trip", tripId] as const;
