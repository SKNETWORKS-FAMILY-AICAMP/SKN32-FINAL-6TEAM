# v7 부모 실제 배포

## 변경·검증
추가 일정의 날짜/시각 원문 근거 생성과 고객 공개 raw failure 제거 두 hunk를 포함한 v7을 부모가 localhost/LAN8042에 실제 반영했습니다. v6 프로세스 계보·생성시각·listener 소유를 새로 확인하고 현재 runtime의 공유DB readonly active gate가 idle=true(진행접수0/Dining running0/미완료추론0)임을 확인한 뒤 소유 handle만 교체했습니다.

- 새 부모 handle `proc_48790b56e85d`, listener PID27184.
- 기동 readiness timeout12회를 보존하고 준비 뒤 핵심 HTTP14/14 기대상태 및 로드모듈341/341 해시 일치를 확인했습니다. 무중단 전환이라고 주장하지 않습니다.
- 테스트모드ON, 선택 public-web 검색은 OFF 유지.
- 사전 정확 합집합1363/1363, 별도HTTP4/4, controlled privacy JSON3/SSE3 통과. 날짜추가 같은입력 실모델1/1 PASS는 별도 비교DB 증거입니다.
- 증거: profile scratch `action-v7-20261025-182455-ca136945/{SOURCE_V7_PARENT_SWAP.json,runtime-v7-serving/PARENT_SWAP_PUBLIC_VERIFIED.json}`. rollback은 실제 이전v6 런처입니다.

## 미완료와 시험 분모
full49-owner의 새 배치는 준비49/49·현재 계약 실행가능47/49, pending 선행조건 계약불일치2행. primary 실제21행 중12pass/9fail이며 선행2와미실행26은 별도입니다. 과거13pass/7fail/29blocked 집계는 이전 배치 기록으로 보존하고 최신 배치와 합산하지 않습니다. 핵심 신규 실패는 시각 기준 전후/당일 범위 grounding, 명시 고정 미보존 I06, 다른 장소 응답 F02입니다. privacy 성공으로 업무 실패를 성공으로 바꾸지 않았습니다.

## 다음 절
새 자식에 temporal grounding 최소 수정+실모델 재검증, I06/F02 원문 보호와 대상 일치 회귀, 잔여26 실행 분리를 인계합니다. 인증 기존guest readback은 업무 변경 없이 가능하되 정상session touch만 별도 기록합니다. 실고객 재전송·일정 변경·실알림·유료·원격0. 모델 새 소유자는 temporal 자식 한 명만, 새 live runtime-v7의 counters와 공유DB guard를 사용합니다. 제품 경로·모델 threshold 하드코딩 추가 및 신규 무음 fallback 없음.
