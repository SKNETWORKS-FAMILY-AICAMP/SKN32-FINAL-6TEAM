# 마이캡 공식 범위 상품의 웹 연결

2026-10-12. 마이캡을 사전 견적 필수 상품에서 웹의 다섯 번째 공식 범위 즉시호출 상품으로 추가했습니다. quotes는 기존처럼 빈 목록만 받습니다. 개인 영수증·실제 고객 DB·개발자 API·커밋·푸시·배포에 접근하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 계약·backend·frontend 일치 | 반영 | 3/3 = 100% |
| 웹 backend 관련 회귀 | 외부망 차단 통과 | 85/85 = 100% |
| frontend 관련 단위시험 | 통과 | 39/39 = 100% |
| 수정 frontend 파일 ESLint | 통과 | 3/3 = 100% |
| TypeScript 타입검사 | 종료0 | 1/1 = 100% |
| 실제 화면·실제 택시 비용 확인 | 이 담당자 미실행 | 0/2 = 0% |

Python85는 기존84개 합집합에 마이캡 허용값1개를 더한 실제 testcase 수입니다. TS39는 from-review19+move-options8+taxi-pricing12개입니다. 반복 실행을 더하지 않았습니다. 전체21기능의 실사용 완료율이 아닙니다.

## 적용한 근거

[마이캡 공식 승객약관](https://www.blackpin.co.kr/?mode=policy) 제9조의 서울 즉시호출 플랫폼 이용료는 03:00~22:00 0~3,000원, 22:00~03:00 0~5,000원입니다. 부칙 시행일은2025-03-05입니다. 루트 담당자는2026-10-12T04:32:40+09:00에 실제 웹 JavaScript 모달의 제1~23조와 부칙을 모두 읽었습니다. 관측 기록은 [공식 화면 사실 JSON](C:/Users/playdata2/Documents/final_workspace/datasets/mobility/raw/official_mycap_20261012_v3/screen-observed-facts-v1.json)과 [수집 보고서](C:/Users/playdata2/Documents/final_workspace/datasets/mobility/raw/official_mycap_20261012_v3/REPORT.md)입니다.

이 담당자의 일반 웹 텍스트 도구는 해당 동적 모달을 가져오지 못했습니다. 따라서 독립적으로 원문 전체를 다시 확인했다고 주장하지 않고 루트의 실제 렌더 화면 관측 근거를 재사용했습니다. 현재 공개된 약관이 과거 이용 당시에도 같은 버전이었다는 사실은 확인되지 않았습니다.

## 변경 범위

- 공유 계약을 먼저 수정한 뒤 backend의 정확한 허용 상품 목록에 mycap_immediate를 추가했습니다. 사전 견적을 받지 않는 웹 초기 계약과 지원 밖 상품 거절은 유지했습니다.
- frontend의 상품 목록에 마이캡을 추가해 같은 목록을 사용하는 파서가 손상 없이 받아들입니다. 모든 택시 구간에 선택 상품의 공식 이용료 범위 상단을 예산으로 포함한다는 안내로 바꾸고, 마이캡 미지원 문장은 제거했습니다. 예약·별도 견적 상품 미지원 경계는 명시했습니다.
- 기존 지원 밖 입력 시험의 마이캡을 예약/미확인 브랜드로 바꿨습니다. backend의 마이캡 허용 시험과 frontend 파서 허용 시험이 각각 실행되었습니다.

엔진 카탈로그·요율 시험, 브라우저 spec, 루트 보고서는 루트 담당자가 소유하며 수정하지 않았습니다. backend 저장·후보·확정 연결과 revision별 후보 폐기는 앞선 구현을 유지했습니다.

## 실행 근거

- `mycap-web-offline-v1.xml`/`.log`:85개 모두 통과, 오류·실패·건너뜀0. 외부 socket 접속 차단 하네스 사용. 종료 후 기존 pyreadline3 소멸자 handle 경고가 출력되었으나 testcase 실패 및 비정상 종료는 없었습니다.
- `mycap-web-vitest-v3.xml`/`.log`:39개 모두 통과, 오류·실패·건너뜀0. `--pool=threads --no-file-parallelism --maxWorkers=1` 사용.
- `mycap-web-vitest-v1`/`v2`는 sandbox forks의 임시 ssr 캐시 ENOENT로 일부 파일을 수집하지 못한 원본 기록입니다. 실제 assertion 실패가 아니라 시험 시작 단계 오류였으며 삭제하거나 통과 기록으로 바꾸지 않았습니다.
- `mycap-web-typecheck-v1.log`: `tsc --noEmit` 종료0, 진단 출력 없음.
- `mycap-web-eslint-v1.log`:수정 frontend3파일 ESLint 종료0, 진단 출력 없음. 첫 실행 지연으로 동일3파일의 정적검사를 sandbox 밖에서 실행한 v2도 종료0입니다. 외부 API·DB·배포 작업은 수행하지 않았습니다.

## 보존

변경한 기존7파일은 각각 부모 `_backup/2026-10-12_0432_mycap_official_web/`에 수정 전에 복사했습니다. 파일별 원본·현재 SHA256은 `mycap-web-hashes-v1.json`에 있습니다. source의 URL·제9조·시행일·관측일 주석에는 과거 이용 당시 버전 확정 근거가 아니라는 제한도 적었습니다.

이번 검증은 코드·웹 입력 계약의 연결을 확인했습니다. 루트가 별도로 진행하는 브라우저 화면 결과, 실제 cs 프로젝트 서버 환경 반영, 실제 택시 비용 오차 측정과 합치지 않습니다.
