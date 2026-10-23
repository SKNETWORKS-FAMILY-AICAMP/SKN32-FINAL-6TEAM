"""대기 작업의 공간과 입력 조건을 읽고 새로운 관측 파일에 저장한다."""
import sys, json, subprocess
from pathlib import Path
if '--remote' in sys.argv:
    m=sys.argv[-1]
    disk=subprocess.getoutput('df -B1 /root /tmp /workspace 2>/dev/null').splitlines()
    result={'disk': [' '.join(line.split()[1:]) for line in disk[1:]]}
    if m=='B':
        result['configs']={str(p):p.exists() for p in [Path('/root/hf_models/spark_s1_4b/config.json'),Path('/root/hf_models/jevify_e4b/config.json'),Path('/root/hf_models/gemma-4-E4B-it/config.json')]}
        result['download_space_check']=subprocess.getoutput('df -BG --output=avail /root')
        result['b56_status']={str(p):p.read_text(errors='replace')[-3000:] for p in Path('/root/daily_rag_20261008').glob('*.log')}
    else:
        manifest=json.loads(Path('/tmp/tripilot-a-backlog-20261008/manifest.json').read_text())
        result['job_inputs']={j['id']:all(Path(j[k]).exists() for k in ['model','prompts','script']) for j in manifest['jobs']}
    print(json.dumps(result,ensure_ascii=True))
else:
    sys.stdout.reconfigure(encoding='utf-8')
    m,alias=sys.argv[1:3]
    root=Path(__file__).resolve().parent
    run=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',alias,'python3 - --remote '+m],input=Path(__file__).read_text(encoding='utf-8'),capture_output=True,text=True,encoding='utf-8',timeout=60)
    if run.returncode: raise RuntimeError(run.stderr)
    data=json.loads(run.stdout)
    with (root/'results/gpu_backlog_20261008'/f'{m}_conditions_1023.json').open('x',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2)
    print(json.dumps(data,ensure_ascii=False))
