"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject, type FocusEventHandler } from "react";
import Link from "next/link";
import { Check, Send, ArrowUp, ArrowDown } from "lucide-react";
import { Button } from "@/components/ui";
import { routes } from "@/lib/routes";
import { useT } from "@/lib/settings";
import { draftOfItem, draftProblem, needs, type ItemDraft, type PlanCheckView, type PlanItem, type TripIssue } from "./model";
import { Act, reason } from "./parts";
import styles from "./plan-check.module.css";
import tripStyles from "../trip/trip-screen.module.css";

/**
 * The stop's own details — name, date, times, the place by name or 「장소 없음」 — under the change screen (「직접 고치기」).
 * What the screen can check it checks first (`draftProblem`); the rest is the server's to say, and a refusal keeps the
 * editor open with what was typed.
 */
export function StopEditor({ item, onCancel, onSave, autoFocus = true }: { item: PlanItem; onCancel: () => void; onSave: (draft: ItemDraft) => Promise<void>; autoFocus?: boolean }) {
  const t = useT();
  const [draft, setDraft] = useState(() => draftOfItem(item));
  const [problem, setProblem] = useState<ReturnType<typeof draftProblem>>(null);
  const [refusal, setRefusal] = useState("");
  const [saving, setSaving] = useState(false);
  const first = useRef<HTMLInputElement>(null);
  useEffect(() => { if (autoFocus) first.current?.focus(); }, [autoFocus]);
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
    onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onCancel(); } }}>
    <h3 id="plan-editor-title" className={styles.editorTitle}>{t(`「${item.title}」 고치기`, `Edit “${item.title}”`)}</h3>
    <label className={styles.field}>{t("장소 이름", "Place")}
      <input ref={first} type="search" value={draft.place} disabled={draft.noPlace} placeholder={t("장소 이름으로 찾기", "Find a place by name")}
        aria-invalid={problem === "place"} onChange={(event) => change({ place: event.target.value })} />
    </label>
    <label className={styles.toggle}><input type="checkbox" checked={draft.noPlace} onChange={(event) => change({ noPlace: event.target.checked })} />{t("장소 없음(자유 시간 등)", "No place (free time etc.)")}</label>
    <p className={styles.editorNote}>{t("저장하면 서버가 이 이름으로 장소를 다시 찾고 일정을 다시 확인해요.", "On save the server looks the place up by this name and checks the plan again.")}</p>
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
  /** The same for the plan 「전체 자동 추천」 would make (its dry run was checked by the server too); undefined when there is no preview. */
  previewReady?: boolean;
  busy: boolean;
  /** Registers the plan the server holds NOW (it reads the revision when called, so a plan saved a moment ago is the one registered). */
  onRegister: () => void;
  /** A refusal, in the server's words, with its listed problems. */
  error: string | null;
  problems: string[];
  /** `[2026-10-04]` The refusal is a guest's limit (`guest_*`, `login_required`): logging in lifts it, so the screen says where. */
  loginRequired?: boolean;
  loginHref?: string;
  /** Set once registered: where the trip opens. */
  registeredHref: string | null;
}

