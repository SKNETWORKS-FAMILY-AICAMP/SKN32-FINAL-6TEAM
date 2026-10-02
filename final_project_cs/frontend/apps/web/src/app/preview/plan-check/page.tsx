import { notFound } from "next/navigation";
import { PlanCheckPreview } from "@/features/plan-check/preview";
import { DATA_MODE } from "@/lib/data-mode";

/**
 * The plan-check screen with example data — not connected to the server. Opens on the dev server and in demo builds
 * only; a live build answers 404, so customers never reach it.
 */
export default function PlanCheckPreviewPage() {
  if (process.env.NODE_ENV === "production" && DATA_MODE !== "demo") notFound();
  return <PlanCheckPreview />;
}
