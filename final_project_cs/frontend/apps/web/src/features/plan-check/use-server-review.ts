"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { autofixUndo, restorePlace } from "@/features/intake-review/autofix-undo";
import { editsFor, rows } from "@/features/intake-review/model";
import { translator, type Language, type Translate } from "@/lib/i18n";
import { LiveError } from "@/lib/live/client";
import { editIntake, restoreIntake, type IntakeEdit } from "@/lib/live/intake";
import { getMoveOptions, setMoveMode as postMoveMode, type MoveOptions } from "@/lib/live/move-options";
import { itemEdit } from "@/lib/live/intake-edits";
import {
  autofixIntake, getCandidates, getPlacePhotos, pickedPlace, revalidateIntake, searchPlaces, streamCandidates,
  type CandidateList, type CandidatePlace, type CandidateUpdate, type ReviewItem, type ReviewedIntakeView,
} from "@/lib/live/intake-review";
import { isLodgingReviewItem, planCandidate, safePhotoUrl } from "./from-review";
import type { PlaceInfo } from "./model";
import type { AutoResult, EditHow, PlaceChoice, PlanCheckActions } from "./plan-check";
import { retimeEdits } from "./retime-edits";
import { ReviewUndo } from "./review-undo";
import { newStopEdits } from "./new-stop";
import { candidateTimeEdits, proposedTimeOf } from "./risk-candidate-edits";
import { itemRiskOf, riskSignature } from "@/lib/live/risks";
import type { PlanCandidate } from "./model";
import { assertPlaceSearchComplete } from "./place-search-status";

/** How many alternatives get their photos fetched (A, B, C) — each is one call to the tourism photo service. */
const PHOTO_CANDIDATES = 3;
/** The re-check shows each stop for this long while the server works. */
const RECHECK_STEP_MS = 380;

/**
 * The plan-check screen's changes, done through the server's check-screen calls (`wiki/external/rest-endpoints.md`
 * 「확인 화면 검사 · 대체 후보 · 장소 검색 · 사진 · 잠금 · 전체 자동 추천 · 재검증」).
 *
 * ★The server decides; this only sends and shows its answer. Rules it enforces and this must not work around: a locked
 *   stop cannot be changed (409 `item_locked`), a lock goes alone (422 `lock_with_changes`), a picked place is taken by its
 *   coordinates, and an edit made on an older revision is refused (409 `stale_revision`) — the plan is then read again.
 * ★「되돌리기」 puts back the last change only when everything it changed can be put back; otherwise it says so (the screen
 *   offers it after a change, so a change that cannot be undone is told when it is pressed — never half-undone).
 */
