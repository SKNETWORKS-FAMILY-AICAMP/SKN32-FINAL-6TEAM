"""승인 실패가 화면에 드러나는지 검사한다.

★결함이었던 것: `approve()` 의 두 분기가 **같은 RedirectResponse** 를 냈다.

    if response.is_error:
        return RedirectResponse("/ops/approvals", 303)
    return RedirectResponse("/ops/approvals", 303)

승인이 실패해도 운영자는 목록으로 돌아올 뿐 무엇이 잘못됐는지 알 수 없었다.
승인은 되돌릴 수 없는 행위인데 실패를 삼키면 "눌렀으니 됐겠지" 로 넘어간다.
CLAUDE.md §3 — 조용한 스킵을 만들지 않는다.

★검사하지 않는 규칙은 지켜지지 않는다. 그래서 테스트로 고정한다.
"""
from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from acop_basement.presentation.api.app import app


def test_failed_approval_shows_the_reason_instead_of_a_silent_redirect():
    client = TestClient(app)
    # 존재하지 않는 case/action → 하위 API 가 404 를 낸다
    response = client.post(f"/ops/approvals/{uuid4()}/{uuid4()}", data={"decision": "approved"},
                           follow_redirects=False)

    # ★조용한 303 이면 안 된다
    assert response.status_code != 303, "승인 실패가 성공과 같은 리다이렉트로 삼켜졌다"
    assert response.status_code == 200
    body = response.text
    assert "승인이 처리되지 않았습니다" in body
    assert "404" in body
    # 목록으로 돌아갈 길은 남겨 둔다
    assert "/ops/approvals" in body
