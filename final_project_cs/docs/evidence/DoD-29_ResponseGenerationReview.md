# DoD-29 — Response Generation & Review 검증

- v8 §27 신설 항목 / 근거: `docs/reports/2026-08-19_DoD29-사실수집.md`(사실 수집,
  Codex) + 이 문서(판정, Claude)
- 판정: **통과** (2026-08-20 배선·golden/holdout 커버리지 완료로 갱신 —
  근거: `docs/reports/2026-08-20_S-DOD29-COMPLETE_리포트.md`)

## 재현 명령과 실제 출력

```powershell
python -m pytest tests/unit/teams/test_response_review.py -v
```
```
6 passed in 1.17s
```

## 통과한 것

- **단위 테스트 6종** — 정상 응답 1회 통과, 금칙어 재시도, PII 즉시
  escalate(재시도 없음), 환불 상한 초과 fact_mismatch, 4회 실패 시
  `review_retries_exhausted`, 정책·톤 결정론 검증. 전부 v8 §8-B 의 설계
  (톤결정→GEN→결정론 REV→LLM 톤 REV, 최대 3~4회, PII 즉시 escalate)와
  일치.
- **기존 할루시네이션 방어 재사용** — `app/core/verification.py` 의
  `verify_proposal`/`Facts` 를 새로 안 만들고 그대로 재사용해 사실대조를
  한다. 검증된 메커니즘 위에 얹었다.
- **`TeamResult` 계약 무변경** — v8 이 요구한 매핑(`final_response_text`→
  `answer`, `retry_count`/`review_history`→`decisions[]`, 반려 사유→
  `warnings[]`, `escalation`→`outcome`/`next_action`)을 계약 스키마
  변경 없이 구현했다(`ConfigDict(extra='forbid')` 위반 없음).
- **잠재 결함 1건을 등록 전에 미리 잡았다** — `app/composition.py` 의
  Team 조립기가 `ResponseGenerationReviewTeam(llm=None)` 처럼 단일 인자
  생성자를 개수만 보고 판단해 `ReadToolbox` 를 `llm` 자리에 잘못 넣는
  결함을 발견·수정했다(`docs/reports/debugs/2026-08-19_composition_단일인자_Team_llm_오배선.md`).
  등록 안 된 상태에서 발견해 실제로 터지기 전에 막았다.

## ★통과로 갱신된 이유 (2026-08-20)

| 항목 | 상태 |
|---|---|
| 단위 테스트(결정론 REV 4종 + 톤 검증) | **통과** |
| `TeamResult` 계약 무변경 매핑 | **통과** |
| ~~`config/project.yaml` 미등록~~ → **통과** | `teams:` 에 등록 완료
  (`implementation_ref: app.modules.customer_ops.response_review:ResponseGenerationReviewTeam`).
  `Controller._maybe_review()` 가 실행 직후 hook 으로 연결됐다 — 다른
  Team 이 만든 `TeamResult.answer` 를 `response_review.enabled` 설정이
  켜져 있을 때만 2차 검증하는 방식. **기본값은 꺼짐**(`enabled: false`) —
  이건 미완성이 아니라 의도된 설계다(안전한 기본값, 팀이 배포 시점에
  켜는 운영 결정). `registry.get()` 경유로 호출해 Core-Team import 금지
  원칙을 지켰다. 근거: `docs/reports/2026-08-20_S-DOD29-COMPLETE_리포트.md`. |
| 실 LLM 호출 검증 | **통과** — `tests/live/test_response_review_live_smoke.py`,
  `1 passed in 10.13s`(2026-08-19 확인). |
| ~~golden/holdout 커버리지 없음~~ → **통과** | v8 §1031 배분(golden 12·
  holdout 4)대로 `eval/datasets/golden.jsonl`·`holdout.jsonl` 에 추가
  완료(`g-response-review-*`/`h-response-review-*`). 전체 golden 72·
  holdout 24, 중복·교집합 없음 확인. 근거: 동 리포트. |
| 배선 통합 테스트 | **통과** — `tests/integration/controller/test_response_review_wiring.py`
  2건(꺼짐 시 회귀 없음, 켜짐 시 검수 결과 반영). 전체 `python -m pytest
  -q -m "not live"` → `329 passed, 3 deselected, 0 failed`(Claude 실
  환경 재확인, 기준선 327 대비 +2). |

## 남은 것 (DoD 판정과 무관, 운영 결정 사안)

- `response_review.enabled` 를 실제로 언제 켤지는 팀의 운영 판단이다 —
  코드·테스트·데이터는 전부 준비됐다.
- 켰을 때 실제 Case 트래픽에서 review pass 의 지연시간·비용 영향은
  아직 측정 안 됨(이번 작업 범위 밖).