export function useServerReview({ intakeId, view, language, apply, reread }: {
  intakeId: string;
  /** Undefined until the plan is read; the actions are only used once it is on screen. */
  view: ReviewedIntakeView | undefined;
  language: Language;
  /** Put the server's answer where the screen reads the plan from. */
  apply: (next: ReviewedIntakeView) => void;
  /** Read the plan again (an edit was refused as stale). */
  reread: () => void;
}): { actions: PlanCheckActions; dirty: boolean; rechecking: string | null; infos: Readonly<Record<string, PlaceInfo>>; preview: ReviewedIntakeView | null } {
  const [dirtyState, setDirtyState] = useState({ intakeId, value: false });
  // `[2026-10-20 사용자 지시]` A revision only saved (`review.checked === false`) is a change still to send: a reload keeps 「다시 제출」, not 「여행 등록」.
  const unchecked = view?.intake_id === intakeId && view.review?.checked === false;
  const dirty = (dirtyState.intakeId === intakeId && dirtyState.value) || unchecked;
  const setDirty = useMemo(() => (value: boolean) => setDirtyState({ intakeId, value }), [intakeId]);
  // `[2026-10-03]` 「전체 자동 추천」 is first only SHOWN (the server's dry run saves nothing): the plan as it would be, kept with the revision it was asked on.
  const [previewed, setPreviewed] = useState<{ view: ReviewedIntakeView; base: number } | null>(null);
  const [rechecking, setRechecking] = useState<string | null>(null);
  const [infos, setInfos] = useState<Record<string, PlaceInfo>>({});
  const latest = useRef<ReviewedIntakeView | undefined>(view);
  const undoEdits = useRef<IntakeEdit[] | null>(null);
  const allUndo = useMemo(() => new ReviewUndo(intakeId), [intakeId]);
  useEffect(() => {
    undoEdits.current = null;
    allUndo.activate();
    return () => { allUndo.deactivate(); };
  }, [allUndo]);
  const pickable = useRef(new Map<string, CandidatePlace>());
  /** `[2026-10-07]` The ways to go for a leg, asked when its box is opened and kept for the revision they were asked on (a re-opened box asks nothing). */
  const moveWays = useRef(new Map<string, Promise<MoveOptions | null>>());
  // `[2026-10-07 사용자 지적 — 이미 받은 대안을 다시 열 때도 로딩이 있다]` The alternatives of a stop: opening the change screen again, or 「자동 추천」 after it, does not ask again.
  // ★`[2026-10-20 사용자 지시]` Kept by stop, not by revision, until 「다시 제출」: after picking one of them (or moving a time) the change screen shows the
  //   same three again instead of working out the alternatives of the changed plan — the changed plan is checked once, when it is sent again.
  const alternatives = useRef(new Map<string, ReturnType<typeof getCandidates>>());
  /** Why the server's list for a stop is short or empty (`notes` of the candidates call), by stop id — said on the change screen. */
  const candidateNotes = useRef(new Map<string, string[]>());
  /**
   * ★`[2026-10-03 사용자 지시]` 목록 끝에서 밀기 전에 「전체 자동 추천」 미리 보기는 이미 받아 둔다: the dry run is asked for as soon as the checked plan is
   * on screen (while the check is still being drawn), so pushing past the end — or the button — shows it at once instead of waiting for the server.
   * One per revision; a failed one is simply asked again when it is needed.
   */
  const warmed = useRef<{ intakeId: string; base: number; ask: Promise<Awaited<ReturnType<typeof autofixIntake>>> } | null>(null);
  const needsLook = (view?.review?.needs?.total ?? 0) > 0;
  // `[2026-10-20]` Not for a revision only saved: its moves are not measured yet (the dry run would work on guesses) - it is asked once the plan is sent again.
  const warmRevision = view?.status === "review" && !unchecked ? view.revision : null;
  useEffect(() => {
    if (warmRevision === null || !needsLook || (warmed.current?.intakeId === intakeId && warmed.current.base === warmRevision)) return;
    const ask = autofixIntake(intakeId, warmRevision, language, true);
    warmed.current = { intakeId, base: warmRevision, ask };
    ask.catch(() => { if (warmed.current?.ask === ask) warmed.current = null; });
  }, [intakeId, language, warmRevision, needsLook]);
  useEffect(() => { latest.current = view?.intake_id === intakeId ? view : undefined; }, [view, intakeId]);

  const actions = useMemo<PlanCheckActions>(() => {
    const t = translator(language);
    const gone = () => new LiveError("item_gone", t("그 일정은 이미 없어요", "That stop is already gone"));
    const plan = (): ReviewedIntakeView => {
      if (!latest.current || latest.current.intake_id !== intakeId || !allUndo.active) throw gone();
      return latest.current;
    };
    const itemOf = (id: string): ReviewItem => {
      const item = plan().review?.items.find((entry) => entry.id === id);
      if (!item) throw gone();
      return item;
    };
    const targetOf = (item: ReviewItem) => ({ source_id: item.source_id, index: item.index });
    const staleThenRethrow = (error: unknown): never => {
      if (allUndo.active && error instanceof LiveError && error.code === "stale_revision") reread();
      throw error;
    };
    /** The stop's alternatives for the revision shown — asked once (a failure is not kept, so it is asked again). */
    // `[2026-10-19 사용자 지시]` Asked as a live answer: prepared alternatives come at once; otherwise the cards come first with straight-line
    // guesses and each measured leg / model reason as it lands (`onFirst` · `onUpdate`), then the final list. A later ask for the same revision gets the final list.
    const alternativesOf = (id: string, item: Parameters<typeof getCandidates>[1],
      onFirst?: (list: CandidateList) => void, onUpdate?: (update: CandidateUpdate) => void) => {
      const revision = plan().revision;
      // `[2026-10-20 사용자 지시]` By stop until 「다시 제출」 (see `alternatives`): a stop whose risk changed since (the changed plan's quick look) keeps the three it had.
      const currentRisk = itemRiskOf(itemOf(id).risk);
      const key = `${id}:${currentRisk ? riskSignature([currentRisk]) : ""}`;
      const kept = alternatives.current.get(key) ?? [...alternatives.current.entries()].find(([old]) => old.startsWith(`${id}:`))?.[1];
      if (kept) return kept;
      const ask = streamCandidates(intakeId, item, revision, language, onFirst ?? (() => undefined), onUpdate ?? (() => undefined))
        .catch((error: unknown) => { alternatives.current.delete(key); return staleThenRethrow(error); });
      alternatives.current.set(key, ask);
      return ask;
    };
    // Any answer that is the plan itself (a change, an undo, a re-check) ends a preview: it was a picture of the plan before that.
    const take = (next: ReviewedIntakeView) => {
      if (!allUndo.active || next.intake_id !== intakeId) return;
      latest.current = next; setPreviewed(null); apply(next);
    };
    /**
     * Send edits. ★`changed` says "the plan is no longer the one that was last checked" and is set BEFORE the new plan is
     * drawn: the other way round, the footer is drawn once with neither "nothing to fix" nor "check again" pending and offers
     * 「여행 등록」 for an instant (a click in that instant registered an unchecked plan — found by the browser test).
     */
    async function save(edits: IntakeEdit[], changed = false, how: EditHow = {}) {
      const before = plan();
      // ★`[2026-10-20 사용자 지시]` A change of the customer's (time · place · alternative · stop added or taken out) is only SAVED: the server does not
      //   measure the moves or re-place the stops around it now - 「다시 제출」 (`recheck`) checks the whole plan once. A lock or the plan's name is checked as before.
      // ★`[2026-10-20 사용자 결정 — 계획 확인 C안]` A pick inside the first check's question (`how.flow`) is saved WITH its check: the card is checked again where it stands and
      //   the check goes on — no 「다시 제출」 (the plan is not 「changed since the last check」) and no undo (the C안 flow has none).
      const next = await (changed && !how.flow ? editIntake(intakeId, before.revision, edits, language, { check: false })
        : editIntake(intakeId, before.revision, edits, language)).catch(staleThenRethrow);
      if (!allUndo.active) throw gone();
      if (!how.flow && edits.some((edit) => !edit.field.endsWith(".locked"))) allUndo.remember(before, next);
      else allUndo.advance(next);
      if (changed && !how.flow) setDirty(true);
      if (how.flow) alternatives.current.clear();                  // the plan is checked: alternatives are asked for the plan as it now is (as after 「다시 제출」)
      take(next);
    }
    /** The photos of one place the tourism service has (never stored here), as the change screen's `PlaceInfo`. */
    async function infoOf(place: { name: string; category?: string | null; address?: string | null; content_id?: string | null; ref?: string | null; kind?: string | null; source?: string | null }, withPhotos: boolean): Promise<PlaceInfo> {
      const ref = place.ref ?? (place.content_id ? `tour:${place.content_id}` : null);
      const info: PlaceInfo = { category: place.category ?? null, address: place.address ?? null, photos: [], kind: place.kind ?? null, origin: place.source ?? null };
      if (!withPhotos || !ref?.startsWith("tour:")) return info;
      try {
        const found = await getPlacePhotos(ref, language);
        info.photos = found.photos.flatMap((photo) => {
          const url = safePhotoUrl(photo.url);
          return url ? [{ caption: [photo.name ?? place.name, found.source_note].filter(Boolean).join(" "), url }] : [];
        });
      } catch { /* a photo that cannot be fetched is just not shown */ }
      return info;
    }
    const replaceWith = async (id: string, edit: IntakeEdit, kind: string | null = null, time?: PlanCandidate["proposedTime"], how: EditHow = {}) => {
      const item = itemOf(id);
      const back = restorePlace(targetOf(item), item.place);
      const timing = candidateTimeEdits(item, time);
      // ★`[2026-10-07 서버 c0ca7054 · 90d9e403]` A place of another kind than the stop (a meal place for an activity, a stay's own meal for a stay) changes the stop's kind with it - the server asks for both
      //   in the same request, or the meal lands in an activity. The undo puts the kind back too.
      const retype = kind !== null && kind !== item.kind;
      await save([edit, ...(retype ? [itemEdit.kind(targetOf(item), kind)] : []), ...timing.edits], true, how);
      undoEdits.current = !how.flow && back && timing.undo !== null ? [back,
        ...(retype && item.kind ? [itemEdit.kind(targetOf(item), item.kind)] : []), ...timing.undo] : null;
    };

    return {
      add: async (draft) => {
        const current = plan();
        const source = current.sources[0];
        if (!source) throw new LiveError("source_missing", t("일정을 넣을 원본을 찾지 못했어요. 다시 열어 주세요.", "No source to add this stop to. Reopen the plan."));
        const { index, edits } = newStopEdits(source, draft);
        await save(edits, true);
        undoEdits.current = [{ source_id: source.source_id, field: `items[${index}].removed`, value: true }];
      },
      edit: async (id, draft, how) => {
        const item = itemOf(id);
        const row = rows(plan()).find((entry) => entry.source.source_id === item.source_id && entry.item.index === item.index);
        if (!row) throw gone();
        const edits = editsFor(row, draft);
        if (!edits.length) return;
        await save(edits, true, how);
        undoEdits.current = null;
      },
      // `[2026-10-04]` Several stops' new times in ONE request: the plan is saved and checked once, not once per stop.
      retime: async (changes, how) => {
        const edits = changes.flatMap((change) => retimeEdits(itemOf(change.id), change));
        if (!edits.length) return;
        await save(edits, true, how);
        undoEdits.current = null;
      },
      remove: async (id) => {
        const item = itemOf(id);
        await save([itemEdit.remove(targetOf(item), true)], true);
        undoEdits.current = [itemEdit.remove(targetOf(item), false)];
      },
      editTrip: (field, value) => save([{ field: `trip.${field}`, value }]),

      // `[2026-10-07 사용자 지시 — 이동수단 고르기]` One leg at a time, only when its box is opened; the same answer for the same revision. A way the server could not finish (`fits: null`) is asked again the next time.
      moveOptions: (id) => {
        const move = plan().review?.moves.find((entry) => `${entry.from}:${entry.to}` === id);
        if (!move) return Promise.reject(gone());
        const revision = plan().revision;
        const key = `${revision}:${id}`;
        for (const old of [...moveWays.current.keys()]) if (!old.startsWith(`${revision}:`)) moveWays.current.delete(old);
        const kept = moveWays.current.get(key);
        if (kept) return kept;
        // A stale revision (409 - the plan moved on) re-reads the plan, like a change would; the box asks again for the new one when opened.
        const ask = getMoveOptions(intakeId, move.from, move.to, language, revision).catch((error: unknown) => { moveWays.current.delete(key); return staleThenRethrow(error); });
        moveWays.current.set(key, ask);
        void ask.then((found) => { if (found?.options.some((option) => option.fits === null)) moveWays.current.delete(key); }, () => undefined);
        return ask;
      },
      // The server counts the leg again with that way and answers with the whole checked plan: it is what the screen shows from now on, and it needs no 「다시 제출」 (the server already checked it).
      setMoveMode: async (id, mode) => {
        const move = plan().review?.moves.find((entry) => `${entry.from}:${entry.to}` === id);
        if (!move) throw gone();
        const answer = await postMoveMode(intakeId, move.from, move.to, plan().revision, mode, language).catch(staleThenRethrow);
        if (!allUndo.active) return;
        const next = { ...plan(), revision: answer.revision, review: answer.review };
        allUndo.advance(next);
        take(next);
      },

      candidates: async (id, onLive) => {
        const item = itemOf(id);
        // The live cards: the first list as the server sent it, changed in place by each update, drawn again each time (photos as they come).
        let first: CandidateList | null = null;
        let photos: (PlaceInfo | null)[] = [];
        let finished = false;
        const draw = () => {
          if (finished || !first || !onLive) return;
          onLive(first.candidates.map((candidate, at) => {
            const card = planCandidate(candidate, id, "candidate", photos[at] ?? null);
            pickable.current.set(card.id, candidate.place);
            return card;
          }));
        };
        const found = await alternativesOf(id, item, (list) => {
          first = { ...list, candidates: list.candidates.map((candidate) => ({ ...candidate })) };
          photos = list.candidates.map(() => null);
          draw();
          void Promise.all(list.candidates.map((candidate, at) => infoOf(candidate.place, at < PHOTO_CANDIDATES))).then((got) => { photos = got; draw(); });
        }, (update) => {
          const candidate = first?.candidates[update.rank - 1];
          if (!candidate) return;
          const { pending, ...rest } = update;
          Object.assign(candidate, { ...rest, rank: candidate.rank });
          candidate.pending = { before: false, after: false, reason: false, ...candidate.pending, ...pending };
          draw();
        });
        finished = true;
        candidateNotes.current.set(id, found.notes ?? []);
        // The stop's own photos fill its 「지금 일정」 card.
        if (item.place) void infoOf({ ...item.place, category: null, address: null }, true).then((info) => setInfos((current) => ({ ...current, [id]: info })));
        const cards = await Promise.all(found.candidates.map(async (candidate, at) => {
          const info = await infoOf(candidate.place, at < PHOTO_CANDIDATES);
          const card = planCandidate(candidate, id, "candidate", info);
          pickable.current.set(card.id, candidate.place);
          return card;
        }));
        return cards;
      },
      candidateNotes: (id) => candidateNotes.current.get(id) ?? [],
      searchToAdd: async (id, words) => {
        const item = itemOf(id);
        const found = await searchPlaces(intakeId, item, plan().revision, words, language).catch(staleThenRethrow);
        if (!allUndo.active) throw gone();
        assertPlaceSearchComplete(found, t);
        return found.results.map((result) => ({
          ...planCandidate(result, id, "search", { category: result.place.category, address: result.place.address, photos: [], kind: result.place.kind, origin: result.place.source }),
          pickedPlace: pickedPlace(result.place),
        }));
      },
      search: async (id, words) => {
        const item = itemOf(id);
        const found = await searchPlaces(intakeId, item, plan().revision, words, language).catch(staleThenRethrow);
        assertPlaceSearchComplete(found, t);
        return found.results.map((result) => {
          const card = planCandidate(result, id, "search", { category: result.place.category, address: result.place.address, photos: [], kind: result.place.kind, origin: result.place.source });
          pickable.current.set(card.id, result.place);
          return card;
        });
      },
      replace: async (id, choice: PlaceChoice, how) => {
        const item = itemOf(id);
        const target = targetOf(item);
        if (!("candidate" in choice)) return replaceWith(id, itemEdit.placeByName(target, choice.name), null, undefined, how);
        const place = pickable.current.get(choice.candidate.id);
        const picked = place && pickedPlace(place);
        // A place the server gave coordinates for is taken as it is; one without them is looked up again by its name.
        return replaceWith(id, picked ? itemEdit.placePicked(target, picked) : itemEdit.placeByName(target, choice.candidate.name), choice.candidate.placeKind ?? null, choice.candidate.proposedTime, how);
      },
      // `[2026-10-20 사용자 결정 — 계획 확인 C안 · 이동 확인 C안]` The way in arrives late: when could the stop start instead? The server works it out for this stop alone and saves nothing
      //   (`autofix {item_id, dry_run}` — after the stop before ends and the way there is made, rounded up to 5 minutes; its end shortened when it must). Only a change of time is an answer here.
      laterStart: async (id) => {
        const result = await autofixIntake(intakeId, plan().revision, language, true, id).catch(staleThenRethrow);
        const change = result.changed.find((entry) => entry.id === id && entry.reason === "time");
        return change?.to.starts_at ? { start: change.to.starts_at, end: change.to.ends_at ?? "" } : null;
      },
      // `[2026-10-20 사용자 결정 — 계획 확인 C안]` 「「…」 그대로」: the place the server took for now (one of several) is the one — sent back as the customer's pick, so the server checks it as chosen.
      confirmPlace: async (id, how) => {
        const item = itemOf(id);
        const picked = item.place && pickedPlace({ ...item.place, address: null, category: item.place.category ?? null, ref: null });
        if (!picked) throw new LiveError("place_missing", t("이 일정의 장소 위치를 몰라 그대로 정할 수 없어요 · 직접 수정에서 골라 주세요", "This stop's place has no position · pick it in Edit"));
        await save([itemEdit.placePicked(targetOf(item), picked)], true, how);
        undoEdits.current = null;
      },
      autoRecommend: async (id) => {
        const item = itemOf(id);
        if (!isLodgingReviewItem(item)) {
          const found = await alternativesOf(id, item);
          const best = found.candidates.find((candidate) => candidate.fits && pickedPlace(candidate.place));
          const picked = best && pickedPlace(best.place);
          if (!picked) throw new LiveError("no_fitting_place", t("시간이 맞는 대체 후보가 없어요 · 수정에서 장소를 직접 골라 주세요", "No alternative fits the time — pick a place in Edit"));
          await replaceWith(id, itemEdit.placePicked(targetOf(item), picked), best.basis === "meal_inferred" ? "dining" : best.place.kind === "dining" || best.place.kind === "activity" ? best.place.kind : null, proposedTimeOf(best));
          return;
        }
        const before = plan();
        const result = await autofixIntake(intakeId, before.revision, language, false, id).catch(staleThenRethrow);
        if (!allUndo.active) throw gone();
        if (!result.changed.length) {
          const noCandidates = result.kept.some((entry) => entry.reason === "no_candidates");
          throw new LiveError("no_fitting_place", noCandidates
            ? t("근처 후보를 찾지 못했어요 · 수정에서 장소를 직접 골라 주세요", "No nearby place found — pick a place in Edit")
            : t("시간을 조정해도 맞는 후보가 없어요 · 수정에서 장소를 직접 골라 주세요", "No alternative fits after adjusting the time — pick a place in Edit"));
        }
        allUndo.remember(before, result.view);
        undoEdits.current = autofixUndo(result.changed);
        take(result.view);
      },
      // Show how 「전체 자동 추천」 would change the plan — saves nothing (the server's dry run), so scrolling or pressing never changes the plan.
      previewRecommendAll: async (): Promise<AutoResult> => {
        const base = plan().revision;
        const early = warmed.current?.intakeId === intakeId && warmed.current.base === base ? warmed.current.ask : null;
        const result = await (early ?? autofixIntake(intakeId, base, language, true)).catch(() => autofixIntake(intakeId, base, language, true)).catch(staleThenRethrow);
        setPreviewed(result.view.preview && result.changed.length ? { view: result.view, base } : null);
        return autoResultOf(result, t);
      },
      // `[2026-10-05]` Is there anything to recommend? Read from the warm dry run above - and shown nowhere (the preview page is not opened by it). null = not asked for yet.
      hasRecommendation: async (): Promise<boolean | null> => {
        // The effect of the screen can run before this hook has taken the plan (`latest` is set after the first paint): not known yet, not an error.
        const base = latest.current?.revision;
        const ask = base !== undefined && warmed.current?.intakeId === intakeId && warmed.current.base === base ? warmed.current.ask : null;
        if (!ask) return null;
        return ask.then((result) => result.changed.length > 0, () => null);
      },
      // Save what the preview showed: the same call without `dry_run` — the server makes the plan it showed.
      applyRecommended: async (): Promise<AutoResult> => {
        const before = plan();
        const result = await autofixIntake(intakeId, before.revision, language).catch(staleThenRethrow);
        if (!allUndo.active) throw gone();
        // ★`[2026-10-04 사용자 지시]` The server checked the plan it made (the dry run the customer was looking at): saving it is not a change the customer has to send again,
        //   so the plan is not marked 「changed since the last check」 — 「여행 등록」 stays open. (A change by hand still is: `save(edits, true)`.)
        if (result.changed.length) {
          allUndo.remember(before, result.view);
          undoEdits.current = autofixUndo(result.changed);          // null when it cannot put ALL of it back
        }
        take(result.view);
        return autoResultOf(result, t);
      },
      discardPreview: () => setPreviewed(null),
      // `[2026-10-07]` One of two readings of a photo's line: the value goes as the customer's. Keeping the current one confirms it (nothing to undo); the other reading can be put back.
      pickReading: async (id, field, value) => {
        const item = itemOf(id);
        const reread = item.rereads?.find((entry) => entry.field === field);
        await save([itemEdit.reading(targetOf(item), field, value)], true);
        undoEdits.current = reread && value !== reread.current ? [itemEdit.reading(targetOf(item), field, reread.current)] : null;
      },
      lock: async (id, locked) => {
        const item = itemOf(id);
        await save([itemEdit.lock(targetOf(item), locked)]);        // a lock goes alone; it does not touch what 「되돌리기」 holds
      },
      unlockAll: async () => {
        const locked = plan().review?.items.filter((item) => item.locked) ?? [];
        if (locked.length) await save(locked.map((item) => itemEdit.lock(targetOf(item), false)));
        return locked.length;
      },
      canUndo: () => undoEdits.current !== null,
      canUndoItem: (id) => allUndo.itemTarget(latest.current, id) !== null,
      undoItem: async (id) => {
        const current = plan();
        const original = allUndo.itemTarget(current, id);
        if (!original) throw new LiveError("cannot_undo", t("이 일정의 복원할 원래 값을 확인하지 못했어요", "The original values of this stop are not available"));
        const next = await restoreIntake(intakeId, current.revision, original.revision, language, { source_id: original.source_id, index: original.index }).catch(staleThenRethrow);
        if (!allUndo.active) return;
        allUndo.advance(next);
        undoEdits.current = null;
        take(next);
      },
      canUndoAll: () => allUndo.canRestore(latest.current),
      undoAll: async () => {
        const current = plan();
        const original = allUndo.target(current);
        if (original === null) throw new LiveError("cannot_undo", t("복원할 원래 판을 확인하지 못했어요. 현재 변경은 그대로 두었어요.", "The original revision is not available. Your changes were kept."));
        const next = await restoreIntake(intakeId, current.revision, original, language).catch(staleThenRethrow);
        if (!allUndo.active) return;
        allUndo.restored(next);
        undoEdits.current = null;
        alternatives.current.clear();
        setDirty(false);                            // restore saved the final check in the same transaction
        take(next);
      },
      undo: async () => {
        const edits = undoEdits.current;
        if (!edits) throw new LiveError("cannot_undo", t("이번 변경은 되돌릴 수 없어요 · 이전 장소를 알 수 없어서요", "This change cannot be undone — the earlier place is not known"));
        await save(edits, true);
        undoEdits.current = null;                     // only once it went through: a refused undo can be tried again
      },
      // ★`[2026-10-04 사용자 지시]` Only the stops that were changed are shown being checked again (`only`); the server checks the whole plan either way.
      recheck: async (only) => {
        const ids = only ?? plan().review?.items.map((entry) => entry.id) ?? [];
        let at = 0;
        setRechecking(ids[0] ?? null);
        const ticker = ids.length > 1 ? setInterval(() => { at = (at + 1) % ids.length; setRechecking(ids[at]); }, RECHECK_STEP_MS) : undefined;
        try {
          const next = await revalidateIntake(intakeId, plan().revision, language).catch(staleThenRethrow);
          if (!allUndo.active) return;
          alternatives.current.clear();                             // `[2026-10-20]` the plan is checked: alternatives are asked for the plan as it now is
          setDirty(false);                                          // before the checked plan is drawn (see `save`)
          take(next);
        } finally {
          clearInterval(ticker);
          setRechecking(null);
        }
      },
    };
  }, [intakeId, language, apply, reread, allUndo, setDirty]);

  // The preview shows only while the plan it was asked on is still the plan (an answer from elsewhere — a re-read after a stale edit — ends it too).
  const preview = previewed && view && previewed.view.intake_id === intakeId && previewed.base === view.revision ? previewed.view : null;
  return { actions, dirty, rechecking, infos, preview };
}

/** What 「전체 자동 추천」 did or would do, as the screen says it: a line per changed stop, how many stayed, which stops the 「바뀜」 tag goes on. */
function autoResultOf(result: Awaited<ReturnType<typeof autofixIntake>>, t: Translate): AutoResult {
  const changes = result.changed.map((change) => {
    const place = change.to.place?.name ?? change.title;
    const time = change.to.starts_at ? ` ${change.to.starts_at}${change.to.ends_at ? `–${change.to.ends_at}` : ""}` : "";
    return `${change.title} → ${place}${time}`;
  });
  return {
    changes, kept: result.kept.filter((entry) => entry.reason === "locked" || entry.reason === "booked" || entry.reason.startsWith("no_")).length,
    changed: result.changed.map((change) => ({ id: change.id, from: change.from.place?.name ?? t("장소 미정", "no place yet") })),
  };
}
