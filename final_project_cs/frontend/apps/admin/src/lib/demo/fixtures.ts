import type { AdminSnapshot, ApiUsage } from '../model';

export const DEMO_CLOCK = '2026-09-29T14:00:00+09:00';
export const DEMO_OPERATOR = 'demo.operator';
const UNKNOWN_API = { used: null, monthlyUsed: null, dailyCap: null, monthlyCap: null, free: null, watch: null, chat: null, paid: null, cost: null, budgetTimezone: '미계측', watches: '계측 협의 필요' };
const apis: ApiUsage[] = [
  { id: 'google-places', name: 'Google Places', adapter: '있음', connection: '데모', metering: '예산 계측 · 데모 값', used: 850, monthlyUsed: 17500, dailyCap: 1000, monthlyCap: 31000, free: 32000, watch: 680, chat: 170, paid: 0, cost: 0, budgetTimezone: 'UTC 일·월', watches: '장소·영업 정보' },
  { id: 'kakao', name: '카카오 로컬', adapter: '있음', connection: '데모', metering: '예산 계측 · 데모 값', used: 1000, monthlyUsed: 21400, dailyCap: 1000, monthlyCap: 31000, free: null, watch: 720, chat: 280, paid: 0, cost: 0, budgetTimezone: 'UTC 일·월', watches: '장소 검색' },
  { ...UNKNOWN_API, id: 'google-routes', name: 'Google Routes', adapter: '설정만 있음', connection: '미연결', metering: '미계측' },
  { ...UNKNOWN_API, id: 'google-maps', name: 'Google 지도 표시', adapter: '브라우저 SDK', connection: '별도 경로', metering: '미계측' },
  { ...UNKNOWN_API, id: 'tour', name: '관광공사 TourAPI', adapter: '있음', connection: '미확인', metering: '미계측' },
  { ...UNKNOWN_API, id: 'weather', name: '기상청', adapter: '있음', connection: '미확인', metering: '미계측' },
  { ...UNKNOWN_API, id: 'air', name: '에어코리아', adapter: '있음', connection: '미확인', metering: '미계측' },
  { ...UNKNOWN_API, id: 'odsay', name: 'ODsay', adapter: '있음', connection: '미확인', metering: '미계측' },
  { ...UNKNOWN_API, id: 'llm', name: '외부 LLM', adapter: '있음', connection: '데모', metering: '토큰 표 참고' },
];

