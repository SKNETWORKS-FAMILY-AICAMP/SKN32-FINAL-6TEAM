import type { Coordinates } from "@/features/map/model";
import type { CheckRow, PlaceInfo, PlanCheckView, PlanItem, PlanLine, PlanMove } from "./model";

/**
 * ★Example data for the preview page only — the mockup's example (`mockups/tripilot-plan-check-streaming.html`), not a
 *   server answer. Place names, addresses, hours, photos and distances are made up; the coordinates are the real landmarks'.
 */
const row = (kind: CheckRow["kind"], result: CheckRow["result"], text: string): CheckRow => ({ kind, result, text });

/** The kinds of place the example stops are, for picking alternatives of the same kind (mockup `GROUP`). */
export type PlaceGroup = "palace" | "market" | "beauty" | "view";

/** One example place (mockup `P`): what it is, where, its hours and closing day as the place data would give them. */
export interface ExamplePlace {
  key: string;
  group: PlaceGroup;
  name: string;
  category: string;
  address: string;
  /** Opening and closing time, or null when it is always open. */
  hours: [string, string] | null;
  hoursText: string;
  /** 「화요일 휴무」 · 「연중무휴」 · 「점포마다 다름」, or null when unknown. */
  closed: string | null;
  source: "관광공사" | "카카오";
  coordinates: Coordinates;
}

const place = (key: string, group: PlaceGroup, name: string, category: string, address: string, hours: [string, string] | null, hoursText: string,
  closed: string | null, source: ExamplePlace["source"], lat: number, lng: number): ExamplePlace =>
  ({ key, group, name, category, address, hours, hoursText, closed, source, coordinates: { lat, lng } });

export const EXAMPLE_PLACES: ExamplePlace[] = [
  place("gyeongbokgung", "palace", "경복궁", "관광지 · 고궁", "서울 종로구 사직로 161", ["09:00", "18:00"], "09:00–18:00", "화요일 휴무", "관광공사", 37.5796, 126.977),
  place("changdeokgung", "palace", "창덕궁", "관광지 · 고궁", "서울 종로구 율곡로 99", ["09:00", "18:00"], "09:00–18:00", "월요일 휴무", "관광공사", 37.5794, 126.991),
  place("changgyeonggung", "palace", "창경궁", "관광지 · 고궁", "서울 종로구 창경궁로 185", ["09:00", "21:00"], "09:00–21:00", "월요일 휴무", "관광공사", 37.5788, 126.995),
  place("deoksugung", "palace", "덕수궁", "관광지 · 고궁", "서울 중구 세종대로 99", ["09:00", "21:00"], "09:00–21:00", "월요일 휴무", "관광공사", 37.5658, 126.9751),
  place("gyeonghuigung", "palace", "경희궁", "관광지 · 고궁", "서울 종로구 새문안로 45", ["09:00", "18:00"], "09:00–18:00", "월요일 휴무", "관광공사", 37.5714, 126.9681),
  place("gwangjang", "market", "광장시장", "전통시장 · 먹거리", "서울 종로구 창경궁로 88", ["09:00", "23:00"], "09:00–23:00", "점포마다 다름", "관광공사", 37.57, 126.9996),
  place("tongin", "market", "통인시장", "전통시장 · 먹거리", "서울 종로구 자하문로15길 18", ["07:00", "21:00"], "07:00–21:00", "점포마다 다름", "관광공사", 37.5809, 126.9696),
  place("namdaemun", "market", "남대문시장", "전통시장 · 먹거리", "서울 중구 남대문시장4길 21", ["00:00", "23:00"], "00:00–23:00", "점포마다 다름", "관광공사", 37.5591, 126.9776),
  place("mangwon", "market", "망원시장", "전통시장 · 먹거리", "서울 마포구 포은로8길 14", ["10:00", "21:00"], "10:00–21:00", "점포마다 다름", "관광공사", 37.556, 126.906),
  place("oyMyeongdong", "beauty", "올리브영 명동 플래그십", "화장품 · 뷰티 편집숍", "서울 중구 명동길 53", ["10:00", "22:30"], "10:00–22:30", "연중무휴", "카카오", 37.5637, 126.9851),
  place("oyJonggak", "beauty", "올리브영 종각역점", "화장품 · 뷰티 편집숍", "서울 종로구 종로 51", ["08:00", "23:00"], "08:00–23:00", "연중무휴", "카카오", 37.5702, 126.9838),
  place("oyInsadong", "beauty", "올리브영 인사동점", "화장품 · 뷰티 편집숍", "서울 종로구 인사동길 49", ["10:00", "22:00"], "10:00–22:00", "연중무휴", "카카오", 37.5741, 126.9857),
  place("oyGwanghwamun", "beauty", "올리브영 광화문점", "화장품 · 뷰티 편집숍", "서울 종로구 종로1길 50", ["08:00", "22:00"], "08:00–22:00 · 주말 10:00부터", null, "카카오", 37.5717, 126.9791),
  place("oyGangnam", "beauty", "올리브영 강남타운", "화장품 · 뷰티 편집숍", "서울 강남구 강남대로 429", ["10:00", "22:30"], "10:00–22:30", "연중무휴", "카카오", 37.501, 127.0265),
  place("nSeoulTower", "view", "N서울타워", "관광지 · 전망대", "서울 용산구 남산공원길 105", ["10:00", "23:00"], "10:00–23:00", "연중무휴", "관광공사", 37.5512, 126.9882),
  place("naksan", "view", "낙산공원", "관광지 · 공원", "서울 종로구 낙산길 41", null, "24시간", null, "관광공사", 37.5806, 127.0075),
  place("palgakjeong", "view", "북악스카이웨이 팔각정", "관광지 · 전망대", "서울 종로구 북악산로 267", ["10:00", "22:00"], "10:00–22:00", "연중무휴", "관광공사", 37.6016, 126.9812),
  place("seoulSky", "view", "롯데월드타워 서울스카이", "관광지 · 전망대", "서울 송파구 올림픽로 300", ["10:30", "22:00"], "10:30–22:00", "연중무휴", "관광공사", 37.5126, 127.1025),
];

