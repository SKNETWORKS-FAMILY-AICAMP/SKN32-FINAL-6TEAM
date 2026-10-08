import { z } from 'zod';
import { createDemoSnapshot, DEMO_OPERATOR } from './demo/fixtures';
import { isDemoMode } from './data-mode';
import type { AdminCommand, AdminSnapshot } from './model';
import { watchState } from './model';

export interface AdminGateway {
  snapshot(): Promise<AdminSnapshot>;
  execute(command: AdminCommand): Promise<void>;
  reset(): Promise<void>;
}
const count = z.number().int().min(1, '1 이상의 정수를 입력해 주세요.').max(100000000);
const body = z.string().trim().min(1, '내용을 입력해 주세요.').max(5000, '5,000자 이내로 입력해 주세요.');
const reason = z.string().trim().min(1, '변경 사유를 입력해 주세요.').max(1000);
const localDate = z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/, '날짜와 시간을 입력해 주세요.').refine(v => Number.isFinite(Date.parse(`${v}+09:00`)), '올바른 날짜를 입력해 주세요.');
const commandSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('block-user'), userId: body, blocked: z.boolean(), reason }),
  z.object({ type: z.literal('user-limit'), userId: body, limit: count.nullable(), period: z.enum(['today','until-cleared']), reason }),
  z.object({ type: z.literal('save-limits'), chatLimit: count, rules: z.array(z.object({ id: body, threshold: z.number().min(1).max(99), multiplier: z.number().min(1.1).max(20) })).max(5), reason }),
  z.object({ type: z.literal('api-cap'), apiId: body, daily: count, monthly: count, reason }),
  z.object({ type: z.literal('inquiry-status'), inquiryId: body, status: z.enum(['접수','처리 중','답변 완료']), assignee: z.string().max(100), reason }),
  z.object({ type: z.literal('reply'), inquiryId: body, body }),
  z.object({ type: z.literal('save-template'), id: body.optional(), title: body, body }),
  z.object({ type: z.literal('maintenance'), enabled: z.boolean(), message: body, messageEn: z.string().max(5000), endsAt: localDate, reason }),
  z.object({ type: z.literal('publish-notice'), notice: z.object({ kind: body, title: body, body, titleEn: z.string().max(5000), bodyEn: z.string().max(5000), startsAt: localDate, endsAt: localDate }) }),
  z.object({ type: z.literal('approval'), approvalId: body, approve: z.boolean(), reason }),
  z.object({ type: z.literal('delegation'), delegationId: body, active: z.boolean(), reason }),
  z.object({ type: z.literal('resolve-outbox'), outboxId: body, resolution: z.enum(['confirmed_delivered','confirmed_not_delivered']), reason }),
  z.object({ type: z.literal('check-server') }),
]);

