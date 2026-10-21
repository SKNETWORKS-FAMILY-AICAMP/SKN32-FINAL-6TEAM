import { distanceM } from "@/features/map/map-geometry";
import type { Language, Translate } from "@/lib/i18n";
import { eun, ro } from "@/lib/josa";
import type { MoveOptions } from "@/lib/live/move-options";
import type { PlanAsk, PlanCandidate, PlanCheckView, PlanItem, PlanMove } from "./model";
import { fareText } from "./move-mode";

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
export type StopAct = { type: "pick"; candidate: PlanCandidate } | { type: "confirm" } | { type: "noplace" }
  | { type: "taxi"; moveId: string } | { type: "later"; start: string; end: string }
  // `[2026-10-21 P6]` An option of an interpretation question; `search`: the stop is put back and the change screen's place search opens on these words.
  | { type: "interpret"; option: string; search: string | null };
/**
 * `why`: the server's reason it cannot be picked (the option is shown, greyed, and says it when pressed) — null when it can.
 * `recommended`: `[2026-10-21 P6]` the server's first option (its reading), marked 「추천」.
 */
export interface StopOption { key: string; label: string; reason: string | null; effect: string; act: StopAct; why?: string | null; recommended?: boolean; tag?: { text: string; basis: string } | null }
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

/** Why a candidate: the server's own reason, how far it is, and its opening-hours check at the stop's time — what the server said, joined (none when it said none). */
function candidateReason(candidate: PlanCandidate, t: Translate): string | null {
  const parts = [candidate.reason ?? null,
    candidate.distance ? t(`${candidate.distance.from}에서 ${candidate.distance.km.toFixed(1)}km`, `${candidate.distance.km.toFixed(1)} km from ${candidate.distance.from}`) : null,
    candidate.checks.find((row) => row.kind === "hours")?.text ?? null].filter((part): part is string => Boolean(part));
  return parts.length ? parts.join(" · ") : null;
}

/** The stops either side on the same day that have a place (the plan as the server has it, not only what is drawn). */
function neighbours(view: PlanCheckView, item: PlanItem): PlanItem[] {
  const day = view.items.filter((entry) => entry.day === item.day);
  const at = day.findIndex((entry) => entry.id === item.id);
  return [day.slice(0, at).reverse().find((entry) => entry.coordinates), day.slice(at + 1).find((entry) => entry.coordinates)].filter((entry): entry is PlanItem => Boolean(entry));
}

export function placeQuestion(item: PlanItem, plan: PlanCheckView, candidates: readonly PlanCandidate[], t: Translate, language: Language): StopAsk {
  const kind = stopKindOf(item);
  const changed = t("바뀐 장소와 앞뒤 이동을 다시 확인해요", "Checking the new place and the moves either side");
  const picks: StopOption[] = candidates.slice(0, STOP_CANDIDATES).map((candidate) => ({
    key: candidate.id,
    label: kind === "unfound" ? t(`${quotedRo(candidate.name)} 정하기`, `Choose “${candidate.name}”`) : t(`${quotedRo(candidate.name)} 바꾸기`, `Change to “${candidate.name}”`),
    reason: candidateReason(candidate, t), effect: changed, act: { type: "pick", candidate },
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
    const near = item.coordinates ? neighbours(plan, item).map((entry) => distanceM(item.coordinates!, entry.coordinates!)) : [];
    const keep: StopOption[] = item.coordinates ? [{
      key: "confirm", label: t(`「${place}」 그대로`, `Keep “${place}”`),
      reason: near.length ? t(`앞뒤 일정에서 평균 ${Math.round(near.reduce((sum, value) => sum + value, 0) / near.length)}m`, `${Math.round(near.reduce((sum, value) => sum + value, 0) / near.length)} m from the stops either side on average`) : null,
      effect: t(`${quotedRo(place)} 확정하고 다시 확인해요`, `Settles on “${place}” and checks again`), act: { type: "confirm" },
    }] : [];
    const question = item.placeChoices && item.placeChoices > 1
      ? t(`${quotedEun(item.title)} 맞는 곳이 ${item.placeChoices}곳이라 가까운 ${quotedRo(place)} 임시로 골랐어요. 어디로 갈까요?`, `${item.placeChoices} places match “${item.title}”, so the nearest, “${place}”, was taken for now. Where should we go?`)
      : t(`${quotedEun(item.title)} 이름이 여러 곳이라 가까운 ${quotedRo(place)} 임시로 골랐어요. 어디로 갈까요?`, `Several places match “${item.title}”, so the nearest, “${place}”, was taken for now. Where should we go?`);
    return { need: "confirm", question, options: [...keep, ...picks] };
  }
  const why = item.checks.find((row) => row.result === "bad")?.text ?? item.checks.find((row) => row.result === "warn")?.text ?? null;
  return { need: "fix", options: picks, question: why
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
export function arrivalQuestion(item: PlanItem, move: PlanMove, from: PlanItem | null, ways: MoveOptions | null, later: { start: string; end: string } | null, t: Translate): StopAsk {
  const late = Math.max(0, -(move.slackMin ?? 0));
  const leg = `${from?.title ?? ""} → ${item.title}`;
  const taxi = ways?.options.find((option) => option.mode === "taxi");
  const options: StopOption[] = [];
  if (taxi) {
    const spare = taxi.slackMin === null ? null : taxi.slackMin < 0 ? t(`일정보다 ${-taxi.slackMin}분 늦어요`, `${-taxi.slackMin} min late`) : t(`${taxi.slackMin}분 여유`, `${taxi.slackMin} min to spare`);
    options.push({ key: "taxi", label: t("택시로 바꾸기", "Take a taxi"),
      reason: [taxi.minutes !== null ? t(`택시 ${taxi.minutes}분`, `Taxi ${taxi.minutes} min`) : null, spare, fareText(taxi, t)].filter(Boolean).join(" · "),
      effect: t("이 구간만 다시 계산해요", "Only this leg is counted again"), act: { type: "taxi", moveId: move.id },
      // The reason a way cannot be picked, as the travel mode box says it (`move-mode.tsx`).
      why: taxi.fits === true ? null : taxi.whyNot ?? (taxi.fits === null ? t("계산이 오래 걸려 확인하지 못했어요", "The server could not finish counting this one")
        : t("다음 일정 시작 안에 닿지 않아요", "It does not reach before the next stop starts")) });
  }
  if (later) options.push({ key: "later", label: t(`「${item.title}」 ${later.start} 시작으로 늦추기`, `Start “${item.title}” at ${later.start}`), reason: null,
    effect: t("시작 시각을 바꾸고 뒤 일정과 이동을 다시 확인해요", "Changes the start and checks the stops and moves after it again"), act: { type: "later", start: later.start, end: later.end } });
  return { need: "fix", options, question: t(`「${leg}」 이동이 일정보다 ${late}분 늦어요. 어떻게 할까요?`, `The way “${leg}” arrives ${late} min late. What should we do?`) };
}
