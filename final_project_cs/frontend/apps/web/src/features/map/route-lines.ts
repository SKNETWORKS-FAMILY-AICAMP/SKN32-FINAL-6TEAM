import type { RouteShape } from "@/lib/live/route-shapes";
import type { TripStop } from "../trip/model";
import { hasValidCoordinates } from "./map-points";
import type { MapLine } from "./model";

const MODE_NAMES: Record<RouteShape["mode"], string> = { walk: "도보", bike: "자전거", taxi: "택시", subway: "지하철", bus: "버스", mixed: "대중교통", unknown: "이동" };

/** The road is not known (a straight line between two places), or the server gives no ground for the line: it is drawn dashed and pale. */
export const isGuess = (shape: RouteShape) => shape.source === "straight_line" || shape.grade === "근거없음" || shape.source === "unknown";

/**
 * The lines that belong to the day on the map: a shape is drawn only when both stops around the move are shown with a place.
 * ★Nothing is made up — a move with no shape from the server has no line, and a shape without two usable ends is left out.
 */
export function visibleShapes(shapes: RouteShape[] | undefined, stops: TripStop[]): RouteShape[] {
  if (!shapes?.length) return [];
  const placed = new Set(stops.filter((stop) => hasValidCoordinates(stop.coordinates)).map((stop) => stop.id));
  return shapes.filter((shape) => placed.has(shape.fromItemId) && placed.has(shape.toItemId));
}

export function toMapLines(shapes: RouteShape[]): MapLine[] {
  return shapes.map((shape) => ({
    id: shape.itemId,
    points: shape.points,
    dashed: isGuess(shape),
    title: `${shape.from ?? "출발"} → ${shape.to ?? "도착"} · ${MODE_NAMES[shape.mode]}${shape.distanceM !== null ? ` ${shape.distanceM >= 1000 ? `${(shape.distanceM / 1000).toFixed(1)}km` : `${Math.round(shape.distanceM)}m`}` : ""}`,
  }));
}

/** What the lines on the map do NOT mean, in one short sentence each — shown with the map, only for the kinds that are drawn. */
export function routeNotes(shapes: RouteShape[]): string[] {
  const notes: string[] = [];
  if (shapes.some(isGuess)) notes.push("점선은 길을 몰라 두 곳을 직선으로 이은 구간이에요.");
  if (shapes.some((shape) => shape.source === "stations")) notes.push("지하철 구간은 역 위치를 순서대로 이은 선이라 실제 선로 모양이 아니에요.");
  if (shapes.some((shape) => shape.mode === "bus" || shape.mode === "mixed")) notes.push("버스는 정류장 정보가 없어 직선으로 이어요.");
  // The server says why for each guess (`note`): the road finder was off, no stop list … — shown as it wrote it, once for each distinct sentence.
  const reasons = new Set(shapes.filter(isGuess).flatMap((shape) => shape.note ? [`${shape.from ?? "출발"} → ${shape.to ?? "도착"}: ${shape.note}`] : []));
  return [...notes, ...reasons];
}
