"use client";

import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { Button, ButtonLink } from "@/components/ui";
import { useT } from "@/lib/settings";
import { draftOfItem, draftProblem, type ItemDraft, type PlanItem, type TripIssue } from "./model";
import styles from "./plan-check.module.css";

/** Why a save did not happen, in the server's own words when it said no (`LiveError.message`). */
const reason = (error: unknown) => error instanceof Error ? error.message : String(error);

/**
 * ⑤ The stop editor, in place of the list (mockup scenario 4): the place by name — the server looks it up again on save —
 * or 「장소 없음」, the stop's name, date and times. What the screen can check it checks first (`draftProblem`); the rest is
 * the server's to say, and a refusal keeps the editor open with what was typed. Candidates and photos have no server call
 * yet, and say so.
 */
export function StopEditor({ item, onCancel, onSave }: { item: PlanItem; onCancel: () => void; onSave: (draft: ItemDraft) => Promise<void> }) {
  const t = useT();
  const [draft, setDraft] = useState(() => draftOfItem(item));
  const [problem, setProblem] = useState<ReturnType<typeof draftProblem>>(null);
  const [refusal, setRefusal] = useState("");
  const [saving, setSaving] = useState(false);
  const first = useRef<HTMLInputElement>(null);
  useEffect(() => { first.current?.focus(); }, []);
  const change = (patch: Partial<ItemDraft>) => { setDraft((current) => ({ ...current, ...patch })); setProblem(null); setRefusal(""); };

  async function save() {
    const found = draftProblem(draft);
    setProblem(found);
    if (found) return;
    setSaving(true);
    try { await onSave(draft); }
    catch (error) { setRefusal(reason(error)); }
    finally { setSaving(false); }
  }

  const message = problem === "title" ? t("일정 이름을 적어 주세요.", "Give the stop a name.")
    : problem === "time" ? t("끝 시각이 시작보다 빨라요.", "The end is before the start.")
      : problem === "place" ? t("장소 이름을 적거나 「장소 없음」을 골라 주세요.", "Type a place name or choose “No place”.") : "";
  return <form className={styles.editor} aria-labelledby="plan-editor-title" noValidate
    onSubmit={(event) => { event.preventDefault(); void save(); }}
    onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); onCancel(); } }}>
    <h3 id="plan-editor-title" className={styles.editorTitle}>{t(`「${item.title}」 고치기`, `Edit “${item.title}”`)}</h3>
    <label className={styles.field}>{t("장소 이름", "Place")}
      <input ref={first} type="search" value={draft.place} disabled={draft.noPlace} placeholder={t("장소 이름으로 찾기", "Find a place by name")}
        aria-invalid={problem === "place"} onChange={(event) => change({ place: event.target.value })} />
    </label>
    <label className={styles.toggle}><input type="checkbox" checked={draft.noPlace} onChange={(event) => change({ noPlace: event.target.checked })} />{t("장소 없음(자유 시간 등)", "No place (free time etc.)")}</label>
    <p className={styles.editorNote}>{t("저장하면 서버가 이 이름으로 장소를 다시 찾고 일정을 다시 확인해요. 후보 장소와 사진 보기는 준비 중이에요.", "On save the server looks the place up by this name and checks the plan again. Candidates and photos are coming later.")}</p>
    <label className={styles.field}>{t("일정 이름", "Name")}
      <input type="text" value={draft.title} aria-invalid={problem === "title"} onChange={(event) => change({ title: event.target.value })} />
    </label>
    <div className={styles.fieldRow}>
      <label className={styles.field}>{t("날짜", "Date")}<input type="date" value={draft.date} onChange={(event) => change({ date: event.target.value })} /></label>
      <label className={styles.field}>{t("시작", "Start")}<input type="time" value={draft.start} aria-invalid={problem === "time"} onChange={(event) => change({ start: event.target.value })} /></label>
      <label className={styles.field}>{t("끝", "End")}<input type="time" value={draft.end} aria-invalid={problem === "time"} onChange={(event) => change({ end: event.target.value })} /></label>
    </div>
    {(message || refusal) && <p className={styles.editorError} role="alert">{message || refusal}</p>}
    <div className={styles.editorButtons}>
      <Button onClick={onCancel} disabled={saving}>{t("취소", "Cancel")}</Button>
      <Button variant="primary" type="submit" disabled={saving}>{saving ? t("저장하는 중…", "Saving…") : t("저장", "Save")}</Button>
    </div>
  </form>;
}

/**
 * ⑥ 「삭제」 asks first, in the middle of the phone screen (mockup 개정 6): cancel has the focus, Esc and a press outside
 * close it, Tab stays between its two buttons. The server cannot put a deleted stop back, so there is no undo after it.
 */
