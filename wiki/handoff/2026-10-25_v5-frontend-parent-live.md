# v5 프런트 실제 교체 확인

## 변경·검증
- 부모가 기존 추적 프로세스의 PID 계보와 3100 listener 소유를 확인한 뒤 localhost, LAN 순서로 교체했습니다.
- localhost BUILD_ID `ZojSXmTH7hmXO9eyo677J`, LAN `oGN1-Tld3XUSF7MCHzon3`.
- 동결 artifact 해시 각 332/332 일치 후 전환했습니다.
- 실제 3100 HTTP 각 5/5, 정적 자산 HTTP/disk 바이트 해시 각 22/22 일치했습니다.
- 새 부모 소유 handle: localhost `proc_85a6dc785a17`, LAN `proc_95fa8f2297ba`.
- 증거: 프로필 scratch `web-v5-release-20261025-170512-b1431a/PARENT_FRONTEND_LIVE.json`, rollback은 같은 폴더 `PREPARED_FRONTEND_SWAP.json`.

## 범위·잔여
사진 1분 고정 안내 수정 프런트가 실제 제공됩니다. 실제 고객 접수 재실행·등록·모델 추론은 하지 않았습니다. API는 기존 실행본 유지 중이며 백엔드 v5 전환은 별도 인증 호환 확인 결과 후 진행합니다. 단위시험 및 fixture replay를 실제 모델 성능 검증으로 확대하지 않습니다.
설정값과 포트는 승인된 배포 manifest에서 읽은 값이며 제품 코드 하드코딩 추가는 없습니다. 신규 fallback은 없습니다.

## 다음 절
새 자식 세션에 실제 브라우저의 공개 페이지·빌드 및 텍스트 안내 수정 번들 확인을 인계합니다. 고객 원본 접수 재실행·상태 변경은 금지합니다.
