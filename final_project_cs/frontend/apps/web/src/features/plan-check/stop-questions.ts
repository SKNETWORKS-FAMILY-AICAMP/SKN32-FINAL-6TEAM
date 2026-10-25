import { distanceM } from "@/features/map/map-geometry";
import type { Language, Translate } from "@/lib/i18n";
import { eun, ro } from "@/lib/josa";
import { checkLineText } from "@/lib/live/error-text";
import type { MoveOptions } from "@/lib/live/move-options";
import type { PlanAsk, PlanCandidate, PlanCheckView, PlanItem, PlanMove } from "./model";
import { fareText } from "./move-mode";
import { canAcknowledgeHours } from "./hours-warning";

/**
 * ★`[2026-10-20 사용자 결정 — 계획 확인 C안]` The question asked inside a card the first check stopped at (flow mockup `mockups/tripilot-plan-flow-register.html` 4단계):
 * a sentence, then options — each with why (「이유:」), the way in and out for a place (`legs`) and what picking it does (「고르면:」). Built from what the server says now
 * (`place_state` · `candidates_hint` · the 휴무 check · `prefill.questions` · the stop's alternatives), told apart by those values, never by reading the words.
 * `confirm`: the server took a place for now and the customer says whether it is the one (「이 일정이 맞는지 먼저 확인해 주세요」); `fix`: something has to change.
 */
export type StopNeed = "confirm" | "fix";

/**
 * `[2026-10-07 서버 c0ca7054]` Which step of the ladder the server took an alternative from — the tag beside it on the change screen and (`[2026-10-21 사용자 지시]`) in the
 * question box: the same stay offered twice (to stay · to eat there, 「호텔 조식」) is told apart by it.
 */
export function basisTag(basis: PlanCandidate["basis"], t: Translate): string | null {
  return basis === "same_kind" ? t("같은 종류", "Same kind") : basis === "similar_experience" ? t("비슷한 경험", "Similar experience")
    : basis === "meal_inferred" ? t("식사 시간 식당", "Meal-time place") : basis === "lodging" ? t("숙소", "Stay")
      : basis === "lodging_meal" ? t("숙소 안 식사", "Meal at the stay") : basis === "taste" ? t("취향 추천", "For your taste") : null;
}
export type StopAct = { type: "pick"; candidate: PlanCandidate } | { type: "confirm" } | { type: "noplace" } | { type: "acknowledge-hours" }
  | { type: "taxi"; moveId: string } | { type: "later"; start: string; end: string }
  // `[2026-10-21 P6]` An option of an interpretation question; `search`: the stop is put back and the change screen's place search opens on these words.
  | { type: "interpret"; option: string; search: string | null };
/**
 * `why`: the server's reason it cannot be picked (the option is shown, greyed, and says it when pressed) — null when it can.
 * `recommended`: `[2026-10-21 P6]` the server's first option (its reading), marked 「추천」.
 */
export interface StopOption {
  key: string; label: string;
  /** `[2026-10-21 사용자 결정 — 이유 · 고르면은 필요한 것만]` The one fact this question tells the options apart by (distance · that day's hours · a taxi's time and fare), shown without a lead word. */
  fact?: string | null;
  /** 「이유:」 — only where the option is another kind than asked (a similar experience, a meal place, a meal at the stay, the customer's taste), or the server's own (interpretation). */
  reason: string | null;
  /** 「고르면:」 — only where the label does not say what happens (empty = no line). */
  effect: string;
  act: StopAct; why?: string | null; recommended?: boolean; tag?: { text: string; basis: string } | null;
}
export interface StopAsk { need: StopNeed; question: string; options: StopOption[] }

/** As many alternatives as the card offers (A · B · C). */
export const STOP_CANDIDATES = 3;

/** `「name」으로` — the particle follows the name's last sound, after the closing mark. */
const quotedRo = (name: string) => `「${name}」${ro(name).slice(name.length)}`;
const quotedEun = (name: string) => `「${name}」${eun(name).slice(name.length)}`;

