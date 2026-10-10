"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useT } from "@/lib/settings";
import { reason } from "./parts";
import type { AddStopPlace, NewStop } from "./new-stop";
import { PlaceSearch } from "./place-search";
import styles from "./add-stop.module.css";
import type { Coordinates } from "@/features/map/model";

export type { AddStopPlace, NewStop } from "./new-stop";
type Field = "title" | "date" | "start" | "end" | "place";

/** 선택한 경계 바로 아래에 연다. 저장 전 검색·취소는 계획을 바꾸지 않는다. */
export function AddStop({ date, blocked, initial, onSave, onCancel, search, onBusy, mapPicker }: {
  mapPicker?: { active: boolean; value: Coordinates | null; onStart: () => void; onClose: () => void };
  date: string; blocked: string | null; initial?: { start: string; end: string };
  onSave: (draft: NewStop) => Promise<void>; onCancel?: () => void;
  search?: (query: string) => Promise<AddStopPlace[]>;
  onBusy?: (busy: boolean) => void;
}) {
  const t = useT();
  const id = useId();
  const box = useRef<HTMLDetailsElement>(null);
  const form = useRef<HTMLFormElement>(null);
  const first = useRef<HTMLInputElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [mapName, setMapName] = useState("");
  const mapStart = useRef<HTMLButtonElement>(null);
  const mapHeading = useRef<HTMLHeadingElement>(null);
  const [draft, setDraft] = useState<NewStop>({ title: "", date, start: initial?.start ?? "", end: initial?.end ?? "", place: "", kind: "activity" });
  const [selected, setSelected] = useState<AddStopPlace | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  const mapActive = mapPicker?.active, endMapPick = mapPicker?.onClose;
  useEffect(() => {
    if (!mapActive) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      event.preventDefault(); endMapPick?.(); requestAnimationFrame(() => mapStart.current?.focus());
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [mapActive, endMapPick]);
  const inline = !!onCancel;
  useEffect(() => { if (!mapPicker?.active && inline && (!search || selected)) first.current?.focus({ preventScroll: true }); }, [inline, search, selected, mapPicker?.active]);
  useEffect(() => { onBusy?.(busy); }, [busy, onBusy]);
  useEffect(() => { if (mapPicker?.active) mapHeading.current?.focus({ preventScroll: true }); }, [mapPicker?.active]);
  const clear = (key: Field) => { setErrors((old) => ({ ...old, [key]: undefined })); setProblem(""); };
  function errorOf(key: Field): string | undefined {
    if (key === "title" && !draft.title.trim()) return t("일정 이름을 입력해 주세요.", "Enter a stop name.");
    if (key === "date" && !draft.date) return t("날짜를 입력해 주세요.", "Enter a date.");
    if (key === "start" && !draft.start) return t("시작 시각을 입력해 주세요.", "Enter the start time.");
    if (key === "end" && !draft.end) return t("끝 시각을 입력해 주세요.", "Enter the end time.");
    if (key === "end" && draft.start >= draft.end) return t("끝 시각은 시작보다 뒤로 입력해 주세요.", "The end must be after the start.");
    if (key === "place" && search && !draft.pickedPlace) return t("검색하거나 지도에서 장소를 선택해 주세요.", "Choose a place from search or the map.");
    if (key === "place" && !search && !draft.place.trim()) return t("장소 이름을 입력해 주세요.", "Enter a place name.");
  }
  const blur = (key: Field) => setErrors((old) => ({ ...old, [key]: errorOf(key) }));
  const change = (key: Field, value: string) => { if (!busy) { setDraft((current) => ({ ...current, [key]: value })); clear(key); } };
  function pick(place: AddStopPlace | null) {
    if (busy) return;
    setSelected(place);
    setDraft((current) => ({ ...current, place: place?.name ?? "", pickedPlace: place?.pickedPlace ?? undefined,
      title: !current.title.trim() || current.title === selected?.name ? place?.name ?? "" : current.title,
      kind: place?.placeKind === "dining" || place?.placeKind === "activity" ? place.placeKind : current.kind,
    }));
    clear("place");
  }
  function cancel() {
    if (busy) return;
    if (onCancel) onCancel();
    else if (box.current) { box.current.open = false; box.current.querySelector("summary")?.focus(); }
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (blocked) { setProblem(blocked); return; }
    const fields: Field[] = ["title", "date", "start", "end", "place"];
    const next = Object.fromEntries(fields.map((key) => [key, errorOf(key)]));
    setErrors(next);
    const invalid = fields.find((key) => next[key]);
    if (invalid) { if (invalid === "place" && search) searchInput.current?.focus(); else form.current?.querySelector<HTMLInputElement>('[name="' + invalid + '"]')?.focus(); return; }
    setBusy(true); setProblem("");
    try {
      await onSave({ ...draft, title: draft.title.trim(), place: draft.pickedPlace?.name ?? draft.place.trim() });
      if (onCancel) onCancel();
      else {
        setDraft({ title: "", date: draft.date, start: "", end: "", place: "", kind: "activity" });
        setSelected(null);
        if (box.current) { box.current.open = false; box.current.querySelector("summary")?.focus(); }
      }
    } catch (error) { setProblem(reason(error)); }
    finally { setBusy(false); }
  }
  const field = (key: Field, label: string, type = "text") => <div className={styles.field}>
    <label htmlFor={`${id}-${key}`}>{label}</label><input id={`${id}-${key}`} aria-describedby={errors[key] ? `${id}-${key}-error` : undefined} ref={key === "title" ? first : undefined} name={key} type={type} required readOnly={busy}
      value={draft[key]} maxLength={key === "title" ? 200 : undefined} aria-invalid={!!errors[key]}
      onFocus={() => clear(key)} onBlur={() => blur(key)} onChange={(event) => change(key, event.target.value)} />
    {errors[key] && <span id={`${id}-${key}-error`} className={styles.error}>{errors[key]}</span>}
  </div>;
  const startMap = () => { searchInput.current?.blur(); setMapName(query.trim().slice(0,80) || selected?.name || draft.title.slice(0,80)); mapPicker?.onStart(); };
  const closeMap = () => { mapPicker?.onClose(); requestAnimationFrame(() => mapStart.current?.focus()); };
  const at = mapPicker?.value;
  // cs 프로젝트 서버의 고객 선택 좌표 계약과 동일한 서울 범위다.
  const inSeoul = !!at && Number.isFinite(at.lat) && Number.isFinite(at.lng) && at.lat>=37.4 && at.lat<=37.72 && at.lng>=126.7 && at.lng<=127.3;
  const placeSearch = search && <PlaceSearch query={query} onQuery={setQuery} inputRef={searchInput} search={search} value={selected} onPick={pick} error={errors.place} onBlur={() => blur("place")} onFocus={() => clear("place")} busy={busy} onCancel={onCancel ? cancel : undefined} />;
  const mapStartButton = mapPicker && <button ref={mapStart} type="button" className={styles.mapPickStart} disabled={busy} onClick={startMap}>{t("지도에서 위치 지정", "Choose a location on the map")}</button>;
  if (mapPicker?.active) return <section className={`${styles.screen} ${styles.mapPicker}`} aria-label={t("지도에서 위치 지정", "Choose a location on the map")} onKeyDown={event => { if (event.key==="Escape") { event.preventDefault(); closeMap(); } }}>
    <h3 ref={mapHeading} tabIndex={-1}>{t("지도에서 위치 지정", "Choose a location on the map")}</h3>
    <p>{t("지도를 눌러 위치를 찍어 주세요. 확대하거나 이동해 다시 찍을 수 있어요.", "Tap the map to pick a location. Zoom or move to pick again.")}</p>
    <label htmlFor={`${id}-map-name`}>{t("장소 이름", "Place name")}</label>
    <input id={`${id}-map-name`} value={mapName} maxLength={80} onChange={event => setMapName(event.target.value)} />
    <p role="status">{at ? `${at.lat.toFixed(6)}, ${at.lng.toFixed(6)}${inSeoul ? "" : t(" · 서울 안에서 선택해 주세요.", " · Choose a location in Seoul.")}` : t("아직 위치를 찍지 않았어요.", "No location selected yet.")}</p>
    <div className={styles.actions}><button type="button" onClick={closeMap}>{t("취소", "Cancel")}</button><button type="button" disabled={!inSeoul || !mapName.trim()} onClick={() => {
      if (!at || !inSeoul || !mapName.trim()) return;
      const name = mapName.trim();
      pick({ id: "map-picked", name, source: "search", rank: null, distance: null, coordinates: at, info: null, checks: [], pickedPlace: { name, latitude: at.lat, longitude: at.lng, source: "map" } });
      mapPicker.onClose();
    }}>{t("이 위치 사용", "Use this location")}</button></div>
  </section>;
  const content = <>{onCancel && <div className={styles.searchBody} data-searching={!!query.trim() && !selected || undefined} data-selected={!!selected || undefined}>{placeSearch}{mapStartButton}</div>}
    {(!onCancel || !search || selected || !query.trim()) && <form ref={form} className={styles.form} onSubmit={save} noValidate aria-label={t("일정 추가", "Add a stop")}
    onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); cancel(); } }}>
    <h3>{t("일정 추가", "Add a stop")}</h3>
    {onCancel && search && !selected && <p className={styles.hint}>{t("장소는 위 검색창에서 골라 주세요.", "Choose a place using the search above.")}</p>}
    {field("title", t("일정 이름", "Stop name"))}
    {field("date", t("날짜", "Date"), "date")}
    <div className={styles.times}>{field("start", t("시작", "Start"), "time")}{field("end", t("끝", "End"), "time")}</div>
    {!onCancel && search ? <>{placeSearch}{mapStartButton}</> : !search ? <>{field("place", t("장소 이름", "Place name"))}<p className={styles.hint}>{t("빈 계획에서는 장소 검색을 연결할 기준 일정이 없어 이름으로 찾아 추가해요.", "This empty plan has no reference stop for search. The place will be looked up by name.")}</p></> : null}
    <label className={styles.field}>{t("일정 종류", "Type")}<select value={draft.kind} aria-disabled={busy}
      onChange={(event) => { if (!busy) { setDraft((current) => ({ ...current, kind: event.target.value as NewStop["kind"] })); setProblem(""); } }}>
      <option value="activity">{t("활동", "Activity")}</option><option value="dining">{t("식사", "Meal")}</option>
    </select></label>
    <p className={styles.hint}>{t("추가할 때 앞뒤 이동시간을 다시 확인해 일정에 넣어요.", "Travel times are rechecked when this stop is added.")}</p>
    {problem && <p className={styles.error} role="alert">{problem}</p>}
    <div className={styles.actions}><button type="button" aria-disabled={busy} onClick={cancel}>{t("취소", "Cancel")}</button>
      <button type="submit" aria-busy={busy}>{busy ? t("추가 중…", "Adding…") : t("일정에 추가", "Add to plan")}</button></div>
  </form>}</>;
  return onCancel ? <section className={styles.screen} aria-label={t("일정 추가 화면", "Add a stop screen")}>{content}</section>
    : <details ref={box} className={styles.box} onToggle={(event) => { if (event.currentTarget.open) first.current?.focus({ preventScroll: true }); }}>
      <summary>{t("+ 일정 추가", "+ Add a stop")}</summary>{content}
    </details>;
}
