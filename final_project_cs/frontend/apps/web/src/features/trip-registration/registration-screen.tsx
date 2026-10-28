"use client";

import { useCallback, useState } from "react";
import { JourneyShell } from "@/components/layout/journey-shell";
import { IntakeStarting } from "@/features/intake-review/intake-starting";
import { TripRegistration } from "./trip-registration";

/** 접수 경로를 준비하는 동안에도 누른 화면에서 바로 진행 화면을 그린다. */
export function RegistrationScreen() {
  const [sending, setSending] = useState(false);
  const returnToForm = useCallback(() => setSending(false), []);
  return sending ? <IntakeStarting onReturn={returnToForm} /> : <JourneyShell view="registration" title={["여행 계획 등록", "Add your plan"]}>
    <TripRegistration onSending={() => setSending(true)} />
  </JourneyShell>;
}
