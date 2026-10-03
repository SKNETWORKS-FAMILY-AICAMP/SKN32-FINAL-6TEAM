"use client";

import { useEffect, useRef, useState } from "react";
import { CalendarDays, ChevronDown, MapPin, Maximize2, Search, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui";
import { mapConfiguration } from "@/features/map/config";
import { GoogleMap } from "@/features/map/google-map";
import { MapUnavailable } from "@/features/map/live-map";
import { NaverMap } from "@/features/map/naver-map";
import { OsmMap } from "@/features/map/osm-map";
import type { MapPoint } from "@/features/map/model";
import type { IntakeEdit } from "@/lib/live/intake";
import { useT } from "@/lib/settings";
import { draftOf, editsFor, invalidDraft, mapPoints, overlaps, placeOf, statusOf, type Draft, type ReviewRow } from "./model";
import styles from "./intake-review.module.css";

const icon = { size: 16, strokeWidth: 1.6, "aria-hidden": true } as const;
const ignoreSelection = () => {};

function PlaceMap({ points, selectedId }: { points: MapPoint[]; selectedId: string }) {
  const props = { points, selectedId, onSelect: ignoreSelection };
  const t = useT();
  if (mapConfiguration.provider === "osm") return <OsmMap {...props} tileUrl={mapConfiguration.tileUrl} />;
  if (mapConfiguration.provider === "naver") return <NaverMap {...props} clientId={mapConfiguration.clientId} />;
  if (mapConfiguration.provider === "google") return <GoogleMap {...props} apiKey={mapConfiguration.apiKey} mapId={mapConfiguration.mapId} tileUrl={mapConfiguration.tileUrl} />;
  return <MapUnavailable message={mapConfiguration.provider === "unavailable" ? mapConfiguration.message : t("실제 지도 연결 설정이 필요해요.", "A live map provider needs to be configured.")} />;
}

export function ItemCard({ row, all, open, disabled, revision, onToggle, onCancel, onDirty, onEdit }: {
  row: ReviewRow; all: ReviewRow[]; open: boolean; disabled: boolean; revision: number;
  onToggle: () => void; onCancel: () => void; onDirty: (dirty: boolean) => void; onEdit: (edits: IntakeEdit[], revision: number) => Promise<void>;
}) {
  const t = useT();
  const value = draftOf(row), place = placeOf(row), status = statusOf(row);
  const label = status === "review" ? t("확인 필요", "Needs review") : status === "edited" ? t("수정됨", "Edited") : t("입력 확인", "Read back");
  return <article className={styles.card} data-status={status} data-open={open}>
    <button type="button" className={styles.toggle} aria-expanded={open} aria-controls={`edit-${row.key}`} onClick={onToggle} disabled={disabled}>
      <span className={styles.when}><CalendarDays {...icon} />{value.start || "--:--"}{value.end && `–${value.end}`}</span>
      <span className={styles.nameRow}><span role="heading" aria-level={3}>{value.title || t("이름 없는 일정", "Untitled stop")}</span><span className={styles.category}>{row.item.fields.kind?.value === "dining" ? t("식사", "Dining") : t("일정", "Stop")}</span></span>
      <span className={styles.placeLine}><MapPin {...icon} />{place?.name || (value.noPlace ? t("장소 없음", "No place") : t("장소를 정하지 못했어요", "Place not identified"))}</span>
      <span className={styles.expand}>{open ? t("접기", "Collapse") : t("펼쳐서 고치기", "Expand to edit")}<ChevronDown {...icon} /></span>
    </button>
    <span className={styles.statusBadge}>{label}</span>
    {open && <ItemEditor key={row.key} row={row} all={all} revision={revision} disabled={disabled} onCancel={onCancel} onDirty={onDirty} onEdit={onEdit} />}
  </article>;
}

function ItemEditor({ row, all, revision, disabled, onCancel, onDirty, onEdit }: {
  row: ReviewRow; all: ReviewRow[]; revision: number; disabled: boolean; onCancel: () => void;
  onDirty: (dirty: boolean) => void; onEdit: (edits: IntakeEdit[], revision: number) => Promise<void>;
}) {
  const t = useT();
  // Keep the revision from when editing began. A refreshed response must never silently rebase an unsaved edit.
  const [base] = useState(() => ({ row, revision }));
  const [draft, setDraft] = useState(() => draftOf(row));
  const [error, setError] = useState<string | null>(null);
  const [showMap, setShowMap] = useState(false);
  const [lookup, setLookup] = useState(draft.place);
  const [remove, setRemove] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const lookupInput = useRef<HTMLInputElement>(null);
  const edits = editsFor(base.row, draft);
  const dirty = edits.length > 0;
  const invalid = invalidDraft(draft);
  const conflicts = overlaps(row, draft, all);
  const stale = revision !== base.revision;
  const points = mapPoints(all.filter((other) => draftOf(other).date === draftOf(row).date));
  const ownPoints = points.filter((point) => point.id === row.key);
  const original = row.source.lines.find((line) => line.no === row.item.line)?.text;
  const source = row.item.fields.place?.evidence.source;
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  useEffect(() => {
    if (showMap) { dialog.current?.showModal(); lookupInput.current?.focus({ preventScroll: true }); }
  }, [showMap]);

  async function save(nextDraft: Draft = draft) {
    const values = editsFor(base.row, nextDraft);
    if (!values.length || invalidDraft(nextDraft) || stale || disabled) return;
    setError(null);
    try { await onEdit(values, base.revision); }
    catch (reason) { setError(reason instanceof Error ? reason.message : t("저장하지 못했어요.", "Could not save.")); }
  }
  const errorText = invalid === "order" ? t("끝 시각은 시작 시각보다 늦어야 해요.", "The end time must be after the start.")
    : invalid ? t("일정 이름·날짜·시간·장소 입력을 확인해 주세요.", "Check the title, date, time and place.") : null;
  return <div className={styles.editor} id={`edit-${row.key}`}>
    <div className={styles.editorTitle}><strong>{t("일정 고치기", "Edit stop")}</strong><Button variant="quiet" disabled={disabled || stale} onClick={() => setRemove(true)}><Trash2 {...icon} />{t("삭제", "Remove")}</Button></div>
    {remove && <div className={styles.overlap} role="alert"><p>{t("이 일정을 계획에서 뺄까요?", "Remove this stop from the plan?")}</p><div className={styles.saveRow}><Button disabled={disabled} onClick={() => setRemove(false)}>{t("유지하기", "Keep stop")}</Button><Button variant="danger" disabled={disabled || stale} onClick={() => { setError(null); void onEdit([{ source_id: row.source.source_id, field: `items[${row.item.index}].removed`, value: true }], base.revision).catch((reason: Error) => setError(reason.message)); }}>{t("일정 삭제", "Remove stop")}</Button></div></div>}
    {row.problems.length > 0 && <ul className={styles.itemProblems}>{row.problems.map((problem, index) => <li key={`${problem.field}:${problem.code}:${index}`}>{problem.message}</li>)}</ul>}
    <label className={styles.field}>{t("일정 이름", "Stop title")}<input value={draft.title} maxLength={80} disabled={disabled || stale} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
    <div className={styles.blockLabel}><MapPin {...icon} />{t("장소", "Place")}</div>
    <div className={styles.miniMap}>
      {ownPoints.length ? <PlaceMap points={ownPoints} selectedId={row.key} /> : <p className={styles.mapPlaceholder}>{t("장소가 확인되면 지도에 표시돼요.", "The map appears once the place is identified.")}</p>}
      <Button className={styles.mapButton} onClick={() => { setLookup(draft.place); setShowMap(true); }} aria-label={t("지도 크게 보기", "Expand map")}><Maximize2 {...icon} /></Button>
    </div>
    <div className={styles.chosen}><MapPin {...icon} /><div><strong>{placeOf(row)?.name || (draftOf(row).noPlace ? t("장소 없음", "No place") : t("아직 정하지 못했어요", "Not identified yet"))}</strong><span>{row.item.fields.place?.note || t("저장할 때 장소 이름을 조회해요.", "We look up the place name when you save.")}</span></div></div>
    <Button className={styles.searchEntry} disabled={disabled || stale} onClick={() => { setLookup(draft.place); setShowMap(true); }}><Search {...icon} />{t("업체 이름으로 찾기", "Find by place name")}</Button>
    <label className={styles.field}>{t("장소 이름", "Place name")}<input placeholder={t("다른 장소로 고치기", "Change place")} value={draft.place} maxLength={80} disabled={disabled || stale || draft.noPlace} onChange={(event) => setDraft({ ...draft, place: event.target.value })} /></label>
    <label className={styles.noPlace}><input type="checkbox" checked={draft.noPlace} disabled={disabled || stale} onChange={(event) => setDraft({ ...draft, noPlace: event.target.checked })} />{t("장소 없음으로 두기", "Leave without a place")}</label>
    <p className={styles.note}>{t("정확한 장소·지점 이름을 적어 주세요. 저장하면 조회한 장소 한 곳으로 반영해요.", "Enter the exact place or branch name. Saving applies the one place found.")}</p>
    <div className={styles.blockLabel}><CalendarDays {...icon} />{t("방문 날짜·시간", "Visit date & time")}</div>
    <div className={styles.timeRow}>{([["date", "date", t("방문 날짜", "Visit date")], ["start", "time", t("시작", "Start")], ["end", "time", t("끝", "End")]] as const).map(([name, type, label]) => <label key={name}>{label}<input type={type} value={draft[name]} disabled={disabled || stale} aria-invalid={name === "end" && invalid === "order"} onChange={(event) => setDraft({ ...draft, [name]: event.target.value })} /></label>)}</div>
    {errorText && <p className={styles.fieldError} role="alert">{errorText}</p>}
    {conflicts.length > 0 && <div className={styles.overlap}><strong>{t("겹치는 일정이 있습니다", "These stops overlap")}</strong><ul>{conflicts.map((other) => <li key={other.key}>{draftOf(other).start}–{draftOf(other).end} · {draftOf(other).title}</li>)}</ul><p>{t("입력한 시간 기준이에요. 최종 등록 가능 여부는 저장 후 다시 확인해요.", "Based on entered times. Registration requirements are checked again after saving.")}</p></div>}
    {original && <details className={styles.original}><summary>{t("원문과 읽은 근거", "Original & evidence")}</summary><p>{original}</p>{source && <p>{t("장소 출처", "Place source")}: {source}</p>}
      {row.item.fields.booking_no?.value != null && <p>{t("예약번호", "Booking number")}: {String(row.item.fields.booking_no.value)}</p>}
    </details>}
    {stale && <p className={styles.fieldError} role="alert">{t("다른 화면에서 계획이 바뀌었어요. 입력은 보관했어요. 취소 후 최신 일정에서 다시 고쳐 주세요.", "The plan changed elsewhere. Your input is kept here. Cancel and reopen the latest stop before editing.")}</p>}
    {error && <p className={styles.fieldError} role="alert">{error}</p>}
    <div className={styles.saveRow}><Button disabled={disabled} onClick={onCancel}>{t("취소", "Cancel")}</Button><Button variant="primary" disabled={disabled || stale || !dirty || Boolean(invalid)} onClick={() => void save()}>{disabled ? t("저장하는 중…", "Saving…") : t("저장하고 확인", "Save & check")}</Button></div>
    {showMap && <dialog ref={dialog} className={styles.mapDialog} aria-label={t("장소 찾기 지도", "Find a place on the map")} onCancel={(event) => { event.preventDefault(); if (!disabled) setShowMap(false); }}>
      <div className={styles.dialogMap}><PlaceMap points={points} selectedId={row.key} /></div>
      <Button className={styles.closeMap} aria-label={t("일정 카드로 돌아가기", "Back to stop")} disabled={disabled} onClick={() => setShowMap(false)}><X {...icon} /></Button>
      <form className={styles.mapSearch} onSubmit={(event) => { event.preventDefault(); if (lookup.trim()) void save({ ...draft, place: lookup.trim(), noPlace: false }); }}>
        <label className={styles.field}>{t("장소·업체 검색", "Find a place or business")}<input ref={lookupInput} value={lookup} maxLength={80} placeholder={t("예: 경복궁", "e.g. Gyeongbokgung")} disabled={disabled || stale} onChange={(event) => setLookup(event.target.value)} /></label>
        <p className={styles.note}>{t("찾은 장소와 카드에서 고친 내용을 함께 저장해요. 후보 목록·주변 추천은 아직 제공하지 않아요.", "Saves the matched place and your other card edits together. Multiple results and nearby recommendations are not available yet.")}</p>
        {error && <p role="alert" className={styles.fieldError}>{error}</p>}
        {errorText && <p role="alert" className={styles.fieldError}>{errorText}</p>}
        <Button type="submit" variant="primary" disabled={disabled || stale || !lookup.trim() || Boolean(invalid) || !editsFor(base.row, { ...draft, place: lookup.trim(), noPlace: false }).length}>{disabled ? t("찾고 저장하는 중…", "Finding & saving…") : t("찾아서 저장", "Find & save")}</Button>
      </form>
    </dialog>}
  </div>;
}
