"use client";

import { useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { GuardianCard } from "./guardian-card";
import { GuardianToggle } from "./guardian-toggle";
import { decideGuardian, useCriteria } from "./criteria-store";
import { UndoToast } from "./undo-toast";
import styles from "./guardian-header.module.css";

/** The line under the header (`UndoToast`) stands in this layer, over the page. */
export function ToastLayer({ children }: { children: ReactNode }) {
  return typeof document === "undefined" ? null : createPortal(<div className={styles.toastLayer}>{children}</div>, document.body);
}

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 · 목업 v9 §3-3 · §3-4]` The Course Keeper icon at the top of the screens BEFORE the trip is registered (the plan screen after the card, the reading, the plan check).
 * It is shown only once the customer has been through the card. Pressing it while on turns it off AT ONCE and says so in a line that stays until it is closed, undone, or the screen is left; pressing
 * it while off opens the card once more (the version for a notification: 「켜기」 / 「그대로 두기」). ★Only the page's state: the choice is sent with the plan and again when it is confirmed.
 * (On a registered trip the icon is the server's, `POST /v1/web/trips/{id}/guardian`.)
 */
export function GuardianHeaderControl() {
  const criteria = useCriteria();
  const [card, setCard] = useState(false);
  const [off, setOff] = useState(false);
  if (!criteria.decided || !criteria.guardian) return null;
  const on = criteria.guardian === "on";
  function press() {
    if (on) { decideGuardian("off"); setOff(true); }
    else setCard(true);
  }
  return <>
    <GuardianToggle on={on} onPress={press} />
    {card && <GuardianCard kind="notice" onPrimary={() => { decideGuardian("on"); setCard(false); setOff(false); }} onSecondary={() => setCard(false)} onClose={() => setCard(false)} />}
    {off && !on && <ToastLayer><UndoToast onUndo={() => { decideGuardian("on"); setOff(false); }} onClose={() => setOff(false)} /></ToastLayer>}
  </>;
}
