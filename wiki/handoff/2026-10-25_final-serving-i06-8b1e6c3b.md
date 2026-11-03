# 부모 전용 인계 — I06 frozen 후보 교체 금지

후보: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/final-serving-i06-20261025-203428-8b1e6c3b`.

**PARENT_SWAP.json = HOLD_DO_NOT_SWAP**. 명시고정 실2/2, 고정하지마1/1은 통과했으나 booked-only0/1에서 `예약 완료`→locked=true가 실제 저장·GET까지 이어졌습니다. frozen source를 실I06 후 수정하지 않았습니다. 이 후보를 통과본으로 교체하지 마세요. 실제 dispatch5/8 후 lease반환/inflight0/sharedidle 확인.

최종 단일 exact union2174/2184=99.54%(기존동일8fail,2skip). F02 1389/1389·hours180/180·I06 9/9·추가9/9·date12/12. 실JUnit `union-final.xml`, `real-I06-junit.xml`; 실제 API원문/claim/review/GET 증거 `real-runs/*/private/I06-stored-source-proof.json`. 상세 `REPORT_KO.md`, `FINAL_ACCEPTANCE.json`, `UNION_ACCOUNTING.json`. 원 실패·coldtimeout·oracle교정·donor namespace오염 모두 별도 보존.

full serving launch 조립 preflight RC0. exact argv와 runtime-inputmanifest/sourceclosure는 `PARENT_SWAP.json`, `runtime-serving/SERVING_FREEZE.json`에 있습니다. 새 launcher는 준비만 했고 실행리스너는 시작하지 않았습니다.

미래 launch(현재 실행금지):
`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/api-runtime-20261025-014236/venv/Scripts/python.exe -B C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/final-serving-i06-20261025-203428-8b1e6c3b/runtime-serving/launch-serving.py`

정확 현재 live-v7 rollback:
`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/api-runtime-20261025-014236/venv/Scripts/python.exe -B C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/action-v7-20261025-182455-ca136945/runtime-v7-serving/launch-serving.py`

현재 listenerPID27184/8042, 부모 handle proc48790b56e85d. source-v7 4894파일 SHA 불변. child는 kill/restart/교체0. parent만 최종포트 소유합니다.

allpast owner4f67652c 작업트리/commit 병합0. 후속 최소 pipeline 충돌표: `app/domains/travel_ops/components/intake/pipeline.py::_agent_rows`, title claim 직후 명시 bool+Quote→items[i].locked claim 한 hunk. pre `c8338d7972c5704c925abb3781b5dd61ee9da088571247d79cbaa406450cb89d`, post `cece7b211c7c601621d8fd641212b1dea20fcbdd50dc021adf6d4cfcf4fd2dc0`. hotfix 뒤 전체파일 역복사가 아닌 부모3way hunk 조율 필요. booked-only blocker를 먼저 해결할 새 candidate/lease가 필요합니다.

고객27107a20 rev2 revalidate는 미실행/별도 승인. 고객원문·선택·revision 직접쓰기0. 원본 wiki의 이 고유보고서/인계 추가 외 제품 코드·mutable index 변경0. Git push0.
