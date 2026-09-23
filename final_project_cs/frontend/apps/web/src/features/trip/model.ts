import type { Coordinates } from "../map/model";

export type DemoScenario = "success" | "needs-review" | "failed";
export type StageStatus = "pending" | "running" | "completed" | "failed";

export interface VerificationStage {
  id: string;
  label: string;
  description: string;
  status: StageStatus;
}

export interface VerificationResult {
  id: string;
  stopId: string;
  date: string;
  status: "adjusted" | "unchanged" | "needs_review";
  title: string;
  originalValue: string;
  proposedValue?: string;
  reason: string;
  impact: string;
}

export interface TripStop {
  id: string;
  date: string;
  time: string;
  endTime?: string;
  originalTime?: string;
  title: string;
  area: string;
  kind: string;
  booking: "booked" | "none" | "unknown";
  notes: string;
  movement?: string;
  /** WGS84 coordinates supplied by the backend; missing means no map pin. */
  coordinates?: Coordinates | null;
}

export interface TripMessage {
  id: string;
  role: "assistant" | "user";
  text: string;
  createdAt: string;
}

/** Web view model; not a claim that the existing Case API returns this contract. */
export interface Trip {
  id: string;
  title: string;
  source: string;
  startDate: string;
  endDate: string;
  status: "processing" | "ready" | "active" | "failed";
  stops: TripStop[];
  verification: {
    status: "running" | "completed" | "failed";
    progress: number;
    stages: VerificationStage[];
    results: VerificationResult[];
    error?: string;
  };
  messages: TripMessage[];
}

export interface CreateTripInput {
  source: string;
  scenario?: DemoScenario;
}

export interface TripGateway {
  createTrip(input: CreateTripInput): Promise<Trip>;
  getTrip(tripId: string): Promise<Trip>;
  retryVerification(tripId: string): Promise<Trip>;
  startTrip(tripId: string): Promise<Trip>;
  sendMessage(tripId: string, message: string): Promise<Trip>;
}
