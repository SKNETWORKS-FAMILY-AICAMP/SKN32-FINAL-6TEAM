"use client";

import { useEffect, useId, useRef, useState, type RefObject } from "react";
import { useT } from "@/lib/settings";
import type { AddStopPlace } from "./new-stop";
import { reason } from "./parts";
import styles from "./add-stop.module.css";
import { PlaceSearchHeader } from "./place-search-header";

type Search = (query: string, signal?: AbortSignal) => Promise<AddStopPlace[]>;
const SEARCH_DELAY_MS = 300;

/** 장소 식별값은 검색 결과에서만 고른다. 늦은 응답은 새 검색 결과를 덮지 않는다. */
export function PlaceSearch({ search, value, onPick, error, onBlur, onFocus, busy, onCancel, query, onQuery, inputRef }: {
  query: string; onQuery: (query: string) => void; inputRef: RefObject<HTMLInputElement | null>;
  search?: Search; value: AddStopPlace | null; onPick: (place: AddStopPlace | null) => void;
  error?: string; onBlur: () => void; onFocus: () => void; busy: boolean; onCancel?: () => void;
}) {
  const t = useT(), id = useId();
  const [retry, setRetry] = useState(0);
  const [result, setResult] = useState<{ state: "idle" | "loading" | "ready" | "failed"; list: AddStopPlace[]; message?: string }>({ state: "idle", list: [] });
  const latestSearch = useRef(search);
  useEffect(() => { latestSearch.current = search; }, [search]);
  useEffect(() => {
    const ask = latestSearch.current, words = query.trim();
    if (!ask || words.length < 2 || value) return;
    let active = true;
    // `[2026-10-22]` A search the next letter makes stale is aborted, not left to spend the map search budget.
    const stop = new AbortController();
    const timer = setTimeout(() => {
      setResult({ state: "loading", list: [] });
      void ask(words, stop.signal).then((list) => {
        if (active) setResult({ state: "ready", list });
      }, (problem: unknown) => { if (active) setResult({ state: "failed", list: [], message: reason(problem) }); });
    }, SEARCH_DELAY_MS);
    return () => { active = false; clearTimeout(timer); stop.abort(); };
  }, [query, retry, value]);

  return <div className={styles.place}>
    {onCancel && <PlaceSearchHeader query={query} onQuery={(next) => { if (value) onPick(null); onQuery(next); setResult({ state: "idle", list: [] }); onFocus(); }} onBack={onCancel}
      backLabel={t("일정 추가 취소", "Cancel adding a stop")} placeholder={t("추가할 장소 이름이나 주소", "Place name or address to add")} busy={busy} inputRef={inputRef} errorId={error ? `${id}-hint` : undefined} autoFocus escapeClears />}
    {value ? <div className={styles.selected}>
      <span><strong>{value.name}</strong>{value.info?.address && <small>{value.info.address}</small>}{value.pickedPlace?.source === "map" && <small>{t("지도에서 지정", "Picked on map")} · {value.pickedPlace.latitude.toFixed(6)}, {value.pickedPlace.longitude.toFixed(6)}</small>}</span>
      <button type="button" onClick={() => { if (busy) return; onQuery(""); setResult({ state: "idle", list: [] }); onPick(null); requestAnimationFrame(() => inputRef.current?.focus()); }}>{t("다시 검색", "Search again")}</button>
    </div> : <>
      {!onCancel && <><label htmlFor={id}>{t("장소 검색", "Search places")}</label>
      <input ref={inputRef} id={id} name="place" type="search" autoComplete="off" value={query} maxLength={60}
        placeholder={t("장소 이름이나 주소로 검색", "Search by place name or address")} readOnly={busy}
        aria-invalid={!!error} aria-describedby={`${id}-hint`}
        onFocus={onFocus} onBlur={onBlur}
        onChange={(event) => { onQuery(event.target.value); setResult({ state: "idle", list: [] }); onFocus(); }}
        onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); setRetry((old) => old + 1); } }} /></>}
      {(!onCancel || error || query.trim()) && <p id={`${id}-hint`} className={error ? styles.error : styles.hint}>{error || (query.trim().length === 1
        ? t("두 글자 이상 입력해 주세요.", "Enter at least two characters.")
        : t("검색 결과에서 방문할 장소를 골라 주세요.", "Choose the place you will visit from the results."))}</p>}
      {!search && <p role="alert">{t("장소 검색을 연결하지 못했어요. 화면을 다시 열어 주세요.", "Place search is unavailable. Reopen this screen.")}</p>}
      {query.trim() && search && <div aria-live="polite" aria-busy={result.state === "loading"}>
        {result.state === "loading" && <p role="status">{t("장소를 찾고 있어요…", "Finding places…")}</p>}
        {result.state === "failed" && <><p role="alert">{result.message}</p><button type="button" onClick={() => setRetry((old) => old + 1)}>{t("검색 다시 시도", "Retry search")}</button></>}
        {result.state === "ready" && (result.list.length ? groupsOf(result.list, t).map((group) => <div key={group.key}>
          {group.title && <p className={styles.resultsGroup}>{group.title}<small>{group.hint}</small></p>}
          <ul className={styles.results} aria-label={group.title ?? t("장소 검색 결과", "Place search results")}>
          {group.list.map((place) => <li key={place.id}><button type="button" aria-disabled={!place.pickedPlace || busy}
            onClick={() => { if (!busy && place.pickedPlace) onPick(place); }}>
            <strong>{place.name}{group.tag && <em className={styles.orderTag}>{group.tag}</em>}</strong>
            {place.info?.category && <span>{place.info.category}</span>}
            {place.info?.address && <small>{place.info.address}</small>}
            {place.distance && <small>{t(`${place.distance.from}에서 ${place.distance.km.toFixed(1)}km`, `${place.distance.km.toFixed(1)} km from ${place.distance.from}`)}</small>}
            {!place.pickedPlace && <small>{t("위치 정보가 없어 선택할 수 없어요", "Cannot select without location data")}</small>}
          </button></li>)}
          </ul></div>) : <p role="status">{t("검색 결과가 없어요. 다른 이름이나 주소로 찾아 주세요.", "No results. Try another name or address.")}</p>)}
      </div>}
    </>}
  </div>;
}

/**
 * `[2026-10-23 사용자 지시 — Codex 합의]` The add search answers two lists: least out of the way between the stops either side (`route`, 「동선순」 — or nearest to the one
 * stop there is, `distance`) and best name match (`relevance`). Each gets a heading and a tag; an older server's single list is drawn as one plain list.
 */
function groupsOf(list: AddStopPlace[], t: ReturnType<typeof useT>) {
  const way = list.filter((place) => place.order === "route" || place.order === "distance");
  const names = list.filter((place) => place.order === "relevance");
  if (!way.length && !names.length) return [{ key: "all", title: null, hint: null, tag: null, list }];
  const route = way.some((place) => place.order === "route");
  return [
    ...(way.length ? [{ key: "way", title: route ? t("동선순", "On the way") : t("가까운 순", "Nearest first"),
      hint: route ? t("앞뒤 일정 사이에서 덜 돌아가는 곳부터", "least out of the way between the stops either side") : t("옆 일정에서 가까운 곳부터", "closest to the stop beside it"),
      tag: route ? t("동선순", "On the way") : t("거리순", "Nearest"), list: way }] : []),
    ...(names.length ? [{ key: "names", title: t("이름이 잘 맞는 순", "Best name match"), hint: t("거리와 상관없이 서울 전체에서", "anywhere in Seoul"),
      tag: t("일치도순", "Name match"), list: names }] : []),
  ];
}
