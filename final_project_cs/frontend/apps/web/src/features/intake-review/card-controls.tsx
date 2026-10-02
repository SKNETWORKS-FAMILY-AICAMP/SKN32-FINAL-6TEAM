"use client";

import type { ReactNode } from "react";
import { Lock, LockOpen, Pencil, Sparkles, Trash2 } from "lucide-react";
import type { ReviewItem } from "@/lib/live/intake-review";
import { useT } from "@/lib/settings";
import { ActionButton } from "./action-button";
import { ro } from "./review-actions";
import styles from "./review-sheet.module.css";
import { useCandidates } from "./use-candidates";

/**
 * A little icon button on a card. `unavailable` greys it but keeps it pressable, so a press can say why it cannot be used
 * now (the mockup's 「꺼진 버튼을 누르면 이유를 알려 준다」).
 */
export function IconAction({ label, unavailable, pressed, onPress, onBlocked, children, ...data }: {
  label: string; unavailable: boolean; pressed?: boolean; onPress: () => void; onBlocked: () => void; children: ReactNode;
} & { "data-act"?: string; "data-item"?: string }) {
  return <button type="button" className={styles.ic} aria-label={label} title={label} aria-pressed={pressed} aria-disabled={unavailable || undefined}
    onClick={() => { if (unavailable) onBlocked(); else onPress(); }} {...data}>{children}</button>;
}

/** 「꼭 넣을 일정으로 고정」 — before the name. */
export function LockControl({ item, unavailable, onToggle, onBlocked }: { item: ReviewItem; unavailable: boolean; onToggle: () => void; onBlocked: () => void }) {
  const t = useT();
  const label = item.locked ? t("고정 풀기", "Unlock") : item.can_lock ? t("꼭 넣을 일정으로 고정", "Lock — keep this stop in the plan") : t("지금은 고정할 수 없어요", "Cannot be locked now");
  return <IconAction label={label} pressed={item.locked} unavailable={unavailable} onPress={onToggle} onBlocked={onBlocked} data-act="lock" data-item={item.id}>
    {item.locked ? <Lock aria-hidden="true" /> : <LockOpen aria-hidden="true" />}
  </IconAction>;
}

/** Edit and delete — after the status word. `onEdit` is absent where there is no edit screen to go to. */
export function TrailControls({ item, unavailable, onEdit, onDelete, onBlocked }: {
  item: ReviewItem; unavailable: boolean; onEdit?: () => void; onDelete: () => void; onBlocked: () => void;
}) {
  const t = useT();
  return <>
    {onEdit && <IconAction label={t("수정", "Edit")} unavailable={unavailable} onPress={onEdit} onBlocked={onBlocked} data-act="edit" data-item={item.id}><Pencil aria-hidden="true" /></IconAction>}
    <IconAction label={t("일정 삭제", "Delete this stop")} unavailable={unavailable} onPress={onDelete} onBlocked={onBlocked} data-act="delete" data-item={item.id}><Trash2 aria-hidden="true" /></IconAction>
  </>;
}

/**
 * The card's own buttons at the bottom of its check lines: 「자동 추천」 switches to the top alternative the server found, and
 * the note says which one that is (read when the card is open). The alternatives come from the server; nothing is guessed here.
 */
export function CardActions({ intakeId, revision, item, open, unavailable, lockedNote, onAuto, onEdit, onBlocked }: {
  intakeId: string; revision: number; item: ReviewItem; open: boolean; unavailable: boolean;
  /** The reason a locked card gives instead of the note about the top alternative. */
  lockedNote: string | null;
  onAuto: () => void; onEdit?: () => void; onBlocked: () => void;
}) {
  const t = useT();
  const candidates = useCandidates(intakeId, item, revision, open && !item.locked);
  const top = candidates.data?.candidates[0]?.place.name;
  const note = lockedNote ?? (top
    ? <>{t("자동 추천은 1순위 ", "Auto-fix switches to the top alternative, ")}<b>{top}</b>{t(`${ro(top).slice(top.length)} 바로 바꿔요`, " right away")}</>
    : candidates.data ? t("바꿀 만한 대체 장소를 찾지 못했어요", "No alternative place was found")
    : candidates.isError ? t("대체 장소를 불러오지 못했어요", "Could not load the alternatives") : null);
  return <>
    <div className={styles.acts}>
      <ActionButton unavailable={unavailable} onBlocked={onBlocked} onClick={onAuto}><Sparkles aria-hidden="true" />{t("자동 추천", "Auto-fix")}</ActionButton>
      {onEdit && <ActionButton variant="primary" unavailable={unavailable} onBlocked={onBlocked} onClick={onEdit}><Pencil aria-hidden="true" />{t("수정", "Edit")}</ActionButton>}
    </div>
    {note && <p className={styles.actsNote}>{note}</p>}
  </>;
}
