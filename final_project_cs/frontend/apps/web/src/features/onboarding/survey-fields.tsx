"use client";

import { Fragment, useCallback, useState, type MouseEvent } from "react";
import type { Translate } from "@/lib/i18n";
import { DrawnCheck, OnboardingIcon } from "./icons";
import { PARTY_SIZES, type Area, type Option } from "./model";
import styles from "./onboarding.module.css";

/**
 * `[2026-10-20 ST4F-665]` The pieces of the preference cards, shared by the start survey (`preferences.tsx`) and the questions asked while a plan
 * is read (`features/survey-questions/question-card.tsx`), so both look and behave the same: single-pick chips, the travelers row, the three ranked
 * area cards and the dining / activities rows. Each piece draws what it is given and reports a press; what a press changes is the caller's.
 */

export interface FieldOption { id: string; label: string }
/** A part the plan already told (`read` of the server's loading questions): shown instead of being asked. */
export interface ReadNote { text: string; quotes: readonly string[] }
type Press<T extends unknown[]> = (event: MouseEvent<HTMLButtonElement>, ...value: T) => void;

/** Icons of the three priority areas (onboarding line icons). */
export const AREA_ICONS: Record<Area, string> = { food: "food", activity: "activity", mobility: "public" };

export const fieldOptions = (list: readonly Option[], t: Translate): FieldOption[] => list.map(([id, ko, en]) => ({ id, label: t(ko, en) }));

const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

/** The press feedback of the cards: the pressed control takes the focus and gives a short pulse; `touched` keys add the drawn-check motion. */
export function usePressFeedback(onFeedback?: () => void) {
  const [touched, setTouched] = useState<ReadonlySet<string>>(new Set());
  const feedback = useCallback((control: HTMLButtonElement, key: string) => {
    control.focus({ preventScroll: true });
    onFeedback?.();
    if (reducedMotion()) return;
    setTouched((current) => new Set(current).add(key));
    control.animate([
      { transform: "scale(.97)", boxShadow: "0 0 0 0 transparent" },
      { transform: "scale(1.015)", boxShadow: "0 0 0 3px color-mix(in srgb, var(--color-selected) 8%, transparent)", offset: .6 },
      { transform: "scale(1)", boxShadow: "0 0 0 0 transparent" },
    ], { duration: 220, easing: "cubic-bezier(.2,.8,.2,1)" });
  }, [onFeedback]);
  return { touched, feedback };
}

const feedbackClass = (touched: ReadonlySet<string> | undefined, key: string) => touched?.has(key) ? styles.selectionFeedback : "";

/** One pick from a row of chips (`name` keys the press feedback: `name:option`). */
export function ChoiceChips({ name, options, selected, touched, onPick }: {
  name: string; options: readonly FieldOption[]; selected: string | null; touched?: ReadonlySet<string>; onPick: Press<[id: string]>;
}) {
  return <div className={styles.chips} role="group">{options.map((option) => {
    const on = selected === option.id;
    return <button key={option.id} type="button" className={`${styles.chip} ${on ? styles.selected : ""} ${feedbackClass(touched, `${name}:${option.id}`)}`} aria-pressed={on} onClick={(event) => onPick(event, option.id)}>
      <span className={styles.optionCheck} aria-hidden="true"><DrawnCheck className={styles.drawnCheck} /></span>
      {option.label}
    </button>;
  })}</div>;
}

/** The field under the chips when the own-words chip is picked (the companions' 기타: who it is — the default words). */
export function OtherField({ t, id, value, maxLength, label, placeholder, onChange }: {
  t: Translate; id: string; value: string; maxLength?: number; label?: string; placeholder?: string; onChange: (value: string) => void;
}) {
  return <div className={styles.otherField}>
    <label htmlFor={id} className={styles.groupLabel}>{label ?? t("누구와 함께 여행하는지 알려 주세요.", "Tell us who you’re traveling with.")}</label>
    <input id={id} className={styles.otherInput} value={value} maxLength={maxLength} autoComplete="off" placeholder={placeholder ?? t("예: 직장 동료", "e.g. coworkers")}
      onChange={(event) => onChange(event.target.value)} />
  </div>;
}

/**
 * `[2026-10-19 사용자 지시]` How many travel, under the companions once one is picked: 혼자 · 연인 set it (1 · 2) and the chips stay fixed;
 * 친구 · 가족 start at 2 with 1 not offered; 기타 picks one of 1–4. The rule is the model's (`canPickPartySize` · `sizeFor`).
 */
