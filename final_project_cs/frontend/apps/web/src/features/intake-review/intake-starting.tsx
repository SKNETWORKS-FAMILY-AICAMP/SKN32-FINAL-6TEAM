"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { sendingOf } from "@/features/plan-check/from-intake";
import { PlanCheck } from "@/features/plan-check/plan-check";
import { getIntake } from "@/lib/live/intake";
import { endIntakeStart, intakeStart, rememberIntakeFailure } from "@/lib/live/intake-start";
import { routes } from "@/lib/routes";
import { useT } from "@/lib/settings";
import styles from "./intake-review.module.css";

/**
 * `[2026-10-03 사용자 지시]` The plan check from the moment 「계획 확인하기」 is pressed. The entry page has already started
 * sending (`beginIntake`) and navigated here at once; this screen is the progress screen with the customer's own lines
 * (`sendingOf`) while the server takes the plan. When the server gives the intake an id it reads the intake once (so the next
 * page opens on what the server has, not on a loading screen) and moves to the intake's page, where the server's progress
 * stream (`GET …/events`) takes over: the stages move the bar and the lines, places and checks come one at a time.
 *
 * A refusal sends the customer back to the entry page with the server's sentence and the files they attached.
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

  useEffect(() => {
    if (!start) { router.replace(routes.newTrip); return; }
    let live = true;
    start.result.then(async ({ intake_id }) => {
      if (!live || left.current) return;
      try { await queryClient.fetchQuery({ queryKey: ["intake", intake_id, start.language], queryFn: () => getIntake(intake_id, start.language) }); }
      catch { /* the intake's own page reads it again and says what went wrong */ }
      if (!live || left.current) return;
      endIntakeStart(start);
      router.replace(routes.intake(intake_id));
    }, (error: unknown) => {
      if (!live || left.current) return;
      rememberIntakeFailure(start, error instanceof Error ? error.message : String(error));
      endIntakeStart(start);
      router.replace(routes.newTrip);
    });
    return () => { live = false; };
  }, [start, router, queryClient]);

  const note = start?.files.length
    ? t("파일을 서버로 올리는 중이에요…", "Uploading your files to the server…")
    : t("계획을 서버로 보내는 중이에요…", "Sending your plan to the server…");
  return <PlanCheck view={view} sending notice={<p className={styles.sendingNote}>{note}</p>}
    onBack={() => { left.current = true; if (start) { start.cancel(); endIntakeStart(start); } router.push(routes.newTrip); }} />;
}
