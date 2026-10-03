export type ViewState = 'normal' | 'loading' | 'empty' | 'error';
export type InquiryStatus = '접수' | '처리 중' | '답변 완료';
export interface User {
  id: string; blocked: boolean; issuedAt: string; lastUsed: string;
  chat: number; web: number; exceptionLimit: number | null;
  exceptionPeriod: 'today' | 'until-cleared' | null;
  trips: { id: string; title: string; status: string; places: number }[];
  paths: { path: string; count: number }[];
}
export interface ApiUsage {
  id: string; name: string; adapter: string; connection: string; metering: string;
  used: number | null; monthlyUsed: number | null; dailyCap: number | null; monthlyCap: number | null;
  free: number | null; watch: number | null; chat: number | null;
  paid: number | null; cost: number | null; budgetTimezone: string; watches: string;
}
export interface WatchRule { id: string; threshold: number; multiplier: number }
export interface Inquiry {
  id: string; userId: string; title: string; body: string; language: string;
  receivedAt: string; status: InquiryStatus; assignee: string;
  replies: { body: string; operator: string; at: string }[];
  history: { text: string; at: string }[];
}
export interface Notice {
  id: string; kind: string; title: string; body: string; titleEn: string; bodyEn: string;
  startsAt: string; endsAt: string; author: string;
}
export interface AuditEntry { id: string; at: string; actor: string; action: string; target: string; before: string; after: string; reason: string }
export interface Approval { id: string; userId: string; trip: string; request: string; evidence: string; at: string; status: '대기' | '승인' | '거절' }
export interface Delegation { id: string; userId: string; scope: string; active: boolean }
export interface OutboxItem { id: string; topic: string; attempts: number; error: string; status: 'unknown'; resolution: 'confirmed_delivered' | 'confirmed_not_delivered' | null; resolvedBy: string | null; note: string | null }
export interface ServerCheck { name: string; status: '정상' | '이상' | '미확인'; detail: string }
export interface AdminSnapshot {
  clock: string; users: User[]; apis: ApiUsage[]; chatLimit: number; watchRules: WatchRule[];
  inquiries: Inquiry[]; templates: { id: string; title: string; body: string }[];
  notices: Notice[]; maintenance: { enabled: boolean; message: string; messageEn: string; endsAt: string };
  audit: AuditEntry[]; approvals: Approval[]; delegations: Delegation[]; outbox: OutboxItem[];
  server: { checkedAt: string; checks: ServerCheck[]; cpu: number; memory: number; disk: number; uptime: string; dbSize: string; dbConnections: number; slowQueries: number; lastWatch: string; watchFailures: number; restarts: number };
  requests: { path: string; count: number; users: number; errorRate: number; p50: number; p95: number }[];
  llm: { model: string; calls: number; input: number; output: number; cost: number | null; latency: number; local: boolean }[];
  daily: { day: string; watch: number; chat: number }[];
}
export type AdminCommand =
  | { type: 'block-user'; userId: string; blocked: boolean; reason: string }
  | { type: 'user-limit'; userId: string; limit: number | null; period: 'today' | 'until-cleared'; reason: string }
  | { type: 'save-limits'; chatLimit: number; rules: WatchRule[]; reason: string }
  | { type: 'api-cap'; apiId: string; daily: number; monthly: number; reason: string }
  | { type: 'inquiry-status'; inquiryId: string; status: InquiryStatus; assignee: string; reason: string }
  | { type: 'reply'; inquiryId: string; body: string }
  | { type: 'save-template'; id?: string; title: string; body: string }
  | { type: 'maintenance'; enabled: boolean; message: string; messageEn: string; endsAt: string; reason: string }
  | { type: 'publish-notice'; notice: Omit<Notice, 'id' | 'author'> }
  | { type: 'approval'; approvalId: string; approve: boolean; reason: string }
  | { type: 'delegation'; delegationId: string; active: boolean; reason: string }
  | { type: 'resolve-outbox'; outboxId: string; resolution: 'confirmed_delivered' | 'confirmed_not_delivered'; reason: string }
  | { type: 'check-server' };
export interface ScreenProps {
  data: AdminSnapshot;
  onCommand: (command: AdminCommand) => Promise<void>;
  navigate: (path: string) => void;
}
export const formatNumber = (value: number) => value.toLocaleString('ko-KR');
export const chatLimitFor = (user: User, data: AdminSnapshot) => user.exceptionLimit ?? data.chatLimit;
export function watchState(api: ApiUsage, rules: WatchRule[]) {
  if (api.used === null || api.dailyCap === null) return '미계측';
  const ratio = Math.max(api.used / api.dailyCap, api.monthlyUsed !== null && api.monthlyCap !== null ? api.monthlyUsed / api.monthlyCap : 0);
  if (ratio >= 1) return '멈춤';
  const rule = [...rules].sort((a, b) => b.threshold - a.threshold).find(r => ratio * 100 >= r.threshold);
  return rule ? `간격 ×${rule.multiplier}` : '정상';
}
