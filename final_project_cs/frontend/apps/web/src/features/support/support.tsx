"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { Button, ButtonLink } from "@/components/ui";
import { routes } from "@/lib/routes";
import type { Translate } from "@/lib/i18n";
import { useSettings, useT } from "@/lib/settings";
import { createInquiry, inquiries, requestIdentity, type Inquiry } from "./client";
import styles from "./support.module.css";

/** `[2026-10-12 사용자 지시]` 「내 문의」 칸에 한 번에 보이는 문의 수 — 넘치면 칸 아래 페이지 번호로 넘긴다. 칸 높이(`.box`)도 이 수의 줄에 맞춘 고정값이다. */
const INQUIRIES_PER_PAGE = 5;

/**
 * `[2026-10-12 사용자 지시]` 문의 중 · 답변 완료. The server's status is 접수 · 처리 중 · 답변 완료 (an operator's answer sets 답변 완료,
 * `admin_service.py`); the customer sees only whether it is answered. It follows the status, not the answers: an operator may set it
 * back to 처리 중 after answering.
 */
const answered = (item: Inquiry) => item.status === "답변 완료";
const StatusTag = ({ item, t }: { item: Inquiry; t: Translate }) => <span className={styles.status} data-answered={answered(item) || undefined} data-inquiry-status>{answered(item) ? t("답변 완료", "Answered") : t("문의 중", "In progress")}</span>;

/** `[2026-10-12 사용자 지시]` Newest inquiry first (by when it was received — the server orders by its last change, which an answer moves). */
const newestFirst = (items: Inquiry[]) => [...items].sort((a, b) => (Date.parse(b.receivedAt) || 0) - (Date.parse(a.receivedAt) || 0));

/** 「10.12」 — the day the inquiry was received, in this browser's time zone. */
function shortDate(iso: string): string {
  const day = new Date(iso);
  return Number.isNaN(day.getTime()) ? "" : `${String(day.getMonth() + 1).padStart(2, "0")}.${String(day.getDate()).padStart(2, "0")}`;
}

/**
 * `[2026-10-12 사용자 지시]` 문의함(옛 「문의하기」) is two screens: this list of my inquiries with a 「문의 작성」 button, and the form that
 * writes one (`SupportForm`, `/support/new`). `sent`: the form has just recorded an inquiry (`/support?sent=1`) — said once here, and the
 * mark is taken out of the address so a reload does not say it again.
 * 「내 문의」 is one white box of a fixed height that is always there: the empty sentence (centred) when there are none, otherwise five
 * one-line rows at a time (title … 문의 중 / 답변 완료 · date, newest first) with the page buttons always under it (「‹ 1 ›」 when there is
 * one page). A row opens the inquiry's own page (`InquiryPage`, `/support/[id]`) — the box never grows. The server sends the whole list
 * (no paging on its side), so the pages are cut here.
 */
/** `[2026-10-17 ST4F-603]` 운영자의 답변 · 상태는 서버에서 바뀐다 — 탭으로 돌아오면 다시 읽고(앱 기본값은 안 읽음), 문의를 연 동안은 30초마다 읽는다. */
const INQUIRY_REFRESH_MS = 30_000;

