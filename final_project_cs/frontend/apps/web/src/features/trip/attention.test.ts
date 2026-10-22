import { describe, expect, it } from "vitest";
import type { Notice, Proposal } from "@/lib/live/extras";
import { causeLines, changeOf, dayBefore, NOTICE_LIMIT, noticeFeed, openChoices, proposalStop, proposalText, recentNotices, undoableChange, withoutPlanLink } from "./attention";
import type { TripStop } from "./model";

const stop = (id: string): TripStop => ({ id, date: "2026-09-28", time: "12:00", title: "황생가칼국수", booking: "unknown", notes: "" });
const proposal = (id: string, status: string): Proposal => ({ id, itemId: "i1", baseVersion: 1, reason: "closed", status, safety: false, expiresAt: null, options: [] });
const notice = (key: string, at: string, over: Partial<Notice> = {}): Notice => ({ key, type: "change_notice", kind: null, text: "t", version: 1, proposalId: null, delivery: "sent", at, rollback: null, safety: null, changed: null, ...over });

describe("what the trip screen asks the customer to decide", () => {
  it("lists only proposals that are still open, with the stop they are about", () => {
    const choices = openChoices([proposal("p1", "open"), proposal("p2", "kept"), proposal("p3", "chosen")], [], [stop("i1")]);
    expect(choices.map((choice) => choice.proposal.id)).toEqual(["p1"]);
    expect(choices[0].stop?.title).toBe("황생가칼국수");
  });

  it("takes the sentence from the notice that carries the proposal, and says nothing of its own when there is none", () => {
    const withText = openChoices([proposal("p1", "open")], [notice("n1", "2026-09-28T12:00:00+09:00", { type: "proposal_request", proposalId: "p1", text: "식당이 닫았어요." })], [stop("i1")]);
    expect(withText[0].text).toBe("식당이 닫았어요.");
    expect(openChoices([proposal("p1", "open")], [], [stop("i1")])[0].text).toBeNull();
  });

  it("takes the proposal's NEWEST sentence — once the options came, not the first 「바꿀까요?」 (2026-10-22 실서버)", () => {
    const asked = notice("proposal:p1", "2026-10-22T21:42:00+09:00", { type: "proposal_request", proposalId: "p1", text: "학고재 — 예보 주의사항이 있어요(강수확률 70%). … 「예보에 맞게 일정 변경」을 누르면 …" });
    const options = notice("proposal:p1:options", "2026-10-22T21:46:00+09:00", { type: "proposal_request", proposalId: "p1", text: "학고재 — 날씨 예보에 문제가 있어요. 어떻게 할까요? 1) 이솝 삼청 …" });
    expect(openChoices([proposal("p1", "open")], [asked, options], [stop("i1")])[0].text).toContain("어떻게 할까요?");
    expect(openChoices([proposal("p1", "open")], [options, asked], [stop("i1")])[0].text).toContain("어떻게 할까요?");   // the server lists oldest first — order does not matter
  });

  it("keeps a choice whose stop is gone — the proposal is still open, hiding it would hide a decision", () => {
    expect(openChoices([proposal("p1", "open")], [], [])[0].stop).toBeNull();
  });
});

describe("the notice list", () => {
  it("shows the newest first and says how many it left out", () => {
    const many = Array.from({ length: NOTICE_LIMIT + 3 }, (_, index) => notice(`n${index}`, `2026-09-28T${String(10 + (index % 10)).padStart(2, "0")}:00:00+09:00`));
    const { shown, total, hidden } = recentNotices(many);
    expect(shown).toHaveLength(NOTICE_LIMIT);
    expect(total).toBe(NOTICE_LIMIT + 3);
    expect(hidden).toBe(3);
    expect(Date.parse(shown[0].at)).toBeGreaterThanOrEqual(Date.parse(shown[1].at));
  });

  it("offers an undo only for the automatic change that made the version the trip is on now", () => {
    const undo = (base: number) => ({ baseVersion: base, toVersion: base - 1, requestId: `rollback:v${base}->v${base - 1}` });
    const notices = [notice("n2", "2026-09-28T10:00:00+09:00", { rollback: undo(2) }), notice("n3", "2026-09-28T11:00:00+09:00", { rollback: undo(3) }),
      notice("n4", "2026-09-28T12:00:00+09:00")];                                   // a change without an undo
    expect(undoableChange(notices, 3)?.key).toBe("n3");
    expect(undoableChange(notices, 4)).toBeNull();                                   // the plan moved on — an older undo would be refused
    expect(undoableChange(notices, undefined)).toBeNull();
  });
});

