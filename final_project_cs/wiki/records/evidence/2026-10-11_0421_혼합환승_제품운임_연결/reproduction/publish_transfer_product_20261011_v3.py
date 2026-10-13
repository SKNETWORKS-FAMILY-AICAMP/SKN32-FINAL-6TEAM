"""외부 통신 없는 동일 구성의 7개 대조 결과를 최종 보고에 반영한다."""
from pathlib import Path

source = Path(__file__).with_name('publish_transfer_product_20261011.py').read_text(encoding='utf8')
source = source.replace('baseline-three', 'baseline-seven').replace('baseline_three', 'baseline_seven')
source = source.replace('3개', '7개').replace('불일치3', '불일치7').replace(',3개', ',7개')
source = source.replace('불일치3 |', '불일치7 |')
source = source.replace('test_golden, test_contract_keys, test_golden_all_modes.',
                        'test_golden, test_contract_keys, test_golden_all_modes, test_option_ids_mode_tag, '
                        'test_bus_from_place_recheck, test_replan_fare_known_locked, test_bus_cap_zero_keeps_planned.')
source = source.replace('저장된 후보 제외 사유가 현재 탐색 결과와 다르고, basis 계약 기대에 subway_station_version이 빠져 있습니다.',
                        '저장된 후보 제외 사유가 현재 탐색 결과와 다르고, basis 계약 기대에 subway_station_version이 빠져 있습니다. '
                        '로컬 보행망 구성에서는 bus_405가 현재 후보에 없는데도 여러 시험이 그 후보를 고정해 기대하며, 버스 접두의 혼합 경로를 버스 단독으로 간주한 기대도 불일치합니다. '
                        '할인 연결 비활성 대조에도 같은 실패가 남으므로 금액 변경의 회귀로 단정하지 않습니다.')
exec(compile(source, __file__, 'exec'))