export function TravelerSizes({ t, labelId, size, canPick, touched, onPick }: {
  t: Translate; labelId: string; size: number | null; canPick: (size: number) => boolean; touched?: ReadonlySet<string>; onPick: Press<[size: number]>;
}) {
  return <div className={styles.sizeField} role="group" aria-labelledby={labelId}>
    <p id={labelId} className={styles.groupLabel}>{t("인원", "Travelers")}</p>
    <div className={styles.chips}>{PARTY_SIZES.map((n) => {
      const selected = size === n;
      return <button key={n} type="button" className={`${styles.chip} ${styles.sizeChip} ${selected ? styles.selected : ""} ${feedbackClass(touched, `partySize:${n}`)}`}
        aria-pressed={selected} disabled={!canPick(n)} onClick={(event) => onPick(event, n)}>
        <span className={styles.optionCheck} aria-hidden="true"><DrawnCheck className={styles.drawnCheck} /></span>
        {t(`${n}명`, `${n}`)}
      </button>;
    })}</div>
  </div>;
}

/** 「계획서에서 읽었어요: 택시 (“웬만하면 택시로”)」 — a part the plan told, so it is not asked. */
export function ReadLine({ t, read }: { t: Translate; read: ReadNote }) {
  const quote = read.quotes.find((text) => text.trim());
  return <p className={styles.readNote}>{t("계획서에서 읽었어요", "Read from your plan")}: {read.text}{quote ? ` (“${quote}”)` : ""}</p>;
}

export interface AreaCard {
  id: string;
  label: string;
  icon: string;
  options: readonly FieldOption[];
  /** The details must be exactly this many (activities: `ACTIVITY_PICKS`); none = one or more. */
  exact?: number;
  /** The plan told this area's details: they are not asked. */
  read?: ReadNote | null;
}

const rank = (t: Translate, order: number, className: string) =>
  <span className={className}><span aria-hidden="true">{order}</span><span className="sr-only">{t(`, ${order}순위`, `, rank ${order}`)}</span></span>;

/**
 * Three area cards in a fixed order. Tapping an area ranks it (1, 2, 3 in tapping order) and opens its details, which rank the same way inside the
 * area. Nothing moves on screen. An area with `exact` says how many to pick, and once full the rest wait until one is un-picked.
 */
export function PriorityAreas({ t, areas, order, details, idPrefix = "", onArea, onDetail }: {
  t: Translate; areas: readonly AreaCard[]; order: readonly string[]; details: Readonly<Record<string, readonly string[]>>; idPrefix?: string;
  onArea: Press<[area: string]>; onDetail: Press<[area: string, id: string]>;
}) {
  return <div className={styles.areas}>{areas.map((area) => {
    const place = order.indexOf(area.id) + 1;
    const picked = details[area.id] ?? [];
    const full = area.exact !== undefined && picked.length >= area.exact;
    return <div key={area.id} className={`${styles.area} ${place ? styles.areaOn : ""}`}>
      <button type="button" className={styles.areaHead} aria-pressed={place > 0} aria-expanded={place > 0} aria-controls={`${idPrefix}details-${area.id}`}
        onClick={(event) => onArea(event, area.id)}>
        <span className={styles.areaIcon}><OnboardingIcon name={area.icon} size={18} /></span>
        <span className={styles.areaName}>{area.label}</span>
        {place > 0 && rank(t, place, styles.rank)}
      </button>
      <div id={`${idPrefix}details-${area.id}`} className={styles.areaDetails} role="group" aria-label={t(`${area.label} 세부 항목`, `${area.label} details`)} hidden={!place}>
        {area.read ? <ReadLine t={t} read={area.read} /> : <>
          {area.exact !== undefined && <p className={styles.pickCount}>{t(`누른 순서대로 ${area.exact}개를 골라 주세요 · ${picked.length}/${area.exact}`, `Pick ${area.exact} in order of importance · ${picked.length}/${area.exact}`)}</p>}
          {area.options.map((option) => {
            const at = picked.indexOf(option.id) + 1;
            return <button key={option.id} type="button" className={`${styles.chip} ${styles.rankedChip} ${at ? styles.selected : ""}`} aria-pressed={at > 0} disabled={full && !at}
              onClick={(event) => onDetail(event, area.id, option.id)}>
              {option.label}{at > 0 && rank(t, at, styles.chipRank)}
            </button>;
          })}
        </>}
      </div>
    </div>;
  })}</div>;
}

export interface PairPart {
  id: string;
  /** Keys the press feedback (`name:option`). */
  name: string;
  label: string;
  options: readonly FieldOption[];
  read?: ReadNote | null;
}

/** Dining and activities, one pick each: a label over each row; a part the plan told shows what it said instead. */
export function PairRows({ t, parts, selected, touched, onPick }: {
  t: Translate; parts: readonly PairPart[]; selected: Readonly<Record<string, string>>; touched?: ReadonlySet<string>; onPick: Press<[part: string, id: string]>;
}) {
  return <>{parts.map((part) => <Fragment key={part.id}>
    <p className={styles.groupLabel}>{part.label}</p>
    {part.read ? <ReadLine t={t} read={part.read} />
      : <ChoiceChips name={part.name} options={part.options} selected={selected[part.id] || null} touched={touched} onPick={(event, id) => onPick(event, part.id, id)} />}
  </Fragment>)}</>;
}
