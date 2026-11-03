---
type: guide
title: F3 원문 probe 3건 해소 인계
status: draft
domain: travel
---

# 한 일과 다음 경계

원문 F3 scheduler probe 3건(81행 `paid_called.wait`와 90행 `paid == []`가 서로 모순)을 사용자 지시로 동등 시험 `test_llm_f3_acceptance.py`로 대체했습니다. 원문은 바이트 보존, 같은 시험 바이트로 수정 전 RED 3/3·수정 후 GREEN 3/3, 관련 회귀 208/212(bind 정책 차단 4, 제품 실패 0)로 이전과 동일합니다. 제품 코드·DB·서비스·모델·배포 변경 0.

다음 세션은 원문 3건을 다시 만들지 않습니다. 근거와 한계는 [상세 보고](../records/reports/2026-10-25_f3-contradictory-probe-resolution.md)를 읽습니다.