function find<T extends {id: string}>(rows: T[], id: string): T {
  const value = rows.find(row => row.id === id);
  if (!value) throw new Error('대상을 찾을 수 없습니다. 목록을 다시 확인해 주세요.');
  return value;
}
function timestamp(date: string) { return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul', dateStyle: 'short', timeStyle: 'medium' }).format(new Date(date)); }

export function createAdminGateway(mode: string | undefined): AdminGateway {
  if (!isDemoMode(mode)) throw new Error('연결 미설정: NEXT_PUBLIC_ADMIN_DATA_MODE=demo를 명시해 주세요.');
  let state = createDemoSnapshot();
  let sequence = 0;
  return {
    async snapshot() { return structuredClone(state); },
    async reset() { state = createDemoSnapshot(); sequence = 0; },
    async execute(input) {
      const result = commandSchema.safeParse(input);
      if (!result.success) throw new Error(result.error.issues[0].message);
      const command = result.data;
      const next = structuredClone(state);
      next.clock = new Date(Date.parse(next.clock) + 1000).toISOString();
      const at = timestamp(next.clock);
      const record = (action: string, target: string, before: unknown, after: unknown, note: string) => {
        next.audit.unshift({ id: `audit-${sequence + 1}`, at, actor: DEMO_OPERATOR, action, target, before: typeof before === 'string' ? before : JSON.stringify(before), after: typeof after === 'string' ? after : JSON.stringify(after), reason: note });
      };
      switch (command.type) {
        case 'block-user': {
          const user = find(next.users, command.userId);
          record(command.blocked ? '사용자 차단' : '사용자 차단 해제', user.id, user.blocked ? '차단' : '정상', command.blocked ? '차단' : '정상', command.reason);
          user.blocked = command.blocked; break;
        }
        case 'user-limit': {
          const user = find(next.users, command.userId);
          record('예외 한도 변경', user.id, { limit: user.exceptionLimit, period: user.exceptionPeriod }, { limit: command.limit, period: command.limit === null ? null : command.period }, command.reason);
          user.exceptionLimit = command.limit; user.exceptionPeriod = command.limit === null ? null : command.period; break;
        }
        case 'save-limits': {
          const sorted = [...command.rules].sort((a,b) => a.threshold - b.threshold);
          if (new Set(sorted.map(r => r.threshold)).size !== sorted.length || new Set(sorted.map(r => r.id)).size !== sorted.length) throw new Error('감시 단계의 기준과 ID가 중복됩니다.');
          if (sorted.some((r,i) => i > 0 && r.multiplier <= sorted[i-1].multiplier)) throw new Error('소진율이 높을수록 감시 간격을 더 늘려 주세요.');
          record('기본 한도·감시 조절 변경', '서비스 전체', { chatLimit: next.chatLimit, rules: next.watchRules }, { chatLimit: command.chatLimit, rules: sorted }, command.reason);
          next.chatLimit = command.chatLimit; next.watchRules = sorted; break;
        }
        case 'api-cap': {
          const api = find(next.apis, command.apiId);
          if (api.used === null) throw new Error('미계측 API의 운영 상한은 조정할 수 없습니다.');
          if (command.daily > command.monthly) throw new Error('월 운영 상한은 하루 운영 상한 이상이어야 합니다.');
          record('외부 API 운영 상한 변경', api.name, { daily: api.dailyCap, monthly: api.monthlyCap }, { daily: command.daily, monthly: command.monthly }, command.reason);
          api.dailyCap = command.daily; api.monthlyCap = command.monthly; break;
        }
        case 'inquiry-status': {
          const inquiry = find(next.inquiries, command.inquiryId);
          record('문의 상태 변경', inquiry.id, { status: inquiry.status, assignee: inquiry.assignee }, { status: command.status, assignee: command.assignee }, command.reason);
          inquiry.status = command.status; inquiry.assignee = command.assignee;
          inquiry.history.push({ at, text: `${command.status} · ${command.reason}` }); break;
        }
        case 'reply': {
          const inquiry = find(next.inquiries, command.inquiryId);
          record('문의 답변', inquiry.id, inquiry.status, '답변 완료', command.body);
          inquiry.replies.push({ body: command.body, operator: DEMO_OPERATOR, at });
          inquiry.status = '답변 완료'; inquiry.assignee = DEMO_OPERATOR;
          inquiry.history.push({ at, text: '답변 완료 · 답변 본문은 운영 기록에 보관' }); break;
        }
        case 'save-template': {
          if (command.id) {
            const template = find(next.templates, command.id);
            record('답변 템플릿 변경', template.id, template.body, command.body, command.body);
            template.title = command.title; template.body = command.body;
          } else {
            const id = `tpl-${sequence + 1}`;
            next.templates.push({ id, title: command.title, body: command.body });
            record('답변 템플릿 추가', id, '', command.title, command.body);
          } break;
        }
        case 'maintenance': {
          record('점검 모드 전환', '사용자 웹 · 데모 미리보기', next.maintenance, { enabled: command.enabled, message: command.message, messageEn: command.messageEn, endsAt: command.endsAt }, command.reason);
          next.maintenance = { enabled: command.enabled, message: command.message, messageEn: command.messageEn, endsAt: command.endsAt }; break;
        }
        case 'publish-notice': {
          if (command.notice.startsAt >= command.notice.endsAt) throw new Error('게시 종료는 시작보다 늦어야 합니다.');
          const id = `notice-${sequence + 1}`;
          next.notices.push({ ...command.notice, id, author: DEMO_OPERATOR });
          record('공지 게시', id, '', command.notice.title, JSON.stringify(command.notice)); break;
        }
        case 'approval': {
          const approval = find(next.approvals, command.approvalId);
          if (approval.status !== '대기') throw new Error('이미 처리한 요청입니다.');
          const status = command.approve ? '승인' : '거절';
          record('예약 요청 ' + status, approval.id, approval.status, status, command.reason); approval.status = status; break;
        }
        case 'delegation': {
          const delegation = find(next.delegations, command.delegationId);
          record('위임 변경', delegation.userId, delegation.active ? '활성' : '없음', command.active ? '활성' : '없음', command.reason); delegation.active = command.active; break;
        }
        case 'resolve-outbox': {
          const item = find(next.outbox, command.outboxId);
          if (item.resolution) throw new Error('확인 결과가 이미 기록되었습니다.');
          record('발송 확인 결과 기록', item.id, 'unknown · 결과 미확인', command.resolution, command.reason);
          item.resolution = command.resolution; item.resolvedBy = DEMO_OPERATOR; item.note = command.reason;
          break;
        }
        case 'check-server': {
          next.server.checkedAt = next.clock;
          const stopped = next.apis.filter(api => watchState(api, next.watchRules) === '멈춤');
          const external = next.server.checks.find(check => check.name === '외부 API');
          if (external) {
            external.status = stopped.length ? '이상' : '정상';
            external.detail = stopped.length ? `${stopped.map(api => api.name).join(' · ')} 운영 상한 도달 · 데모 점검` : '계측된 API의 운영 상한 여유 있음 · 데모 점검';
          }
          const notification = next.server.checks.find(check => check.name === '알림 채널');
          if (notification) notification.detail = `발송 결과 미확인 ${next.outbox.filter(item => !item.resolution).length}건 · 실제 채널 연결 미검증`;
          break;
        }
      }
      sequence += 1;
      state = next;
    },
  };
}
