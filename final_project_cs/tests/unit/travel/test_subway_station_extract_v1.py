"""공식 역ID 추출의 자료 무결성. 실제 도착 조회나 역명 유사도 시험이 아니다."""
import pytest

from scripts.mobility.build_subway_realtime_stations import HEADER, build_snapshot, canonical_line, extract_file


def build(rows):
    return build_snapshot([HEADER, *rows], source_sha256='controlled-source-hash', basis_date='2026-09-02')


def test_homonyms_keep_line_and_exact_official_ids():
    result = build([(1005, 1005000522, '양평', '5호선'), (1063, 1063075135, '양평', '경의중앙선')])
    assert [r['station_id'] for r in result['stations']] == ['1005000522', '1063075135']
    assert result['station_count'] == 2 and result['line_count'] == 2
    assert not result['connected_to_departure']


def test_string_id_leading_zero_and_official_query_name_survive():
    result = build([('01002', '001234', '천호(풍납토성)', '02호선')])['stations'][0]
    assert result['line_id'] == '01002' and result['station_id'] == '001234'
    assert result['query_station'] == '천호(풍납토성)' and result['line'] == '2호선'
    assert result['source_row'] == 2


@pytest.mark.parametrize('value', [None, True, False, 0, -1, 12.0, '1.0', '', '\u00b2'])
def test_malformed_id_is_rejected(value):
    with pytest.raises(ValueError):
        build([(1002, value, '강남', '2호선')])


@pytest.mark.parametrize('row', [(1002, 123), (1002, 123, '', '2호선'),
                                 (1002, 123, '강남', None), (1002, 123, [], '2호선')])
def test_malformed_row_is_rejected(row):
    with pytest.raises(ValueError):
        build([row])


@pytest.mark.parametrize('rows', [
    [(1002, 123, '강남', '2호선'), (1002, 123, '역삼', '2호선')],
    [(1002, 123, '강남', '2호선'), (1002, 124, '강남', '2호선')],
    [(1002, 123, '강남', '2호선'), (1002, 124, '역삼', '7호선')],
    [(1002, 123, '강남', '2호선'), (1007, 124, '역삼', '2호선')],
])
def test_duplicate_and_conflicting_identity_are_rejected(rows):
    with pytest.raises(ValueError):
        build(rows)


def test_missing_or_wrong_header_is_rejected():
    for rows in [[], [HEADER], [('station', 'line')]]:
        with pytest.raises(ValueError):
            build_snapshot(rows, source_sha256='hash', basis_date='2026-09-02')


def test_line_normalization_does_not_merge_other_lines():
    assert canonical_line('02호선') == '2호선'
    assert canonical_line('경의선') != canonical_line('경의중앙선')


def test_existing_output_is_preserved_before_source_read(tmp_path):
    out = tmp_path / 'existing.json'
    out.write_text('previous evidence', encoding='utf8')
    with pytest.raises(FileExistsError):
        extract_file(tmp_path / 'missing.xlsx', out, basis_date='2026-09-02')
    assert out.read_text(encoding='utf8') == 'previous evidence'
