"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { Button, ButtonLink } from "@/components/ui";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { createInquiry, inquiries, requestIdentity } from "./client";
import styles from "./support.module.css";

/**
 * `[2026-10-12 사용자 지시]` 문의하기 is two screens: this list of my inquiries with a 「문의 작성」 button, and the form that writes one
 * (`SupportForm`, `/support/new`). `sent`: the form has just recorded an inquiry (`/support?sent=1`) — said once here, and the mark is
 * taken out of the address so a reload does not say it again.
 */
export function SupportPage({ sent = false }: { sent?: boolean }) {
  const t = useT();
  const { language } = useSettings();
  const router = useRouter();
  const list = useQuery({ queryKey: ["support-inquiries", language], queryFn: () => inquiries(language) });
  const [justSent] = useState(sent);
  useEffect(() => { if (sent) router.replace(routes.support, { scroll: false }); }, [sent, router]);
  const status = () => t("기록 완료", "Recorded");
  return <div className={styles.page}>
    <div className={styles.row}><h1>{t("문의하기", "Contact support")}</h1><ButtonLink href="/mypage" variant="quiet">{t("마이페이지", "My page")}</ButtonLink></div>
    {/* `[2026-10-12 사용자 지시]` 안내 문장은 뺐다. 왼쪽 「여행에서 다시 요청」, 오른쪽 「문의 작성」 — 한 줄(좁으면 왼쪽 글자가 줄바꿈된다). */}
    <div className={styles.actions}>
      <ButtonLink href="/trips">{t("여행에서 다시 요청 · 장소 정보 보완", "Open your trip to retry or correct a place")}</ButtonLink>
      <ButtonLink href={routes.supportNew} variant="primary">{t("문의 작성", "Write an inquiry")}</ButtonLink>
    </div>
    {justSent && <p className={styles.success} role="status">{t("내용을 기록했어요. 접수는 여행 문제 해결을 뜻하지 않아요.", "Your report was recorded. Receipt does not mean the trip issue is resolved.")}</p>}
    <section className={styles.section} aria-labelledby="support-list-title">
      <div className={styles.row}><h2 id="support-list-title">{t("내 문제 신고 · 건의 기록", "My reports and suggestions")}</h2>
        {/* `[2026-10-12 사용자 지시]` 글자 대신 새로고침 그림 단추 — 이름(읽어 주는 말 · 툴팁)은 그대로 「접수 기록 새로고침」. */}
        <Button className={styles.iconButton} aria-label={t("접수 기록 새로고침", "Refresh records")} title={t("접수 기록 새로고침", "Refresh records")} aria-disabled={list.isFetching || undefined} style={list.isFetching ? { opacity: .48 } : undefined} onClick={() => { if (!list.isFetching) void list.refetch(); }}><RefreshCw size={18} strokeWidth={1.9} aria-hidden="true" /></Button></div>
      {list.isPending && <p role="status">{t("문의를 불러오고 있어요.", "Loading your inquiries.")}</p>}
      {list.error && <p role="alert" className={styles.error}>{t("목록을 불러오지 못했어요. 새로고침 단추로 다시 확인해 주세요.", "Could not load the list. Use the refresh button to try again.")} {list.error.message}</p>}
      {list.data?.inquiries.length === 0 && <p className={styles.muted}>{t("아직 접수한 문의가 없어요. 위의 「문의 작성」으로 첫 문의를 보내 주세요.", "No inquiries yet. Use Write an inquiry above to send your first one.")}</p>}
      <ul className={styles.list}>{list.data?.inquiries.map((item) => <li key={item.id} className={styles.inquiry}><details>
        <summary>{item.title} · {status()}</summary>
        <time dateTime={item.receivedAt}>{new Date(item.receivedAt).toLocaleString(language)}</time>
        <p className={styles.body}>{item.body}</p>
        {item.replies.length === 0 ? <p className={styles.muted}>{t("서비스 개선을 위한 기록이에요. 여행 문제는 위의 여행 화면에서 다시 요청해 주세요.", "This is a service improvement record. Open your trip above to retry a trip request.")}</p> : item.replies.map((reply, index) => <div className={styles.reply} key={`${reply.at}-${index}`}><strong>{t("이전 안내 기록", "Previous message")}</strong><p className={styles.body}>{reply.body}</p><time dateTime={reply.at}>{new Date(reply.at).toLocaleString(language)}</time></div>)}
      </details></li>)}</ul>
    </section>
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
