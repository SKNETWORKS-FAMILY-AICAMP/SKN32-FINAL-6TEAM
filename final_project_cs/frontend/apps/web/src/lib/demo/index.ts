import type { Trip, TripGateway, VerificationResult } from "../../features/trip/model";
import { translator, type Translate } from "../i18n";
import { demoReply } from "./chat";
import { GatewayError } from "./errors";
import { parseDemoPlan } from "./parse-plan";
import { scenarioSchema, stageIds, storedTripSchema, type StoredTrip } from "./schema";

export { SAMPLE_PLANS } from "./sample";
export const DEMO_STORAGE_PREFIX = "tripilot.web-mvp.trip:";
export const DEMO_VERIFICATION_DURATION = 6000;

export interface DemoStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

interface DemoGatewayOptions {
  storage?: DemoStorage | (() => DemoStorage);
  now?: () => number;
  delay?: (milliseconds: number) => Promise<void>;
}

type StoredStage = StoredTrip["trip"]["verification"]["stages"][number];
type StoredResult = StoredTrip["trip"]["verification"]["results"][number];

function stages(progress: number, failed = false): StoredStage[] {
  const active = progress < 20 ? 0 : progress < 55 ? 1 : progress < 80 ? 2 : 3;
  return stageIds.map((id, index) => ({
    id,
    status: progress === 100 || index < active ? "completed" : index === active ? failed ? "failed" : "running" : "pending",
  }));
}

function stageText(id: StoredStage["id"], t: Translate): [string, string] {
  switch (id) {
    case "plan": return [t("여행 계획 읽기", "Read your plan"), t("날짜와 장소, 머무는 시간을 정리해요.", "Organize dates, places, and planned times.")];
    case "places": return [t("장소와 운영시간", "Places & opening hours"), t("방문 조건을 확인하는 과정을 살펴봐요.", "Preview the checks for each visit.")];
    case "conditions": return [t("이동과 예약 조건", "Travel & reservations"), t("이동 여유와 예약 시간을 함께 살펴봐요.", "Review travel buffers and reserved times.")];
    case "overall": return [t("전체 일정 정리", "Bring it all together"), t("달라진 점과 유지할 내용을 모아요.", "Gather changes and the plans to keep.")];
  }
}

function resultText(reason: StoredResult["reason"], t: Translate): Pick<VerificationResult, "reason" | "impact"> {
  switch (reason) {
    case "unverified": return {
      reason: t("[시연] 이 일정의 이동 정보 확인을 마치지 못한 상황이에요.", "[Preview] This demonstrates an item whose travel information could not be verified."),
      impact: t("다시 검증하기 전에는 여행 관리를 시작할 수 없어요.", "Travel management stays unavailable until verification is completed."),
    };
    case "buffer": return {
      reason: t("[시연] 이동 여유 15분을 더한 조정 예시예요. 실제 이동 시간은 조회하지 않았어요.", "[Preview] This example adds a 15-minute buffer. Actual travel times have not been checked."),
      impact: t("시연된 시작 시각 변경이 여행 일정에 반영돼요. 예약 변경은 실행하지 않아요.", "The example start-time change appears in your itinerary. No bookings are changed."),
    };
    case "booked": return {
      reason: t("입력 내용에 예약이 있어 시작 시각을 유지했어요. 실제 업체 예약 확인은 하지 않았어요.", "The entered plan marks this item as booked, so its start time is unchanged. The provider booking has not been checked."),
      impact: t("입력한 일정 유지 · 예약 변경 및 취소 실행 없음", "Entered schedule preserved; no bookings changed or cancelled."),
    };
    case "kept": return {
      reason: t("[시연] 입력한 시작 시각을 유지하는 결과예요. 실제 운영·이동 정보는 확인하지 않았어요.", "[Preview] This example keeps the entered start time. Actual opening hours and travel information have not been checked."),
      impact: t("입력한 일정 유지 · 예약 변경 및 취소 실행 없음", "Entered schedule preserved; no bookings changed or cancelled."),
    };
  }
}

/** The stored trip keeps no generated sentences, so every read can speak the reader's language. */
function present({ trip }: StoredTrip, t: Translate): Trip {
  const { verification } = trip;
  return {
    ...trip,
    verification: {
      status: verification.status,
      progress: verification.progress,
      stages: verification.stages.map((stage) => {
        const [label, description] = stageText(stage.id, t);
        return { ...stage, label, description };
      }),
      results: verification.results.map(({ reason, ...result }) => ({ ...result, ...resultText(reason, t) })),
      ...(verification.status === "failed" ? { error: t("검증이 중단된 상황을 체험하고 있어요. 입력한 계획을 유지한 채 다시 시도할 수 있어요.", "This preview simulates an interrupted check. You can retry with your original plan preserved.") } : {}),
    },
  };
}

