"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { ButtonLink } from "@/components/ui";
import { routes } from "@/lib/routes";
import type { Translate } from "@/lib/i18n";
import { useSettings, useT } from "@/lib/settings";
import { noticeBoard, type BoardNotice } from "./client";
import { kindOf, NOTICE_REFRESH_MS } from "./service-notices";
import styles from "./support.module.css";

/**
 * `[2026-10-17 사용자 결정 — ST4F-604]` 한 쪽 10줄. 최신 기종 중 보이는 높이가 가장 작은 아이폰 16 · 17(iOS 26 Safari 약 700)과 갤럭시 S25 · S26 기본형(크롬 약 704 추정)에서도
 *   쪽 단추까지 한 화면에 든다(제목 아래 끝 131px + 칸 459px + 쪽 단추). 토스 공지사항도 한 쪽 10개다. 칸 높이는 이 줄 수에 맞춰 고정한다(`.noticeBox`).
 */
const NOTICES_PER_PAGE = 10;

/** The board, read every 15 seconds like the banner and again when the tab comes back — a notice posted or ended shows without a reload. */
function useNoticeBoard() {
  const { language } = useSettings();
  return useQuery({ queryKey: ["service-notice-board", language], queryFn: () => noticeBoard(language), refetchInterval: NOTICE_REFRESH_MS, refetchOnWindowFocus: true });
}

const titleOf = (notice: BoardNotice, language: string) => language === "en" && notice.titleEn ? notice.titleEn : notice.title;
/** `2026-10-17T14:00` (Korean time, as the admin app writes it) → 「10.17」, the date at the end of an inquiry's line. */
const dayOf = (value: string) => /^\d{4}-\d{2}-\d{2}/.test(value) ? `${Number(value.slice(5, 7))}.${Number(value.slice(8, 10))}` : "";
/** → 「10.17 14:00」 */
const timeOf = (value: string) => /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value) ? `${dayOf(value)} ${value.slice(11, 16)}` : "";

/** 「게시 중」 (the inquiries' 「답변 완료」 look) or 「종료」 (the 「문의 중」 look) — before the title. */
const StatusTag = ({ notice, t }: { notice: BoardNotice; t: Translate }) =>
  <span className={styles.status} data-notice-status={notice.status} data-posted={notice.status === "posted" || undefined}>{notice.status === "posted" ? t("게시 중", "Posted") : t("종료", "Ended")}</span>;

/**
 * `[2026-10-17 사용자 결정 — ST4F-604 · 목업 A안]` 공지사항 (`/notices`, 메뉴 「공지사항」) — the operator's notices that have been posted, in the inquiries' box:
 * one line each (게시 중 / 종료 · title · the day it was posted), posted ones first, then the ended ones, each newest first (the server's order), ten to a page with the
 * inquiries' page buttons always under it. A line opens the notice on its own page (`NoticePage`). Mockup: `mockups/tripilot-notice-board.html`.
 */