describe("「소식」 — one card per proposal, what waits stays in 「할 일」", () => {
  const none = { proposals: new Set<string>(), notices: new Set<string>() };
  const at = (time: string) => `2026-10-22T${time}:00+09:00`;
  const registered = notice("v1", at("11:40"), { type: "change_notice" });
  const asked = notice("proposal:p0", at("11:54"), { type: "proposal_request", proposalId: "p0" });
  const options = notice("proposal:p0:options", at("11:56"), { type: "proposal_request", proposalId: "p0" });
  const changed = notice("v2", at("20:53"), { type: "change_notice", version: 2, proposalId: "p0" });
  const service = notice("service:s1", at("18:00"), { kind: "service_notice" });

  it("puts a proposal's notices (asked · options · the change it made) on one entry, oldest first inside, newest entry first", () => {
    const feed = noticeFeed([registered, asked, options, changed], [proposal("p0", "chosen")], none);
    expect(feed.map((entry) => entry.kind)).toEqual(["proposal", "notice"]);
    const group = feed[0];
    expect(group.kind === "proposal" && group.notices.map((entry) => entry.key)).toEqual(["proposal:p0", "proposal:p0:options", "v2"]);
    expect(group.at).toBe(at("20:53"));
    expect(group.kind === "proposal" && group.proposal?.status).toBe("chosen");
  });

  it("leaves out what 「할 일」 holds and a service notice (it is under 「공지」)", () => {
    const feed = noticeFeed([registered, asked, options, service], [proposal("p0", "open")], { proposals: new Set(["p0"]), notices: new Set(["v1"]) });
    expect(feed).toEqual([]);
  });

  it("puts a version no notice told about in the list as its own line (the old 「변경 이력」), at its Seoul time", () => {
    const history = [{ version: 1, reason: "created", at: "2026-10-22 11:40", causes: [] }, { version: 3, reason: "customer_request", at: "2026-10-22 15:10", causes: ["점심을 옮겼어요."] }];
    const feed = noticeFeed([{ ...registered, version: 1 }], [], none, history);
    expect(feed.map((entry) => entry.kind)).toEqual(["version", "notice"]);
    expect(feed[0].at).toBe("2026-10-22T15:10:00+09:00");
    expect(changeOf({ type: "change_notice", version: 1 }, history)?.reason).toBe("created");
    expect(changeOf({ type: "proposal_request", version: 1 }, history)).toBeNull();
  });
});

describe("the stop a closed proposal is about now (server changed[].new_item_id, 2026-10-23)", () => {
  const moved = notice("v2", "2026-10-22T20:53:00+09:00", { proposalId: "p1", changed: [{ itemId: "i1", newItemId: "i2", from: "학고재", to: "이솝 삼청", at: "2026-10-29T10:45:00+09:00" }] });
  it("a picked one is the new stop its change notice names", () => {
    expect(proposalStop([moved], proposal("p1", "chosen"), [stop("i2")])?.id).toBe("i2");
  });
  it("kept or expired, the stop it asked about; none when that stop is gone or the pick predates the new id", () => {
    expect(proposalStop([], proposal("p1", "kept"), [stop("i1")])?.id).toBe("i1");
    expect(proposalStop([moved], proposal("p1", "chosen"), [stop("i1")])).toBeNull();
    expect(proposalStop([notice("v2", "2026-10-22T20:53:00+09:00", { proposalId: "p1" })], proposal("p1", "chosen"), [stop("i9")])).toBeNull();
  });
});

