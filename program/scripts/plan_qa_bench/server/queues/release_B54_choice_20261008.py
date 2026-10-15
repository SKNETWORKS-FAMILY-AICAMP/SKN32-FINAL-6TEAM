"""승인된 기존 첫 자료를 선택해 GPU 서버 B의 선택 대기만 해제한다."""
from pathlib import Path

p = Path('/root/train_choice.txt')
if p.exists():
    print('EXISTING_CHOICE', p.read_text().strip())
else:
    with p.open('x') as f:
        f.write('train_oos.jsonl\n')
    print('CHOICE_CREATED train_oos.jsonl')