/** 제출·등록은 여행 화면의 채팅 단추와 같은 크기·위치의 플로팅 동작이다. 수정안은 기존처럼 저장 후 등록한다. */
export function ResultFooter({ view, registration, frozen, explain, previewing = false, needsTotal, pendingRemovals = 0, onRecheck, onRegisterPreview, footerRef, muted = false, focusHandlers }: {
  footerRef?: RefObject<HTMLElement | null>;
  muted?: boolean;
  focusHandlers?: { onFocusCapture: FocusEventHandler<HTMLElement>; onBlurCapture: FocusEventHandler<HTMLElement> };
  view: PlanCheckView; registration?: Registration;
  /** The plan shown is the proposed one (nothing saved yet). */
  previewing?: boolean;
  /** What still needs a look in the plan shown, not counting stops marked for deletion (they are leaving). */
  needsTotal?: number;
  /** Stops marked for deletion: they go when the plan is sent again. */
  pendingRemovals?: number;
  /** Why nothing can be pressed now (being checked again, registered), or null. */
  frozen: string | null;
  explain: (why: string) => void;
  onRecheck?: () => void;
  onRegisterPreview?: () => void;
}) {
  const t = useT();
  const total = needsTotal ?? needs(view).total;
  const registered = Boolean(registration?.registeredHref);
  let status: ReactNode = null;
  if (registration?.error) {
    status = <div role="alert"><p>{registration.error}</p>{registration.problems.length > 0 && <ul>{registration.problems.map((problem, index) => <li key={index}>{problem}</li>)}</ul>}
      {registration.loginRequired && <p className={styles.loginHint}>
        <Link href={registration.loginHref ?? `${routes.myPage}#accounts`}>{t("계정으로 계속하기", "Continue with an account")}</Link>
        {t(" — 로그인하면 작성 중인 일정을 계정에 넣고 여기로 돌아와요.", " — sign in to keep this plan in your account and return here.")}</p>}
      </div>;
  }
  let next: ReactNode;
  if (registered) {
    next = <Link href={registration!.registeredHref!} className={`${styles.footButton} ${tripStyles.chatFab}`} data-done aria-label={t("등록 완료 — 여행 보기", "Registered — open the trip")}><Check size={23} aria-hidden="true" /><span className="sr-only">{t("등록 완료", "Registered")}</span></Link>;
  } else if (view.rechecking) {
    next = <button type="button" className={`${styles.footButton} ${tripStyles.chatFab}`} data-primary aria-label={t("다시 확인하는 중…", "Checking again…")} aria-disabled="true" onClick={() => explain(t("다시 확인하는 중이에요 · 잠시만요", "Checking again · one moment"))}>
      <span className={styles.spinner} aria-hidden="true" /></button>;
  } else if (total > 0 || (!previewing && (view.dirty || pendingRemovals > 0))) {
    // ★`[2026-10-04]` What the customer changed (or marked for deletion) can always be sent again — a stop to take out must not wait for every other stop to be fixed.
    //   Only a plan with nothing to send and something still to look at has to be fixed first.
    const pending = !previewing && (view.dirty || pendingRemovals > 0);
    const why = pending ? frozen ?? (!onRecheck ? t("다시 제출은 준비 중이에요", "Sending again is coming") : null)
      : t(`확인이 필요한 항목 ${total}건이 남아 있어요 · 전체 자동 추천이나 수정으로 먼저 고쳐 주세요`, `${total} item${total > 1 ? "s" : ""} still need a look · fix them with Recommend all or Edit first`);
    next = <Act className={`${styles.footButton} ${tripStyles.chatFab}`} data-primary why={why} explain={explain} onPress={() => onRecheck?.()} aria-label={t("다시 제출", "Send again")} tooltip={t("다시 제출", "Send again")}><Send size={22} aria-hidden="true" /></Act>;
  } else {
    const ready = previewing ? registration?.previewReady ?? registration?.ready : registration?.ready;
    const why = !registration ? t("여행 등록은 준비 중이에요", "Registering is coming")
      : frozen ?? (registration.busy ? t("등록하는 중이에요", "Registering") : !ready
        ? (registration.problems.join(" · ") || t("서버가 아직 등록할 수 없다고 해요 · 위의 확인할 것을 먼저 고쳐 주세요", "The server cannot register it yet · fix what is listed above first")) : null);
    next = <Act className={`${styles.footButton} ${tripStyles.chatFab}`} data-primary why={why} explain={explain} onPress={() => (previewing && onRegisterPreview ? onRegisterPreview() : registration?.onRegister())} aria-label={registration?.busy ? t("등록하는 중…", "Registering…") : t("여행 등록", "Register trip")} tooltip={t("여행 등록", "Register trip")}>{registration?.busy ? <span className={styles.spinner} aria-hidden="true" /> : <Check size={24} aria-hidden="true" />}</Act>;
  }
  return <footer ref={footerRef} className={`${styles.footer} ${tripStyles.chatBar}`} data-quiet={muted || undefined} inert={muted} aria-hidden={muted || undefined} {...focusHandlers}>
    {status}
    {next}
  </footer>;
}

export function PreviewHint({ direction, text, onPress, why, explain, edge, progress }: {
  direction: "up" | "down"; text: string; onPress: () => void; why: string | null;
  explain: (why: string) => void; edge?: string; progress: number;
}) {
  const Icon = direction === "up" ? ArrowUp : ArrowDown;
  return <Act className={styles.pullHint} why={why} explain={explain} onPress={onPress} data-edge={edge}
    style={{ "--pull": progress } as CSSProperties}>
    <span className={styles.pullDirection}>{text}<Icon size={16} strokeWidth={1.6} aria-hidden="true" /></span>
    <span className={styles.pullBar} aria-hidden="true"><span /></span>
  </Act>;
}
