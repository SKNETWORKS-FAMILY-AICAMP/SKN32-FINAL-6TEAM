# -*- coding: utf-8 -*-
"""산출물 문서를 한 번에 다시 만든다.

실행: python program/산출물양식/_build/build_all.py

주의. 결과 파일을 Word 나 Excel 로 열어 두면 덮어쓸 수 없다.
그때는 옆에 _새버전 이름으로 저장되니, 프로그램을 닫고 다시 실행하거나
_새버전 파일을 원래 이름으로 바꾸면 된다.
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STEPS = ["build_기획서.py", "build_화면설계서.py", "build_아키텍처.py",
         "build_요구사항정의서.py", "build_데이터정의서.py", "build_DB설계서.py"]

print("도표부터 만든다.")
runpy.run_path(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))),
                            "program", "plan", "diagram", "make_charts.py"),
               run_name="__main__")
for s in STEPS:
    print("\n[%s]" % s)
    runpy.run_path(os.path.join(HERE, s), run_name="__main__")
print("\n전부 끝났다.")
