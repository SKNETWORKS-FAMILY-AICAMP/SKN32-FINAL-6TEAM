import type { IntakeEdit, IntakeSource } from "@/lib/live/intake";
import type { PickedPlace } from "@/lib/live/intake-review";
import type { PlanCandidate } from "./model";

export interface NewStop {
  title: string; date: string; start: string; end: string; place: string; kind: "activity" | "dining";
  /** 검색에서 고른 장소 원값. 이름 재검색으로 지점이 바뀌지 않게 보존한다. */
  pickedPlace?: PickedPlace;
}

export interface AddStopPlace extends PlanCandidate { pickedPlace: PickedPlace | null }

/** 삭제 이력의 번호도 보존하며 기존 원본에 새 항목 하나를 append한다. */
export function newStopEdits(source: Pick<IntakeSource, "source_id" | "items">, draft: NewStop): { index: number; edits: IntakeEdit[] } {
  const index = Math.max(-1, ...source.items.map((item) => item.index)) + 1;
  const values = {
    title: draft.title, date: draft.date, starts_at: draft.start, ends_at: draft.end,
    kind: draft.kind, place: draft.pickedPlace ?? { name: draft.place },
  };
  return { index, edits: Object.entries(values).map(([field, value]) => ({ source_id: source.source_id, field: `items[${index}].${field}`, value })) };
}
