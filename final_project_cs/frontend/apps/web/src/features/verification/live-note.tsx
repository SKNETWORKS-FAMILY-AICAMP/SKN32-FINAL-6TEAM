"use client";

import { ArrowRight, ShieldCheck } from "lucide-react";
import { ButtonLink, Panel } from "@/components/ui";
import { routes } from "@/lib/routes";
import { useT } from "@/lib/settings";
import styles from "./verification.module.css";

/**
 * Live mode has no separate verification step to show: the server judges the plan when it is registered
 * (`_create_trip`), and what it found and sent appears on the trip screen (warnings, notices, history).
 * The demo's progress and result screens would show made-up zeros here, so they are replaced by this note.
 */
export function LiveVerificationNote({ tripId }: { tripId: string }) {
  const t = useT();
  return <Panel className={styles.gate}>
    <ShieldCheck size={28} strokeWidth={1.6} aria-hidden="true" />
    <h1>{t("실제 연결에서는 검증 단계가 따로 없어요", "There is no separate check step in live mode")}</h1>
    <p>{t("일정은 등록할 때 서버가 판정해요. 살펴볼 점과 받은 알림, 변경 이력은 여행 화면에서 볼 수 있어요.", "The server judges your plan when it is registered. What it found, the notices it sent and the change history are on your trip screen.")}</p>
    <ButtonLink href={routes.trip(tripId)}>{t("여행 화면으로", "Go to your trip")}<ArrowRight size={18} strokeWidth={1.6} aria-hidden="true" /></ButtonLink>
  </Panel>;
}
