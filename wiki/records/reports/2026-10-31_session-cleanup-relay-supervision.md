---
type: report
title: C: 400GB — 기존 세션별 자기 산출물 정리 지시의 후속 감독, 중복 제거 합계 14,704,308,111 B
description: 텔레그램 세션이 12개 기존 세션에 보낸 정리 지시의 실제 완료를 state.db 읽기 전용으로 확인했다. 라우팅 세션에만 후속 요청을 2번 보냈다. 9개 세션 완료, 1개는 승인 대기, 2개는 차단됐다.
status: done
domain: travel
impl_scope: 운영 기록 — 제품 코드·설정 변경 없음. 세션 메시지 전달(gateway session.resume→prompt.submit→end_reason 없는 detach)만 사용
---

# 세션별 정리 지시 후속 감독 (2026-10-31 04:26–05:52)

앞선 기록: [9차](2026-10-31_c-drive-400gb-cleanup-round9.md). 단위: GB=10⁹ B. 상세 표와 원인은 guguroute 프로필 `cache/scratch/relay_supervision_report.md`, 합계 계산은 `sup_totals.json`에 있다.

## 결과

- 정리량(세션 사이 경로 겹침 0건, 중복 제거): **14,704,308,111 B**
  - 파일 이동/인수인계 f1015e: 13,477,382,073 B (자식 2be3e3이 실행, `deleted_manifest.json`)
  - NPU 445eef: 686,162,304 B
  - 라우팅 36cd5c: 276,669,712 B
  - 키미 60b194: 264,072,240 B
  - 유선 전송 598c90: 14,662 B
  - Check pending transfer 02e2b1: 7,120 B
  - 디코봇·팀 UI·myapp 현황: 각 0 B
- 상태 12개: 완료 9 / 수락했으나 사용자 승인 대기 1 (RE 6a803e, bin/obj 1,195,852,670 B) / 차단 2 (3e66dd, 4791b6). 12개 세션 모두 열린 상태로 남았다.
- C: 여유 공간은 05:52에 220,240,261,120 B였다. 400 GB 기준 55.06%이며 **179.76 GB가 부족하다.**

## 확인된 사실

- 백그라운드 프로세스 완료 알림은 viewer가 없는 local 세션에서 기록만 되고 새 턴을 시작하지 않았다. 라우팅 세션에서 04:18:49와 05:00:05 두 번 확인했다. 그래서 그 세션에 후속 요청을 2번 보냈다.
  - 자식 위임(delegate) 완료 알림은 정상적으로 턴을 시작했다(f1015e).
- 4791b6: 세션 route가 `antigravity-oauth`이고 base_url이 `agy://local`이다. `session.resume`이 http(s) 검증에 걸려 거부된다. 10-25 이후 같은 거부가 13건 있었다.
- 3e66dd: 세션의 custom route(`127.0.0.1:18434`)가 API 키를 요구하는 Hermes 관리 llama-server에 키 없이 요청해 401을 받았다.

## 다음

- RE 세션의 bin/obj 삭제 여부는 사용자가 답해야 한다.
- 4791b6과 3e66dd는 세션 모델이나 route를 고친 뒤 다시 보내야 한다. 이번에는 다른 세션의 설정을 바꾸지 않았다.
- 남은 큰 항목은 세션 범위 밖에 있다: `frog-npu-dev/experiments` 100 GB 이상, WSL `ext4.vhdx` 약 47 GB, pagefile, scratch `_archive_20261027` 9.7 GB.