export function NoticeBoard() {
  const t = useT();
  const { language } = useSettings();
  const board = useNoticeBoard();
  const [page, setPage] = useState(1);
  const all = board.data ?? [];
  const pages = Math.max(1, Math.ceil(all.length / NOTICES_PER_PAGE));
  const current = Math.min(page, pages);                                   // a refresh may leave fewer pages than the one open
  const shown = all.slice((current - 1) * NOTICES_PER_PAGE, current * NOTICES_PER_PAGE);
  return <div className={styles.page}>
    <div className={styles.row}><h1>{t("공지사항", "Notices")}</h1></div>
    <section className={styles.section} aria-label={t("공지 목록", "Notice list")}>
      <div className={`${styles.box} ${styles.noticeBox}`} data-notice-box>
        {board.isPending && <p role="status" className={styles.muted}>{t("공지를 불러오고 있어요.", "Loading the notices.")}</p>}
        {board.error && <p role="alert" className={styles.error}>{t("공지를 불러오지 못했어요. 잠시 뒤 다시 열어 주세요.", "Could not load the notices. Please open this again in a moment.")} {board.error.message}</p>}
        {board.data === null && <p className={styles.muted}>{t("공지 목록은 아직 준비 중이에요.", "The notice list is not available yet.")}</p>}
        {board.data?.length === 0 && <p className={styles.muted}>{t("아직 올라온 공지가 없어요.", "No notices yet.")}</p>}
        {shown.length > 0 && <ul className={styles.list}>{shown.map((notice) => <li key={notice.id}>
          <Link href={routes.notice(notice.id)} className={styles.inquiry} data-notice={notice.id}>
            <StatusTag notice={notice} t={t} />
            <span className={styles.inquiryTitle}>{titleOf(notice, language)}</span>
            <time className={styles.inquiryDate} dateTime={notice.startsAt}>{dayOf(notice.startsAt)}</time>
          </Link>
        </li>)}</ul>}
      </div>
      <nav className={styles.pager} aria-label={t("공지 페이지 이동", "Notice pages")}>
        <button type="button" aria-label={t("이전 페이지", "Previous page")} disabled={current === 1} onClick={() => setPage(current - 1)}><ChevronLeft size={18} aria-hidden="true" /></button>
        {Array.from({ length: pages }, (_, index) => index + 1).map((number) => <button key={number} type="button" aria-current={number === current ? "page" : undefined}
          aria-label={t(`${number}페이지`, `Page ${number}`)} onClick={() => setPage(number)}>{number}</button>)}
        <button type="button" aria-label={t("다음 페이지", "Next page")} disabled={current === pages} onClick={() => setPage(current + 1)}><ChevronRight size={18} aria-hidden="true" /></button>
      </nav>
    </section>
  </div>;
}

/** One notice on its own page (`/notices/[id]`, like one inquiry): 게시 중 / 종료 and its kind, the title, when it is posted (Korean time) and the text. */
export function NoticePage({ id }: { id: string }) {
  const t = useT();
  const { language } = useSettings();
  const board = useNoticeBoard();
  const notice = board.data?.find((entry) => entry.id === id);
  const kind = notice ? kindOf(notice.kind) : null;
  return <div className={styles.page}>
    <div className={styles.row}><h1>{t("공지", "Notice")}</h1><ButtonLink href={routes.notices} variant="quiet">{t("공지사항", "Notices")}</ButtonLink></div>
    {board.isPending && <p role="status" className={styles.muted}>{t("공지를 불러오고 있어요.", "Loading the notice.")}</p>}
    {board.error && <p role="alert" className={styles.error}>{t("공지를 불러오지 못했어요. 공지사항에서 다시 열어 주세요.", "Could not load the notice. Open it again from Notices.")} {board.error.message}</p>}
    {board.data === null && <p className={styles.muted}>{t("공지 목록은 아직 준비 중이에요.", "The notice list is not available yet.")}</p>}
    {board.data && !notice && <p role="alert" className={styles.error}>{t("이 공지를 찾을 수 없어요. 공지사항에서 다시 골라 주세요.", "This notice was not found. Choose it again from Notices.")}</p>}
    {notice && kind && <article className={`${styles.card} ${styles.tone}`} data-tone={kind.tone} aria-labelledby="notice-title">
      <div className={styles.cardMeta}><StatusTag notice={notice} t={t} /><span className={styles.noticeKind}>{language === "en" ? kind.en : notice.kind}</span></div>
      <h2 id="notice-title">{titleOf(notice, language)}</h2>
      <p className={styles.cardMeta}>{t("게시 ", "Posted ")}{timeOf(notice.startsAt)} ~ {timeOf(notice.endsAt)}</p>
      <p className={styles.body}>{language === "en" && notice.bodyEn ? notice.bodyEn : notice.body}</p>
    </article>}
  </div>;
}