export function createDemoSnapshot(): AdminSnapshot {
  return structuredClone({
    clock: DEMO_CLOCK,
    users: [
      { id: 'demo-user-01', blocked: false, issuedAt: '2026-09-20 10:30', lastUsed: '2026-09-29 13:52', chat: 50, web: 128, exceptionLimit: null, exceptionPeriod: null, trips: [{ id: 'trip-01', title: '서울의 오래된 골목, 3일', status: '진행 중', places: 8 }], paths: [{ path: '/v1/web/trips', count: 72 }, { path: '/v1/web/plans', count: 40 }, { path: '/v1/web/intake', count: 16 }] },
      { id: 'demo-user-02', blocked: false, issuedAt: '2026-09-23 11:20', lastUsed: '2026-09-29 13:45', chat: 32, web: 86, exceptionLimit: 80, exceptionPeriod: 'today', trips: [{ id: 'trip-02', title: '한강과 서울숲 산책', status: '진행 중', places: 5 }], paths: [{ path: '/v1/web/trips', count: 60 }, { path: '/v1/web/plans', count: 26 }] },
      { id: 'demo-user-03', blocked: true, issuedAt: '2026-09-24 09:10', lastUsed: '2026-09-29 12:30', chat: 15, web: 342, exceptionLimit: null, exceptionPeriod: null, trips: [{ id: 'trip-03', title: '박물관 하루 여행', status: '예정', places: 3 }], paths: [{ path: '/v1/web/plans', count: 342 }] },
      { id: 'demo-user-04', blocked: false, issuedAt: '2026-09-26 17:00', lastUsed: '2026-09-29 12:12', chat: 8, web: 24, exceptionLimit: null, exceptionPeriod: null, trips: [], paths: [{ path: '/v1/web/intake', count: 24 }] },
      { id: 'demo-user-05', blocked: false, issuedAt: '2026-09-27 15:45', lastUsed: '2026-09-29 11:08', chat: 27, web: 63, exceptionLimit: null, exceptionPeriod: null, trips: [{ id: 'trip-05', title: '북촌과 경복궁', status: '완료', places: 6 }], paths: [{ path: '/v1/web/trips', count: 63 }] },
      { id: 'demo-user-06', blocked: false, issuedAt: '2026-09-29 10:00', lastUsed: '2026-09-29 10:02', chat: 0, web: 2, exceptionLimit: null, exceptionPeriod: null, trips: [], paths: [{ path: '/v1/web/session', count: 2 }] },
    ],
    apis, chatLimit: 50, watchRules: [{ id: 'rule-01', threshold: 80, multiplier: 2 }],
    inquiries: [
      { id: 'inq-01', userId: 'demo-user-01', title: '여행 중 채팅 한도가 다 찼어요', body: '오늘 일정을 여러 번 확인하다 채팅 한도에 도달했습니다. 저녁 이동 경로를 한 번 더 확인하고 싶어요. 오늘만 한도를 늘릴 수 있을까요?', language: '한국어', receivedAt: '2026-09-29 10:15', status: '접수', assignee: '', replies: [], history: [{ at: '2026-09-29 10:15', text: '문의 접수' }] },
      { id: 'inq-02', userId: 'demo-user-02', title: '장소 정보가 갱신되지 않아요', body: '여행 화면에서 장소 정보가 오래된 것처럼 보입니다. 확인 부탁드립니다.', language: '한국어', receivedAt: '2026-09-29 11:40', status: '처리 중', assignee: DEMO_OPERATOR, replies: [], history: [{ at: '2026-09-29 11:40', text: '문의 접수' }, { at: '2026-09-29 12:10', text: '담당자 지정 · 처리 중' }] },
      { id: 'inq-03', userId: 'demo-user-05', title: '여행 내역 확인 방법', body: '완료된 여행도 다시 볼 수 있나요?', language: '한국어', receivedAt: '2026-09-28 15:30', status: '답변 완료', assignee: DEMO_OPERATOR, replies: [{ body: '내 여행 목록에서 완료된 여행을 선택해 확인할 수 있습니다.', operator: DEMO_OPERATOR, at: '2026-09-28 15:50' }], history: [{ at: '2026-09-28 15:50', text: '답변 완료' }] },
    ],
    templates: [
      { id: 'tpl-limit', title: '채팅 한도 안내', body: '문의해 주셔서 감사합니다. 채팅 일일 한도는 한국 시각 자정에 초기화됩니다. 여행 중 필요한 추가 확인은 운영자가 사용 상황을 확인한 뒤 안내드리겠습니다.' },
      { id: 'tpl-watch', title: '장소 정보 지연 안내', body: '장소 정보 갱신이 일시적으로 늦어지고 있습니다. 확인한 내용은 공지와 문의 답변으로 안내드리겠습니다.' },
    ],
    notices: [{ id: 'notice-01', kind: '안내', title: '여행 중 궁금한 점은 문의함에 남겨 주세요', body: '운영자가 확인한 뒤 문의함으로 답변합니다.', titleEn: 'Need help during your trip?', bodyEn: 'Leave a message in your inquiry inbox.', startsAt: '2026-09-28T09:00', endsAt: '2026-10-02T18:00', author: DEMO_OPERATOR }],
    maintenance: { enabled: false, message: '서비스 점검 중입니다. 잠시 후 다시 이용해 주세요.', messageEn: 'We are performing maintenance. Please try again shortly.', endsAt: '2026-09-29T16:00' },
    audit: [{ id: 'audit-seed-01', at: '2026-09-29 12:30:00', actor: DEMO_OPERATOR, action: '사용자 차단', target: 'demo-user-03', before: '정상', after: '차단', reason: '비정상 반복 요청 확인 · 시연 예시' }],
    approvals: [{ id: 'approval-01', userId: 'demo-user-02', trip: '한강과 서울숲 산책', request: '방문 시간 변경 요청', evidence: '사용자 변경 요청 접수. 공급자 확인 내용은 데모 문서입니다.', at: '2026-09-29 11:00', status: '대기' }],
    delegations: [{ id: 'delegation-01', userId: 'demo-user-01', scope: '여행 일정 확인', active: false }, { id: 'delegation-02', userId: 'demo-user-02', scope: '여행 일정 확인', active: true }],
    outbox: [{ id: 'outbox-01', topic: '여행 일정 변경 안내', attempts: 1, error: '응답 시간 초과 — 수신 여부 확인 필요', status: 'unknown', resolution: null, resolvedBy: null, note: null }],
    server: { checkedAt: DEMO_CLOCK, checks: [{ name: 'API 서버', status: '정상', detail: '데모 연결 상태 · 8042' }, { name: '데이터베이스', status: '정상', detail: '데모 연결 상태' }, { name: 'LLM', status: '정상', detail: '데모 연결 상태' }, { name: '외부 API', status: '이상', detail: '카카오 운영 상한 도달 · 추가 호출 멈춤' }, { name: '알림 채널', status: '미확인', detail: '발송 결과 미확인 알림 1건' }, { name: '사용자 웹 ↔ 서버', status: '정상', detail: '허용 출처와 마지막 성공 호출 · 데모 값' }], cpu: 24, memory: 43, disk: 31, uptime: '3일 12시간', dbSize: '284 MB', dbConnections: 7, slowQueries: 0, lastWatch: '2026-09-29 13:58', watchFailures: 1, restarts: 0 },
    requests: [{ path: '/v1/web/messages', count: 132, users: 5, errorRate: 1.5, p50: 340, p95: 1250 }, { path: '/v1/web/trips', count: 195, users: 4, errorRate: 0, p50: 85, p95: 210 }, { path: '/v1/web/plans', count: 408, users: 4, errorRate: 0.2, p50: 110, p95: 330 }],
    llm: [{ model: '외부 모델 · 데모', calls: 87, input: 142800, output: 32100, cost: null, latency: 1250, local: false }, { model: '로컬 모델 · 데모', calls: 45, input: 78500, output: 18400, cost: null, latency: 680, local: true }],
    daily: Array.from({ length: 30 }, (_, i) => ({ day: new Date(Date.UTC(2026, 7, 31 + i)).toISOString().slice(0, 10), watch: i === 29 ? 1400 : 700 + ((i * 137) % 650), chat: i === 29 ? 450 : 150 + ((i * 79) % 280) })),
  });
}