/** Example photo captions by kind — the drawings stand where the place data's photos will go (mockup `CAPS`). */
const PHOTO_CAPTIONS: Record<PlaceGroup, string[]> = {
  palace: ["정문", "전각", "회랑", "정원", "관람로", "입구 안내"],
  market: ["입구", "먹거리 골목", "점포", "좌판", "골목 풍경", "안내도"],
  beauty: ["매장 외관", "진열대", "기초 화장품", "색조 코너", "계산대", "입구"],
  view: ["전망", "야경", "입구", "산책로", "전망대 안", "주변 풍경"],
};

export const placeInfo = (example: ExamplePlace): PlaceInfo =>
  ({ category: example.category, address: example.address, photos: PHOTO_CAPTIONS[example.group].map((caption) => ({ caption, url: null })) });

const at = (key: string) => EXAMPLE_PLACES.find((entry) => entry.key === key)!;

const stop = (fields: Omit<PlanItem, "locked" | "info" | "suggestion">, key: string | null, suggestion: string | null): PlanItem =>
  ({ ...fields, locked: false, info: key ? placeInfo(at(key)) : null, suggestion });

const items: PlanItem[] = [
  stop({ id: "a", day: 1, date: "2026-10-01", startsAt: "10:00", endsAt: "11:30", title: "경복궁", place: "경복궁", noPlace: false, coordinates: at("gyeongbokgung").coordinates, verdict: "keep",
    checks: [row("place", "ok", "관광공사 정보로 찾았어요"), row("hours", "ok", "09:00–18:00 안에 머물러요"), row("closed", "ok", "화요일 휴무 · 방문은 목요일")] }, "gyeongbokgung", "창덕궁"),
  stop({ id: "b", day: 1, date: "2026-10-01", startsAt: "11:00", endsAt: "12:00", title: "올리브영", place: "", noPlace: false, coordinates: null, verdict: "review",
    checks: [row("place", "bad", "지점이 여러 곳이라 정하지 못했어요"), row("time", "warn", "경복궁 관람과 30분 겹쳐요 · 등록 때 막힐 수 있어요"),
      row("hours", "unknown", "지점을 고르면 확인해요"), row("closed", "unknown", "지점을 고르면 확인해요")] }, null, "올리브영 광화문점"),
  stop({ id: "c", day: 1, date: "2026-10-01", startsAt: "12:30", endsAt: "13:30", title: "광장시장", place: "광장시장", noPlace: false, coordinates: at("gwangjang").coordinates, verdict: "adjusted",
    checks: [row("place", "ok", "가게 이름이 없어 광장시장으로 잡았어요"), row("time", "filled", "끝 시각이 없어 식사 1시간으로 채웠어요"),
      row("hours", "ok", "09:00–23:00 안에 머물러요"), row("closed", "unknown", "점포마다 달라요")] }, "gwangjang", "통인시장"),
  stop({ id: "d", day: 2, date: "2026-10-02", startsAt: "15:00", endsAt: "16:30", title: "N서울타워", place: "N서울타워", noPlace: false, coordinates: at("nSeoulTower").coordinates, verdict: "keep",
    checks: [row("place", "ok", "「남산타워」를 N서울타워로 찾았어요"), row("hours", "ok", "10:00–23:00 안에 머물러요"), row("closed", "ok", "연중무휴")] }, "nSeoulTower", "낙산공원"),
];

