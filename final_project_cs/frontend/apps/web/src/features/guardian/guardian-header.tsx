"use client";

import { useState } from "react";
import { useAppToast } from "@/components/app-toast";
import { useT } from "@/lib/settings";
import { GuardianCard } from "./guardian-card";
import { GuardianToggle } from "./guardian-toggle";
import { decideGuardian, useCriteria } from "./criteria-store";

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 · 목업 v9 §3-3 · §3-4]` The Course Keeper icon at the top of the screens BEFORE the trip is registered (the plan screen, the reading, the plan check).
 * It is shown once the choice is made (the card, or 「켜진 상태가 기본」 - a customer who turned it on once starts every plan with it on). Pressing it while on turns it off AT ONCE and says so in the app's notice
 * bar (`useAppToast`: gone by itself after a few seconds, with 「되돌리기」); pressing it while off opens the card once more (the version for a notification: 「켜기」 / 「그대로 두기」).
 * ★Only the page's state: the choice is sent with the plan and again when it is confirmed. (On a registered trip the icon is the server's, `POST /v1/web/trips/{id}/guardian`.)
 */
export function GuardianHeaderControl() {
  const t = useT();
  const criteria = useCriteria();
  const [card, setCard] = useState(false);
  const { show, node } = useAppToast();
  if (!criteria.decided || !criteria.guardian) return null;
  const on = criteria.guardian === "on";
  function press() {
    if (on) {
      decideGuardian("off");
      show({ text: t("항로 지킴이를 껐어요. 문제가 생기면 물어볼게요.", "Course Keeper is off. We will ask you when something goes wrong."), action: { label: t("되돌리기", "Undo"), run: () => decideGuardian("on") } });
    } else setCard(true);
  }
  return <>
    <GuardianToggle on={on} onPress={press} />
    {card && <GuardianCard kind="notice"
      onPrimary={() => { decideGuardian("on"); setCard(false); show({ text: t("항로 지킴이를 켰어요.", "Course Keeper is on.") }); }}
      onSecondary={() => setCard(false)} onClose={() => setCard(false)} />}
    {node}
  </>;
}
