"use client";

import { useEffect, useRef, type KeyboardEvent } from "react";
import type { Translate } from "@/lib/i18n";
import { DrawnCheck, OnboardingIcon } from "./icons";
import styles from "./onboarding.module.css";

/** Interaction-only draft terms; replace the copy with reviewed terms before release. */
const sections = [
  ["이 문서에 대하여", "About this document", "이 문서는 약관 열람과 동의 동작을 확인하기 위한 목업용 예시입니다. 실제 서비스의 확정된 이용약관이나 개인정보 처리방침이 아닙니다. 정식 서비스에 적용하기 전에 운영 주체, 실제 처리 방식과 이용자 권리를 반영한 문서로 교체해야 합니다.", "This is sample content for previewing the reading and consent flow. It is not the final terms of service or privacy policy. Before release, replace it with reviewed documents that describe the operator, actual data practices, and user rights."],
  ["서비스 이용 안내", "Using the service", "triPilot 목업에서는 여행 취향을 선택하고 준비한 여행 계획을 등록하는 흐름을 체험할 수 있습니다. 일정과 장소, 이동 시간 등을 살펴보고 여행 계획을 조정하는 화면을 제공합니다. 화면에 표시되는 결과는 기능 설명을 위한 예시입니다.", "The triPilot prototype lets you explore selecting travel preferences and adding a travel plan. Screens demonstrate reviewing places, travel times, and itinerary changes. Results shown in the prototype illustrate the intended experience."],
  ["여행 정보 확인", "Checking travel information", "여행지의 운영시간, 예약 조건, 교통편과 방문 가능 여부는 달라질 수 있습니다. 실제 예약이나 방문 전에는 해당 시설 또는 제공 업체의 최신 안내를 직접 확인하는 흐름을 전제로 합니다. 목업의 예시 일정은 실제 예약이나 예약 확정을 의미하지 않습니다.", "Opening hours, reservation requirements, transport, and availability can change. Travelers should check current information with the relevant venue or provider before booking or visiting. Sample itineraries do not represent bookings or confirmations."],
  ["입력 항목과 활용", "Information you enter", "이 화면에서는 언어, 여행 테마, 동행 인원, 교통수단, 예산과 여행 일정 등 입력 항목을 보여줍니다. 해당 정보는 사용자가 원하는 여행 조건을 이해하고 일정을 구성하는 화면에 활용하는 것으로 표현되어 있습니다. 실제 수집 항목과 처리 목적은 정식 안내에서 명확히 정해야 합니다.", "This preview includes language, travel themes, group size, transport, budget, and itinerary fields. These inputs are presented as context for understanding travel preferences and organizing an itinerary. The actual collection fields and purposes must be specified in the final notice."],
  ["선택 정보", "Optional information", "식사 제한이나 종교 관련 항목은 원하는 경우에만 입력하는 선택 정보로 구성되어 있습니다. 입력하지 않고 건너뛰는 흐름을 제공합니다. 실제 서비스에서 이러한 정보를 처리한다면 그 필요성과 별도 동의 여부를 검토하고 명확하게 안내해야 합니다.", "Food restrictions and religion-related fields are optional in this preview, with a skip option. If the released service processes this information, its necessity and any separate consent requirements must be reviewed and explained clearly."],
  ["보관과 이용자 권리", "Retention and user rights", "이 목업의 온보딩 답변은 현재 페이지의 상태로 유지됩니다. 서비스의 실제 보관 기간, 파기 방법, 열람·수정·삭제 요청 절차와 문의처는 아직 이 예시 문서에 정해져 있지 않습니다. 출시 전 확정된 정책을 구체적으로 안내해야 합니다.", "Onboarding answers in this prototype are held in the current page state. Actual retention periods, deletion practices, access and correction procedures, and contact details are not defined by this sample. The released service must provide its finalized policies."],
  ["동의 전 확인", "Before agreeing", "이 문서의 끝까지 내려오면 아래 동의 체크박스가 활성화됩니다. 체크하면 전체 화면이 닫히고 기존 카드에도 동일한 동의 상태가 표시됩니다. 체크하지 않고 닫을 수도 있으며, 카드에서 동의를 해제하면 다음 단계로 진행할 수 없습니다. 이 동작은 목업에서만 확인하는 예시 동의 절차입니다.", "Reaching the end enables the agreement checkbox below. Checking it closes this view and updates the checkbox on the card. You may close without agreeing. Clearing consent on the card prevents continuing to the next step. This is a demonstration consent flow only."],
] as const;

const requiredConsent = (t: Translate) => t("[필수] 서비스 이용약관 및 개인정보 수집·이용 내용을 확인하고 동의합니다.", "[Required] I have reviewed and agree to the terms of service and the collection and use of personal data.");