export function SupportPage({ sent = false }: { sent?: boolean }) {
  const t = useT();
  const { language } = useSettings();
  const router = useRouter();
  const list = useQuery({ queryKey: ["support-inquiries", language], queryFn: () => inquiries(language), refetchOnWindowFocus: true });
  const [justSent] = useState(sent);
  const [page, setPage] = useState(1);
  useEffect(() => { if (sent) router.replace(routes.support, { scroll: false }); }, [sent, router]);
  const all = newestFirst(list.data?.inquiries ?? []);
  const pages = Math.max(1, Math.ceil(all.length / INQUIRIES_PER_PAGE));
  const current = Math.min(page, pages);                                   // a refresh may leave fewer pages than the one open
  const shown = all.slice((current - 1) * INQUIRIES_PER_PAGE, current * INQUIRIES_PER_PAGE);
  return <div className={styles.page}>
    <div className={styles.row}><h1>{t("문의함", "Inquiries")}</h1></div>
    {/* `[2026-10-22 사용자 결정 — ST4F-717]` 묻기 전에 「이용 방법」의 자주 묻는 질문으로 — 한 줄. */}
    <Link href={`${routes.help}?tab=faq`} className={styles.helpLine}>{t("문의하기 전에 자주 묻는 질문을 확인해 보세요", "Check the FAQ before you ask")}<ChevronRight size={16} aria-hidden="true" /></Link>
    {/* `[2026-10-12 사용자 지시]` 안내 문장은 뺐다. 왼쪽 「여행에서 다시 요청」, 오른쪽 「문의 작성」 — 한 줄(좁으면 왼쪽 글자가 줄바꿈된다). */}
    <div className={styles.actions}>
      <ButtonLink href="/trips">{t("여행에서 다시 요청 · 장소 정보 보완", "Open your trip to retry or correct a place")}</ButtonLink>
      <ButtonLink href={routes.supportNew} variant="primary">{t("문의 작성", "Write an inquiry")}</ButtonLink>
    </div>
    {justSent && <p className={styles.success} role="status">{t("내용을 기록했어요. 접수는 여행 문제 해결을 뜻하지 않아요.", "Your report was recorded. Receipt does not mean the trip issue is resolved.")}</p>}
    <section className={styles.section} aria-labelledby="support-list-title">
      <div className={styles.row}><h2 id="support-list-title">{t("내 문의", "My inquiries")}</h2>
        {/* `[2026-10-12 사용자 지시]` 글자 대신 새로고침 그림 단추 — 이름(읽어 주는 말 · 툴팁)은 그대로 「접수 기록 새로고침」. */}
        <Button className={styles.iconButton} aria-label={t("접수 기록 새로고침", "Refresh records")} title={t("접수 기록 새로고침", "Refresh records")} aria-disabled={list.isFetching || undefined} style={list.isFetching ? { opacity: .48 } : undefined} onClick={() => { if (!list.isFetching) void list.refetch(); }}><RefreshCw size={18} strokeWidth={1.9} aria-hidden="true" /></Button></div>
      <div className={styles.box} data-inquiry-box>
        {list.isPending && <p role="status" className={styles.muted}>{t("문의를 불러오고 있어요.", "Loading your inquiries.")}</p>}
        {list.error && <p role="alert" className={styles.error}>{t("목록을 불러오지 못했어요. 새로고침 단추로 다시 확인해 주세요.", "Could not load the list. Use the refresh button to try again.")} {list.error.message}</p>}
        {list.data?.inquiries.length === 0 && <p className={styles.muted}>{t("아직 접수한 문의가 없어요. 위의 「문의 작성」으로 첫 문의를 보내 주세요.", "No inquiries yet. Use Write an inquiry above to send your first one.")}</p>}
        {shown.length > 0 && <ul className={styles.list}>{shown.map((item) => <li key={item.id}>
          <Link href={routes.supportInquiry(item.id)} className={styles.inquiry} data-inquiry={item.id}>
            <span className={styles.inquiryTitle} data-inquiry-title>{item.title}</span>
            <StatusTag item={item} t={t} />
            <time className={styles.inquiryDate} dateTime={item.receivedAt}>{shortDate(item.receivedAt)}</time>
          </Link>
        </li>)}</ul>}
      </div>
      <nav className={styles.pager} aria-label={t("내 문의 페이지 이동", "My inquiries pages")}>
        <button type="button" aria-label={t("이전 페이지", "Previous page")} disabled={current === 1} onClick={() => setPage(current - 1)}><ChevronLeft size={18} aria-hidden="true" /></button>
        {Array.from({ length: pages }, (_, index) => index + 1).map((number) => <button key={number} type="button" aria-current={number === current ? "page" : undefined}
          aria-label={t(`${number}페이지`, `Page ${number}`)} onClick={() => setPage(number)}>{number}</button>)}
        <button type="button" aria-label={t("다음 페이지", "Next page")} disabled={current === pages} onClick={() => setPage(current + 1)}><ChevronRight size={18} aria-hidden="true" /></button>
      </nav>
    </section>
  </div>;
}

/**
 * `[2026-10-12 사용자 지시]` One inquiry on its own page (`/support/[id]`, like 「문의 작성」): its title and text, and — once an operator has
 * answered — a separate 「답변」 box under them. There is no call for one inquiry: it is read from the same list `/support` shows (already
 * there when coming from it).
 */
