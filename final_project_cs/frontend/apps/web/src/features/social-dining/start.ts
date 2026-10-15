import type { Language } from "@/lib/i18n";
import { submitIntake, type IntakePlanInput } from "@/lib/live/intake";
import { createDiningDraft } from "@/lib/live/social-dining";
import type { OpProgress } from "@/lib/live/stream";
import { routes } from "@/lib/routes";
export function diningEntry(url: string): boolean { try { return new URL(url).searchParams.get("dining") === "1"; } catch { return false; } }
export async function openDiningIntake(language: Language, humanToken?: string | null, submit: typeof submitIntake = submitIntake): Promise<string> {
  const { intake_id } = await submit("", [], language, humanToken);
  return `${routes.intake(intake_id)}?dining=1`;
}
export function generateWithDiningLinks(id: string, revision: number, input: Omit<IntakePlanInput, "keep_read_items">, language: Language,
  progress?: (next: OpProgress) => void, plan: typeof createDiningDraft = createDiningDraft) {
  return plan(id, revision, input, language, progress);
}
