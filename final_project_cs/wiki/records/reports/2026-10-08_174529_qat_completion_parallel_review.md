# 완료 답안 회수·병렬 검증·독립 보류 자료 준비

[실측] 기존 승인된 GPU 서버 A의 완료 시험 두 개를 새 폴더에 보관하고 원격·로컬 답안 SHA를 대조했다. 추가 에이전트는 읽기 전용 결과 검증과 새 보류 자료 준비 계약을 분담했다. 새로운 GPU 실행·작업 중단·외부 전송·결제는 없다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 추가 답안 보관·고정 문항 대조 | 완료 | 3,735/3,735 = 100% |
| 추가 에이전트 분담 | 완료 | 2/2 = 100% |
| 독립 재계수·조건 확인 | 통과 | 65/65 = 100% |
| 완료 리포트 링크 확인 | 통과 | 24/24 = 100% |
| 독립 보류 기본 문항 작성 | 미착수 | 0/720 = 0% |

## 실제 결과와 원본 대조

| 시험 | 우리 여행 추가 학습 없는 같은 기반 원본 | 우리 여행 어댑터 |
|---|---|---|
| oos1 D2 항목 선택 없음 정답 | 931/1,000 = 93.10% | 995/1,000 = 99.50% |
| oos1 D2 실제 오지목 | 68/1,000 = 6.80% | 5/1,000 = 0.50% |
| oos1 D2 실패 | 1/1,000 = 0.10% | 0/1,000 = 0.00% |
| oos2 D 정상 요청 정답 | 730/883 = 82.67% | 796/883 = 90.15% |
| oos2 D 항목 선택 없음 오지목 | 76/1,786 = 4.26% | 14/1,786 = 0.78% |

원본은 개발사 지시·양자화 학습이 있는 Gemma-4-E4B-it QAT Q4_0이고 우리 여행 어댑터를 별도로 적용했다. D2 정답 증가64개는 실제 오지목 감소63개와 실패 감소1개로 나뉜다. 정상 요청이 없는 D2에서 정상 선택률은 계산하지 않는다. D 전체2,735개 중 단일선택2,669개와 복합 진단66개를 구분한다. 복합의 고정 단일 선택 정답 일치는 전체 요청 집합 정확 일치 C 점수가 아니다. 개발/회귀 자료 모델 실행1회이며 새 독립 보류 검증·최종 채택·상용화 판정은 아니다.

[oos1 D2 회수·검증·백업](2026-10-08_173726_e4bqat_oos1_d2-completion.md) · [oos2 D 회수·검증·백업](2026-10-08_174041_e4bqat_oos2_d-completion.md) · [추가 에이전트 직접 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/review_hb1735.json).

## 분담과 실제 운영

결과 검증 에이전트는 기존 파일을 수정하지 않고 신규 검증 기록 하나만 작성했다. 준비 계약 에이전트는 새 지역 준비 문서 하나만 작성했고 정본·색인·일일 상태는 수정하지 않았다. 주 작업 담당자가 검토 후 연결했다. 분담 완료는 자료 작성·사람 정답 검수·GPU 실측 완료를 뜻하지 않는다.

[독립 보류 자료 준비 초안](../../../../program/research/daily_rag_slm/independent_holdout_contract_2026-10-08_v1.md): 구성·복합 출력·기준 연결은 검토 대기이며 기존 합격 기준을 변경하지 않았다. 실제 기본 문항0/720, 사람 검수0/720이다.

관측 당시 GPU 서버 A는 다음 oos2 D2를 수행하고 준비된4개가 대기한다. GPU 서버 B는 Spark 학습과 기존 기반의4개 학습 예약을 유지한다. 추가 기반 다운로드 후보1개는 공간·실행 조건 재확인이 필요하다. 기존 실행기와 학습을 중복·중단하지 않았다.

Oracle ARM 관측2026-10-08T08:36:41.623945+00:00, 최근300.06초 두 코어 대비 작업 CPU89.56%, 기계 busy90.23%, steal0.16%다. 서비스는 활성·재시작0회, 건강 확인은 ok이며 답안95/360개는 진행 중이다. 남은 공간54,411,526,144바이트, 작업 메모리9,021,267,968바이트(파일 캐시 포함)를 확인했다. 최근5분 목표 충족을24시간 유지나 cs 프로젝트 전체 배포 완료로 해석하지 않는다.

[ARM 원본 관측](../../../../program/scripts/plan_qa_bench/results/arm_serving_20261008/observation_hb1735.json) · [ARM 상태 수정 직전 백업](../../../../program/research/daily_rag_slm/_backup/2026-10-08_174128_arm_hb1735/arm_serving_2026-10-08.json).

## 수정 직전 백업

- [program/research/daily_rag_slm/_backup/2026-10-08_174529_parallel_completion_hb1735/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_174529_parallel_completion_hb1735/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_174529_parallel_completion_hb1735/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_174529_parallel_completion_hb1735/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_174529_parallel_completion_hb1735/index.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_174529_parallel_completion_hb1735/index.md)
- [program/research/daily_rag_slm/_backup/2026-10-08_174529_parallel_completion_hb1735/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_174529_parallel_completion_hb1735/2026-10-08.md)
- [final_project_cs/wiki/_backup/2026-10-08_174529_parallel_completion_hb1735/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_174529_parallel_completion_hb1735/log.md)
