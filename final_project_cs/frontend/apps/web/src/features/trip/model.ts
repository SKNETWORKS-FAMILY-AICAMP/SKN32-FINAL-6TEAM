import type { Language } from "@/lib/i18n";
import type { Coordinates } from "../map/model";
import type { TripSurvey } from "../onboarding/payload";

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
  /** The customer fixed this stop — the server does not move it on its own. */
  pinned?: boolean;
  /** Other options the server kept for this stop (best one is already applied). Shown as information. */
  otherOptions?: TripOption[];
  /** Opens this place in the customer's own map app (Google Maps link from the server; no API key, no billing). */
  mapUrl?: string;
  /** What the server knows about the place (address, phone, hours, badges). Missing fields are not shown. */
  placeInfo?: PlaceInfo | null;
}

export interface TripOption { key: string; name: string }

export interface PlaceInfo {
  address?: string;
  phone?: string;
  category?: string;
  /** Opening hours in the server's words, one line per rule ("월 11:00–21:00"). */
  hours: string[];
  /** Hours the source gave only as text, or conditions the weekly table cannot hold ("공휴일 휴무"). */
  hoursNotes: string[];
  /** Facility badges as the server named them ("card_payment", "parking", …). */
  tags: string[];
  michelin?: { level: string; year?: number } | null;
  /** Credit line the source asks for (e.g. "ⓒ한국관광공사"). */
  sourceNote?: string;
}

/** One saved version of the trip (server `history`): why it changed and what caused it, in the server's words. */
export interface TripChange {
  version: number;
  reason: string;
  /** Seoul wall clock, "2026-09-28 12:23". */
  at: string;
  causes: string[];
}

/** A finding the server made about the plan (server `warnings`), with what to do about it when it says so. */
export interface TripWarning {
  code: string;
  date: string | null;
  reason: string;
  remedy: string | null;
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
  /** Live only: what the server did to the trip and what it found. Absent in demo. */
  history?: TripChange[];
  warnings?: TripWarning[];
  /** The server's per-trip plan page (a link that needs no login). */
  planUrl?: string;
  /** Live only: the day's route to open in the customer's map app, by date. Several links when a day has more stops than one link holds. */
  dayRoutes?: Record<string, string[]>;
  /** Live only: directions between two consecutive stops in the customer's map app, keyed `${fromStopId}>${toStopId}`. */
  legs?: Record<string, string>;
}

/** One row of "My trips" — only what the server list (`GET /v1/web/trips`) gives: no trip dates, status or open proposals. */
export interface TripSummary {
  id: string;
  title: string;
  /** When the trip was registered (ISO instant). Null for a demo trip saved before registration time was kept. */
  createdAt: string | null;
  /** Itinerary version; above 1 means the itinerary changed after registration. Null where there are no versions (demo). */
  version: number | null;
}

export interface CreateTripInput {
  source: string;
  scenario?: DemoScenario;
  /** Onboarding answers, sent as the backend's `constraints.survey`. Absent when onboarding was not finished. */
  survey?: TripSurvey;
}

/** Every call names the reader's language; generated text comes back in that language. */
export interface TripGateway {
  createTrip(input: CreateTripInput, language: Language): Promise<Trip>;
  /** This browser's trips, newest first. */
  listTrips(language: Language): Promise<TripSummary[]>;
  getTrip(tripId: string, language: Language): Promise<Trip>;
  retryVerification(tripId: string, language: Language): Promise<Trip>;
  startTrip(tripId: string, language: Language): Promise<Trip>;
  /** `itemId` — the stop the customer picked on screen; the server uses it when the sentence does not name one. */
  sendMessage(tripId: string, message: string, language: Language, itemId?: string | null): Promise<Trip>;
  /**
   * Delete one trip, or reject with why it was not deleted. Absent where a trip cannot be deleted: the server has no
   * delete call yet (`/v1/web/trips` is GET and POST only), so only the demo offers it.
   */
  deleteTrip?(tripId: string, language: Language): Promise<void>;
}
