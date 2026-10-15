"use client";

import { useId, useState, type FormEvent } from "react";
import type { Translate } from "@/lib/i18n";
import type { DiningLink, DiningLinkPatch, DiningPreview } from "@/lib/live/social-dining";
import { safeSourceUrl } from "./model";
import { diningReason, diningStatus } from "./text";
import styles from "./social-dining.module.css";

type Update = (key: string, patch: DiningLinkPatch) => Promise<boolean>;
export function DiningCards({ links, busy, t, onUpdate }: { links: DiningLink[]; busy: boolean; t: Translate; onUpdate: Update }) {
  return <ul className={styles.cards} aria-label={t("보관한 맛집 링크", "Saved restaurant links")}>{links.map((link) => <DiningCard key={link.key} link={link} busy={busy} t={t} onUpdate={onUpdate} />)}</ul>;
}
function DiningCard({ link, busy, t, onUpdate }: { link: DiningLink; busy: boolean; t: Translate; onUpdate: Update }) {
  const id = useId();
  const [name, setName] = useState("");
  const [area, setArea] = useState("");
  const restaurant = link.restaurants[link.restaurant_index ?? 0];
  const menus = typeof restaurant?.menu === "string" ? [restaurant.menu] : (restaurant?.menu ?? []);
  function supplement(event: FormEvent) { event.preventDefault(); if (!busy && (name.trim() || area.trim())) void onUpdate(link.key, { ...(name.trim() ? { name: name.trim() } : {}), ...(area.trim() ? { area: area.trim() } : {}) }); }
  return <li className={styles.card}>
    <div className={styles.cardHead}><strong>{restaurant?.name || t("식당 정보 확인", "Restaurant details")}</strong><span>{diningStatus(link.status, t)}</span></div>
    {link.reason && <p className={styles.note}>{diningReason(link.reason, t)}</p>}
    <p className={styles.placement}>{link.placement_status === "applied" ? t("이 확인 중인 일정에 넣었어요 · 여행 저장은 완료 버튼에서 해 주세요.", "Added to the plan being checked · save the trip with Done.") : link.placement_status === "unplaced" && link.placement_reason !== link.reason ? diningReason(link.placement_reason, t) : t("일정에는 아직 넣지 않았어요", "Not added to the itinerary yet")}</p>
    <label className={styles.field} htmlFor={`${id}-priority`}>{t("가고 싶은 정도", "Your preference")}
      <select id={`${id}-priority`} value={link.priority} disabled={busy} onChange={(event) => void onUpdate(link.key, { priority: event.target.value as DiningLink["priority"] })}>
        <option value="if_fits">{t("동선이 맞으면 가고 싶어요", "Visit if it fits")}</option><option value="must">{t("꼭 가고 싶어요", "Must go")}</option>
      </select></label>
    {link.restaurants.length > 1 && <label className={styles.field} htmlFor={`${id}-restaurant`}>{t("게시물에서 원하는 식당", "Restaurant from the post")}
      <select id={`${id}-restaurant`} value={link.restaurant_index ?? ""} disabled={busy} onChange={(event) => { if (event.target.value !== "") void onUpdate(link.key, { restaurant_index: Number(event.target.value) }); }}>
        <option value="">{t("식당을 골라 주세요", "Choose a restaurant")}</option>{link.restaurants.map((item, index) => <option key={index} value={index}>{[item.name, item.branch, item.area].filter(Boolean).join(" · ")}</option>)}
      </select></label>}
    {restaurant && <div className={styles.note}>
      {[restaurant.area, restaurant.branch].filter(Boolean).join(" · ") && <p>{[restaurant.area, restaurant.branch].filter(Boolean).join(" · ")}</p>}
      {!!menus.length && <p>{t("게시물의 메뉴", "Menu in the post")} · {menus.join(", ")}</p>}
      {!!restaurant.evidence?.length && <details><summary>{t("식당을 읽은 근거", "Source details")}</summary>{restaurant.evidence.map((item, index) => <p key={index}>
        「{item.quote}」 · {item.source === "customer_note" ? t("내가 남긴 메모", "Your note") : t("게시물 내용", "Post text")}
      </p>)}</details>}
    </div>}
    {!!link.choices?.length && <fieldset className={styles.choices} disabled={busy}><legend>{t("실제로 방문할 지점", "Branch to visit")}</legend>
      {link.choices.map((choice) => <label key={choice.ref}><input type="radio" name={`${id}-branch`} checked={link.selected_ref === choice.ref} onChange={() => void onUpdate(link.key, { selected_ref: choice.ref })} />
        <span><strong>{choice.name}</strong>{choice.address && <small>{choice.address}</small>}{choice.checks?.filter((check) => check.text).map((check, index) => <small key={index}>{check.text}</small>)}</span></label>)}
    </fieldset>}
    <details className={styles.supplement}><summary>{t("식당명·지역 보완", "Add restaurant details")}</summary>
      <form onSubmit={supplement} className={styles.stack}>
        <label className={styles.field} htmlFor={`${id}-name`}>{t("식당 이름", "Restaurant name")}<input id={`${id}-name`} value={name} onChange={(event) => setName(event.target.value)} disabled={busy} /></label>
        <label className={styles.field} htmlFor={`${id}-area`}>{t("지역 또는 지점", "Area or branch")}<input id={`${id}-area`} value={area} onChange={(event) => setArea(event.target.value)} disabled={busy} /></label>
        <button className={styles.button} type="submit" disabled={busy || (!name.trim() && !area.trim())}>{t("보완해서 다시 확인", "Save details and check again")}</button>
      </form>
    </details>
    <div className={styles.sources}><span>{link.platform}</span>{link.checked_at && <span>{t("확인 시각", "Checked")} · <time dateTime={link.checked_at}>{link.checked_at}</time></span>}
      {link.source_urls.map((url, index) => { const safe = safeSourceUrl(url); return safe ? <a key={`${index}:${url}`} href={safe} target="_blank" rel="noopener noreferrer">{t(`원본 링크 ${index + 1}`, `Source link ${index + 1}`)}</a> : <span key={index}>{t("원본 주소를 열 수 없어요", "This source address cannot be opened")}</span>; })}</div>
  </li>;
}

