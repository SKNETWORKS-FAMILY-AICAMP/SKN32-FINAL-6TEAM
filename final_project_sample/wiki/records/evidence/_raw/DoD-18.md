# DoD-18 실측 원문 (수집: Codex, 판정 없음)

## 재현 명령
```powershell
$p=Start-Process python -ArgumentList '-m','uvicorn','app.presentation.api.app:app','--host','127.0.0.1','--port','8765' -PassThru; ... Invoke-WebRequest /ui/cases /ui/approvals /ui/voc /ui/cases/{id}; Stop-Process
```

## 실제 출력
```
PATH=/ui/cases STATUS=200
<!doctype html><html lang='ko'><head>...<title>Case 목록</title>...
PATH=/ui/approvals STATUS=200
<!doctype html><html lang='ko'><head>...<title>Approval</title>...
PATH=/ui/voc STATUS=200
<!doctype html><html lang='ko'><head>...<title>VOC 일일 리포트</title>...
PATH=/ui/cases/00000000-0000-0000-0000-000000000000 STATUS=200
<!doctype html><html lang='ko'><head>...<title>Case 상세</title>...
SERVER_PID=29188 STOPPED
```

## 관측 사실
- 네 UI 경로의 HTTP 상태 코드는 모두 200이다.
- 본문 일부에 각각 `Case 목록`, `Approval`, `VOC 일일 리포트`, `Case 상세` title이 포함되어 있다.
- 서버 PID 출력은 29188이고 종료 출력은 `STOPPED`이다.

## 확인하지 못한 것
- 브라우저에서 CSS와 상호작용을 시각적으로 확인한 결과는 수집하지 못했다.