/** Which example place each stop is (null: not settled) and what kind of place it should be — the preview's own bookkeeping. */
export const EXAMPLE_PLACE_OF: Record<string, string | null> = { a: "gyeongbokgung", b: null, c: "gwangjang", d: "nSeoulTower" };
export const EXAMPLE_GROUP_OF: Record<string, PlaceGroup> = { a: "palace", b: "beauty", c: "market", d: "view" };

const moves: PlanMove[] = [
  { id: "a-b", fromId: "a", toId: "b", day: 1, departAt: "11:30", mode: "도보", summary: "12분 · 0.8km", verdict: "review",
    checks: [row("route", "warn", "올리브영 지점이 미정이라 가장 가까운 광화문점 기준이에요"), row("mode", "ok", "도보 12분 · 0.8km · 이 구간은 걷는 게 가장 빨라요"),
      row("arrival", "warn", "관람이 11:30에 끝나면 11:42 도착 · 일정보다 42분 늦어요")] },
  { id: "b-c", fromId: "b", toId: "c", day: 1, departAt: "12:00", mode: "지하철", summary: "18분 · 1호선 2정거장", verdict: "keep",
    checks: [row("route", "ok", "종각역 → 종로5가역 · 1호선 2정거장"), row("mode", "ok", "지하철 18분(걷기 7분 포함) · 택시보다 시간이 일정해요"),
      row("arrival", "ok", "12:00에 나서면 12:18 도착 · 12분 여유")] },
];

const lines: PlanLine[] = [
  { no: 1, text: "10월 1일 서울 여행", read: true, found: { kind: "date", date: "2026-10-01" } },
  { no: 2, text: "10시 경복궁 관람 1시간 반", read: true, found: { kind: "item", day: 1, startsAt: "10:00", title: "경복궁" } },
  { no: 3, text: "11시 올리브영", read: true, found: { kind: "item", day: 1, startsAt: "11:00", title: "올리브영" } },
  { no: 4, text: "12시 반 광장시장 빈대떡", read: true, found: { kind: "item", day: 1, startsAt: "12:30", title: "광장시장" } },
  { no: 5, text: "둘째 날 3시 남산타워", read: true, found: { kind: "item", day: 2, startsAt: "15:00", title: "남산타워" } },
];

const days = [{ day: 1, date: "2026-10-01" }, { day: 2, date: "2026-10-02" }];

/** The final state: every check in, the trip titled. */
export const exampleDone: PlanCheckView = { stage: "done", title: "10월 서울 여행", days, lines, items, moves, dirty: false, rechecking: null };

/**
 * What a server might send, in four coarse snapshots — received, every line read, every check in, done. The screen
 * draws the changes between them one at a time (`nextStep`), as it would with a stream burst or a re-read.
 */
export const exampleSnapshots: { at: number; view: PlanCheckView }[] = [
  { at: 0, view: { ...exampleDone, stage: "received", title: null, days: [], lines: lines.map((line) => ({ ...line, read: false, found: null })), items: [], moves: [] } },
  { at: 400, view: { ...exampleDone, stage: "reading", title: null, items: [], moves: [] } },
  { at: 1200, view: { ...exampleDone, stage: "checking", title: null } },
  { at: 1500, view: exampleDone },
];
