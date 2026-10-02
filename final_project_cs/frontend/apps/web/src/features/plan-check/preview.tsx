"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { routes } from "@/lib/routes";
import { useT } from "@/lib/settings";
import { useDocumentTitle } from "@/lib/use-document-title";
import { exampleSnapshots } from "./fixtures";
import { needs, type ItemDraft, type PlanCheckView } from "./model";
import { PlanCheck } from "./plan-check";
import { applyPlace, candidatesFor, exampleState, findPlaceByName, recheckOrder, recommendAll, removeStop, searchPlaces, setLocked, waitingFor, type PreviewState } from "./preview-engine";
import styles from "./preview.module.css";

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Ids of the stops whose content differs between two views — what a change touched. */
const touched = (before: PlanCheckView, after: PlanCheckView) =>
  after.items.filter((item) => JSON.stringify(item) !== JSON.stringify(before.items.find((other) => other.id === item.id))).map((item) => item.id);

/**
 * Plays the example snapshots on their own clock, as a server would send them, then runs every result action of the
 * mockup on this page with the preview's example rules (`preview-engine.ts`) — nothing leaves the page.
 */
function Player({ start }: { start: "play" | "done" }) {
  const router = useRouter();
  const [state, setState] = useState<PreviewState>(() => start === "done" ? exampleState() : { ...exampleState(), view: exampleSnapshots[0].view });
  const [past, setPast] = useState<PreviewState | null>(null);
  const [registered, setRegistered] = useState(false);
  const current = useRef(state);
  useEffect(() => { current.current = state; }, [state]);
  useEffect(() => {
    if (start === "done") return;
    const last = exampleSnapshots.at(-1)!.at;
    const timers = exampleSnapshots.slice(1).map(({ at, view }) => setTimeout(() => setState((now) => ({ ...now, view })), at));
    timers.push(setTimeout(() => setState(exampleState()), last + 10));
    return () => timers.forEach(clearTimeout);
  }, [start]);

  /** A change as a server would answer it: the touched stops wait (their checks refill one by one), then the new plan. */
  async function commit(next: PreviewState, moves: string[] = []) {
    const before = current.current;
    setPast(before);
    const ids = touched(before.view, next.view);
    setState({ ...next, view: waitingFor(next.view, ids, moves) });
    current.current = next;
    await pause(400);
    setState(next);
  }
  const newMoves = (before: PreviewState, after: PreviewState) => after.view.moves.filter((move) => !before.view.moves.some((other) => other.id === move.id)).map((move) => move.id);

  function edited(base: PreviewState, id: string, draft: ItemDraft): PreviewState {
    let next = base;
    const item = base.view.items.find((entry) => entry.id === id)!;
    if (!draft.noPlace && draft.place.trim() !== item.place) {
      const found = findPlaceByName(draft.place);
      if (!found) throw new Error(`미리보기의 예시 장소에서 「${draft.place.trim()}」을 찾지 못했어요 · 예: 창덕궁, 통인시장, 올리브영 명동`);
      next = applyPlace(next, id, found.key, "search");
    }
    return { ...next, view: { ...next.view, dirty: true, items: next.view.items.map((entry) => entry.id !== id ? entry : {
      ...entry, title: draft.title.trim(), date: draft.date, startsAt: draft.start, endsAt: draft.end,
      ...(draft.noPlace ? { place: "", noPlace: true, coordinates: null, info: null, verdict: "adjusted" as const, checks: [{ kind: "place" as const, result: "unknown" as const, text: "장소 없이 두었어요" }] } : {}),
    }) } };
  }

  const view = state.view;
  return <PlanCheck view={view} onBack={() => router.push(routes.newTrip)}
    actions={{
      edit: async (id, draft) => { await pause(200); await commit(edited(current.current, id, draft)); },
      remove: async (id) => { await pause(200); const next = removeStop(current.current, id); await commit(next, newMoves(current.current, next)); },
      candidates: async (id) => { await pause(250); return candidatesFor(current.current, id); },
      search: async (id, query) => { await pause(150); return searchPlaces(current.current, id, query); },
      replace: async (id, choice) => {
        const key = "candidate" in choice ? choice.candidate.id : findPlaceByName(choice.name)?.key;
        if (!key) throw new Error("미리보기의 예시 장소에서 찾지 못했어요");
        await pause(200);
        await commit(applyPlace(current.current, id, key, "candidate" in choice && choice.candidate.source === "candidate" ? "pick" : "search"));
      },
      autoRecommend: async (id) => {
        const first = candidatesFor(current.current, id)[0];
        if (!first) throw new Error("바꿀 대체 후보가 없어요");
        await pause(200);
        await commit(applyPlace(current.current, id, first.id, "auto"));
      },
      autoRecommendAll: async () => {
        const outcome = recommendAll(current.current);
        if (outcome.changes.length) await commit(outcome.state);
        return { changes: outcome.changes, kept: outcome.kept };
      },
      lock: async (id, locked) => { await pause(150); setState(setLocked(current.current, id, locked)); },
      undo: async () => {
        if (!past) throw new Error("되돌릴 것이 없어요");
        await pause(150);
        setState(past); current.current = past; setPast(null);
      },
      recheck: async () => {
        for (const id of recheckOrder(current.current.view)) {
          setState((now) => ({ ...now, view: { ...now.view, rechecking: id } }));
          await pause(420);
        }
        setState((now) => ({ ...now, view: { ...now.view, rechecking: null, dirty: false } }));
        setPast(null);
      },
    }}
    registration={{
      ready: needs(view).total === 0 && !view.dirty, busy: false, onRegister: () => setRegistered(true),
      error: null, problems: [], registeredHref: registered ? routes.trips : null,
    }} />;
}

/**
 * ★Preview of the plan-check screen with the mockup's example data — not connected to the server, and labelled so.
 *   The real route (`/intakes/[id]`) shows the server's reading and result (`from-intake.ts`); this page shows the whole
 *   mockup — alternatives, search, photos, lock, undo, 「전체 자동 추천 → 재검증 → 여행 등록」 — with example rules.
 */
export function PlanCheckPreview() {
  const t = useT();
  useDocumentTitle(t("triPilot · 계획 확인 미리보기", "triPilot · Plan check preview"));
  const [run, setRun] = useState<{ id: number; start: "play" | "done" }>({ id: 0, start: "play" });
  return <>
    <Player key={run.id} start={run.start} />
    <aside className={styles.preview} aria-label={t("미리보기 조작", "Preview controls")}>
      <span>{t("미리보기 · 예시 데이터 · 서버 미연결", "Preview · example data · not connected")}</span>
      <button type="button" onClick={() => setRun((current) => ({ id: current.id + 1, start: "play" }))}>{t("처음부터 재생", "Replay")}</button>
      <button type="button" onClick={() => setRun((current) => ({ id: current.id + 1, start: "done" }))}>{t("결과 바로 보기", "Show result")}</button>
    </aside>
  </>;
}