export function DiningProposal({ proposal, busy, t, onApply }: { proposal: DiningPreview; busy: boolean; t: Translate; onApply: () => void }) {
  return <section className={styles.proposal} aria-label={t("맛집 반영안", "Restaurant proposal")}>
    <h3>{t("이렇게 바꿀 수 있어요", "Proposed meal changes")}</h3>
    <p className={styles.note}>{t("아래 변경안을 적용하기 전까지 일정은 그대로예요.", "Your itinerary stays as it is until you apply the changes below.")}</p>
    {proposal.planning && (proposal.planning.mode === "partial" || proposal.planning.omissions.length > 0 || proposal.planning.messages.length > 0) && <p className={styles.unplaced} role="status">{t(proposal.planning.messages.join("\n") || "일부 후보의 배치를 확인하지 못했어요. 미반영 이유도 확인해 주세요.", "Some placement details could not be checked. Review the proposed changes and the restaurants left out.")}</p>}
    {!!proposal.changes.length && <ul className={styles.changes}>{proposal.changes.map((change) => <li key={`${change.key}:${change.item_id}`}><span>{change.from?.name || t("식당 없는 식사", "Meal without a restaurant")} → <strong>{change.to.name}</strong></span>{change.to.address && <small>{change.to.address}</small>}</li>)}</ul>}
    {!!proposal.unplaced.length && <div className={styles.unplaced}><h4>{t("이번에 넣지 못한 식당", "Restaurants left out")}</h4><ul>{proposal.unplaced.map((item) => <li key={item.key}><strong>{item.name || t("식당 후보", "Restaurant candidate")}</strong>{item.priority === "must" && item.reason !== "already_scheduled" && <b className={styles.must}>{t("꼭 가기 미충족", "Must-go not met")}</b>}<p>{item.message ? t(item.message, diningReason(item.reason, t)) : diningReason(item.reason, t)}</p></li>)}</ul></div>}
    <button type="button" className={styles.primary} disabled={busy || !proposal.changes.length} onClick={onApply}>{t("이 변경안 적용", "Apply these changes")}</button>
  </section>;
}
