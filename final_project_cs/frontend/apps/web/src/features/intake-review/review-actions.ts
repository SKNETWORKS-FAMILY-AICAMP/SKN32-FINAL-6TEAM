import type { Translate } from "@/lib/i18n";
import type { AutofixChange, AutofixKeptReason, ReviewItem } from "@/lib/live/intake-review";

/**
 * The words of the check screen's actions: what it says when something was done, and why a button cannot be pressed now.
 * (2026-10-02 mockup: `toast`, `reason`, `WHY`.) Korean particles follow the last syllable of the name.
 */

/** The final consonant of a Hangul syllable: 0 = none, 8 = ㄹ; 0 as well for anything that is not Hangul. */
function finalConsonant(word: string): number {
  const code = word.charCodeAt(word.length - 1) - 0xAC00;
  return code >= 0 && code <= 11171 ? code % 28 : 0;
}
export const eul = (word: string) => word + (finalConsonant(word) ? "을" : "를");
export const ro = (word: string) => { const jong = finalConsonant(word); return word + (jong && jong !== 8 ? "으로" : "로"); };
export const gwa = (word: string) => word + (finalConsonant(word) ? "과" : "와");

export type ActionKind = "lock" | "edit" | "auto" | "delete" | "autoAll" | "register";

export interface BlockedInput {
  action: ActionKind;
  item?: Pick<ReviewItem, "status" | "locked" | "can_lock">;
  /** Something is being checked again, or a request is on its way. */
  busy: boolean;
  /** How many places and legs still need the customer (for 「다음 동작」). */
  needs?: number;
}

/**
 * Why a button cannot be pressed now, or null when it can. The mockup's rule: a stop that needs a look must be fixed before it
 * is locked, a locked stop cannot be changed, and nothing is pressed while the server is still checking.
 */
export function blockedReason({ action, item, busy, needs = 0 }: BlockedInput, t: Translate): string | null {
  if (busy) return t("바뀐 일정을 다시 확인하는 중이에요 · 잠시만요", "A change is being checked again · one moment");
  if (action === "lock") {
    if (item && !item.locked && !item.can_lock) return item.status === "review"
      ? t("확인이 필요한 일정은 먼저 고쳐야 고정할 수 있어요", "A stop that needs review must be fixed before it can be locked")
      : t("장소가 정해진 일정만 고정할 수 있어요", "Only a stop with a settled place can be locked");
    return null;
  }
  if (action === "autoAll") return needs === 0 ? t("고칠 곳이 없어요", "Nothing to fix") : null;
  if (action === "register") return needs > 0 ? t(`확인이 필요한 항목 ${needs}건이 남아 있어요 · 전체 자동 추천이나 수정으로 먼저 고쳐 주세요`, `${needs} items still need review · fix them with Auto-fix all or by editing first`) : null;
  if (item?.locked) {
    if (action === "delete") return t("고정한 일정은 삭제할 수 없어요 · 잠금을 먼저 풀어 주세요", "A locked stop cannot be deleted · unlock it first");
    return t("고정한 일정이라 바꿀 수 없어요 · 잠금을 풀면 수정할 수 있어요", "This stop is locked · unlock it to change it");
  }
  return null;
}

export interface ToastText { message: string; sub?: string }

const KEPT_WORD: Record<AutofixKeptReason, readonly [ko: string, en: string]> = {
  locked: ["고정한 일정이에요", "locked"],
  no_time: ["시각이 없어요", "no time set"],
  no_candidates: ["대체 후보가 없어요", "no alternatives"],
  no_fitting_place: ["시간이 맞는 장소가 없어요", "no place that fits the time"],
  no_fitting_time: ["이동 시간에 맞는 시각이 없어요", "no time that fits the travel"],
  nothing_to_change: ["바꿀 것이 없어요", "nothing to change"],
};

const span = (value: { starts_at: string | null; ends_at: string | null }) => value.starts_at && value.ends_at ? `${value.starts_at}–${value.ends_at}` : value.starts_at ?? "";

