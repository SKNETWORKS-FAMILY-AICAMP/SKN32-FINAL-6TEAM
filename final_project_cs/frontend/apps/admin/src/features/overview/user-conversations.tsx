'use client';

import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { operationConversations, operationMessages } from '../../lib/gateway';
import type { ChatMessage, Conversation, MessagesPage, User } from '../../lib/model';
import { Pagination, userTime } from './user-list';
import styles from './users.module.css';

export function UserConversations({ user, live, clock }: { user: User; live: boolean; clock: string }) {
  const [selected, setSelected] = useState('');
  const query = useQuery({ queryKey: ['user-conversations', user.id, clock], queryFn: () => operationConversations(user.id), enabled: live });
  const conversations = live ? query.data?.conversations : demoConversations(user);
  const conversation = conversations?.find(item => item.id === selected) ?? conversations?.[0];
  return <section className={`panel ${styles.conversations}`} aria-label="채팅 대화 전문">
    <h2>채팅 대화 전문</h2>
    <p className="muted">여행을 선택하면 최신 구간부터 표시합니다. 20개 메시지씩 이동하며, 긴 메시지는 펼쳐서 전문을 읽을 수 있습니다. 시각은 한국 기준입니다.</p>
    {!live && <p className="notice">화면 확인용 예시 대화입니다.</p>}
    {live && query.isPending ? <p role="status">대화 목록을 불러오는 중…</p> : live && query.isError ? <><p className="error" role="alert">대화 목록을 불러오지 못했습니다. {query.error.message}</p><button onClick={() => void query.refetch()}>대화 목록 다시 불러오기</button></> : !conversation ? <p className={styles.empty}>저장된 채팅 대화가 없습니다.</p> : <>
      <label className={styles.conversationPicker}>대화한 여행<select value={conversation.id} onChange={event => setSelected(event.target.value)}>{conversations?.map(item => <option key={item.id} value={item.id}>{item.title} · {item.total}개 메시지</option>)}</select></label>
      <p className="muted">{userTime(conversation.firstAt)} ~ {userTime(conversation.lastAt)} · 저장된 대화 기준 · 개인정보는 가려서 표시합니다.</p>
      <MessageWindow key={`${user.id}:${conversation.id}`} userId={user.id} conversation={conversation} live={live} clock={clock} />
    </>}
  </section>;
}

function MessageWindow({ userId, conversation, live, clock }: { userId: string; conversation: Conversation; live: boolean; clock: string }) {
  const transcript = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState(Math.max(1, Math.ceil(conversation.total / 20)));
  const query = useQuery({ queryKey: ['user-messages', userId, conversation.id, page, clock], queryFn: () => operationMessages(userId, conversation.id, page), enabled: live });
  const result = live ? query.data : demoMessagePage(conversation.id, page);
  const info = result ?? { total: conversation.total, page, pageSize: 20, pages: Math.max(1, Math.ceil(conversation.total / 20)) };
  function changePage(next: number) { setPage(next); transcript.current?.scrollIntoView({ block: 'start' }); }
  const pager = <Pagination info={info} noun="개 메시지" onPage={changePage} disabled={live && (query.isPending || query.isError)} />;
  return <div ref={transcript} aria-busy={live && query.isPending}>
    {pager}
    {live && query.isError ? <><p className="error" role="alert">대화를 불러오지 못했습니다. {query.error.message}</p><button onClick={() => void query.refetch()}>이 구간 다시 불러오기</button></> : !result ? <p role="status">대화를 불러오는 중…</p> : <>
      <p className={styles.range} role="status">{result.messages.length ? `이 구간: ${userTime(result.messages[0].at)} ~ ${userTime(result.messages.at(-1)!.at)}` : '이 구간에 저장된 메시지가 없습니다.'}</p>
      <ol className={styles.messages} start={(result.page - 1) * result.pageSize + 1} aria-label="시간순 대화">
        {result.messages.map((message, index) => <li key={message.id} className={message.role === 'customer' ? styles.customer : styles.assistant}>
          <div className={styles.messageMeta}><strong>{message.role === 'customer' ? '사용자' : 'guguroute'}</strong><time dateTime={message.at}>{userTime(message.at)}</time><span>#{(result.page - 1) * result.pageSize + index + 1}</span></div>
          {message.text.length > 600 || message.text.split('\n').length > 10 ? <details className={styles.longMessage}>
            <summary><span className={styles.preview}>{message.text.slice(0, 240)}…</span><span className={styles.expand}>전문 펼치기 / 접기 · {message.text.length.toLocaleString('ko-KR')}자</span></summary>
            <div className={styles.fullText} tabIndex={0} role="region" aria-label={`${message.role === 'customer' ? '사용자' : 'guguroute'} 메시지 전문`}>{message.text}</div>
          </details> : <p className={styles.messageText}>{message.text}</p>}
        </li>)}
      </ol>
    </>}
    {result && result.messages.length > 5 && pager}
  </div>;
}

function demoConversations(user: User): Conversation[] {
  return user.trips.map(trip => ({ id: trip.id, title: trip.title, total: 46, firstAt: '2026-09-29T09:00:00+09:00', lastAt: '2026-09-29T09:45:00+09:00' }));
}
function demoMessagePage(tripId: string, requestedPage: number): MessagesPage {
  const messages: ChatMessage[] = Array.from({ length: 46 }, (_, i) => ({
    id: `${tripId}-${i}`, role: i % 2 ? 'assistant' : 'customer', at: new Date(Date.parse('2026-09-29T09:00:00+09:00') + i * 60000).toISOString(),
    text: i === 43 ? '서울 여행 일정 검토 예시입니다.\n' + Array.from({ length: 30 }, (_, n) => `${n + 1}. 이동 시간과 관람 시간을 함께 확인합니다. 긴 대화도 전문을 펼쳐 읽을 수 있습니다.`).join('\n') + '\n[예시 전문 끝]' : i % 2 ? '서울 여행 일정의 해당 항목을 확인했습니다. 방문 시각과 이동 여유를 함께 확인해 주세요.' : '서울 여행 일정에서 다음 장소까지 이동 시간을 확인해 주세요.',
  }));
  const page = Math.min(requestedPage, 3);
  return { messages: messages.slice((page - 1) * 20, page * 20), total: 46, page, pageSize: 20, pages: 3 };
}
