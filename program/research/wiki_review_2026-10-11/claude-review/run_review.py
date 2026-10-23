from pathlib import Path
import subprocess,json,datetime,shutil

p=Path(__file__).resolve().parent
q=(p/'review-request-v1.txt').read_text(encoding='utf-8')
q+='\n추가 확인: guardian.is_on은 survey.auto_on_disruption을 호출하고, 이 함수는 survey_answered에 직접 선택 기록이 없으면 False다. pending.decide는 on_disruption을 따로 읽는다. 실제 호출 경로 동작은 이번에 시험하지 않았다. 옛 기본값 설명과 함수별 기준의 차이는 정합성 검사 대상으로 두고 실행 버그로 확정하지 마라.'
dest=p/'review-response-v2.json'
try:
    r=subprocess.run(['claude.cmd','-p','--model','claude-sonnet-5-5','--tools','','--strict-mcp-config','--safe-mode','--no-session-persistence','--output-format','json'],input=q,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240)
    data={'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'requested_model':'claude-sonnet-5-5','created_at':datetime.datetime.now().isoformat()}
except subprocess.TimeoutExpired as e:
    def decode(v):return v.decode('utf-8',errors='replace') if isinstance(v,bytes) else (v or '')
    data={'returncode':124,'stdout':decode(e.stdout),'stderr':decode(e.stderr),'requested_model':'claude-sonnet-5-5','error':'timeout 240s'}
if dest.exists():raise FileExistsError(dest)
dest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('returncode',data['returncode'])
try:
    d=json.loads(data['stdout']); result=d.get('result',data['stdout'])
    (p/'review-response-v2.md').write_text(result,encoding='utf-8')
    print(result);print('modelUsage',list(d.get('modelUsage',{})))
except ValueError:print(data['stdout'][:2000]);print(data['stderr'][:1000])
