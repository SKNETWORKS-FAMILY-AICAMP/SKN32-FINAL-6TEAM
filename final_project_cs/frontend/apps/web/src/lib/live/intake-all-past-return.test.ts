import { afterEach, describe, expect, it, vi } from "vitest";
import { translator } from "../i18n";
import { LiveError } from "./client";
import { ALL_PAST_CODE, ALL_PAST_TEXT } from "./error-text";
import type { IntakeView } from "./intake";
import { planFromIntake, type PlanDeps, type PlanHooks } from "./intake-plan";
import { clearIntakeArrival, clearIntakeFailure, entryReturnOf, forgetIntakeSubmission, intakeFailure, rememberEmptyIntake, rememberIntakeArrival } from "./intake-start";

// `[2026-10-26 사용자 지시]` 「전부 과거면 계획 고르는 화면으로 넘어가면 안되고 그 전에 있는 계획담기 페이지의 가드레일에 걸려서 통과 안되게」.
// The server ends such an intake on the plan entry: `status: fatal` · `fatal_code: all_dates_in_past` (wiki web-intakes.md). The page goes back to
// 「계획 담기」 with the sentence instead of opening the plan check — as it already does for a read without stops.
const SERVER_SENTENCE = "모든 일정이 오늘 이전이에요. 여행 날짜를 확인해주세요";
const item = { id: "0-0" };
const view = (status: IntakeView["status"], extra: Partial<IntakeView> = {}): IntakeView =>
  ({ intake_id: "i1", status, stage: status, stage_label: status, revision: 1, fatal: null, trip_id: null, sources: [], check: null, needs_review: [], ...extra }) as IntakeView;
const allPast = view("fatal", { fatal: { code: ALL_PAST_CODE, detail: SERVER_SENTENCE },
  sources: [{ source_id: "s", kind: "text", lines: [{ text: "2026년 10월 20일 10:00 경복궁" }], items: [] }] as unknown as IntakeView["sources"] });

afterEach(() => { clearIntakeArrival("i1"); forgetIntakeSubmission("i1"); clearIntakeFailure(); });

describe("entryReturnOf — a finished read that goes back to the plan entry instead of the plan check", () => {
  it("every stop before today: the server's sentence on the Korean screen, the web's on the English one", () => {
    expect(ALL_PAST_CODE).toBe("all_dates_in_past");
    expect(entryReturnOf(allPast, translator("ko"))).toBe(SERVER_SENTENCE);
    expect(entryReturnOf(allPast, translator("en"))).toBe(ALL_PAST_TEXT[1]);
    expect(ALL_PAST_TEXT[0]).toBe(SERVER_SENTENCE);
  });

  it("a read without stops still goes back with its own sentence (unchanged)", () => {
    const empty = view("review", { sources: [{ source_id: "s", kind: "text", lines: [], items: [] }] as unknown as IntakeView["sources"] });
    expect(entryReturnOf(empty, translator("ko"))).toBe("일정을 찾지 못했어요. 날짜·시간·장소를 확인해 다시 입력하거나 파일을 올려 주세요.");
    expect(entryReturnOf(empty, translator("en"))).toBe("No stops were found. Check the dates, times and places, then edit your plan or upload a file.");
  });

  it("stays on the intake page for everything else: reading, a plan with stops (partly past included), another failure", () => {
    const withStops = view("review", { sources: [{ source_id: "s", kind: "text", lines: [], items: [item] }] as unknown as IntakeView["sources"] });
    expect(entryReturnOf(view("reading"), translator("ko"))).toBeNull();
    expect(entryReturnOf(withStops, translator("ko"))).toBeNull();
    expect(entryReturnOf(view("fatal", { fatal: { code: "reading_failed", detail: "읽지 못했어요" } }), translator("ko"))).toBeNull();
    expect(entryReturnOf(undefined, translator("ko"))).toBeNull();
  });

  it("the entry page gets the sentence and what was sent back (text and files), without sending it again", () => {
    const file = new Blob(["계획"]) as File;
    rememberIntakeArrival("i1", "서울 여행 계획\n2026년 10월 20일 10:00 경복궁", [file]);
    rememberEmptyIntake("i1", entryReturnOf(allPast, translator("en"))!, "읽힌 원문");
    expect(intakeFailure()).toEqual({ message: ALL_PAST_TEXT[1], text: "서울 여행 계획\n2026년 10월 20일 10:00 경복궁", files: [file], plan: null });
  });
});

describe("planFromIntake — a wish read as wholly past stays on the entry page with the same sentence", () => {
  function deps(v: IntakeView): PlanDeps {
    return { getIntake: vi.fn(async () => v), planIntake: vi.fn(async () => ({ status: "confirmed" as const, trip: { trip_id: "t" } })), sleep: vi.fn(async () => undefined), now: () => 0 };
  }
  const hooks: PlanHooks = { phase: vi.fn(), progress: vi.fn(), cancelled: () => false };
  const ask = { start_date: "2026-11-05", days: 2, party_size: 2, wish: "궁궐" };

  it.each([["ko", SERVER_SENTENCE], ["en", ALL_PAST_TEXT[1]]] as const)("%s", async (language, sentence) => {
    const d = deps(allPast);
    const error = await planFromIntake("i1", ask, language, hooks, d).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(LiveError);
    expect((error as LiveError).code).toBe(ALL_PAST_CODE);
    expect((error as LiveError).message).toBe(sentence);
    expect(d.planIntake).not.toHaveBeenCalled();
  });

  it("another read failure keeps the server's detail (unchanged)", async () => {
    const error = await planFromIntake("i1", ask, "en", hooks, deps(view("fatal", { fatal: { code: "reading_failed", detail: "서버 문장" } }))).catch((e: unknown) => e);
    expect((error as LiveError).message).toBe("서버 문장");
  });
});