/** What kind of question the stop asks — the first that applies: the place was not found, the day is a closed day, one of several places was taken for now, anything else. */
export function stopKindOf(item: PlanItem): "unfound" | "closed" | "nearest" | "other" {
  if (item.unfound) return "unfound";
  if (item.checks.some((row) => row.kind === "closed" && row.result === "bad")) return "closed";
  if (item.placeState === "picked_nearest") return "nearest";
  return "other";
}

/** 「10.26(월)」 */
function dayText(date: string, language: Language): string {
  const weekday = new Intl.DateTimeFormat(language === "ko" ? "ko-KR" : "en-US", { weekday: "short", timeZone: "Asia/Seoul" }).format(new Date(`${date}T12:00:00+09:00`));
  return `${date.slice(5, 7)}.${date.slice(8, 10)}(${weekday})`;
}

/**
 * ★`[2026-10-21 사용자 결정 — 이유 · 고르면은 필요한 것만]` (목업 `mockups/tripilot-plan-check-option-lines.html`) The server's reason sentence says the step, the distance, the hours and the time
 * to spare in one sentence — values that come on their own too (the tag, `distance`, the hours check, the legs). The question box shows them as such, not the sentence:
 * one fact line, the one this question tells the options apart by — that day's hours first for a stop closed that day, the distance otherwise (no hours for a stay).
 */
function candidateFact(candidate: PlanCandidate, kind: ReturnType<typeof stopKindOf>, t: Translate): string | null {
  const distance = candidate.distance ? t(`${candidate.distance.from}에서 ${candidate.distance.km.toFixed(1)}km`, `${candidate.distance.km.toFixed(1)} km from ${candidate.distance.from}`) : null;
  const stay = candidate.basis === "lodging" || candidate.basis === "lodging_meal";
  const row = stay ? undefined : candidate.checks.find((check) => check.kind === "hours");
  const hours = !row ? null : row.result === "unknown" ? t("운영시간을 몰라요", "Opening hours unknown") : row.text || null;
  const parts = kind === "closed" ? [hours, distance] : [distance, hours];
  const line = parts.filter((part): part is string => Boolean(part)).join(" · ");
  return line || null;
}

/** The meal of a stop's time (the server's meal windows, `candidates.py` 「끼니 시간의 시장」), or null outside them. */
function mealOf(start: string | null | undefined, t: Translate): string | null {
  const at = start && /^\d{2}:\d{2}$/.test(start) ? Number(start.slice(0, 2)) * 60 + Number(start.slice(3)) : null;
  if (at === null) return null;
  return at >= 420 && at <= 600 ? t("아침", "Breakfast") : at >= 690 && at <= 870 ? t("점심", "Lunch") : at >= 1050 && at <= 1230 ? t("저녁", "Dinner") : null;
}

const EXPERIENCES: Record<string, [string, string]> = { indoor_exhibit: ["실내 전시를 하는", "an indoor exhibition"], outdoor_walk: ["야외에서 걷고 둘러보는", "an outdoor walk"] };

/** 「이유:」 for an alternative of another kind than asked — told from its step (`basis`), in the app's own words; none for the same kind (its tag says it). */
function candidateReason(candidate: PlanCandidate, item: PlanItem, t: Translate): string | null {
  if (candidate.basis === "similar_experience") {
    const group = candidate.experience ? EXPERIENCES[candidate.experience] : undefined;
    return group ? t(`같은 종류는 가까이에 없어 ${group[0]} 곳이에요`, `Nothing of the same kind is near, so a place for ${group[1]}`)
      : t("같은 종류는 가까이에 없어 비슷한 경험을 하는 곳이에요", "Nothing of the same kind is near, so a place for a similar experience");
  }
  if (candidate.basis === "meal_inferred") {
    const meal = mealOf(item.startsAt, t);
    return meal ? t(`${meal} 시간이고 그 시간에 식사 일정이 따로 없어 식당도 보여 드려요`, `It is ${meal.toLowerCase()} time with no meal planned then, so places to eat are shown too`)
      : t("식사 시간이고 그 시간에 식사 일정이 따로 없어 식당도 보여 드려요", "It is a meal time with no meal planned then, so places to eat are shown too");
  }
  if (candidate.basis === "lodging_meal") return t("이 숙소 안에서 식사하는 경우예요 · 숙소 안 식당이 있는지는 확인하지 못했어요", "A meal at this stay · whether it has a restaurant was not checked");
  if (candidate.basis === "taste") return candidate.reason ?? null;          // what of the customer's taste it follows — the server's own words
  return null;
}