export const said = {
  locked: (name: string, t: Translate): ToastText => ({
    message: t(`${eul(name)} 꼭 넣을 일정으로 고정했어요`, `Locked ${name} — it stays in the plan`),
    sub: t("다시 짜거나 바꿔도 빠지지 않게 서버에 알렸어요", "Replanning or other changes will keep it"),
  }),
  unlocked: (name: string, t: Translate): ToastText => ({
    message: t(`${name} 고정을 풀었어요`, `Unlocked ${name}`),
    sub: t("이제 바꾸거나 삭제할 수 있어요", "You can change or delete it now"),
  }),
  removed: (name: string, t: Translate): ToastText => ({ message: t(`${name} 일정을 삭제했어요`, `Deleted ${name}`) }),
  changedPlace: (from: string, to: string, how: "auto" | "pick" | "search", t: Translate): ToastText => ({
    message: t(`${eul(from)} ${ro(to)} 바꿨어요`, `Changed ${from} to ${to}`),
    sub: how === "auto" ? t("대체 후보 1순위 · 바뀐 장소와 앞뒤 이동을 다시 확인해요", "Top alternative · the new place and the legs around it are checked again")
      : t("바뀐 장소와 앞뒤 이동을 다시 확인해요", "The new place and the legs around it are checked again"),
  }),
  timesChanged: (name: string, t: Translate): ToastText => ({
    message: t(`${name} 시각을 바꿨어요`, `Changed the time of ${name}`),
    sub: t("바뀐 일정과 앞뒤 이동을 다시 확인해요", "The stop and the legs around it are checked again"),
  }),
  /** 「확인이 필요한 2건을 검증된 대체 일정으로 바꿨어요」 — what the server changed, from → to. */
  autofixed: (changes: readonly AutofixChange[], fixed: number, kept: number, t: Translate): ToastText => ({
    message: t(`확인이 필요한 ${fixed}건을 검증된 대체 일정으로 바꿨어요`, `Switched ${fixed} ${fixed === 1 ? "item" : "items"} that needed review to checked alternatives`),
    sub: [
      ...changes.slice(0, 3).map((change) => `${change.from.place?.name ?? change.title} → ${change.to.place?.name ?? change.title} ${span(change.to)}`.trim()),
      ...(changes.length > 3 ? [t(`외 ${changes.length - 3}곳`, `and ${changes.length - 3} more`)] : []),
      ...(kept ? [t(`${kept}곳은 그대로`, `${kept} left as they are`)] : []),
    ].join(" · "),
  }),
  /** Nothing could be changed: say why, in the server's reasons. */
  autofixNothing: (kept: readonly { reason: AutofixKeptReason }[], t: Translate): ToastText => {
    const reasons = [...new Set(kept.map((entry) => entry.reason).filter((reason) => reason !== "nothing_to_change"))].map((reason) => t(...KEPT_WORD[reason]));
    return { message: t("바꿀 수 있는 대체 일정이 없어요", "There is no alternative plan to switch to"), sub: reasons.join(" · ") || undefined };
  },
  revalidated: (ready: boolean, needs: number, t: Translate): ToastText => ready
    ? { message: t("재검증을 통과했어요", "Passed the recheck"), sub: t("이대로 진행할 수 있어요 · 오른쪽 버튼이 「여행 등록」으로 바뀌었어요", "You can go ahead · the right button now says Register trip") }
    : { message: t("다시 확인했어요", "Checked again"), sub: needs > 0 ? t(`확인이 필요한 항목 ${needs}건이 남아 있어요`, `${needs} ${needs === 1 ? "item" : "items"} still need review`) : t("위의 확인할 것을 먼저 채워 주세요", "Fill in the items above first") },
  undone: (t: Translate): ToastText => ({ message: t("되돌렸어요", "Undone"), sub: t("바꾸기 전 값으로 다시 보냈어요", "Sent the earlier values again") }),
  noAlternative: (t: Translate): ToastText => ({ message: t("바꿀 수 있는 대체 장소가 없어요", "There is no alternative place to switch to") }),
};

/** 「삭제할 일정」 dialog text: the title and the day/time line. */
export function deleteQuestion(name: string, when: string, t: Translate): { title: string; detail: string } {
  return {
    title: t(`${name} 일정을 삭제하시겠습니까?`, `Delete ${name}?`),
    detail: when,
  };
}