describe("what the notice cards show of the server's words", () => {
  const url = "http://127.0.0.1:8062/plan/34f919ba?t=9a0e";
  it("takes the plan's address off the registration sentence only in the server's frame, for this trip's address (2026-10-22 실서버 문장)", () => {
    expect(withoutPlanLink(`여행 일정이 준비되었습니다 — 내 여행. 계획서: ${url}`, url)).toBe("여행 일정이 준비되었습니다 — 내 여행.");
    expect(withoutPlanLink(`여행 일정이 준비되었습니다 — 내 여행. 계획서: ${url}`, "http://other/plan/x")).toBeNull();
    expect(withoutPlanLink(`계획서는 ${url} 에서 보세요.`, url)).toBeNull();
    expect(withoutPlanLink("문장", undefined)).toBeNull();
  });

  it("leaves out a cause that is the server's code only", () => {
    expect(causeLines(["closed", "customer_request · alternate", "식당이 문을 닫았어요."])).toEqual(["식당이 문을 닫았어요."]);
  });

  it("knows yesterday across a month", () => {
    expect(dayBefore("2026-10-22")).toBe("2026-10-21");
    expect(dayBefore("2026-11-01")).toBe("2026-10-31");
  });
});

describe("the server's proposal sentence without what the card draws (pending.proposal_notice, 2026-10-22 실서버 문장)", () => {
  const option = (rank: number, name: string, warnings: string[] = []) => ({ key: name, rank, name, startsAt: null, note: null, warnings });
  const warn = ["가격을 몰라 추가 비용을 계산할 수 없다", "그 시각 영업을 확인할 수 없다"];
  const sentence = "학고재 — 날씨 예보에 문제가 있어요. 어떻게 할까요? 1) 이솝 삼청 · 2) 아트스페이스3 이솝 삼청: 가격을 몰라 추가 비용을 계산할 수 없다 이솝 삼청: 그 시각 영업을 확인할 수 없다 아트스페이스3: 가격을 몰라 추가 비용을 계산할 수 없다 아트스페이스3: 그 시각 영업을 확인할 수 없다 답이 없으면 원래 일정을 그대로 둡니다.";
  const drawn = [option(1, "이솝 삼청", warn), option(2, "아트스페이스3", warn)];

  it("takes out the stop's name, the numbered options and their warnings when the card shows them", () => {
    expect(proposalText(sentence, { stopTitle: "학고재", options: drawn })).toBe("날씨 예보에 문제가 있어요. 어떻게 할까요? 답이 없으면 원래 일정을 그대로 둡니다.");
    expect(proposalText(sentence, { options: drawn })).toBe("학고재 — 날씨 예보에 문제가 있어요. 어떻게 할까요? 답이 없으면 원래 일정을 그대로 둡니다.");   // the chat card names no stop
  });

  it("keeps everything that is not the server's frame to the letter", () => {
    expect(proposalText(sentence, { stopTitle: "경복궁", options: [option(1, "이솝 삼청", warn), option(2, "다른 곳", warn)] })).toBe(sentence);
    expect(proposalText(sentence, {})).toBe(sentence);
    const noWarnings = "창덕궁 관람 — 날씨 예보에 문제가 있어요. 어떻게 할까요? 1) 국립고궁박물관 · 2) 서울역사박물관 답이 없으면 원래 일정을 그대로 둡니다.";
    expect(proposalText(noWarnings, { stopTitle: "창덕궁 관람", options: [option(1, "국립고궁박물관"), option(2, "서울역사박물관")] })).toBe("날씨 예보에 문제가 있어요. 어떻게 할까요? 답이 없으면 원래 일정을 그대로 둡니다.");
  });
});
