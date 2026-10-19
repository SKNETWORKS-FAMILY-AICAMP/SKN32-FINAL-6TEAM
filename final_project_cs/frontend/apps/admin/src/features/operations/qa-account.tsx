'use client';

import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { operationQaAccount, saveQaAccount, openQaAccount } from '../../lib/gateway';
import styles from './qa-account.module.css';

type State = { enabled: boolean; revision: number; customer_id: string | null; trips: number; started_at: string | null };

export function QaAccount() {
  const query = useQuery({ queryKey: ['qa-account'], queryFn: () => operationQaAccount<State>(), staleTime: 0 });
  const [reason, setReason] = useState('');
  const [reasonError, setReasonError] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [link, setLink] = useState<{ url: string; ticket: string; expires_in_seconds: number } | null>(null);
  const [deleting, setDeleting] = useState<State | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const confirm = useRef<HTMLButtonElement>(null);
  const stop = useRef<HTMLButtonElement>(null);
  const start = useRef<HTMLButtonElement>(null);
  const reasonInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!busy && query.data?.enabled === false && message.startsWith('테스트 계정과 시험 데이터를 삭제')) start.current?.focus();
  }, [busy, query.data?.enabled, message]);

  function closeDialog() {
    if (dialog.current?.open) { dialog.current.close(); stop.current?.focus(); }
    setDeleting(null);
  }

  function validReason() {
    if (reason.trim()) return true;
    setReasonError('작업 사유를 입력해 주세요. 시작과 종료 기록에 함께 남습니다.');
    reasonInput.current?.focus();
    return false;
  }

  async function perform(action: 'start' | 'stop' | 'open') {
    const state = action === 'stop' ? deleting : query.data;
    if (!state || busy || !validReason()) return;
    setBusy(true); setError(''); setMessage(''); setLink(null);
    try {
      const payload = { expected_revision: state.revision, reason: reason.trim() };
      if (action === 'open') {
        setLink(await openQaAccount(payload));
        setMessage('아래 링크로 테스트 화면을 여세요. 한 번 사용하면 만료됩니다.');
      } else {
        await saveQaAccount({ ...payload, enabled: action === 'start', confirm_customer_id: action === 'stop' ? state.customer_id : null });
        setMessage(action === 'start' ? '테스트 계정을 만들었습니다. 테스트 화면을 열 수 있습니다.' : '테스트 계정과 시험 데이터를 삭제했습니다. 현재 꺼짐 상태입니다.');
        closeDialog();
        await query.refetch();
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '처리하지 못했습니다. 현재 상태를 다시 읽어 주세요.');
      closeDialog();
      await query.refetch();
    } finally { setBusy(false); }
  }

  return <section className={`panel ${styles.page}`}>
    <h1>테스트 계정</h1>
    <p>시험할 때만 계정을 만들고, 종료하면 계정과 시험 데이터를 삭제합니다. 평소에는 꺼짐으로 두세요.</p>
    {query.isPending ? <p role="status">현재 상태를 읽는 중…</p> : query.isError ? <p role="alert" className="error">{query.error.message}</p> : query.data && <>
      <div className={styles.state}>
        <h2>{query.data.enabled ? '켜짐 · 테스트 중' : '꺼짐 · 테스트 계정 없음'}</h2>
        {query.data.enabled && <dl><dt>전용 계정 번호</dt><dd>{query.data.customer_id}</dd><dt>시험 여행</dt><dd>{query.data.trips}개</dd></dl>}
        <p>게스트 여행 수·채팅·계정과 IP별 일일 이용 횟수 제한을 해제합니다. 서비스 전체 예산과 외부 API 상한, 본인 여행만 접근하는 규칙, 약관 동의는 유지합니다.</p>
      </div>
      <label className={styles.reason}>작업 사유<input ref={reasonInput} value={reason} onChange={event => { setReason(event.target.value); setReasonError(''); setError(''); }} onBlur={() => { if (!reason.trim()) setReasonError('작업 사유를 입력해 주세요. 시작과 종료 기록에 함께 남습니다.'); }} aria-required="true" aria-invalid={!!reasonError} aria-describedby={reasonError ? 'qa-reason-error' : undefined} autoComplete="off" maxLength={500} placeholder="예: 예시 일정의 숙소·예약 보호 확인" /></label>
      {reasonError && <p id="qa-reason-error" role="alert" className="error">{reasonError}</p>}
      <div className={styles.actions}>
        {!query.data.enabled ? <button ref={start} className="primary" disabled={busy} onClick={() => void perform('start')}>{busy ? '처리 중…' : '테스트 시작'}</button> : <button className="primary" disabled={busy} onClick={() => void perform('open')}>{busy ? '처리 중…' : '테스트 로그인 링크 만들기'}</button>}
        <button disabled={busy} onClick={() => { setLink(null); void query.refetch(); }}>현재 상태 다시 읽기</button>
      </div>
      {link && <form action={link.url} method="post" target="_blank" rel="noopener noreferrer"><input type="hidden" name="ticket" value={link.ticket} /><button type="submit">테스트 화면 열기</button><p>발급 후 {link.expires_in_seconds}초 동안 한 번만 사용할 수 있습니다.</p></form>}
      {query.data.enabled && <div className={styles.danger}><h2>테스트 종료</h2><p>전용 계정과 시험 여행 {query.data.trips}개, 접수·대화·세션·키를 삭제합니다. 일반 계정은 변경하지 않습니다.</p><button ref={stop} className={styles.delete} disabled={busy} onClick={() => { if (!validReason()) return; setDeleting(query.data); dialog.current?.showModal(); cancel.current?.focus(); }}>종료하고 시험 데이터 삭제</button></div>}
    </>}
    {error && <p role="alert" className="error">{error}</p>}
    {message && <p role="status" className="success">{message}</p>}
    <dialog ref={dialog} className={styles.dialog} aria-labelledby="qa-delete-title" aria-describedby="qa-delete-description" onKeyDown={event => { if (event.key === 'Tab') { event.preventDefault(); (document.activeElement === cancel.current ? confirm.current : cancel.current)?.focus(); } }} onCancel={event => { event.preventDefault(); if (!busy) closeDialog(); }} onClick={event => { if (event.target === event.currentTarget && !busy) closeDialog(); }}>
      <h2 id="qa-delete-title">테스트 계정 ‘{deleting?.customer_id}’을 삭제할까요?</h2>
      <p id="qa-delete-description">시험 여행 {deleting?.trips ?? 0}개와 접수·대화·세션·키를 영구 삭제합니다. 이 작업은 되돌릴 수 없습니다.</p>
      <div className={styles.actions}><button ref={cancel} disabled={busy} onClick={closeDialog}>취소</button><button ref={confirm} className={styles.delete} disabled={busy} onClick={() => void perform('stop')}>{busy ? '삭제 중…' : '테스트 계정 삭제'}</button></div>
    </dialog>
  </section>;
}