function browserStorage(): DemoStorage {
  if (typeof window === "undefined") throw new Error("No browser storage");
  return window.sessionStorage;
}

/** Local, deterministic demo adapter. No place, routing, booking, or AI API is called. */
export function createDemoGateway(options: DemoGatewayOptions = {}): TripGateway {
  const now = options.now ?? Date.now;
  const delay = options.delay ?? ((milliseconds: number) => new Promise<void>((resolve) => setTimeout(resolve, milliseconds)));

  function storage(t: Translate): DemoStorage {
    try {
      return typeof options.storage === "function" ? options.storage() : options.storage ?? browserStorage();
    } catch {
      throw new GatewayError("STORAGE_UNAVAILABLE", t("이 브라우저에서 세션 저장소를 사용할 수 없어요. 저장소 사용을 허용한 뒤 다시 시도해 주세요.", "Session storage is unavailable in this browser. Allow storage and try again."));
    }
  }

  function read(tripId: string, t: Translate): StoredTrip {
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(tripId)) throw notFound(t);
    let raw: string | null;
    try { raw = storage(t).getItem(DEMO_STORAGE_PREFIX + tripId); }
    catch (error) { throw error instanceof GatewayError ? error : storageError(t); }
    if (raw === null) throw notFound(t);
    try {
      const stored = storedTripSchema.parse(JSON.parse(raw));
      if (stored.trip.id !== tripId) throw new Error("ID mismatch");
      return stored;
    } catch {
      throw new GatewayError("CORRUPT_STORAGE", t("저장된 여행 데이터를 읽을 수 없어요. 입력 원본이 남아 있다면 새 여행으로 다시 등록해 주세요.", "The saved trip could not be read. If you still have your plan, add it again as a new trip."));
    }
  }

  function save(stored: StoredTrip, t: Translate): Trip {
    const checked = storedTripSchema.safeParse(stored);
    if (!checked.success) throw new GatewayError("CORRUPT_STORAGE", t("여행 데이터 형식이 올바르지 않아 저장하지 못했어요.", "The trip data is malformed, so it was not saved."));
    try { storage(t).setItem(DEMO_STORAGE_PREFIX + stored.trip.id, JSON.stringify(checked.data)); }
    catch (error) { throw error instanceof GatewayError ? error : storageError(t); }
    return present(checked.data, t);
  }

  function refresh(tripId: string, t: Translate): StoredTrip {
    const stored = read(tripId, t);
    if (stored.trip.verification.status !== "running") return stored;
    const elapsed = Math.max(0, now() - stored.startedAt);
    const nextProgress = Math.min(100, Math.floor(elapsed / DEMO_VERIFICATION_DURATION * 100));
    // Preserve monotonic progress even when the browser clock moves backwards.
    const progress = Math.max(stored.trip.verification.progress, nextProgress);
    if (stored.scenario === "failed" && progress >= 55) {
      stored.trip.status = "failed";
      stored.trip.verification = { status: "failed", progress: 55, stages: stages(55, true), results: [] };
    } else if (progress === 100) {
      complete(stored);
    } else {
      stored.trip.verification.progress = progress;
      stored.trip.verification.stages = stages(progress);
    }
    save(stored, t);
    return stored;
  }

  return {
    async createTrip(input, language) {
      const t = translator(language);
      const source = typeof input.source === "string" ? input.source : "";
      if (!source.trim()) throw new GatewayError("INVALID_INPUT", t("시간과 장소가 있는 여행 계획을 입력해 주세요.", "Enter a travel plan with times and places."));
      if (source.length > 12000) throw new GatewayError("INVALID_INPUT", t("여행 계획은 12,000자 이내로 입력해 주세요.", "Keep your travel plan within 12,000 characters."));
      const scenario = scenarioSchema.safeParse(input.scenario ?? "success");
      if (!scenario.success) throw new GatewayError("INVALID_INPUT", t("지원하지 않는 시연 검증 결과예요.", "Unsupported preview verification scenario."));
      const stops = parseDemoPlan(source, t);
      const trip: StoredTrip["trip"] = {
        id: crypto.randomUUID(),
        source,
        startDate: stops[0].date,
        endDate: stops.at(-1)!.date,
        status: "processing",
        stops,
        verification: { status: "running", progress: 0, stages: stages(0), results: [] },
        messages: [],
      };
      return save({ version: 2, scenario: scenario.data, startedAt: now(), trip }, t);
    },
    async getTrip(tripId, language) {
      const t = translator(language);
      return present(refresh(tripId, t), t);
    },
    async retryVerification(tripId, language) {
      const t = translator(language);
      const stored = read(tripId, t);
      const retryable = stored.trip.verification.status === "failed" || stored.trip.verification.results.some((result) => result.status === "needs_review");
      if (!retryable) throw new GatewayError("NOT_READY", t("다시 시도할 검증 오류가 없어요.", "There is no failed check to retry."));
      stored.scenario = "success";
      stored.startedAt = now();
      stored.trip.status = "processing";
      stored.trip.stops = stored.trip.stops.map((stop) => {
        const { originalTime, ...rest } = stop;
        return { ...rest, time: originalTime ?? stop.time };
      });
      stored.trip.verification = { status: "running", progress: 0, stages: stages(0), results: [] };
      return save(stored, t);
    },
    async startTrip(tripId, language) {
      const t = translator(language);
      const stored = refresh(tripId, t);
      if (stored.trip.verification.results.some((result) => result.status === "needs_review")) {
        throw new GatewayError("VERIFICATION_BLOCKED", t("미확인 항목을 해결해야 시작할 수 있어요.", "Resolve the items needing review before starting."));
      }
      if (stored.trip.verification.status !== "completed") throw new GatewayError("NOT_READY", t("검증이 완료된 뒤 여행 관리를 시작할 수 있어요.", "You can start your trip once the check is complete."));
      if (stored.trip.status === "active") return present(stored, t);
      stored.trip.status = "active";
      return save(stored, t);
    },
    async sendMessage(tripId, message, language) {
      const t = translator(language);
      const text = message.trim();
      if (!text || text.length > 600) throw new GatewayError("INVALID_INPUT", t("메시지를 1~600자 이내로 입력해 주세요.", "Enter a message of 1 to 600 characters."));
      // Visible pending state for the demo. Read after the delay to avoid
      // overwriting changes saved while the reply was waiting.
      await delay(350);
      const stored = read(tripId, t);
      if (stored.trip.status !== "active") throw new GatewayError("NOT_READY", t("여행 관리를 시작한 뒤 대화를 이용할 수 있어요.", "Chat is available after you start your trip."));
      const createdAt = new Date(now()).toISOString();
      stored.trip.messages.push(
        { id: crypto.randomUUID(), role: "user", text, createdAt },
        { id: crypto.randomUUID(), role: "assistant", text: demoReply(stored.trip.stops, text, t), createdAt },
      );
      return save(stored, t);
    },
  };
}

