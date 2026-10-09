"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useT } from "@/lib/settings";
import type { AddStopPlace } from "./new-stop";
import { reason } from "./parts";
import styles from "./add-stop.module.css";
import { PlaceSearchHeader } from "./place-search-header";

type Search = (query: string) => Promise<AddStopPlace[]>;
const SEARCH_DELAY_MS = 300;

/** 장소 식별값은 검색 결과에서만 고른다. 늦은 응답은 새 검색 결과를 덮지 않는다. */
export function PlaceSearch({ search, value, onPick, error, onBlur, onFocus, busy, onCancel }: {
  search?: Search; value: AddStopPlace | null; onPick: (place: AddStopPlace | null) => void;
  error?: string; onBlur: () => void; onFocus: () => void; busy: boolean; onCancel?: () => void;
}) {
  const t = useT(), id = useId();
  const [query, setQuery] = useState("");
  const [retry, setRetry] = useState(0);
  const [result, setResult] = useState<{ state: "idle" | "loading" | "ready" | "failed"; list: AddStopPlace[]; message?: string }>({ state: "idle", list: [] });
  const latestSearch = useRef(search);
  useEffect(() => { latestSearch.current = search; }, [search]);
  useEffect(() => {
    const ask = latestSearch.current, words = query.trim();
    if (!ask || words.length < 2 || value) return;
    let active = true;
    const timer = setTimeout(() => {
      setResult({ state: "loading", list: [] });
      void ask(words).then((list) => {
        if (active) setResult({ state: "ready", list });
      }, (problem: unknown) => { if (active) setResult({ state: "failed", list: [], message: reason(problem) }); });
    }, SEARCH_DELAY_MS);
    return () => { active = false; clearTimeout(timer); };
  }, [query, retry, value]);

  return <div className={styles.place}>
    {onCancel && <PlaceSearchHeader query={query} onQuery={(next) => { if (value) onPick(null); setQuery(next); setResult({ state: "idle", list: [] }); onFocus(); }} onBack={onCancel}
      backLabel={t("일정 추가 취소", "Cancel adding a stop")} placeholder={t("추가할 장소 이름이나 주소", "Place name or address to add")} busy={busy} autoFocus />}
    {value ? <div className={styles.selected}>
      <span><strong>{value.name}</strong>{value.info?.address && <small>{value.info.address}</small>}</span>
      <button type="button" onClick={() => { if (busy) return; setQuery(""); setResult({ state: "idle", list: [] }); onPick(null); requestAnimationFrame(() => document.querySelector<HTMLInputElement>('[data-hide-brand] input[type="search"]')?.focus()); }}>{t("다시 검색", "Search again")}</button>
    </div> : <>
      {!onCancel && <><label htmlFor={id}>{t("장소 검색", "Search places")}</label>
      <input id={id} name="place" type="search" autoComplete="off" value={query} maxLength={60}
        placeholder={t("장소 이름이나 주소로 검색", "Search by place name or address")} readOnly={busy}
        aria-invalid={!!error} aria-describedby={`${id}-hint`}
        onFocus={onFocus} onBlur={onBlur}
        onChange={(event) => { setQuery(event.target.value); setResult({ state: "idle", list: [] }); onFocus(); }}
        onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); setRetry((old) => old + 1); } }} /></>}
      <p id={`${id}-hint`} className={error ? styles.error : styles.hint}>{error || (query.trim().length === 1
        ? t("두 글자 이상 입력해 주세요.", "Enter at least two characters.")
        : t("검색 결과에서 방문할 장소를 골라 주세요.", "Choose the place you will visit from the results."))}</p>
      {!search && <p role="alert">{t("장소 검색을 연결하지 못했어요. 화면을 다시 열어 주세요.", "Place search is unavailable. Reopen this screen.")}</p>}
      {query.trim() && search && <div aria-live="polite" aria-busy={result.state === "loading"}>
        {result.state === "loading" && <p role="status">{t("장소를 찾고 있어요…", "Finding places…")}</p>}
        {result.state === "failed" && <><p role="alert">{result.message}</p><button type="button" onClick={() => setRetry((old) => old + 1)}>{t("검색 다시 시도", "Retry search")}</button></>}
        {result.state === "ready" && (result.list.length ? <ul className={styles.results} aria-label={t("장소 검색 결과", "Place search results")}>
          {result.list.map((place) => <li key={place.id}><button type="button" aria-disabled={!place.pickedPlace || busy}
            onClick={() => { if (!busy && place.pickedPlace) onPick(place); }}>
            <strong>{place.name}</strong>
            {place.info?.category && <span>{place.info.category}</span>}
            {place.info?.address && <small>{place.info.address}</small>}
            {!place.pickedPlace && <small>{t("위치 정보가 없어 선택할 수 없어요", "Cannot select without location data")}</small>}
          </button></li>)}
        </ul> : <p role="status">{t("검색 결과가 없어요. 다른 이름이나 주소로 찾아 주세요.", "No results. Try another name or address.")}</p>)}
      </div>}
    </>}
  </div>;
}
