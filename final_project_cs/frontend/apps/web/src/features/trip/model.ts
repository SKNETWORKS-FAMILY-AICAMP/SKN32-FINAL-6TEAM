import type { Language } from "@/lib/i18n";
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
  booking: "booked" | "none" | "unknown";
  notes: string;
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

/** Every call names the reader's language; generated text comes back in that language. */
export interface TripGateway {
  createTrip(input: CreateTripInput, language: Language): Promise<Trip>;
  getTrip(tripId: string, language: Language): Promise<Trip>;
  retryVerification(tripId: string, language: Language): Promise<Trip>;
  startTrip(tripId: string, language: Language): Promise<Trip>;
  sendMessage(tripId: string, message: string, language: Language): Promise<Trip>;
}
