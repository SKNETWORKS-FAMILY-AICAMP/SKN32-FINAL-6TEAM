codex
**판정: 고칠 것 있음**

- **`agent_read.py` → `dates.py`: 없는 날짜가 과거 날짜로 채워질 수 있음.**  
  `_grounded_date`: `"return None, False, False"`로 잘못된 날짜를 버린 뒤, `resolve_dates`의 `"if first is not None:"` 경로가 다른 항목에서 얻은 첫날을 채웁니다. 예를 들어 명시적 과거 일정과 `2/30` 항목이 함께 있으면, 없는 날짜 항목까지 과거로 채워져 전부 과거로 거절될 수 있습니다. 잘못된 날짜와 단순 날짜 누락을 구분하고, 전자는 날짜 추론에서 제외해야 합니다.

- **새 테스트가 이 경로를 놓침.**  
  `test_all_past_gate_date_forms.py`: `'{"date": "--02-30"}'`를 `resolve_dates`에 직접 넣습니다. 실제 에이전트 경로에서는 `_grounded_date`가 먼저 이를 `None`으로 바꾸므로 다른 동작입니다. `ground → _agent_rows → review.wholly_past` 경로에서 **없는 날짜 + 명시적 과거 날짜** 조합을 추가해야 합니다. 현재 테스트는 날짜 해석과 판정 사이의 연결만 검증하며, 저장된 revision-1을 읽는 연결까지 검증하지는 않습니다.

나머지는 제시된 코드 기준 **OK**입니다.

- `resolve_dates`가 첫 검사 저장 전에 실행되므로, 정상적인 yearless·year_unverified는 미래 날짜로 저장되어 관문과 충돌하지 않습니다.
- 고정 enum인 `date_form`과 문자열 필드인 `year_quote`는 원문을 스키마 enum에 넣지 않습니다. 원격 커밋이 피한 원문 유출 방식과 다릅니다. 다만 실제 유료 경로 전체의 준수 여부는 제시되지 않은 wrapper 구현까지 확인해야 확정할 수 있습니다.
- 테스트 설명의 **“연도를 적은 지난 날만 … 거절”**은 부정확합니다. `relative`인 어제도 과거로 유지되어 거절 대상입니다.
- Wiki는 앞선 OK 판단에 **“당시 HEAD 2cccbfaef/07dcebe35 기준”** 한정을 붙이면 됩니다.
tokens used
