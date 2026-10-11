"use client";

import { useContext, useState, type ReactNode } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAppToast } from "@/components/app-toast";
import { CloseMenu } from "@/components/layout/settings-menu";
import { tripKey, useTrip } from "@/features/trip/use-trip";
import type { Trip } from "@/features/trip/model";
import { setGuardian, type GuardianVia } from "@/lib/live/extras";
import { useSettings, useT } from "@/lib/settings";
import { rememberGuardian } from "./criteria-store";
import { GuardianCard } from "./guardian-card";
import { GuardianToggle } from "./guardian-toggle";

type Change = { enabled: boolean; via: GuardianVia };

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 3단계 · 목업 v9 §3-3 · §3-4 · 알림 링크]` The Course Keeper icon of a REGISTERED trip. What it shows is the server's (`guardian` of the trip view) and a press
 * is a call to the server (`POST /v1/web/trips/{id}/guardian`, recorded with where it came from: `header` · `notice`):
 *   - on, pressed -> turns off AT ONCE (the screen follows without waiting) and the app's notice bar says so, with 「되돌리기」 (it goes by itself after a few seconds);
 *   - off, pressed -> the card (「켜기 / 그대로 두기」) asks once;
 *   - the server did not take it -> the screen goes back to what it was and the notice says so with 「다시 시도하기」 (nothing is shown as changed that was not);
 *   - a notification link (`/trips/{id}?guardian=on`) opens that same card at once when it is off - the link alone turns nothing on.
 * `[2026-10-06 사용자 지시]` Turned on once, it is how every plan after starts (`rememberGuardian`); turned off, that is forgotten.
 * Nothing is drawn when the server does not say (`guardian` absent: an older server, or the trip has not loaded).
 *
 * ★`[2026-10-07 사용자 결정 — 목업 C안]` The icon lives in the menu drawer's head, left of its close button (`tool`, for `DeviceFrame` `menuTools`), no longer in the header. The card and the
 *   notice are drawn outside the drawer (`overlay`): pressing the icon while it is off closes the drawer first and then asks.
 */
export function useTripGuardian(tripId: string): { tool: ReactNode; overlay: ReactNode } {
  const t = useT();
  const { language } = useSettings();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const trip = useTrip(tripId);
  const { show, node } = useAppToast();
  const guardian = trip.data?.guardian ?? null;
  const [pressed, setPressed] = useState(false);
  const [linkClosed, setLinkClosed] = useState(false);
  const fromLink = params.get("guardian") === "on";
  const key = tripKey(tripId, language);

  const change = useMutation({
    mutationFn: ({ enabled, via }: Change) => setGuardian(tripId, enabled, via, language),
    // The screen follows the press at once; the server's word replaces it, and a refusal puts back what was there.
    onMutate: ({ enabled, via }) => {
      const before = queryClient.getQueryData<Trip>(key);
      queryClient.setQueryData<Trip>(key, (current) => current && { ...current, guardian: { enabled, since: current.guardian?.since ?? null, via } });
      return { before };
    },
    onSuccess: (answer, { enabled }) => {
      queryClient.setQueryData<Trip>(key, (current) => current && { ...current, guardian: answer });
      rememberGuardian(enabled);
      show(enabled
        ? { text: t("항로 지킴이를 켰어요.", "Course Keeper is on."), action: { label: t("되돌리기", "Undo"), run: () => send({ enabled: false, via: "header" }) } }
        : { text: t("항로 지킴이를 껐어요. 문제가 생기면 물어볼게요.", "Course Keeper is off. We will ask you when something goes wrong."), action: { label: t("되돌리기", "Undo"), run: () => send({ enabled: true, via: "header" }) } });
    },
    onError: (_error, variables, context) => {
      if (context?.before) queryClient.setQueryData<Trip>(key, context.before);
      show({ text: t("항로 지킴이를 바꾸지 못했어요. 연결을 확인하고 다시 시도해 주세요.", "Course Keeper could not be changed. Check the connection and try again."), action: { label: t("다시 시도하기", "Try again"), run: () => send(variables) } });
    },
  });

  function send(next: Change) { change.mutate(next); }

  const on = guardian?.enabled ?? false;
  const cardOpen = pressed || (fromLink && !linkClosed && !on);
  const leaveLink = () => { setLinkClosed(true); if (fromLink) router.replace(pathname); };

  return {
    tool: guardian ? <DrawerToggle on={on} onOff={() => send({ enabled: false, via: "header" })} onAsk={() => setPressed(true)} /> : null,
    overlay: <>
    {guardian && cardOpen && <GuardianCard kind="notice" iconIn="menu"
      onPrimary={() => { const via: GuardianVia = pressed ? "header" : "notice"; setPressed(false); leaveLink(); send({ enabled: true, via }); }}
      onSecondary={() => { setPressed(false); leaveLink(); }}
      onClose={() => { setPressed(false); leaveLink(); }} />}
    {node}
  </>,
  };
}

/** The icon in the menu drawer's head: on, a press turns it off; off, the drawer closes before the card asks. */
function DrawerToggle({ on, onOff, onAsk }: { on: boolean; onOff: () => void; onAsk: () => void }) {
  const close = useContext(CloseMenu);
  return <GuardianToggle on={on} onPress={() => { if (on) onOff(); else { close(); onAsk(); } }} />;
}
