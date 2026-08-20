# S-UI-HOVER-JITTER 조사 리포트

## 결론

이번 환경에서는 브라우저 제어 대상이 없어 실제 마우스 오버 재현과 수정 후 브라우저 재검증을 완료할 수 없었다. 따라서 재현하지 못한 현상을 추측으로 고치지 않았다. 이번 작업에서 변경한 코드는 없으며, 이 리포트만 신규 작성했다.

## 확인 환경

- 개발 서버 설정: `.claude/launch.json`
- 설정된 구성: `acop-cs-ui`
- 설정된 포트: `8042` (`--reload`)
- 요청 배경에 적힌 `acop-ui`, `8041`과 실제 저장소 설정이 일치하지 않는다.
- `8042`에서 서버를 실행했다.

## 서버 화면 확인

HTTP 응답은 다음과 같았다.

| 화면 | 결과 |
|---|---:|
| `/ui/cases` | 200, 14,568 bytes |
| `/ui/approvals` | 200, 15,933 bytes |
| `/ui/voc` | 200, 12,965 bytes |
| `/ui/trace` | 404 |

현재 라우트에는 전역 `/ui/trace`가 없고, Case 상세에서 `/ui/cases/{case_id}/trace` 형태로 제공된다.

브라우저 연결을 시도했으나 사용 가능한 브라우저 목록이 빈 배열(`[]`)로 반환되어 실제 hover 이동, DOM의 실시간 위치 관찰, 스크린샷 캡처를 수행할 수 없었다. 따라서 네 화면에서 jitter가 재현됐는지 여부는 판정하지 않았다.

## 소스 및 DOM 응답으로 확인한 사실

- 표 행 하이라이트 규칙은 `app/presentation/ui/theme.py`의 `tbody tr:hover{background:var(--surface-2)}` 하나다.
- 같은 규칙에서 padding, border, height, transform, filter, transition, animation을 변경하지 않는다. 행의 레이아웃 변경으로 hover 경계가 움직이는 구조는 확인되지 않았다.
- `topbar`는 `position:sticky`이지만 불투명한 `background:var(--bg)`를 사용하며 `backdrop-filter`는 현재 CSS에 없다.
- 하이라이트 대상과 hover 대상이 분리된 별도 pseudo-element/overlay 구조도 현재 테이블 생성 HTML(`table > thead/tbody > tr`)에서 확인되지 않았다.
- `nav a`, 접이식 카드 제목, 버튼, stage 제목에는 별도 hover 규칙이 있으나 표 행과 중첩되지 않는다.

위 사실만으로는 후보 원인 중 어느 것도 실제 원인이라고 확정할 수 없다. 특히 현재 브라우저 관찰이 불가능하므로 `theme.py`의 검증된 색상·다크모드·반응형 규칙을 보수적으로 유지했다.

## 테스트

실행 명령:

```text
python -m pytest -q -m "not live"
```

결과: 실패(수집 단계)

```text
3 deselected, 2 warnings, 1 error in 4.70s
ERROR collecting tests/integration/messaging/test_payment_timeout_unknown.py
TypeError: Instance and class checks can only be used with @runtime_checkable protocols
```

실패 지점은 `app/infrastructure/messaging/mock_payment_publisher.py:41`의
`isinstance(MockPaymentGatewayPublisher(), MessageBrokerPort)`이며, hover 변경으로 인한 실패는 아니다.

## 후속 확인 필요

브라우저가 연결되는 환경에서 다음을 다시 수행해야 한다.

1. `/ui/cases`, `/ui/approvals`, `/ui/voc`의 실제 표/목록 행 위를 천천히 왕복 이동한다.
2. Case ID가 있는 경우 `/ui/cases/{case_id}/trace`의 타임라인 항목도 동일하게 확인한다.
3. DevTools에서 hover 전후 행의 `getBoundingClientRect()`와 computed `padding`, `border`, `height`, `transform`, `filter`를 비교한다.
4. jitter가 재현될 때에만 해당 DOM/CSS 원인을 특정하고 최소 변경으로 수정한다.
