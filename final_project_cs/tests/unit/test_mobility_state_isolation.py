# -*- coding: utf-8 -*-
"""앞 시험이 이동 계산기를 「꺼짐」으로 바꿔 놓아도 뒤 시험은 깨끗한 상태로 시작한다 - 이동 담당 보고서 #54.

두 시험은 **이 파일 안의 순서**대로 돈다. 앞 시험이 서버 조립과 같은 일(설정 비움 → 꺼짐)을 하고, 뒤 시험이 그 흔적이 없는지 본다.
"""
from app.modules.travel_ops.mobility import wiring
from app.modules.travel_ops.mobility.engine import paths


def test_a_test_that_disables_the_engine_like_the_server_assembly_does():
    wiring.configure(data_dir="")                      # build_registry 가 설정이 비면 하는 일
    assert paths.SOURCE == "disabled" and wiring.mode() == "disabled"


def test_the_next_test_starts_from_the_initial_state_not_from_a_disabled_one():
    assert paths.SOURCE == "unset", "앞 시험(또는 import 때 만든 앱)의 꺼짐이 남아 이동 시험이 자료 없음으로 건너뛰어진다"
    assert wiring.mode() == "unconfigured"
