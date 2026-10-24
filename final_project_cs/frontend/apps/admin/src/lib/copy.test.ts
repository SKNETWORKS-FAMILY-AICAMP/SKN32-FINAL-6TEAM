import { describe, expect, it } from 'vitest';
import { adminCopy } from './copy';

function commandMessages(live: boolean) {
  const copy = adminCopy(live);
  return [copy.confirmationDone, copy.userLimitDone, copy.blockDone(false), copy.blockDone(true), copy.apiCapDone('장소 API')];
}

describe('실제·데모 운영 문구 경계', () => {
  it('실제 모드의 모든 성공 문구는 계약과 일치하고 데모를 포함하지 않는다', () => {
    const messages = commandMessages(true);
    expect(messages).toEqual([
      '확인 결과를 운영 기록에 남겼습니다.',
      '예외 한도를 저장하고 운영 기록에 남겼습니다.',
      '차단를 저장했습니다.',
      '차단 해제를 저장했습니다.',
      '장소 API 운영 상한을 저장했습니다.',
    ]);
    messages.forEach(message => expect(message).not.toContain('데모'));
  });

  it('데모 모드의 모든 성공 문구는 기존 문장을 유지한다', () => {
    expect(commandMessages(false)).toEqual([
      '확인 결과를 데모에 기록했습니다.',
      '예외 한도를 데모에 반영하고 운영 기록에 남겼습니다.',
      '차단를 데모에 반영했습니다.',
      '차단 해제를 데모에 반영했습니다.',
      '장소 API 운영 상한을 데모에 반영했습니다.',
    ]);
  });

  it('실제 모드의 ops 경고와 기간 라벨은 계약과 일치하고 데모를 포함하지 않는다', () => {
    const copy = adminCopy(true);
    expect(copy.opsNotice).toBe('이 화면의 승인·위임·발송 확인은 cs 프로젝트 서버에 바로 저장되고 고객 예약·알림에 영향을 줍니다. 사유는 운영 기록에 남습니다.');
    expect(copy.exceptionPeriods).toEqual({ today: '오늘만', 'until-cleared': '해제할 때까지' });
    [copy.opsNotice, ...Object.values(copy.exceptionPeriods)].forEach(message => expect(message).not.toContain('데모'));
  });

  it('데모 모드의 ops 경고와 기간 라벨은 기존 문장을 유지한다', () => {
    const copy = adminCopy(false);
    expect(copy.opsNotice).toBe('이번 범위에 둘지는 팀에서 정합니다. 모든 처리는 데모 상태에만 반영됩니다.');
    expect(copy.exceptionPeriods).toEqual({ today: '오늘만 · 데모', 'until-cleared': '해제할 때까지 · 데모' });
  });
});
