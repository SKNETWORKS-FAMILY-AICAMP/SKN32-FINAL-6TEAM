import { guideSteps, type GuideStep } from "@/features/intro/guide-steps";
import { FAQ, SCREENS, type FaqCategory, type HelpPoint, type Pair, type ScreenId, type Switch } from "./content";

/** The operator's switches as the web reads them (`lib/live/features.ts`); what cannot be read counts as on, like the screens themselves. */
export type Features = Record<Switch, boolean>;
export type HelpTab = "start" | "screens" | "faq";
export type HelpTarget = { tab: "start"; step: number } | { tab: "screens"; screen: ScreenId; point?: number } | { tab: "faq"; faq: string };

/** `[2026-10-22 사용자 결정 — ST4F-717 D4]` What the operator has switched off is not explained either. */
export const shown = <T extends { needs?: Switch }>(items: readonly T[] | undefined, on: Features): T[] => (items ?? []).filter((item) => !item.needs || on[item.needs]);

export const stepDetail = (step: GuideStep, on: Features): Pair => !on.guardian && step.withoutGuardian ? step.withoutGuardian : step.detail;

export const ruleOf = (point: HelpPoint, on: Features): Pair | undefined => point.rule && (!point.ruleNeeds || on[point.ruleNeeds]) ? point.rule : undefined;

/** The text without the marks around the app's words, for searching. */
export const plain = (text: string) => text.replace(/[「」“”‘’]/g, "");

export interface HelpHit { kind: "step" | "point" | "faq"; group: Pair | null; title: string; body: string; target: HelpTarget }

/** Everything on the three tabs that holds the words, in the order the tabs show them. */
export function searchHelp(query: string, pick: (pair: Pair) => string, on: Features): HelpHit[] {
  const words = plain(query).trim().toLowerCase();
  if (!words) return [];
  const all: HelpHit[] = [
    ...guideSteps.map((step, index): HelpHit => ({ kind: "step", group: null, title: pick(step.title), body: pick(stepDetail(step, on)), target: { tab: "start", step: index + 1 } })),
    ...SCREENS.flatMap((screen) => [
      ...shown(screen.points, on).map((point, index): HelpHit => ({ kind: "point", group: screen.name, title: pick(point.label), body: [point.desc, ruleOf(point, on)].filter((pair): pair is Pair => !!pair).map(pick).join(" "), target: { tab: "screens", screen: screen.id, point: index } })),
      ...shown(screen.more, on).map((point): HelpHit => ({ kind: "point", group: screen.name, title: pick(point.label), body: pick(point.desc), target: { tab: "screens", screen: screen.id } })),
    ]),
    ...shown(FAQ, on).map((faq): HelpHit => ({ kind: "faq", group: null, title: pick(faq.q), body: pick(faq.a), target: { tab: "faq", faq: faq.id } })),
  ];
  return all.filter((hit) => plain(`${hit.title} ${hit.body} ${hit.group ? pick(hit.group) : ""}`).toLowerCase().includes(words));
}

const screenIds = new Set<string>(SCREENS.map((screen) => screen.id));
/** `/help?screen=input` (the (?) on a screen opens that screen's part) · `/help?tab=faq` (from the inquiries). Anything else: the first tab. */
export function openingOf(tab: string | undefined, screen: string | undefined): { tab: HelpTab; screen: ScreenId } {
  if (screen && screenIds.has(screen)) return { tab: "screens", screen: screen as ScreenId };
  return { tab: tab === "faq" || tab === "screens" ? tab : "start", screen: SCREENS[0].id };
}

export const faqCount = (category: FaqCategory | "all", on: Features) => shown(FAQ, on).filter((faq) => category === "all" || faq.category === category).length;
