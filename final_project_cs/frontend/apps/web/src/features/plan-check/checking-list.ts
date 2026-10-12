import { timeline, type PlanCheckView, type PlanItem } from "./model";

/** Read stops stand in the list before their checks or map pins are revealed. */
export function checkingList(shown: PlanCheckView, source: PlanCheckView): { view: PlanCheckView; activeId: string | null; waiting: ReadonlySet<string> } {
  if (shown.stage === "done") return { view: shown, activeId: null, waiting: new Set() };
  const drawn = new Map(shown.items.map(item => [item.id, item]));
  const known = new Map(source.items.map(item => [item.id, item]));
  const items: PlanItem[] = [];
  const included = new Set<string>();
  const dates = [...new Set([...source.days.map(day => day.date), ...source.lines.flatMap(line => line.read && line.found?.kind === "item" && line.found.date ? [line.found.date] : [])])].filter(Boolean).sort();
  const add = (item: PlanItem) => { if (!included.has(item.id)) { included.add(item.id); items.push(drawn.get(item.id) ?? item); } };
  for (const line of source.lines) {
    if (!line.read || line.found?.kind !== "item") continue;
    const found = line.found;
    const existing = (found.id ? known.get(found.id) : undefined) ?? (found.sourceKey ? known.get(found.sourceKey) : undefined);
    // Older in-memory views have no identity on their lines: their full item list is authoritative.
    if (!found.id && source.items.length) continue;
    const id = existing?.id ?? found.id ?? `read-line-${line.no}`;
    const date = found.date ?? existing?.date ?? "";
    const day = found.day ?? existing?.day ?? (date ? source.days.find(entry => entry.date === date)?.day ?? dates.indexOf(date) + 1 : 0);
    add({ id, day, date, startsAt: found.startsAt ?? "", endsAt: "", title: found.title,
      place: "", noPlace: false, coordinates: null, checks: [], verdict: null, locked: false, booked: null, info: null, suggestion: null });
  }
  for (const item of source.items) add({ ...item, place: "", coordinates: null, checks: [], verdict: null, info: null, suggestion: null });
  for (const item of shown.items) add(item);
  const days = [...new Map(items.map(item => [item.day, { day: item.day, date: item.date }])).values()].sort((a, b) => a.day - b.day);
  const order = [...new Set(shown.items.map(item => item.day))].sort((a, b) => a - b).flatMap(day => timeline(shown, day));
  const last = order.at(-1);
  return {
    view: { ...shown, days, items },
    activeId: last ? last.type === "item" ? last.item.id : last.move.id : null,
    waiting: new Set(items.filter(item => !drawn.has(item.id)).map(item => item.id)),
  };
}
