export function adminCopy(live: boolean) {
  return {
    opsNotice: live
      ? '이 화면의 승인·위임·발송 확인은 cs 프로젝트 서버에 바로 저장되고 고객 예약·알림에 영향을 줍니다. 사유는 운영 기록에 남습니다.'
      : '이번 범위에 둘지는 팀에서 정합니다. 모든 처리는 데모 상태에만 반영됩니다.',
    confirmationDone: live ? '확인 결과를 운영 기록에 남겼습니다.' : '확인 결과를 데모에 기록했습니다.',
    userLimitDone: live ? '예외 한도를 저장하고 운영 기록에 남겼습니다.' : '예외 한도를 데모에 반영하고 운영 기록에 남겼습니다.',
    blockDone: (blocked: boolean) => live
      ? `${blocked ? '차단 해제' : '차단'}를 저장했습니다.`
      : `${blocked ? '차단 해제' : '차단'}를 데모에 반영했습니다.`,
    exceptionPeriods: {
      today: live ? '오늘만' : '오늘만 · 데모',
      'until-cleared': live ? '해제할 때까지' : '해제할 때까지 · 데모',
    },
    apiCapDone: (name: string) => live ? `${name} 운영 상한을 저장했습니다.` : `${name} 운영 상한을 데모에 반영했습니다.`,
  };
}
