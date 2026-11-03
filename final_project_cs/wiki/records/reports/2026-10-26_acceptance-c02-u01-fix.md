# 2026-10-26 수용 C02·U01 실패 — 원인 확정·C02 생성 문법 수정·U01 계약 보고

- 작성: 2026-10-26 (KST), Claude Opus 하위 작업자. 원본 코드 수정·커밋·push·x600·live(8042/3100) 교체 없음(부모 몫).
- 기준 코드: temporal/F02 최종 후보 `cache/scratch/f02-origin-20261025-201456-5daacb/source` 사본(`decision_unit.py` SHA256 `040a8a5a…`, integ-v8 source와 같음).
- 후보 폴더: `C:\Users\kcxsz\AppData\Local\hermes\profiles\guguroute\cache\scratch\c02-u01-fix-20261026-011759-27440\` (상세 `REPORT_KO.md`).

## 결론

| 건 | 원인 | 조치 | 시험 | 실모델 |
|---|---|---|---|---|
| C02 「1월 2일 일정을 전부 보여줘」 | E4B가 목록 읽기 `schedule`에 엉뚱한 대상 `i2`·범위 `today`(지금=여행 전날)·같은 대상 후보를 냄 → 서버가 계약대로 해석 실패(`목록 조회의 범위·행동이 유효하지 않습니다`) | `decision_unit._schema` 생성 문법만 수정: 목록 읽기 전용 갈래(대상·변경 대상 none, 범위 필수, 후보 0), 문장에 적힌 일정 달력 날짜로 범위 날 제한(숫자 경계 포함). 답 고쳐 쓰기·서버 완화 없음 | 신규 RED 5/7 실패 → GREEN 7/7; 관련 163/163; 합집합 기준 1383/1383, 후보 1390/1390 = 100% | 2/2회: 수정 전 재현 실패 1, 수정 후 **통과 15/15 검사**(1월 2일 3개 정확, 판 1→1) |
| U01 「내 예약을 취소하고 카드로 환불해줘」 | 모델 `ask_policy` → `answered / decision_ask_policy`(규정 자료 없음 안내, 실행 0). 실패는 판정기의 공개 `unsupported` 표식 요구 | **수정 보류**: 웹 메시지 `reason=decision_<action>`(web-intakes), 채팅 공개 `unsupported` 상태·이유 값은 계약에 없음. 행렬도 `answered` 허용·`contract_resolution_required` 표시 | — | 0회 |

- patch `c02-product.patch` SHA256 `18fa52d719f448d3442c6ae05bfe0c52013ea923fea4aecf749e8128b5929408`(CRLF 보존, `git -c core.autocrlf=false apply` roundtrip 2/2 해시 일치). 변경 파일: `app/domains/travel_ops/components/conversation/decision_unit.py`, 신규 `tests/unit/travel/test_list_read_quoted_day_generation.py`.
- 통합 충돌 예상: `decision_unit.py` `_schema`(약 375–548행) 한 곳. 현재 integ-v8 source에 `apply --check` 통과(검사만).

## 남은 결정·한계

- U01: 업체 예약 취소·환불 실행 요청의 채팅 공개 표식을 계약에 넣을지(그러면 `UNSUPPORTED` 확장 + wiki 선행), 아니면 판정기를 현재 계약(`answered`)에 맞출지 결정 필요.
- 문법 변경은 모든 채팅 해석에 적용되나 실모델 확인은 C02 1문장뿐. 49건 재실행 필요.
- 시각 범위 옮기기의 기존 `day_quotes`는 숫자 경계 없는 비교를 유지(「11월 2일」 오인 가능) — 후속 후보.
- 첫 base 합집합이 f02-origin `external-dining/runtime4/policy-counters.json`·`last-egress-block.json`을 덮어씀(제 하네스 실수). 만든 `__pycache__` 2개는 삭제, JSON은 이전 값 근거가 없어 그대로 두고 보고. 이후 내 폴더 사본으로 재실행했고 다른 외부 폴더 새 파일 0.
