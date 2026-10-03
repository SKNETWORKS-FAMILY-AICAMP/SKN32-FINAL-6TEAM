"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { sendingOf } from "@/features/plan-check/from-intake";
import { PlanCheck } from "@/features/plan-check/plan-check";
import { STAGE_MIN_MS } from "@/features/plan-check/use-reveal";
import { PlanningProgress, type PlanningPhase } from "@/features/plan-check/planning-progress";
import { tripsKey } from "@/lib/gateway";
import { getIntake } from "@/lib/live/intake";
import { planFromIntake } from "@/lib/live/intake-plan";
import { endIntakeStart, intakeStart, rememberIntakeFailure } from "@/lib/live/intake-start";
import type { OpProgress } from "@/lib/live/stream";
import { routes } from "@/lib/routes";
import { useT } from "@/lib/settings";
import styles from "./intake-review.module.css";

/** The server has not answered the plan yet: say it is slow after this long, and that it is very slow after this long. */
export const SLOW_AFTER_MS = 4_000;
export const VERY_SLOW_AFTER_MS = 15_000;

/**
 * `[2026-10-03 사용자 지시]` The plan check from the moment 「계획 확인하기」 is pressed. The entry page has already started
 * sending (`beginIntake`) and navigated here at once; this screen is the progress screen with the customer's own lines
 * (`sendingOf`) while the server takes the plan. When the server gives the intake an id it reads the intake once (so the next
 * page opens on what the server has, not on a loading screen) and moves to the intake's page, where the server's progress
 * stream (`GET …/events`) takes over: the stages move the bar and the lines, places and checks come one at a time.
 *
 * ★`[2026-10-03 사용자 지시]` 「계획 짜 주기」 (the entry page's third panel) takes the other way: there is no plan to read, so the screen
 * says 「일정을 짜는 중이에요」 with the stage the server reports (`PlanningProgress`), asks the server to plan once it has read the short text
 * (`planFromIntake`) and, when the trip is registered, goes to the trip.
 *
 * A refusal sends the customer back to the entry page with the server's sentence and what they had chosen to send.
 */
export function IntakeStarting() {
  const t = useT();
  const router = useRouter();
  const queryClient = useQueryClient();
  // Read on the first render only. After a reload there is nothing to follow (the files are gone): back to the entry page.
  const [start] = useState(intakeStart);
  const view = useMemo(() => sendingOf(start?.text ?? ""), [start]);
  // Set when the customer leaves with the back arrow: the abort that follows is not a failure to report.
  const left = useRef(false);
  // `[2026-10-03 사용자]` How long the server has been silent: after a few seconds the screen says so (and that going back is possible).
  const [slow, setSlow] = useState<0 | 1 | 2>(0);
  useEffect(() => {
    if (!start) return;
    const first = setTimeout(() => setSlow(1), SLOW_AFTER_MS);
    const second = setTimeout(() => setSlow(2), VERY_SLOW_AFTER_MS);
    return () => { clearTimeout(first); clearTimeout(second); };
  }, [start]);
  // 「계획 짜 주기」 only: where the sequence is, the words of the server for the reading, and what it says while it plans.
  const [phase, setPhase] = useState<PlanningPhase>("sending");
  const [readLabel, setReadLabel] = useState<string | null>(null);
  const [planning, setPlanning] = useState<OpProgress | null>(null);

  useEffect(() => {
    if (!start) { router.replace(routes.newTrip); return; }
    let live = true;
    const fail = (error: unknown) => {
      if (!live || left.current) return;
      rememberIntakeFailure(start, error instanceof Error ? error.message : String(error));
      endIntakeStart(start);
      router.replace(routes.newTrip);
    };
    const shownAt = Date.now();
    start.result.then(async ({ intake_id }) => {
      if (!live || left.current) return;
      if (start.plan) {
        try {
          const tripId = await planFromIntake(intake_id, start.plan, start.language, {
            phase: (next, label) => { setPhase(next); if (label !== undefined) setReadLabel(label); },
            progress: setPlanning,
            cancelled: () => !live || left.current,
          });
          if (tripId === null || !live || left.current) return;
          endIntakeStart(start);
          // The new trip is not in the cached list: drop it so the home card and "My trips" read it again.
          queryClient.removeQueries({ queryKey: tripsKey });
          router.replace(routes.trip(tripId));
        } catch (error) { fail(error); }
        return;
      }
      try { await queryClient.fetchQuery({ queryKey: ["intake", intake_id, start.language], queryFn: () => getIntake(intake_id, start.language) }); }
      catch { /* the intake's own page reads it again and says what went wrong */ }
      // ★`[2026-10-03 사용자 지적]` 「받았어요」 is the first stage of the bar at the top: it stays as long as every stage does (a fast server used to
      //   answer in a few hundred ms and the bar moved on before it could be seen).
      const seenFor = Date.now() - shownAt;
      if (seenFor < STAGE_MIN_MS) await new Promise((resolve) => setTimeout(resolve, STAGE_MIN_MS - seenFor));
      if (!live || left.current) return;
      endIntakeStart(start);
      router.replace(routes.intake(intake_id));
    }, fail);
    return () => { live = false; };
  }, [start, router, queryClient]);

  // Going back gives the entry page what the customer had chosen to send (the files, the planning conditions) — with no sentence of a refusal.
  const goBack = () => { left.current = true; if (start) { start.cancel(); rememberIntakeFailure(start, ""); endIntakeStart(start); } router.push(routes.newTrip); };
  // The slow notes are about the first answer only; once the server has given the intake an id, its own stage words take over.
  const waitingOnServer = phase === "sending";
  const note = waitingOnServer && slow === 2 ? t("서버가 많이 늦어요 · 계속 기다리거나, 뒤로 가서 다시 보낼 수 있어요", "The server is very slow · keep waiting, or go back and send again")
    : waitingOnServer && slow === 1 ? t("서버가 답하는 데 시간이 걸리고 있어요 · 조금만 기다려 주세요…", "The server is taking a while to answer · one moment…")
      : start?.plan ? t("계획 조건을 서버로 보내는 중이에요…", "Sending your conditions to the server…")
        : start?.files.length ? t("파일을 서버로 올리는 중이에요…", "Uploading your files to the server…")
          : t("계획을 서버로 보내는 중이에요…", "Sending your plan to the server…");

  if (start?.plan) {
    const waiting: [string, string] = phase === "reading"
      ? [readLabel || "원하는 여행을 읽는 중이에요…", readLabel || "Reading the trip you described…"]
      : phase === "planning" ? ["일정을 짜 달라고 보냈어요…", "Sent your planning request…"]
        : [note, note];
    // Before the server has said anything the line under the title is the note (it turns into the slow notes by itself).
    return <PlanningProgress phase={phase} progress={planning} waiting={waiting} onBack={phase === "planning" ? undefined : goBack} />;
  }
  return <PlanCheck view={view} sending notice={<p className={styles.sendingNote}>{note}</p>} onBack={goBack} />;
}
