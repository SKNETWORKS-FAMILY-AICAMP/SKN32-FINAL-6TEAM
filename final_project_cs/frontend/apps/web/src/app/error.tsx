"use client";

import { QueryState } from "@/components/ui";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return <QueryState loading={false} error={new Error("화면을 표시하지 못했어요. 다시 시도해 주세요.")} retry={reset} />;
}
