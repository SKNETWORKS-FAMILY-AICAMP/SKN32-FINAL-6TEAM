from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
source = HERE/'walk_web_20261010_v1.py'
text = source.read_text(encoding='utf8')
prefix = text.split('EV.mkdir(exist_ok=False)')[0]
helpers = text.split('def sha(p):')[1].split('old = json.loads')[0]
run = text.split('attempts = []')[1]
run = run.replace("data_dir=str(ROOT/'datasets/mobility/processed/mobility')", "data_dir=str(ROOT/'datasets/mobility/processed')")
code = prefix + '\ndef sha(p):' + helpers + '\nfacts = json.loads((RAW/"web-facts-v1.json").read_text(encoding="utf8"))\n'
code += 'baseline = json.loads((EV/"baseline-v1.json").read_text(encoding="utf8"))["hashes"]\n'
code += 'attempts = []' + run
exec(compile(code, str(source), 'exec'))
