# I-2 실사용 문서 격리 후보 — 인계

## 현재 결론

팀 role-manager pin `93c7ba8e` 가 현재 원격과 같다(팀·개인 role-manager 모두). 관리자 사용자 계약 문장은 18/19 = 94.7% 가 pin 코드와 일치하고, 부분 일치 1건은 대화 정렬이 turn_id 저장 순서라는 점이다. UTIC 설명은 5/6 = 83.3% 가 일치하고, 「운영 검증 전」 문장은 10-18 12:20 오라클 반영 기록과 맞지 않아 정정했다. 문서 후보는 격리 bare 저장소와 패치로만 만들었다. 원본 쓰기 0, 커밋·push 0. [보고서](../records/reports/2026-10-27_finalspace-i2-doc-candidate.md)

## 한 일 목록

- `git ls-remote` 로 팀·origin role-manager = `93c7ba8e` 를 확인했다.
- `admin_api.py`·`admin_users.py`·`ops_entrypoint.py`·관리자 웹 중간 경로·화면, `guardrails.yaml`·`base.py` 를 문장별로 대조했다.
- 후보 A(색인 1줄 + `admin-users.md` 정정판 + UTIC 문단)와 B(링크 대상 10-18 보고서 2건 원문)를 만들었다. apply-check·tree 왕복 3/3, `diff --check` 0줄.
- 새 파일: 보고서, `wiki/records/evidence/2026-10-27_finalspace-i2-doc-candidate/`(claims.json, 패치 3개), 이 인계. 목차는 고치지 않았다.

## 다음

1. 반영 결정: A 는 권장, B 는 선택이다(B 안 로컬 링크 8개는 저장소에서 끊긴다). 반영은 pin 위에서 `git apply` 로 하고 두 role-manager 에 함께 푸시한다(이번에는 금지라 하지 않았다).
2. 시험 공백: users 목록·대화 API 시험 0개, utic_timeout 시험 0개.
3. 이어서 I-1 → I-3 → I-4 순서로 진행한다.
