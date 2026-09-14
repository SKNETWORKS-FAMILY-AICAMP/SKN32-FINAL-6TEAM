# DoD-01 — 원본 v4 파일 hash 가 변경되지 않았다

- v5 §20 항목 1 / 검증 방법: `Get-FileHash A-COP_구현계획서(4).md`
- 실행: 2026-08-12 15:20
- 판정: **통과 (기준선 기록)**

## 재현 명령

```powershell
Get-FileHash "C:\Users\playdata2\Documents\final_workspace\A-COP_구현계획서(4).md" -Algorithm SHA256
```

## 실제 출력 (2026-08-12 15:20)

```
sha256 = b675556cf4d72e64...  (앞 16자, python -m scripts.check_env 출력)
size   = 21,790 bytes
```

전체 hash 는 `python -m scripts.check_env` 의 `v4 원본 존재` 행에서 매번 재계산된다.

## 실행 조건

- 커밋: 8b13fff 직후 (P0)
- 이 저장소(`final_project_sample/`)는 상위 폴더의 계획서 2건을 **읽기만** 한다.
  `RULE.md` §0 · §6 이 수정을 금지한다.

## 남은 것

- 이 값은 **기준선**이다. P10 종료 시 같은 명령으로 재측정해 **일치**를 확인해야 DoD 1 이 최종 통과다.
- `_v5.md` 도 같은 이유로 수정 금지지만 v5 §20 은 v4 만 명시한다. 둘 다 재측정한다.