export function DeleteDialog({ item, dayLabel, onCancel, onDelete }: { item: PlanItem; dayLabel: string; onCancel: () => void; onDelete: () => Promise<void> }) {
  const t = useT();
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState("");
  const cancel = useRef<HTMLButtonElement>(null);
  const confirm = useRef<HTMLButtonElement>(null);
  useEffect(() => { cancel.current?.focus(); }, []);
  function keys(event: KeyboardEvent) {
    if (event.key === "Escape" && !busy) { event.preventDefault(); onCancel(); }
    if (event.key !== "Tab") return;
    const order = [cancel.current, confirm.current];
    const at = order.indexOf(document.activeElement as HTMLButtonElement);
    event.preventDefault();
    order[(at + (event.shiftKey ? order.length - 1 : 1)) % order.length]?.focus();
  }
  async function remove() {
    setBusy(true);
    try { await onDelete(); }
    catch (error) { setRefusal(reason(error)); setBusy(false); }
  }
  return <div className={styles.scrim} onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onCancel(); }}>
    <div className={styles.dialog} role="alertdialog" aria-modal="true" aria-labelledby="plan-delete-title" aria-describedby="plan-delete-detail" onKeyDown={keys}>
      <p id="plan-delete-title" className={styles.dialogTitle}>{t(`「${item.title}」 일정을 삭제하시겠습니까?`, `Delete “${item.title}”?`)}</p>
      <p id="plan-delete-detail" className={styles.dialogDetail}>{dayLabel}{item.startsAt && ` · ${item.startsAt}`}<br />{t("삭제한 일정은 되돌릴 수 없어요.", "A deleted stop cannot be brought back.")}</p>
      {refusal && <p className={styles.editorError} role="alert">{refusal}</p>}
      <div className={styles.dialogButtons}>
        <Button ref={cancel} onClick={onCancel} disabled={busy}>{t("취소", "Cancel")}</Button>
        <Button ref={confirm} variant="danger" onClick={() => void remove()} disabled={busy}>{busy ? t("삭제하는 중…", "Deleting…") : t("삭제", "Delete")}</Button>
      </div>
    </div>
  </div>;
}

/** What the trip as a whole still needs before it can be registered — answered here, sent to the server at once. */
export function TripIssues({ issues, onSave }: { issues: TripIssue[]; onSave?: (field: "first_day" | "party_size", value: string | number) => Promise<void> }) {
  const t = useT();
  return <section className={styles.tripIssues} aria-labelledby="plan-trip-issues">
    <h3 id="plan-trip-issues" className={styles.tripIssuesTitle}>{t("여행 전체에서 확인할 것", "For the whole trip")}</h3>
    <ul>{issues.map((issue, index) => <li key={`${issue.field}-${index}`}><p>{issue.message}</p>
      {issue.field && onSave && <TripAnswer field={issue.field} onSave={onSave} />}</li>)}</ul>
  </section>;
}

function TripAnswer({ field, onSave }: { field: "first_day" | "party_size"; onSave: (field: "first_day" | "party_size", value: string | number) => Promise<void> }) {
  const t = useT();
  const [value, setValue] = useState(field === "party_size" ? "2" : "");
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState("");
  async function save() {
    if (!value) return;
    setBusy(true); setRefusal("");
    try { await onSave(field, field === "party_size" ? Number(value) : value); }
    catch (error) { setRefusal(reason(error)); }
    finally { setBusy(false); }
  }
  return <form className={styles.tripAnswer} onSubmit={(event) => { event.preventDefault(); void save(); }}>
    <label className={styles.field}>{field === "first_day" ? t("여행 첫날", "First day") : t("인원", "Travellers")}
      {field === "first_day"
        ? <input type="date" value={value} onChange={(event) => setValue(event.target.value)} />
        : <select value={value} onChange={(event) => setValue(event.target.value)}>{[1, 2, 3, 4].map((n) => <option key={n} value={n}>{t(`${n}명`, `${n}`)}</option>)}</select>}
    </label>
    <Button type="submit" disabled={busy || !value}>{busy ? t("저장하는 중…", "Saving…") : t("저장", "Save")}</Button>
    {refusal && <p className={styles.editorError} role="alert">{refusal}</p>}
  </form>;
}

export interface Registration {
  /** The server says the plan can be registered as it stands (`check.ready`). */
  ready: boolean;
  busy: boolean;
  onRegister: () => void;
  /** A refusal, in the server's words, with its listed problems. */
  error: string | null;
  problems: string[];
  /** Set once registered: where the trip opens. */
  registeredHref: string | null;
}

/**
 * ⑦ The bottom of the result (mockup scenario 7): 「전체 자동 추천」 on the left — no server call for it yet, so it says
 * 「준비 중」 — and the next step on the right. The server checks the plan again on every save, so there is no separate
 * re-check: 「여행 등록」 opens as soon as the server says the plan is ready.
 */
export function ResultFooter({ registration, review, autoAll }: { registration?: Registration; review: number; autoAll?: () => Promise<void> }) {
  const t = useT();
  let status: ReactNode = null;
  if (registration?.error) {
    status = <div role="alert"><p>{registration.error}</p>{registration.problems.length > 0 && <ul>{registration.problems.map((problem, index) => <li key={index}>{problem}</li>)}</ul>}</div>;
  } else if (registration?.registeredHref) status = <p>{t("이미 등록했어요.", "Already registered.")}</p>;
  else if (registration && !registration.ready) {
    status = <p role="status">{t("확인 필요한 것을 고치면 등록할 수 있어요. 고칠 때마다 서버가 다시 확인해요.", "Fix what needs a look to register. The server checks again on every save.")}</p>;
  }
  return <footer className={styles.footer}>
    {status}
    <Button disabled={!autoAll} onClick={() => void autoAll?.()}>
      {t("전체 자동 추천", "Recommend all")}{review > 0 && <span className={styles.badge}>{review}</span>}{!autoAll && <small className={styles.soon}>{t("준비 중", "soon")}</small>}
    </Button>
    {registration && (registration.registeredHref
      ? <ButtonLink href={registration.registeredHref} variant="primary">{t("여행 보기", "Open trip")}</ButtonLink>
      : <Button variant="primary" disabled={!registration.ready || registration.busy} onClick={registration.onRegister}>
        {registration.busy ? t("등록하는 중…", "Registering…") : t("여행 등록", "Register trip")}</Button>)}
  </footer>;
}
