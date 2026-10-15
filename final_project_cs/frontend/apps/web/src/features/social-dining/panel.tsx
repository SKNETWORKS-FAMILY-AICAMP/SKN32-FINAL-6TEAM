"use client";

import { useEffect, useId, useMemo, useState, useSyncExternalStore, type FormEvent, type ReactNode } from "react";
import { useSettings, useT } from "@/lib/settings";
import { progressText } from "@/lib/live/stream";
import { DiningCards, DiningProposal } from "./cards";
import { linkEntries, SocialDiningController, type DiningContext } from "./model";
import styles from "./social-dining.module.css";

export interface DiningMeal { id: string; label: string }
export function SocialDiningPanel({ context, meals, blocked, initiallyOpen = false, children }: { context: DiningContext; meals: DiningMeal[]; blocked?: string | null; initiallyOpen?: boolean; children?: ReactNode }) {
  const t = useT(), { language } = useSettings(), id = useId();
  const controller = useMemo(() => new SocialDiningController(context.intakeId, 0, language,
    { applied: () => undefined, refresh: () => undefined }), [context.intakeId, language]);
  const state = useSyncExternalStore(controller.subscribe, controller.snapshot, controller.snapshot);
  const [open, setOpen] = useState(initiallyOpen);
  const [text, setText] = useState(""), [note, setNote] = useState(""), [inputError, setInputError] = useState("");
  const [target, setTarget] = useState("");
  useEffect(() => { controller.activate(); return () => controller.dispose(); }, [controller]);
  useEffect(() => { controller.setHooks({ applied: context.onApplied, refresh: context.onRefresh }); }, [controller, context]);
  useEffect(() => { controller.setRevision(context.revision); }, [controller, context.revision]);
  useEffect(() => { if (open) void controller.load(); }, [controller, open]);
  const busy = Boolean(state.pending) || Boolean(blocked);
  async function submit(event: FormEvent) {
    event.preventDefault(); if (busy) return;
    try { const entries = linkEntries(text, note); setInputError(""); if (await controller.resolve(entries)) { setText(""); setNote(""); } }
    catch { setInputError(t("https://로 시작하는 링크를 한 줄에 하나씩 넣어 주세요.", "Paste one https:// link per line.")); }
  }
  return <details className={styles.panel} open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary>{t("맛집 링크 모아보기·추가", "Save restaurant links")}</summary>
    {open && <div className={styles.content}>
      <p className={styles.note}>{t("Instagram · TikTok · YouTube의 공개 링크를 모아 둘 수 있어요. 서울 식당의 이름과 지점을 확인한 뒤 식사에 넣을 변경안을 보여 드려요.", "Save public Instagram, TikTok and YouTube links. Confirm the Seoul restaurant and branch, then review a proposal for your meals.")}</p>
      <form onSubmit={submit} className={styles.stack}>
        <label className={styles.field} htmlFor={`${id}-links`}>{t("맛집 링크 · 한 줄에 하나", "Restaurant links · one per line")}<textarea id={`${id}-links`} rows={3} value={text} onChange={(event) => { setText(event.target.value); setInputError(""); }} disabled={busy} placeholder="https://…" /></label>
        <label className={styles.field} htmlFor={`${id}-note`}>{t("식당 이름이나 메모 (선택)", "Restaurant name or note (optional)")}<input id={`${id}-note`} value={note} onChange={(event) => setNote(event.target.value)} disabled={busy} /></label>
        <button className={styles.button} type="submit" disabled={busy || !text.trim()}>{state.pending === "resolve" ? t("링크 확인 중…", "Checking links…") : t("링크 확인하고 보관", "Check and save links")}</button>
      </form>
      {(inputError || state.error) && <div className={styles.error} role="alert">{inputError || state.error}{state.pending === null && state.error && <button type="button" className={styles.button} onClick={() => void controller.load()}>{t("저장한 후보 다시 읽기", "Reload saved candidates")}</button>}</div>}
      {state.pending && <p role="status" className={styles.note}>{state.progress ? progressText(state.progress, t, ["맛집 정보를 확인하고 있어요…", "Checking restaurant details…"]) : state.pending === "apply" ? t("변경안을 적용하고 있어요…", "Applying your changes…") : state.pending === "preview" ? t("식사와 이동을 확인하고 있어요…", "Checking meals and travel…") : t("식당 후보를 확인하고 있어요…", "Checking restaurant candidates…")}</p>}
      {blocked && <p role="status" className={styles.note}>{blocked}</p>}
      <DiningCards links={state.links} t={t} busy={busy} onUpdate={(key, patch) => controller.update(key, patch)} />
      {!!state.links.length && <div className={styles.stack}>
        <label className={styles.field} htmlFor={`${id}-meal`}>{t("어느 식사에 넣을까요?", "Which meal should change?")}<select id={`${id}-meal`} value={target} disabled={busy} onChange={(event) => { setTarget(event.target.value); controller.clearProposal(); }}><option value="">{t("남은 식사에서 맞는 자리 찾기", "Find suitable remaining meals")}</option>{meals.map((meal) => <option key={meal.id} value={meal.id}>{meal.label}</option>)}</select></label>
        <button type="button" className={styles.button} disabled={busy} onClick={() => void controller.preview(meals.some((meal) => meal.id === target) ? target : undefined)}>{t("반영안 확인", "Preview meal changes")}</button>
      </div>}
      {state.proposal && <DiningProposal proposal={state.proposal} t={t} busy={busy || state.proposal.revision !== context.revision} onApply={() => void controller.apply()} />}
      {state.applied && <p role="status" className={styles.success}>{t("확인 중인 일정에 반영했어요. 여행 저장은 기존 완료·등록 버튼에서 이어가 주세요.", "The plan being checked is updated. Continue with its Done or Register button to save the trip.")}</p>}
      {children && <fieldset className={styles.generation} disabled={busy}>{children}</fieldset>}
    </div>}
  </details>;
}
