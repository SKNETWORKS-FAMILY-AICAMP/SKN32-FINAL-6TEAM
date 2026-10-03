"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { autofixUndo, restorePlace } from "@/features/intake-review/autofix-undo";
import { editsFor, rows } from "@/features/intake-review/model";
import { translator, type Language } from "@/lib/i18n";
import { LiveError } from "@/lib/live/client";
import { editIntake, type IntakeEdit } from "@/lib/live/intake";
import { itemEdit } from "@/lib/live/intake-edits";
import {
  autofixIntake, getCandidates, getPlacePhotos, pickedPlace, revalidateIntake, searchPlaces,
  type CandidatePlace, type ReviewItem, type ReviewedIntakeView,
} from "@/lib/live/intake-review";
import { planCandidate, safePhotoUrl } from "./from-review";
import type { PlaceInfo } from "./model";
import type { AutoResult, PlaceChoice, PlanCheckActions } from "./plan-check";

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
}): { actions: PlanCheckActions; dirty: boolean; rechecking: string | null; infos: Readonly<Record<string, PlaceInfo>> } {
  const [dirty, setDirty] = useState(false);
  const [rechecking, setRechecking] = useState<string | null>(null);
  const [infos, setInfos] = useState<Record<string, PlaceInfo>>({});
  const latest = useRef<ReviewedIntakeView | undefined>(view);
  const undoEdits = useRef<IntakeEdit[] | null>(null);
  const pickable = useRef(new Map<string, CandidatePlace>());
  useEffect(() => { if (view) latest.current = view; });

  const actions = useMemo<PlanCheckActions>(() => {
    const t = translator(language);
    const gone = () => new LiveError("item_gone", t("그 일정은 이미 없어요", "That stop is already gone"));
    const plan = (): ReviewedIntakeView => {
      if (!latest.current) throw gone();
      return latest.current;
    };
    const itemOf = (id: string): ReviewItem => {
      const item = plan().review?.items.find((entry) => entry.id === id);
      if (!item) throw gone();
      return item;
    };
    const targetOf = (item: ReviewItem) => ({ source_id: item.source_id, index: item.index });
    const staleThenRethrow = (error: unknown): never => {
      if (error instanceof LiveError && error.code === "stale_revision") reread();
      throw error;
    };
    const take = (next: ReviewedIntakeView) => { latest.current = next; apply(next); };
    /**
     * Send edits. ★`changed` says "the plan is no longer the one that was last checked" and is set BEFORE the new plan is
     * drawn: the other way round, the footer is drawn once with neither "nothing to fix" nor "check again" pending and offers
     * 「여행 등록」 for an instant (a click in that instant registered an unchecked plan — found by the browser test).
     */
    async function save(edits: IntakeEdit[], changed = false) {
      const next = await editIntake(intakeId, plan().revision, edits, language).catch(staleThenRethrow);
      if (changed) setDirty(true);
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
    const replaceWith = async (id: string, edit: IntakeEdit) => {
      const item = itemOf(id);
      const back = restorePlace(targetOf(item), item.place);
      await save([edit], true);
      undoEdits.current = back ? [back] : null;
    };

    return {
      edit: async (id, draft) => {
        const item = itemOf(id);
        const row = rows(plan()).find((entry) => entry.source.source_id === item.source_id && entry.item.index === item.index);
        if (!row) throw gone();
        const edits = editsFor(row, draft);
        if (!edits.length) return;
        await save(edits, true);
        undoEdits.current = null;
      },
      remove: async (id) => {
        const item = itemOf(id);
        await save([itemEdit.remove(targetOf(item), true)], true);
        undoEdits.current = [itemEdit.remove(targetOf(item), false)];
      },
      editTrip: (field, value) => save([{ field: `trip.${field}`, value }]),

      candidates: async (id) => {
        const item = itemOf(id);
        const found = await getCandidates(intakeId, item, plan().revision, language).catch(staleThenRethrow);
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
      search: async (id, words) => {
        const item = itemOf(id);
        const found = await searchPlaces(intakeId, item, plan().revision, words, language).catch(staleThenRethrow);
        return found.results.map((result) => {
          const card = planCandidate(result, id, "search", { category: result.place.category, address: result.place.address, photos: [], kind: result.place.kind, origin: result.place.source });
          pickable.current.set(card.id, result.place);
          return card;
        });
      },
      replace: async (id, choice: PlaceChoice) => {
        const item = itemOf(id);
        const target = targetOf(item);
        if (!("candidate" in choice)) return replaceWith(id, itemEdit.placeByName(target, choice.name));
        const place = pickable.current.get(choice.candidate.id);
        const picked = place && pickedPlace(place);
        // A place the server gave coordinates for is taken as it is; one without them is looked up again by its name.
        return replaceWith(id, picked ? itemEdit.placePicked(target, picked) : itemEdit.placeByName(target, choice.candidate.name));
      },
      autoRecommend: async (id) => {
        const item = itemOf(id);
        const found = await getCandidates(intakeId, item, plan().revision, language).catch(staleThenRethrow);
        const best = found.candidates.find((candidate) => candidate.fits && pickedPlace(candidate.place));
        const picked = best && pickedPlace(best.place);
        if (!picked) throw new LiveError("no_fitting_place", t("시간이 맞는 대체 후보가 없어요 · 수정에서 장소를 직접 골라 주세요", "No alternative fits the time — pick a place in Edit"));
        await replaceWith(id, itemEdit.placePicked(targetOf(item), picked));
      },
      autoRecommendAll: async (): Promise<AutoResult> => {
        const result = await autofixIntake(intakeId, plan().revision, language).catch(staleThenRethrow);
        if (result.changed.length) {
          undoEdits.current = autofixUndo(result.changed);          // null when it cannot put ALL of it back
          setDirty(true);                                           // before the new plan is drawn (see `save`)
        }
        take(result.view);
        const changes = result.changed.map((change) => {
          const place = change.to.place?.name ?? change.title;
          const time = change.to.starts_at ? ` ${change.to.starts_at}${change.to.ends_at ? `–${change.to.ends_at}` : ""}` : "";
          return `${change.title} → ${place}${time}`;
        });
        return {
          changes, kept: result.kept.filter((entry) => entry.reason === "locked" || entry.reason.startsWith("no_")).length,
          changed: result.changed.map((change) => ({ id: change.id, from: change.from.place?.name ?? t("장소 미정", "no place yet") })),
        };
      },
      lock: async (id, locked) => {
        const item = itemOf(id);
        await save([itemEdit.lock(targetOf(item), locked)]);        // a lock goes alone; it does not touch what 「되돌리기」 holds
      },
      undo: async () => {
        const edits = undoEdits.current;
        if (!edits) throw new LiveError("cannot_undo", t("이번 변경은 되돌릴 수 없어요 · 이전 장소를 알 수 없어서요", "This change cannot be undone — the earlier place is not known"));
        await save(edits, true);
        undoEdits.current = null;                     // only once it went through: a refused undo can be tried again
      },
      recheck: async () => {
        const ids = plan().review?.items.map((entry) => entry.id) ?? [];
        let at = 0;
        setRechecking(ids[0] ?? null);
        const ticker = ids.length > 1 ? setInterval(() => { at = (at + 1) % ids.length; setRechecking(ids[at]); }, RECHECK_STEP_MS) : undefined;
        try {
          const next = await revalidateIntake(intakeId, plan().revision, language).catch(staleThenRethrow);
          setDirty(false);                                          // before the checked plan is drawn (see `save`)
          take(next);
        } finally {
          clearInterval(ticker);
          setRechecking(null);
        }
      },
    };
  }, [intakeId, language, apply, reread]);

  return { actions, dirty, rechecking, infos };
}
