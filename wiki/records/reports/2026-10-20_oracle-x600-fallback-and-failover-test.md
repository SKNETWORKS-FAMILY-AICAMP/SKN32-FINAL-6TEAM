# 2026-10-20 오라클 모델 순서 점검 · x600 통로 · 런팟 끊김 시험 보류

결론 한 줄: 오라클 api·worker 에 x600 경유 줄을 넣고 x600 통로를 다시 열어 두 경로가 실제로 답하는 것까지 확인했다. **런팟 끊김 → x600 전환은 운영 터널을 끊어야 해서 시험하지 못했다.** 점검 공지도 켜지 못했다(관리자 로그인 자격은 이 세션이 읽지 않았다).

## 한 일 (확인 범위 표시)

| 항목 | 구분 | 내용 |
|---|---|---|
| 오라클 `.env.apikeys` 에 `ACOP_OLLAMA_FALLBACK_BASE_URLS=http://127.0.0.1:11438` 한 줄 추가 | 운영 적용 | 백업 `control/_backup/env-x600-fallback-20261020-083852`. 줄 수 1 확인 |
| 오라클 api·worker 재생성 | 운영 적용 | 컨테이너 안에서 새 값 확인(`ACOP_OLLAMA_FALLBACK_BASE_URLS` 가 보임). 로그 Traceback 0건. 이 시점 이미지는 r8 |
| x600 → 오라클 역방향 통로 재기동 | 운영 적용 | x600 에서 `run-eks-model-reverse.ps1` 을 프로세스로 시작. 오라클 `127.0.0.1:11438` LISTEN, `/api/tags` 200 |
| 경로 응답 확인 (읽기+소형 질의) | 실제 경로 아님 | 오라클 api 컨테이너 안에서 `OllamaChat.text` 로 「대한민국의 수도는?」. 런팟 터널 11436 「서울」 2.0초, x600 11438 「서울」 2.2초 |
| 내장 올라마 18312 | 미확인 | `/api/tags` 404. 내장 주소가 맞는지 따로 확인 필요 |
| develop `ae6f4236` 원격 확인 | 원격 확인 | `git ls-remote` 로 확인. `502da503` 이 그 안에 포함됨(`merge-base --is-ancestor`) |
| 오라클 api 판 | 확인 | 네 컨테이너(api·worker·web·admin)가 `ae6f4236e572` 이미지, 생성 2026-10-20 15:24 UTC |
| 점검 모드 경로 | 코드 확인 | 떠 있는 api `/srv/app/presentation/admin_api.py` 에 `POST /admin/api/commands`, 종류 `maintenance`. 로그인은 `/admin/api/login` |

## 하지 못한 것

- **런팟 끊김 → x600 전환 실제 시험.** 운영 런팟 터널(`ssh -L 11436`)을 끊는 작업은 자동 권한 심사가 두 번 막았다. 우회하지 않았다. 설정 주소를 바꾸고 재기동하는 방식도 같은 이유로 실행하지 않았다.
- **점검 공지 켜기.** 관리자 로그인 자격은 서버 설정 파일에 있다. 이 세션은 그 값을 읽지 않았다. 관리 콘솔에서 켜는 것이 필요하다.
- **오라클 자동 배포 수동 표시 해제 여부.** `state.json` 백업 이름(`state-before-overlay-lift-20261020T110748Z`)은 있으나, 누가 언제 풀었는지는 이 세션이 확인하지 못했다.
- **디스크 여유.** commit 세션 보고는 10.00GiB 였다. 이 세션이 `df /` 로 본 값은 56G 로 다르다. 어느 경로·시점 값인지 정리되지 않았다.

## 교차 검증 (Codex, 읽기 전용)

`codex exec -s read-only` 로 주장 다섯 개를 검증했다. 결과:

| 주장 | 판정 | 비고 |
|---|---|---|
| 호출 순서 조립(`wrap_from_settings`) | 로컬 기준 틀림 | 로컬 HEAD 는 원격보다 뒤처져 있어 SSH·내장 처리가 없다. 원격 `fb840cd1` 기준으로는 맞다 |
| `_build` 의 SSH·local 처리 | 로컬 기준 틀림 | 같은 이유 |
| 기본 제한시간 6.0 | 맞음 | `settings.py:174`, `llm_failover.py:587` |
| 점검 관리 경로·본문 | 일부 맞음 | 저장본 `e127873a` 에서는 맞다. 원격 최신 조회는 실패했다 |
| 위키에 점검 공지 기록 없음 | **틀림** | 아래 정정 참조 |

**정정.** 이 세션의 앞선 답변은 「위키에 점검 공지 기록이 없다」고 했다. 틀렸다. `wiki/records/reports/2026-10-18_notice-resend-and-service-delivery.md` 86행에 점검 설정 `enabled=true`, 감사 사유 「테스트」 기록이 있고, `wiki/handoff/2026-10-18_customer-notice-links.md` 230행에 공지·점검 발송 대상 기록이 있다.

## 남은 일

1. 관리 콘솔에서 점검 공지를 켠다(사용자 몫).
2. 점검이 켜진 상태에서 런팟 터널을 짧게 끊고 x600 전환을 확인한다. 끝나면 터널을 되살리고 점검을 끈다.
3. 내장 올라마 18312 가 맞는 주소인지 확인한다.
4. 디스크 여유 기준(10.00GiB)을 같은 경로로 다시 잰다.
5. commit 세션이 밀린 커밋 1189건과 `manual_overlay` 해제를 처리한다.
6. 아마존(EKS) 쪽 확인은 kubectl 접속 설정이 생긴 뒤에 한다.

관련 기록: [10-18 점검 발송 기록](2026-10-18_notice-resend-and-service-delivery.md), 인계 [2026-10-20_oracle-failover-session](../../handoff/2026-10-20_oracle-failover-session.md)
