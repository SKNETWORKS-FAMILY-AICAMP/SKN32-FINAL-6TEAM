"use client";

import { useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { tripKey, useTrip } from "@/features/trip/use-trip";
import type { Trip } from "@/features/trip/model";
import { setGuardian, type GuardianVia } from "@/lib/live/extras";
import { useSettings } from "@/lib/settings";
import { GuardianCard } from "./guardian-card";
import { ToastLayer } from "./guardian-header";
import { GuardianToggle } from "./guardian-toggle";
import { UndoToast } from "./undo-toast";

type Change = { enabled: boolean; via: GuardianVia };
type Toast = { kind: "off" | "on" } | { kind: "failed"; retry: Change } | null;

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 3단계 · 목업 v9 §3-3 · §3-4 · 알림 링크]` The Course Keeper icon of a REGISTERED trip. What it shows is the server's (`guardian` of the trip view) and a press
 * is a call to the server (`POST /v1/web/trips/{id}/guardian`, recorded with where it came from: `header` · `notice`):
 *   - on, pressed -> turns off AT ONCE (the screen follows without waiting) and a line says so, with 「되돌리기」; it does not go away by itself;
 *   - off, pressed -> the card (「켜기 / 그대로 두기」) asks once;
 *   - the server did not take it -> the screen goes back to what it was and the line says so with 「다시 시도하기」 (nothing is shown as changed that was not);
 *   - a notification link (`/trips/{id}?guardian=on`) opens that same card at once when it is off - the link alone turns nothing on.
 * Nothing is drawn when the server does not say (`guardian` absent: an older server, or the trip has not loaded).
 */
export function TripGuardianControl({ tripId }: { tripId: string }) {
  const { language } = useSettings();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const trip = useTrip(tripId);
  const guardian = trip.data?.guardian ?? null;
  const [pressed, setPressed] = useState(false);
  const [linkClosed, setLinkClosed] = useState(false);
  const [toast, setToast] = useState<Toast>(null);
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
      setToast({ kind: enabled ? "on" : "off" });
    },
    onError: (_error, variables, context) => {
      if (context?.before) queryClient.setQueryData<Trip>(key, context.before);
      setToast({ kind: "failed", retry: variables });
    },
  });

  if (!guardian) return null;
  const on = guardian.enabled;
  const cardOpen = pressed || (fromLink && !linkClosed && !on);
  const leaveLink = () => { setLinkClosed(true); if (fromLink) router.replace(pathname); };
  const send = (next: Change) => { setToast(null); change.mutate(next); };

  return <>
    <GuardianToggle on={on} onPress={() => { if (on) send({ enabled: false, via: "header" }); else setPressed(true); }} />
    {cardOpen && <GuardianCard kind="notice"
      onPrimary={() => { const via: GuardianVia = pressed ? "header" : "notice"; setPressed(false); leaveLink(); send({ enabled: true, via }); }}
      onSecondary={() => { setPressed(false); leaveLink(); }}
      onClose={() => { setPressed(false); leaveLink(); }} />}
    {toast && <ToastLayer>
      {toast.kind === "failed"
        ? <UndoToast failed onRetry={() => send(toast.retry)} onClose={() => setToast(null)} />
        : <UndoToast kind={toast.kind} onUndo={() => send({ enabled: toast.kind === "off", via: "header" })} onClose={() => setToast(null)} />}
    </ToastLayer>}
  </>;
}
