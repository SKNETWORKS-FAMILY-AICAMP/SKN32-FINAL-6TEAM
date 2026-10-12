# Winnow-E4B 원본·여행 학습판 평가 회수와 추가 예약

[실측] Jev 계열 모델 중 Winnow-E4B(우리 학습 없는 배포 원본)의 어려운 문장 평가와 우리 여행 자료 학습판의 기본 평가를 보관했다. 새 학습판의 전체 성능 개선은 아직 판단하지 않는다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 원본 H 답안 보관·문항 대조 | 완료 | 1,316/1,316개 = 100% |
| 원본 H 정상 요청 정답 | 실측 | 401/461개 = 86.98% |
| 원본 H 요청 없음 오지목 | 실측 | 403/855개 = 47.13% |
| 학습판 기본 답안 보관 | 완료 | 835/835개 = 100% |
| 학습판 추가 평가 등록 | 예약 | 5/5개 = 100% |

## 실제 수행·원본 검증

[원본 H 답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_original_h/d_test_h_backlog_winnow_original.jsonl) · [실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_original_h/started.json) · [유형별 집계·실패 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_original_h/h_counts.json) · [독립 직접 계수·해시 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_original_h/verification.json). GPU 서버 A 원본 SHA256과 같고 고정 입력·전체 ID·정답·유형이 일치했다. 정상 요청461개 중 형식 실패2개, 요청 없음855개 중17개다. 요청 없음 정답435개·오지목403개·실패17개로 합계855개를 유지했다. 실패19개를 제외해 정답률이나 오지목률 분모를 줄이지 않았다. 오류 출력 배열 등을 단일 번호나 null로 고쳐 정답 처리하지 않았다.

[학습판 기본 평가 해시·완료 표시](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308/basic_completion_verified_1328.json) · [B/C 직접 집계·파일 해시](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308/basic_scores_1328.json) · [실행 로그](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308/qlora_eval_winnow_e4b_oos.log). 다섯 파일·835개가 완결이고 호출/읽기 오류0이다. 동일 고정 문항 B(여러 정답 중 하나라도 맞힘)826/835=98.92%, C(전체 정답 목록 일치)760/835=91.02%, 복합66개 제외760/769=98.83%다. 두 요청 문항의 B66/66·C0/66은 단일 항목 출력 계약의 결과이며 복합 요청 지원을 뜻하지 않는다. 원본 H와 학습판 기본835는 서로 다른 세트·실행 경로이므로 직접 정확도 향상 비교로 사용하지 않는다.

## 기반 호환·일감 보충

[공식 Hugging Face revision별 파일 해시](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308/publisher_revisions_1335.json)에서 revision 두 개의 BF16과 Q8 파일 SHA256이 각각 같은 것을 확인했다. [공식 원본 저장소](https://huggingface.co/EldanRing/Winnow-E4B)의 파일 메타데이터를 기존 HfApi로 조회했으며 새 가중치를 받지 않았다. 학습 기반 BF16의 cache SHA256은53c3e504c061f6a7ce84cb6240d427ac6c630850a2cf93f3c2ee980c8136e7e7, GPU 서버 A 기반 Q8의 실제 파일 SHA256은840e3f50e5a9c218727f44e121d1b37cc9e2c3b318c8eb422ba6ef2e27b618a2다. 어댑터 실제 사본 SHA256은3a4f2646ed55ce3758bc0c6e66b6ee005840886c499da4189e2503b2301ef963로 로컬과 같다.

[GGUF 구조 대조](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308/adapter_base_structure_1333.json)는 gemma4 구조와516개 어댑터 텐서의258/258 A/B쌍 입력·출력·rank16 모양을 기존 기반과 확인했다. 이 확인은 GPU 엔진에서 어댑터를 읽고 답한 성공이나 정확도 향상 측정이 아니다. 첫 추가 평가 D3의 실제 로딩·답안·실패를 다음 확인에서 읽는다.

[대기열 추가·백업 근거](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/manifest_winnow_oos_appended_1338.json). 기존17개에 학습판 D3/D/D2/H/MX5개·9,425문항을 추가해 총22개·43,030문항이다. 기존 worker PID가 살아 있는 것을 확인했고, 기존 manifest를 같은 폴더 _backup에 보관한 뒤 임시 파일→원자적 교체로 등록했다. 같은 실행기만 사용하며 현재 Winnow 원본 MX는 계속 실행한다. 입력까지 준비된 대기8개가 확인됐다. 등록된 추가 답안0/9,425개이며 엔진 성공은 대기다.

GPU 서버 B는 첫 보강 자료로 Spark의 본 학습을 시작했고 뒤 학습3개가 예약돼 있다.2개는 기존 기반의 cosine/FINCH이며1개는 Jev 계열 jevify-gemma4-e4b 기반 다운로드가 필요하다. 현재 여유14GB는 다음 다운로드 기준22GB보다 작다. 이미 실행 중인 B54의 임시 Spark 다운로드 폴더 정리 단계 뒤 공간을 다시 확인하며, 여전히 부족하면 건너뛴 후보를 완료로 처리하지 않고 다음 준비 작업과 재개를 기록한다. 이번 작업은 새 삭제 동작을 추가하지 않았다. 진행 중 작업 중단·새 실행기·새 결제·GPU 임대·기존 모델 삭제는 하지 않았다.

## 도구 보완·한계·다음 확인

집계 도구는 모든 모델을 개발사 지시 학습판이라고 잘못 표시할 수 있어 실제 모델 역할 기록 또는 공식 카드 확인 대기 표시를 쓰도록 수정했다. 예전 산출물은 수정하지 않았고 새 Winnow H 집계에 적용했다. 캡처 도구는 새 파일명을 받을 수 있어 부분 평가 검증을 덮지 않고 완결 검증을 새 JSON으로 저장했다. GGUF 헤더 도구는 GPU 계산 없이 구조만 읽는다. 변경·생성 도구와 일일 Markdown/JSON·대기열 JSON·평가/운영 wiki·cs log를 연결했다.

기존 개발/회귀 문항·모델 실행1회다. 독립 고정 보류 자료·반복·전체 원본 비교군 완료 전 상위권이나 서비스 채택을 확정하지 않는다. 말로 한 확신도와 토큰 확률, 모델 변경 정확도와 같은 모델 엔진 속도를 구분한다. 다음 확인은 원본 MX 완료 회수, Spark 단계 변경·다운로드 공간, 학습판 D3 최초 엔진 결과, 나머지 추가 평가 순서다.

스크립트 수정 직전 [백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-08_1329_winnow_role_capture/)과 문서·상태 수정 직전 백업:

- [program/research/daily_rag_slm/_backup/2026-10-08_133908_winnow_eval_queue/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_133908_winnow_eval_queue/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_133908_winnow_eval_queue/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_133908_winnow_eval_queue/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_133908_winnow_eval_queue/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_133908_winnow_eval_queue/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_133908_winnow_eval_queue/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_133908_winnow_eval_queue/slm-model-evaluation.md)
- [final_project_cs/wiki/operations/_backup/2026-10-08_133908_winnow_eval_queue/gpu-work-queue.md](../../../../final_project_cs/wiki/operations/_backup/2026-10-08_133908_winnow_eval_queue/gpu-work-queue.md)
- [final_project_cs/wiki/_backup/2026-10-08_133908_winnow_eval_queue/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_133908_winnow_eval_queue/log.md)
