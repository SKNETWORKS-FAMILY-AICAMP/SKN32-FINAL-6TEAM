"use client";

import { useEffect, useId, useRef, useState, type ComponentProps, type ReactNode } from "react";
import { Check, ChevronDown, Globe } from "lucide-react";
import { languages } from "@/lib/i18n";
import { updateSettings, useSettings, useT } from "@/lib/settings";
import styles from "./language-picker.module.css";

/**
 * Language card that opens downward, on the settings screen (`[2026-10-13]` it left the menu; before the terms the intro and start screen have `LanguageButton`).
 * Every entry of `languages` is listed; choosing one applies it at once, closes the list and returns focus.
 * `caption` is the small label above the chosen language.
 */
export function LanguagePicker({ caption, className = "", ...props }: { caption?: ReactNode } & Omit<ComponentProps<"div">, "children" | "onKeyDown">) {
  const { language } = useSettings();
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const id = useId();

  function close() {
    setOpen(false);
    toggle.current?.focus({ preventScroll: true });
  }

  return <div {...props} className={`${open ? styles.open : ""} ${className}`}
    // Escape closes only the list; a surrounding menu stays open.
    onKeyDown={(event) => { if (event.key === "Escape" && open) { event.stopPropagation(); close(); } }}>
    <button ref={toggle} type="button" className={styles.toggle} aria-expanded={open} aria-controls={`${id}-list`} onClick={() => setOpen((value) => !value)}>
      <Globe size={18} aria-hidden="true" />
      <span>{caption && <small>{caption}</small>}<strong>{languages.find(([value]) => value === language)?.[1]}</strong></span>
      <ChevronDown size={18} aria-hidden="true" className={styles.chevron} />
    </button>
    <div id={`${id}-list`} className={styles.list} inert={!open}>
      <div>{languages.map(([value, label]) => (
        <button key={value} type="button" lang={value} className={styles.option} aria-pressed={language === value} onClick={() => { updateSettings({ language: value }); close(); }}>
          {label}{language === value && <Check size={16} aria-hidden="true" />}
        </button>
      ))}</div>
    </div>
  </div>;
}

/**
 * `[2026-10-13 사용자 결정]` The globe beside the menu button on the screens up to the plan input — the intro, the start (terms) screen and 「계획 담기」 (`/trips/new`).
 * It is a second way, not instead: the language card on the settings screen (메뉴 › 설정) changes it on every screen too — but that screen opens only after
 * agreeing, so a first-time visitor picks the language of the terms here. From the plan check on, only the settings screen has it. The same 44px chip as the menu button; its list drops below it. Choosing applies at once, closes the list
 * and returns focus; Escape or a press elsewhere closes it.
 */
export function LanguageButton() {
  const t = useT();
  const { language } = useSettings();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const id = useId();
  const current = languages.find(([value]) => value === language)?.[1];

  useEffect(() => {
    if (!open) return;
    const away = (event: PointerEvent) => { if (!box.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);

  function close() {
    setOpen(false);
    toggle.current?.focus({ preventScroll: true });
  }

  return <div ref={box} className={styles.globe} onKeyDown={(event) => { if (event.key === "Escape" && open) { event.stopPropagation(); close(); } }}>
    <button ref={toggle} type="button" className={styles.globeButton} aria-label={t(`언어 · ${current}`, `Language · ${current}`)} aria-expanded={open} aria-controls={open ? `${id}-list` : undefined} onClick={() => setOpen((value) => !value)}>
      <Globe size={20} aria-hidden="true" />
    </button>
    {open && <div id={`${id}-list`} className={styles.globeList}>{languages.map(([value, label]) => (
      <button key={value} type="button" lang={value} className={styles.option} aria-pressed={language === value} onClick={() => { updateSettings({ language: value }); close(); }}>
        {label}{language === value && <Check size={16} aria-hidden="true" />}
      </button>
    ))}</div>}
  </div>;
}