/** The stops either side on the same day that have a place (the plan as the server has it, not only what is drawn). */
function neighbours(view: PlanCheckView, item: PlanItem): PlanItem[] {
  const day = view.items.filter((entry) => entry.day === item.day);
  const at = day.findIndex((entry) => entry.id === item.id);
  return [day.slice(0, at).reverse().find((entry) => entry.coordinates), day.slice(at + 1).find((entry) => entry.coordinates)].filter((entry): entry is PlanItem => Boolean(entry));
}

/** 「「…」 맞아요」 (mockup `tripilot-plan-check-stop-ask.html`): the place the server has is the one — sent back as the customer's pick. None for a place with no position. */
function keepOption(item: PlanItem, plan: PlanCheckView, place: string, t: Translate): StopOption[] {
  if (!item.coordinates) return [];
  const near = neighbours(plan, item).map((entry) => distanceM(item.coordinates!, entry.coordinates!));
  return [{
    key: "confirm", label: t(`「${place}」 맞아요`, `“${place}” is right`), reason: null,
    fact: near.length ? t(`앞뒤 일정에서 평균 ${Math.round(near.reduce((sum, value) => sum + value, 0) / near.length)}m`, `${Math.round(near.reduce((sum, value) => sum + value, 0) / near.length)} m from the stops either side on average`) : null,
    effect: "", act: { type: "confirm" },
  }];
}