export function InquiryPage({ id }: { id: string }) {
  const t = useT();
  const { language } = useSettings();
  const list = useQuery({ queryKey: ["support-inquiries", language], queryFn: () => inquiries(language), refetchOnWindowFocus: true, refetchInterval: INQUIRY_REFRESH_MS });
  const item = list.data?.inquiries.find((entry) => entry.id === id);
  return <div className={styles.page}>
    <div className={styles.row}><h1>{t("문의 내역", "Inquiry")}</h1><ButtonLink href={routes.support} variant="quiet">{t("문의함", "Inquiries")}</ButtonLink></div>
    {list.isPending && <p role="status" className={styles.muted}>{t("문의를 불러오고 있어요.", "Loading the inquiry.")}</p>}
    {list.error && <p role="alert" className={styles.error}>{t("문의를 불러오지 못했어요. 문의함에서 다시 열어 주세요.", "Could not load the inquiry. Open it again from Inquiries.")} {list.error.message}</p>}
    {list.data && !item && <p role="alert" className={styles.error}>{t("이 문의를 찾을 수 없어요. 문의함에서 다시 골라 주세요.", "This inquiry was not found. Choose it again from Inquiries.")}</p>}
    {item && <>
      <article className={styles.card} aria-labelledby="support-inquiry-title">
        <div className={styles.cardMeta}><StatusTag item={item} t={t} /><time dateTime={item.receivedAt}>{new Date(item.receivedAt).toLocaleString(language)}</time></div>
        <h2 id="support-inquiry-title">{item.title}</h2>
        <p className={styles.body}>{item.body}</p>
      </article>
      {item.replies.length > 0
        ? <section className={styles.answer} aria-labelledby="support-answer-title">
          <h2 id="support-answer-title">{t("답변", "Answer")}</h2>
          {item.replies.map((reply, index) => <div className={styles.answerItem} key={`${reply.at}-${index}`}><p className={styles.body}>{reply.body}</p><time dateTime={reply.at}>{new Date(reply.at).toLocaleString(language)}</time></div>)}
        </section>
        : <p className={styles.muted}>{t("아직 답변이 없어요. 답변이 달리면 이 아래에 보여요.", "No answer yet. It will appear below once there is one.")}</p>}
    </>}
  </div>;
}

/** The form of 문의하기 (`/support/new`). Once the server has recorded the inquiry it goes back to the list, which says so. */
export function SupportForm() {
  const t = useT();
  const { language } = useSettings();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const sending = useRef(false);
  const identity = useRef<ReturnType<typeof requestIdentity> | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (sending.current || !title.trim() || !body.trim()) return;
    sending.current = true;
    setBusy(true);
    setError(null);
    identity.current = requestIdentity(identity.current, title, body, language);
    // A logout removes this account's entry. A later entry with the same key
    // must not receive the previous account's delayed inquiry response.
    // (Opened straight at `/support/new` there is no entry yet: the list fetches the new inquiry itself.)
    const sentQuery = queryClient.getQueryCache().find({ queryKey: ["support-inquiries", language], exact: true });
    try {
      const { inquiry } = await createInquiry(language, { title: title.trim(), body: body.trim(), requestId: identity.current.requestId });
      if (sentQuery && queryClient.getQueryCache().find({ queryKey: ["support-inquiries", language], exact: true }) !== sentQuery) return;
      if (sentQuery) queryClient.setQueryData<{ inquiries: typeof inquiry[] }>(["support-inquiries", language], (old) => ({ inquiries: [inquiry, ...(old?.inquiries ?? []).filter((item) => item.id !== inquiry.id)] }));
      identity.current = null;
      router.push(`${routes.support}?sent=1`);
    } catch (caught) {
      setError(t("접수 여부를 확인하지 못했어요. 입력한 내용은 그대로예요. 같은 내용으로 다시 보내면 중복 접수되지 않아요.", "We could not confirm receipt. Your draft is kept. Sending the same draft again will not create a duplicate.") + (caught instanceof Error ? ` ${caught.message}` : ""));
    } finally { sending.current = false; setBusy(false); }
  }
  return <div className={styles.page}>
    <div className={styles.row}><h1>{t("문의 작성", "Write an inquiry")}</h1><ButtonLink href={routes.support} variant="quiet">{t("내 문의", "My inquiries")}</ButtonLink></div>
    <form className={styles.section} onSubmit={(event) => void submit(event)} aria-busy={busy}>
      <div className={styles.field}><label htmlFor="support-title">{t("제목", "Subject")}</label><input id="support-title" value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={200} readOnly={busy} aria-disabled={busy || undefined} /></div>
      <div className={styles.field}><label htmlFor="support-body">{t("문의 내용", "Message")}</label><textarea id="support-body" value={body} onChange={(event) => setBody(event.target.value)} required maxLength={5000} readOnly={busy} aria-disabled={busy || undefined} aria-describedby="support-privacy" /></div>
      <p id="support-privacy" className={styles.muted}>{t("비밀번호·결제 정보 등 민감한 정보는 적지 마세요.", "Do not include passwords or payment details.")}</p>
      <Button type="submit" variant="primary" disabled={!title.trim() || !body.trim()} aria-disabled={busy || undefined} style={busy ? { opacity: .48 } : undefined}>{busy ? t("접수 중…", "Sending…") : t("문의 보내기", "Send inquiry")}</Button>
      {error && <p className={styles.error} role="alert">{error}</p>}
    </form>
  </div>;
}