export function TermsCardBody({ t, read, agreed, consentMotion, onReadTerms, onAgree, onContinue }: {
  t: Translate; read: boolean; agreed: boolean; consentMotion: boolean;
  onReadTerms: () => void; onAgree: (checked: boolean) => void; onContinue: () => void;
}) {
  return <>
    <p className={styles.termsIntro}>{t("여행을 시작하기 전에", "Before we begin")}</p>
    <button type="button" className={styles.termsSummary} data-action="read-terms" aria-haspopup="dialog" onClick={onReadTerms}>
      <strong>{t("서비스 이용 및 개인정보 안내", "Service & personal data")}</strong>
      <span>{t("입력한 일정과 취향을 여행 지원에 활용합니다. 종교와 식사 관련 정보는 원하는 경우에만 입력할 수 있습니다.", "Your schedule and preferences are used to support your travel. Religion and food information are optional.")}</span>
      <span className={styles.termsReadLink}>{t("전체 약관 읽기 ↗", "Read full terms ↗")}</span>
    </button>
    <label className={styles.termsCheck}>
      <input type="checkbox" id="terms-check" disabled={!read} checked={agreed} onChange={(event) => onAgree(event.target.checked)} />
      <span className={`${styles.consentMark} ${consentMotion ? styles.completionMotion : ""}`} aria-hidden="true"><DrawnCheck className={styles.drawnCheck} /></span>
      <span>{requiredConsent(t)}</span>
    </label>
    <p className={styles.draftNote}>{t("목업용 약관 요약 · 실제 약관 검토 전", "Draft terms summary for the mockup · not final terms")}</p>
    <button type="button" className={`${styles.next} ${styles.termsContinue}`} disabled={!agreed} onClick={onContinue}>{t("동의하고 다음으로", "Agree and continue")}<OnboardingIcon name="arrow" size={15} /></button>
  </>;
}

export function TermsReader({ t, read, agreed, onRead, onAgree, onClose }: {
  t: Translate; read: boolean; agreed: boolean; onRead: () => void; onAgree: (checked: boolean) => void; onClose: () => void;
}) {
  const scroller = useRef<HTMLElement>(null);

  useEffect(() => { scroller.current?.focus(); }, []);
  useEffect(() => {
    const element = scroller.current;
    if (!element) return;
    const checkEnd = () => { if (element.clientHeight > 0 && element.scrollHeight - element.scrollTop - element.clientHeight <= 3) onRead(); };
    const observer = new ResizeObserver(checkEnd);
    observer.observe(element);
    element.addEventListener("scroll", checkEnd, { passive: true });
    const frame = requestAnimationFrame(checkEnd);
    return () => { observer.disconnect(); element.removeEventListener("scroll", checkEnd); cancelAnimationFrame(frame); };
  }, [onRead]);

  function escape(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { event.stopPropagation(); onClose(); }
  }

  return <div className={styles.termsDialog} role="dialog" aria-modal="true" aria-labelledby="terms-full-title" onKeyDown={escape}>
    <header className={styles.termsHeader}>
      <div><small>{t("목업용 예시 · 확정 전", "PROTOTYPE · DRAFT")}</small><h2 id="terms-full-title">{t("서비스 이용 및 개인정보 안내", "Service & personal data")}</h2></div>
      <button type="button" className={styles.termsClose} aria-label={t("약관 닫기", "Close terms")} onClick={onClose}>×</button>
    </header>
    <article ref={scroller} className={styles.termsScroll} tabIndex={0} aria-label={t("약관 전체 내용", "Full terms")}>
      {sections.map((section, index) => <section key={section[0]}><h3>{index + 1}. {t(section[0], section[1])}</h3><p>{t(section[2], section[3])}</p></section>)}
      <p className={styles.termsEnd}>{t("약관 내용의 끝입니다.", "You have reached the end of the terms.")}</p>
    </article>
    <footer className={styles.termsFooter}>
      <p id="terms-read-hint" role="status">{read ? t("내용을 확인했어요. 동의 여부를 선택해 주세요.", "You have reached the end. You can now choose whether to agree.") : t("약관을 끝까지 내려 읽으면 동의할 수 있어요.", "Scroll to the end of the terms to enable agreement.")}</p>
      <label className={styles.termsCheck}>
        <input type="checkbox" id="terms-full-check" disabled={!read} checked={agreed} onChange={(event) => onAgree(event.target.checked)} />
        <span className={styles.consentMark} aria-hidden="true"><DrawnCheck className={styles.drawnCheck} /></span>
        <span>{requiredConsent(t)}</span>
      </label>
    </footer>
  </div>;
}
