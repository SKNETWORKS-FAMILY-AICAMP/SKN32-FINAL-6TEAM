---
type: guide
title: Winnow 뒤 Optuna 선행 E4B 실행 인계
status: draft
domain: travel
---

# Winnow 뒤 Optuna 선행 E4B 실행 인계

2026-10-18 02:25 KST [실제 연결](../../datasets/core/travel_tasks/20261017_audited_G/e4b_optuna_after_winnow_v2_G/activation_G.json)을 완료했습니다. 기존 E4B 한 건만 새 진입점으로 변경, 다른53개·Winnow·원본 자료·기존 모델 보존, 새 예약·GPU 실행기·큐 작업0개입니다.

## 한 일

- [새 별도 판](../../datasets/core/travel_tasks/20261017_audited_G/e4b_optuna_after_winnow_v2_G/README_G.md): Winnow 전체 성공 → Optuna12×최대100단계 → 개발 확인 → 선택 rank/LR에서 CE 계산 교대 검증 → 새 어댑터 본 학습18,478행·2회·4,620단계.
- Focal loss 제외. 개발4과제의 NLL로 후보 선정, 분리된 개발 확인에서 기준보다2% 넘게 나빠지면 기준 사용. 최종 테스트·사람 답은 선택에 사용하지 않음. 짧은 후보의 전체 학습 최적값을 주장하지 않음.
- A4000 전용 환경·800/64/32문항 토큰 검사 통과. A4000 CPU7/7·미완료 Winnow 차단3/3. 백업 신규4/4·회귀20/20. 실제 CUDA 탐색·가속 비교는 미실행.
- 실제 연결 뒤 다른53/53 작업·현재 Winnow PID·기준 코드·원본 학습 및 GGUF 지문 대조. [독립 재확인](../../datasets/core/travel_tasks/20261017_audited_G/e4b_optuna_after_winnow_v2_G/independent_verification_G.json) 당시 Winnow2,530/4,620 = 54.8%, 실제 탐색0/12.
- 최근 완료본의 확인된 과거 비교는 세트별로 엇갈림. 같은90문항에서 Winnow84/90·학습 E4B86/90, 개발88문항에서88/88·83/88. 당시 기록은 차이가 뚜렷하지 않다고 판단. 현재 G 학습본과 구분.

## 남은 일

기존 실행기는 Winnow 성공 이후에만 다음 단계로 갑니다. 실패·자원 부족이면 부분 결과·로그·체크포인트를 보존하며 새 실행기를 만들거나 기존 결과 위에 자동 재시도하지 않습니다. 원본·모델·준비 실패 사본을 지워 공간을 만들지 않습니다. 현재 공유 규칙에 따라 예약을 생성·재활성화하지 않습니다.

실제 Optuna 결과·선정 설정·CE 비교·본 학습·기존 최종 평가·HF 백업은 완료 전입니다. 진행 조회는 사용자 대화 요청 때 수행합니다. 기존 평가·백업 준비 작업의 의존 조건과 완료 증명을 유지합니다. 제품 모델 교체·배포·실제 고객 경로 확인은 하지 않았습니다. [날짜별 기록·보존 위치](../records/reports/2026-10-18_G_e4b_optuna_activation.md).