function notFound(t: Translate) {
  return new GatewayError("NOT_FOUND", t("이 탭에 저장된 여행을 찾을 수 없어요. 여행을 등록했던 탭에서 다시 열거나 새 여행을 등록해 주세요.", "This trip is not saved in this tab. Open it in the tab where you added it, or add a new trip."));
}

function storageError(t: Translate) {
  return new GatewayError("STORAGE_UNAVAILABLE", t("여행 데이터를 이 탭에 저장하거나 불러오지 못했어요. 브라우저의 저장소 설정과 남은 공간을 확인해 주세요.", "The trip could not be saved or loaded in this tab. Check your browser storage settings and free space."));
}

function addFifteen(time: string): string | null {
  const [hours, minutes] = time.split(":").map(Number);
  const next = hours * 60 + minutes + 15;
  return next < 24 * 60 ? `${String(Math.floor(next / 60)).padStart(2, "0")}:${String(next % 60).padStart(2, "0")}` : null;
}

function complete(stored: StoredTrip) {
  const { trip } = stored;
  const blockedId = stored.scenario === "needs-review" ? trip.stops.at(-1)!.id : null;
  // Deterministic examples, never a real travel feasibility calculation.
  const candidates = trip.stops.filter((stop, index) => {
    const proposed = addFifteen(stop.time);
    const next = trip.stops[index + 1];
    return stop.id !== blockedId && stop.booking === "none" && proposed && (!stop.endTime || proposed < stop.endTime) && (!next || next.date !== stop.date || proposed < next.time);
  }).sort((a, b) => priority(a.time) - priority(b.time)).slice(0, 2);
  const candidateIds = new Set(candidates.map((stop) => stop.id));
  const results: StoredResult[] = trip.stops.map((stop) => {
    const base = { id: crypto.randomUUID(), stopId: stop.id, date: stop.date, title: stop.title, originalValue: stop.time };
    if (stop.id === blockedId) return { ...base, status: "needs_review", reason: "unverified" };
    if (candidateIds.has(stop.id)) return { ...base, status: "adjusted", proposedValue: addFifteen(stop.time)!, reason: "buffer" };
    return { ...base, status: "unchanged", proposedValue: stop.time, reason: stop.booking === "booked" ? "booked" : "kept" };
  });
  trip.stops = trip.stops.map((stop) => candidateIds.has(stop.id) ? { ...stop, originalTime: stop.time, time: addFifteen(stop.time)! } : stop);
  trip.status = "ready";
  trip.verification = { status: "completed", progress: 100, stages: stages(100), results };
}

function priority(time: string) { return time === "11:00" ? 0 : time === "14:00" ? 1 : 2; }
