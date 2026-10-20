import { distanceM } from "@/features/map/map-geometry";
import type { Language, Translate } from "@/lib/i18n";
import { eun, ro } from "@/lib/josa";
import type { PlanCandidate, PlanCheckView, PlanItem } from "./model";

/**
 * ★`[2026-10-20 사용자 결정 — 계획 확인 C안]` The question asked inside a card the first check stopped at (flow mockup `mockups/tripilot-plan-flow-register.html` 4단계):
 * a sentence, then options — each with why (「이유:」), the way in and out for a place (`legs`) and what picking it does (「고르면:」). Built from what the server says now
 * (`place_state` · `candidates_hint` · the 휴무 check · `prefill.questions` · the stop's alternatives), told apart by those values, never by reading the words.
 * `confirm`: the server took a place for now and the customer says whether it is the one (「이 일정이 맞는지 먼저 확인해 주세요」); `fix`: something has to change.
 */
export type StopNeed = "confirm" | "fix";
export type StopAct = { type: "pick"; candidate: PlanCandidate } | { type: "confirm" } | { type: "noplace" };
export interface StopOption { key: string; label: string; reason: string | null; effect: string; act: StopAct }
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
