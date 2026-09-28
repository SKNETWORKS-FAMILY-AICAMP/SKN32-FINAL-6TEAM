"use client";

import { useId, useRef, useState, type ComponentProps, type ReactNode } from "react";
import { Check, ChevronDown, Globe } from "lucide-react";
import { languages } from "@/lib/i18n";
import { updateSettings, useSettings } from "@/lib/settings";
import styles from "./language-picker.module.css";

/**
 * Language card that opens downward (home intro and menu share it, and the one language setting).
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
