import type { Language } from "@/lib/i18n";
import type { LocationFix } from "@/lib/location";
import type { OpProgress } from "@/lib/live/stream";
import type { Coordinates } from "../map/model";

export interface TripStop {
  id: string;
  date: string;
  time: string;
  endTime?: string;
  title: string;
  booking: "booked" | "unknown";
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
  /** Development mode only: which rule sections the answer came from (「t_doc_07#c5」). The server sends it only when an
   *  operator turned on `web.dev_mode`; customers never see it. */
  basis?: string[];
  /** The server did not understand and asks 「다음 중 하나인가요?」: each choice's `message` is a sentence it will understand. */
  choices?: { label: string; message: string }[];
  /** The server's heading for `choices` — 「혹시 이런 뜻이었나요?」 when it answered and offers other readings. */
  choicesTitle?: string;
  /** The rest of a long answer, folded under 「더 보기」 (the answer itself keeps only the core). */
  more?: string;
  /** This answer changed the plan to `version`: an 「되돌리기」 button can take it back to `version - 1` while it is still the latest. */
  changedTo?: number;
  /** The answer needs where the customer is now (「여기서 어떻게 가?」): the screen offers to ask the browser and send again. */
  needsLocation?: boolean;
}

/** Web view model of one trip, read from `GET /v1/web/trips/{id}` (not a claim that the Case API returns this shape). */
export interface Trip {
  id: string;
  stops: TripStop[];
  messages: TripMessage[];
  /** What the server did to the trip and what it found. */
  history?: TripChange[];
  warnings?: TripWarning[];
  /** The server's per-trip plan page (a link that needs no login). */
  planUrl?: string;
  /** The itinerary version on the server now (an undo is offered only for the change that made it). */
  version?: number;
  /** The day's route to open in the customer's map app, by date. Several links when a day has more stops than one link holds. */
  dayRoutes?: Record<string, string[]>;
  /** Directions between two consecutive stops in the customer's map app, keyed `${fromStopId}>${toStopId}`. */
  legs?: Record<string, string>;
}

/** One row of "My trips" — only what the server list (`GET /v1/web/trips`) gives: no trip dates, status or open proposals. */
export interface TripSummary {
  id: string;
  title: string;
  /** When the trip was registered (ISO instant). */
  createdAt: string | null;
  /** Itinerary version; above 1 means the itinerary changed after registration. */
  version: number | null;
}

/** Every call names the reader's language; generated text comes back in that language. */
export interface TripGateway {
  /** This customer's trips (the server's list for the stored user key), newest first. */
  listTrips(language: Language): Promise<TripSummary[]>;
  getTrip(tripId: string, language: Language): Promise<Trip>;
  /** `itemId` — the stop the customer picked on screen; the server uses it when the sentence does not name one. */
  /** `location`: where the customer is, from the browser, sent only after the server said the answer needs it. */
  /** `onProgress`: what the server is doing while it works on the message. */
  sendMessage(tripId: string, message: string, language: Language, itemId?: string | null, location?: LocationFix | null,
    onProgress?: (progress: OpProgress) => void): Promise<Trip>;
  /**
   * Delete one trip on the server, or reject with why it was not deleted. A server that has no delete call yet
   * rejects with a `LiveError` whose code is `delete_unsupported` (backend request 2026-10-03).
   */
  deleteTrip(tripId: string, language: Language): Promise<void>;
}
