"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { routes } from "@/lib/routes";
import { useT } from "@/lib/settings";
import { useDocumentTitle } from "@/lib/use-document-title";
import { exampleDone, exampleSnapshots } from "./fixtures";
import type { ItemDraft, PlanCheckView } from "./model";
import { PlanCheck } from "./plan-check";
import styles from "./preview.module.css";

const pause = () => new Promise((resolve) => setTimeout(resolve, 300));

/** The example stop after an edit: what was typed, and — no server here — the place not looked up. */
function edited(view: PlanCheckView, id: string, draft: ItemDraft): PlanCheckView {
  return { ...view, items: view.items.map((item) => {
    if (item.id !== id) return item;
    const placeChanged = draft.noPlace !== item.noPlace || draft.place.trim() !== item.place;
    return { ...item, title: draft.title.trim(), date: draft.date, startsAt: draft.start, endsAt: draft.end, place: draft.place.trim(), noPlace: draft.noPlace,
      verdict: "adjusted", coordinates: placeChanged ? null : item.coordinates,
      checks: placeChanged ? [{ kind: "place", result: "unknown", text: draft.noPlace ? "장소 없이 두었어요" : "미리보기에서는 장소를 찾지 않아요" }] : item.checks };
  }) };
}

/** Plays the example snapshots on their own clock, as a server would send them; edits stay on this page. */
function Player({ start }: { start: "play" | "done" }) {
  const router = useRouter();
  const [view, setView] = useState<PlanCheckView>(start === "done" ? exampleDone : exampleSnapshots[0].view);
  const [registered, setRegistered] = useState(false);
  useEffect(() => {
    if (start === "done") return;
    const timers = exampleSnapshots.slice(1).map(({ at, view: next }) => setTimeout(() => setView(next), at));
    return () => timers.forEach(clearTimeout);
  }, [start]);
  return <PlanCheck view={view} onBack={() => router.push(routes.newTrip)}
    actions={{
      edit: async (id, draft) => { await pause(); setView((current) => edited(current, id, draft)); },
      remove: async (id) => {
        await pause();
        setView((current) => ({ ...current, items: current.items.filter((item) => item.id !== id), moves: current.moves.filter((move) => move.fromId !== id && move.toId !== id) }));
      },
    }}
    registration={{
      ready: !view.items.some((item) => item.verdict === "review"), busy: false, onRegister: () => setRegistered(true),
      error: null, problems: [], registeredHref: registered ? routes.trips : null,
    }} />;
}

/**
 * ★Preview of the plan-check screen with the mockup's example data — not connected to the server, and labelled so.
 *   The real route (`/intakes/[id]`) shows the server's reading and result (`from-intake.ts`); this page shows the whole
 *   mockup, including what the server cannot do yet, with edits kept on this page only.
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
