"""종료한 담당의 고객 신고 화면 접합을 백업 후 마무리합니다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import shutil
import json

ROOT = Path(__file__).resolve().parents[5]
CS = ROOT / "final_project_cs"
STAMP = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d_%H%M%S")
BACKUP = CS / "_backup" / f"{STAMP}_support_copy_integration"
WEB = "frontend/apps/web/"
changes = {
    WEB + "src/features/support/support.tsx": {
        't("문의하기", "Contact support")': 't("문제 신고·건의 기록", "Reports and suggestions")',
        't("문의 내용", "Message")': 't("신고·건의 내용", "Report or suggestion")',
        't("문의 보내기", "Send inquiry")': 't("내용 기록하기", "Record report")',
        't("문의를 불러오고 있어요.", "Loading your inquiries.")': 't("접수 기록을 불러오고 있어요.", "Loading your reports.")',
        't("아직 접수한 문의가 없어요. 위에서 첫 문의를 보내 주세요.", "No inquiries yet. Send your first inquiry above.")': 't("아직 접수한 기록이 없어요. 위에서 문제나 건의를 남겨 주세요.", "No reports yet. Record a report or suggestion above.")',
    },
    WEB + "src/features/support/service-notices.tsx": {
        't("문의하기", "Contact support")': 't("문제 신고·건의 기록", "Reports and suggestions")',
    },
    WEB + "src/app/support/page.tsx": {
        '["문의하기", "Contact support"]': '["문제 신고·건의 기록", "Reports and suggestions"]',
    },
    WEB + "src/features/profile/profile.tsx": {
        't("문의하기 · 내 문의와 답변", "Contact support · My inquiries")': 't("문제 신고·건의 기록", "Reports and suggestions")',
    },
    WEB + "tests/live/support.spec.ts": {
        '"문의 내용"': '"신고·건의 내용"', '"문의 보내기"': '"내용 기록하기"',
        '"문의하기 · 내 문의와 답변"': '"문제 신고·건의 기록"',
        '"No inquiries yet. Send your first inquiry above."': '"No reports yet. Record a report or suggestion above."',
    },
    WEB + "tests/live/uiux-sonnet-trip-20261012.spec.ts": {
        '"문의 내용"': '"신고·건의 내용"', '"문의 보내기"': '"내용 기록하기"',
    },
}
updated = []
for relative, replacements in changes.items():
    target = CS / relative
    old = target.read_text(encoding="utf-8")
    new = old
    for before, after in replacements.items():
        if before not in new:
            raise RuntimeError(f"Expected copy is missing: {relative}: {before}")
        new = new.replace(before, after)
    saved = BACKUP / relative
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, saved)
    target.write_text(new, encoding="utf-8")
    updated.append(relative)
print(json.dumps({"backup": str(BACKUP), "updated": updated}, ensure_ascii=True))