export function placeQuestion(item: PlanItem, plan: PlanCheckView, candidates: readonly PlanCandidate[], t: Translate, language: Language): StopAsk {
  const kind = stopKindOf(item);
  // A pick that makes the stop a meal says so (a meal place for a market, a meal at the stay); a place for a place says nothing more than its label.
  const toMeal = t("식사 일정으로 넣고 앞뒤 이동을 다시 확인해요", "Puts it in as a meal and checks the moves either side again");
  const picks: StopOption[] = candidates.slice(0, STOP_CANDIDATES).map((candidate) => ({
    key: candidate.id,
    label: candidate.basis === "lodging_meal" ? t(`「${candidate.name}」에서 식사하기`, `Eat at “${candidate.name}”`)
      : kind === "unfound" ? t(`${quotedRo(candidate.name)} 정하기`, `Choose “${candidate.name}”`) : t(`${quotedRo(candidate.name)} 바꾸기`, `Change to “${candidate.name}”`),
    fact: candidateFact(candidate, kind, t), reason: candidateReason(candidate, item, t),
    effect: candidate.basis === "lodging_meal" || candidate.basis === "meal_inferred" ? toMeal : "", act: { type: "pick", candidate },
    tag: candidate.basis && basisTag(candidate.basis, t) ? { text: basisTag(candidate.basis, t)!, basis: candidate.basis } : null,
  }));
  if (kind === "unfound") {
    return { need: "fix", question: item.unfound!.question, options: [...picks,
      { key: "noplace", label: t("장소 없이 두기", "Keep without a place"), reason: null, effect: t("앞뒤 이동은 장소가 정해지면 확인해요", "Moves around it are checked once a place is set"), act: { type: "noplace" } }] };
  }
  if (kind === "closed") {
    return { need: "fix", options: picks, question: item.date
      ? t(`${quotedEun(item.title)} ${dayText(item.date, language)} 쉬는 날이에요. 어떻게 할까요?`, `“${item.title}” is closed on ${dayText(item.date, language)}. What should we do?`)
      : t(`${quotedEun(item.title)} 쉬는 날이에요. 어떻게 할까요?`, `“${item.title}” is closed that day. What should we do?`) };
  }
  if (kind === "nearest") {
    const place = item.place || item.title;
    const keep = keepOption(item, plan, place, t);
    const question = item.placeChoices && item.placeChoices > 1
      ? t(`${quotedEun(item.title)} 맞는 곳이 ${item.placeChoices}곳이라 가까운 ${quotedRo(place)} 임시로 골랐어요. 어디로 갈까요?`, `${item.placeChoices} places match “${item.title}”, so the nearest, “${place}”, was taken for now. Where should we go?`)
      : t(`${quotedEun(item.title)} 이름이 여러 곳이라 가까운 ${quotedRo(place)} 임시로 골랐어요. 어디로 갈까요?`, `Several places match “${item.title}”, so the nearest, “${place}”, was taken for now. Where should we go?`);
    return { need: "confirm", question, options: [...keep, ...picks] };
  }
  if (canAcknowledgeHours(item)) return { need: "confirm",
    question: t(`「${item.title}」 영업시간 주의를 읽고 어떻게 할지 골라 주세요`, `Read the opening-hours caution for “${item.title}” and choose how to continue`),
    options: [{ key: "acknowledge-hours", label: t("주의를 읽었어요 · 이 장소로 계속", "I read the caution · continue with this place"), reason: null,
      fact: item.checks.find((row) => row.kind === "hours" && row.result === "warn")?.text,
      effect: t("주의를 남기고 계속해요 · 주문 가능 여부를 확인한 것은 아니에요", "Continues with the caution kept · this does not confirm orders are available"),
      act: { type: "acknowledge-hours" } }, ...picks] };
  // ★`[2026-10-21 사용자 지적 · ST4F-708]` The server found a place but asks whether it is the one (a warning on its place row, nothing that must change — 「… 부분을 우리 장소 목록 정보로
  //   찾았어요 · 맞는지 확인해 주세요」): the question is 「맞는지 확인」, so its first option ends it there (mockup `tripilot-plan-check-stop-ask.html`), then the alternatives.
  const confirm = Boolean(item.place) && !item.checks.some((row) => row.result === "bad") && item.checks.some((row) => row.kind === "place" && row.result === "warn");
  const wrong = item.checks.find((row) => row.result === "bad") ?? item.checks.find((row) => row.result === "warn");
  const why = wrong ? checkLineText(wrong, t) : null;
  return { need: confirm ? "confirm" : "fix", options: confirm ? [...keepOption(item, plan, item.place!, t), ...picks] : picks, question: why
    ? t(`${quotedEun(item.title)} 확인이 필요해요 — ${why}. 어떻게 할까요?`, `“${item.title}” needs a look — ${why}. What should we do?`)
    : t(`${quotedEun(item.title)} 확인이 필요해요. 어떻게 할까요?`, `“${item.title}” needs a look. What should we do?`) };
}

/**
 * ★`[2026-10-21 사용자 결정 — P6 해석 확인 질문]` What a line of the plan means, asked at its time (mockup `mockups/tripilot-plan-check-interpretation.html`): the server's question and options as
 * they are (its first — the AI's reading — on top, marked), in the server's order. An option that puts the stop in and lets the customer pick its place carries the words to search for.
 */
export function interpretationQuestion(ask: PlanAsk): StopAsk {
  return { need: "confirm", question: ask.question, options: ask.options.map((option) => ({
    key: option.id, label: option.label, reason: option.reason, effect: option.effect ?? "", recommended: option.recommended,
    act: { type: "interpret", option: option.id, search: option.pickMyself ? option.query ?? ask.title : null },
  })) };
}

/** `[2026-10-21 P6]` 「직접 선택」 under the question: the option that puts the stop in for the customer to pick its place, else the one that puts it in — searched by its words either way. */
export function pickMyselfAnswer(ask: PlanAsk): { option: string; search: string } | null {
  const own = ask.options.find((option) => option.pickMyself) ?? ask.options.find((option) => option.id === "item");
  return own ? { option: own.id, search: own.query ?? ask.title } : null;
}

