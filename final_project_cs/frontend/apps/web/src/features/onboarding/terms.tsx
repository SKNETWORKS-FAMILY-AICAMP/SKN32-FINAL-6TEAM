"use client";

import { useEffect, useRef, type KeyboardEvent } from "react";
import type { Translate } from "@/lib/i18n";
import { DrawnCheck, OnboardingIcon } from "./icons";
import styles from "./onboarding.module.css";

/**
 * ★`[2026-10-03 사용자 지시]` 이 안내는 **서비스가 실제로 하는 일만** 적는다(서버 문서로 확인한 것: 사용자 키는 해시로만, 디스코드 웹훅은 암호화해 보관,
 *   여행·대화 기록은 서버에 저장). 운영 주체 · 보관 기간 · 삭제·열람 요청 방법 · 문의처는 **아직 정해진 것이 없어** 지어내지 않고 「정해지는 대로
 *   적는다」고 말한다. 법무 검토를 거친 약관 전문은 팀이 확정해 이 목록을 바꾼다.
 */
const sections = [
  ["이 안내에 대하여", "About this notice", "이 안내는 triPilot이 입력하신 여행 계획과 취향을 어떻게 다루는지 알려 드려요. 운영 주체, 보관 기간, 이용자 권리와 문의처처럼 아직 정해지지 않은 내용은 정해지는 대로 이 안내에 적어요.", "This notice explains how triPilot handles the travel plans and preferences you enter. Items that are not decided yet — the operator, retention periods, your rights and contact details — will be added here as soon as they are."],
  ["서비스 이용 안내", "Using the service", "triPilot은 올려 주신 여행 계획을 읽어 일정과 장소, 이동 시간을 확인하고, 등록한 뒤에는 여행이 끝날 때까지 일정을 지켜보며 바뀐 점을 알려 드려요. 일정을 대신 예약하거나 예약을 바꾸거나 취소하지 않고, 결제도 하지 않아요.", "triPilot reads the travel plan you upload, checks its places, times and travel times, and after you register it, watches the plan until the trip ends and tells you what changed. It does not book, change or cancel reservations for you, and it does not take payments."],
  ["여행 정보 확인", "Checking travel information", "운영시간, 휴무일, 이동 시간은 한국관광공사 정보 등 공개된 자료와 지도 서비스에서 가져와 확인해요. 이런 정보는 달라질 수 있으니, 예약이나 방문 전에는 해당 시설이나 업체의 최신 안내를 직접 확인해 주세요. 화면의 예약 표시는 입력하신 내용을 기준으로 해요.", "Opening hours, closing days and travel times are taken from public sources such as Korea Tourism Organization data and from map services. They can change, so please check the venue or provider's latest information before booking or visiting. Booking notes on screen reflect what you entered."],
  ["입력 항목과 활용", "Information you enter", "여행 계획(글이나 파일), 여행 취향 설문, 여행에 대해 묻는 채팅 내용, 그리고 원하시면 디스코드 웹훅 주소를 서버로 보내 일정을 읽고 확인하고 답하는 데 써요. 위치는 「내 위치 알려 주고 다시 묻기」를 누를 때만 브라우저에 물어 그 질문에 답하는 데 써요.", "Your travel plan (text or files), the preference questions, the chat messages you send about your trip and, if you wish, a Discord webhook address are sent to the server to read and check your plan and to answer you. Your location is asked from the browser only when you press “Share my location and ask again”, and is used to answer that question."],
  ["선택 정보", "Optional information", "식사 제한이나 종교 관련 항목, 디스코드 웹훅 주소는 원하시는 경우에만 입력하는 선택 정보예요. 입력하지 않고 건너뛸 수 있고, 건너뛰어도 서비스는 쓸 수 있어요. 다만 그 내용은 일정을 살필 때 반영되지 않아요.", "Food restrictions, religion-related answers and the Discord webhook address are optional; enter them only if you wish. You can skip them and still use the service, but they will not be taken into account when your plan is checked."],
  ["보관과 이용자 권리", "Retention and your rights", "이 브라우저에는 사용자 키와 설문 답변, 화면 설정이 저장돼요. 서버에는 등록한 여행과 대화 기록이 저장되고, 사용자 키는 원문이 아니라 해시로만, 디스코드 웹훅 주소는 암호화해서 보관해요. 보관 기간, 삭제·열람·수정을 요청하는 방법과 문의처는 운영 주체가 정해 이 안내에 적어요.", "This browser keeps your user key, your preference answers and your display settings. The server keeps the trips you register and your chat history; your user key is kept only as a hash and a Discord webhook address is kept encrypted. Retention periods, how to ask for deletion, access or correction, and the contact details will be set by the operator and added here."],
  ["동의 전 확인", "Before agreeing", "이 안내의 끝까지 내려오면 아래 동의 체크박스가 켜져요. 체크하면 전체 화면이 닫히고 카드에도 같은 동의가 표시돼요. 체크하지 않고 닫을 수도 있지만, 동의하지 않으면 다음 단계로 진행할 수 없어요.", "Reaching the end enables the agreement checkbox below. Checking it closes this view and shows the same consent on the card. You may close without agreeing, but you cannot continue to the next step without it."],
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
      <div><small>{t("이용 안내", "NOTICE")}</small><h2 id="terms-full-title">{t("서비스 이용 및 개인정보 안내", "Service & personal data")}</h2></div>
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
