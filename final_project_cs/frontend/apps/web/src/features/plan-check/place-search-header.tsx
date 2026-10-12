"use client";

import { useContext, useEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import { ArrowLeft, Search, X } from "lucide-react";
import { HeaderSlot } from "@/components/layout/device-frame";
import { useT } from "@/lib/settings";
import styles from "./plan-check.module.css";

/** 장소 수정과 추가가 같은 상단 검색·뒤로가기 UI를 사용한다. */
export function PlaceSearchHeader({ query, onQuery, onBack, backLabel, placeholder, busy = false, autoFocus = false, escapeClears = false, inputRef, errorId }: {
  inputRef?: RefObject<HTMLInputElement | null>;
  errorId?: string;
  query: string; onQuery: (query: string) => void; onBack: () => void; backLabel: string;
  placeholder: string; busy?: boolean; autoFocus?: boolean; escapeClears?: boolean;
}) {
  const t = useT(), slot = useContext(HeaderSlot);
  const fallbackInput = useRef<HTMLInputElement>(null);
  const input = inputRef ?? fallbackInput;
  const [open, setOpen] = useState(false);
  useEffect(() => { if (autoFocus) input.current?.focus({ preventScroll: true }); }, [autoFocus, input]);
  const content = <div className={styles.headSearch} data-open={open || undefined} data-hide-brand>
    <button type="button" className={styles.back} aria-label={backLabel} aria-disabled={busy} onClick={() => { if (!busy) onBack(); }}><ArrowLeft size={20} strokeWidth={1.6} aria-hidden="true" /></button>
    <div className={styles.searchField}>
      <Search size={16} strokeWidth={1.8} aria-hidden="true" />
      <input ref={input} type="search" value={query} placeholder={placeholder} aria-label={t("장소 검색", "Search places")} aria-invalid={!!errorId} aria-describedby={errorId} autoComplete="off" readOnly={busy}
        onChange={(event) => onQuery(event.target.value)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
        onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); if (!busy) { if (escapeClears && query) onQuery(""); else onBack(); } } }} />
      {query && <button type="button" className={styles.clear} aria-label={t("검색어 지우기", "Clear the search")} onPointerDown={(event) => event.preventDefault()} onClick={() => { if (!busy) { onQuery(""); input.current?.focus(); } }}><X size={12} strokeWidth={2} aria-hidden="true" /></button>}
    </div>
  </div>;
  return slot ? createPortal(content, slot) : content;
}