/**
 * `[2026-10-20 사용자 결정 — 계획 확인 C안 · 이동 확인 C안]` The way into the stopped card arrives late: asked in that card, after its place. Taxi from the leg's own ways (`GET …/moves/…/options` — its
 * minutes, time to spare and fare as the server gave them; greyed with the server's reason when it does not reach), and the stop started later as the server works it out
 * (`autofix {item_id, dry_run}` — `later`, none when it cannot). 「직접 수정」 opens the stop's own editor (its start and end).
 */
export interface LaterStart {
  start: string; end: string;
  /** `[2026-10-21 사용자 결정]` The stop after it on that day in the server's preview (`autofix {item_id, dry_run}` moves only this stop): how much it would overlap it, or be late to it. Absent when unknown. */
  next?: { title: string; start: string | null; overlapMin: number; lateMin: number } | null;
}

/** 「고르면:」 of 「늦추기」 — its new times and what that does to the stop after it, as the server's preview has it. */
function laterEffect(later: LaterStart, t: Translate): string {
  const span = `${later.start}${later.end ? `–${later.end}` : ""}`;
  if (later.next === undefined) return t("시작 시각을 바꾸고 뒤 일정과 이동을 다시 확인해요", "Changes the start and checks the stops and moves after it again");
  const next = later.next;
  if (!next || (next.overlapMin <= 0 && next.lateMin <= 0)) return t(`${span} · 뒤 일정은 그대로 맞아요`, `${span} · the stops after it still fit`);
  const when = next.start ? `(${next.start})` : "";
  return next.overlapMin > 0
    ? t(`${span} · 다음 「${next.title}」${when}과 ${next.overlapMin}분 겹쳐요 — 그 일정을 이어서 물어요`, `${span} · overlaps the next stop “${next.title}”${when} by ${next.overlapMin} min — it is asked next`)
    : t(`${span} · 다음 「${next.title}」${when}에 ${next.lateMin}분 늦게 닿아요 — 그 일정을 이어서 물어요`, `${span} · reaches the next stop “${next.title}”${when} ${next.lateMin} min late — it is asked next`);
}

export function arrivalQuestion(item: PlanItem, move: PlanMove, from: PlanItem | null, ways: MoveOptions | null, later: LaterStart | null, t: Translate): StopAsk {
  const late = Math.max(0, -(move.slackMin ?? 0));
  const leg = `${from?.title ?? ""} → ${item.title}`;
  const taxi = ways?.options.find((option) => option.mode === "taxi");
  const options: StopOption[] = [];
  if (taxi) {
    const spare = taxi.slackMin === null ? null : taxi.slackMin < 0 ? t(`일정보다 ${-taxi.slackMin}분 늦어요`, `${-taxi.slackMin} min late`) : t(`${taxi.slackMin}분 여유`, `${taxi.slackMin} min to spare`);
    options.push({ key: "taxi", label: t("택시로 바꾸기", "Take a taxi"), reason: null,
      fact: [taxi.minutes !== null ? t(`택시 ${taxi.minutes}분`, `Taxi ${taxi.minutes} min`) : null, spare, fareText(taxi, t)].filter(Boolean).join(" · "),
      effect: "", act: { type: "taxi", moveId: move.id },
      // The reason a way cannot be picked, as the travel mode box says it (`move-mode.tsx`).
      why: taxi.fits === true ? null : taxi.whyNot ?? (taxi.fits === null ? t("계산이 오래 걸려 확인하지 못했어요", "The server could not finish counting this one")
        : t("다음 일정 시작 안에 닿지 않아요", "It does not reach before the next stop starts")) });
  }
  if (later) options.push({ key: "later", label: t(`「${item.title}」 ${later.start} 시작으로 늦추기`, `Start “${item.title}” at ${later.start}`), reason: null,
    effect: laterEffect(later, t), act: { type: "later", start: later.start, end: later.end } });
  return { need: "fix", options, question: t(`「${leg}」 이동이 일정보다 ${late}분 늦어요. 어떻게 할까요?`, `The way “${leg}” arrives ${late} min late. What should we do?`) };
}
