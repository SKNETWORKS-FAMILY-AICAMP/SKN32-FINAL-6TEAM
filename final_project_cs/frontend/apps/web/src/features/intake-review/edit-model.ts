import type { Translate } from "@/lib/i18n";
import type { Candidate, CandidateList, CandidatePlace, CheckLine, ItemRow, ItemStatus, ReviewItem, ReviewPlace } from "@/lib/live/intake-review";
import { pickedPlace } from "@/lib/live/intake-review";

/**
 * The cards of the edit screen (mockup 「수정 화면」): the stop as it is now, then the other places the server found for it,
 * then any place the customer picked from a search. Each card carries the check lines the server worked out for THAT place at
 * THIS stop's day and time — nothing here judges a place.
 */

export type CardKind = "current" | "alternative" | "search";

export interface EditCard {
  key: string;
  kind: CardKind;
  place: ReviewPlace | CandidatePlace | null;
  rank: number | null;
  rows: readonly CheckLine<ItemRow>[];
  /** The current stop's status (alternatives have none). */
  status: ItemStatus | null;
  /** Where the distance is measured from, and how far. */
  distance: { from: string | null; meters: number | null } | null;
  /** This place can be sent as a pick (the server takes a picked place by its coordinates). */
  pickable: boolean;
  /** One leg of it is a straight-line guess, so the lines say 「[추정]」. */
  estimated: boolean;
  subtitle: string;
  /** Registration photos can be asked for — only places that came from the tourism organization have a reference. */
  photoRef: string | null;
}

const placeKey = (place: Pick<ReviewPlace, "name" | "latitude" | "longitude">) => `${place.name}|${place.latitude ?? ""}|${place.longitude ?? ""}`;

function candidateCard(candidate: Candidate, kind: CardKind, rank: number | null): EditCard {
  const place = candidate.place;
  return {
    key: `${kind}:${placeKey(place)}`, kind, place, rank, rows: candidate.rows, status: null,
    distance: { from: candidate.reference, meters: candidate.distance_m }, pickable: pickedPlace(place) !== null, estimated: candidate.estimated,
    subtitle: [place.category, place.address].filter(Boolean).join(" · "), photoRef: place.ref?.startsWith("tour:") ? place.ref : null,
  };
}

/** Current stop → the server's alternatives → (customer's search picks go right after the current stop). */
export function buildCards(item: ReviewItem, list: CandidateList | undefined, picks: readonly Candidate[]): EditCard[] {
  const current: EditCard = {
    key: "current", kind: "current", place: item.place, rank: null, rows: item.rows ?? [], status: item.status, distance: null, pickable: false, estimated: false,
    subtitle: "", photoRef: item.place?.content_id ? `tour:${item.place.content_id}` : null,
  };
  const alternatives = (list?.candidates ?? []).map((candidate) => candidateCard(candidate, "alternative", candidate.rank));
  const seen = new Set([...(item.place ? [placeKey(item.place)] : []), ...alternatives.map((card) => placeKey(card.place!))]);
  const searched: EditCard[] = [];
  for (const candidate of picks) {
    if (seen.has(placeKey(candidate.place))) continue;            // already a card (the stop itself, or one of the alternatives)
    seen.add(placeKey(candidate.place));
    searched.push(candidateCard(candidate, "search", null));
  }
  return [current, ...searched, ...alternatives];
}

/** Where a place the customer picked from a search sits among the cards — its own card, or the existing one with the same place. */
export function indexOfPlace(cards: readonly EditCard[], place: Pick<ReviewPlace, "name" | "latitude" | "longitude">): number {
  return cards.findIndex((card) => card.place && placeKey(card.place) === placeKey(place));
}

export const letterOf = (index: number) => index >= 1 ? "ABCDEFGH"[index - 1] ?? String(index) : "";

export function chipText(card: EditCard, index: number, t: Translate): string {
  if (card.kind === "current") return t("지금 일정", "Current stop");
  if (card.kind === "search") return t(`검색으로 고른 곳 ${letterOf(index)}`, `Picked from search ${letterOf(index)}`);
  return t(`대체 후보 ${letterOf(index)} · ${card.rank}순위`, `Alternative ${letterOf(index)} · #${card.rank}`);
}

export function positionText(card: EditCard, index: number, total: number, t: Translate): string {
  const name = card.kind === "current" ? t("지금 일정", "Current stop") : card.kind === "search" ? t("검색으로 고른 곳", "Picked from search") : t(`대체 후보 ${letterOf(index)}`, `Alternative ${letterOf(index)}`);
  return `${name} · ${index + 1}/${total}`;
}

/** 「경복궁에서 0.8km」 — or just 「0.8km」 when the server did not say from where. */
export function distanceText(distance: EditCard["distance"], t: Translate): string {
  if (!distance || distance.meters === null) return "";
  const km = `${(distance.meters / 1000).toFixed(1)}km`;
  return distance.from ? t(`${distance.from}에서 ${km}`, `${km} from ${distance.from}`) : km;
}

/**
 * A photo address from the server, or null if it is not a plain web address. The pictures come straight from the tourism
 * organization (never stored here); only http and https are ever requested — nothing like `javascript:` or `data:`.
 */
export function safePhotoUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.toString() : null;
  } catch { return null; }
}
