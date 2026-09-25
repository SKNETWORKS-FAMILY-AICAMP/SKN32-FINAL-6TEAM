"use client";

import { JourneyShell } from "@/components/layout/journey-shell";
import { QueryState } from "@/components/ui";
import { useT } from "@/lib/settings";

export default function ErrorPage({ reset }: { reset: () => void }) {
  const t = useT();
  return <JourneyShell view="other" title={["오류", "Error"]}>
    <QueryState loading={false} error={new Error(t("화면을 표시하지 못했어요. 다시 시도해 주세요.", "This screen could not be shown. Please try again."))} retry={reset} />
  </JourneyShell>;
}
