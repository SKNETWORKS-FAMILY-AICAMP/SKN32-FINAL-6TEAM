import pytest
from app.infrastructure.db.migration_sql import atomic_sql


def test_preserves_unicode_comments_strings_and_function_body():
    body = '''
-- COMMIT; 서울
/* BEGIN; /* COMMIT; */ 끝 */
CREATE TABLE "BEGIN" (value text);
INSERT INTO "BEGIN" VALUES ('COMMIT; 한글'), (E'BEGIN;\\nCOMMIT;');
CREATE FUNCTION migration_phrase() RETURNS text LANGUAGE plpgsql AS $fn$
BEGIN
  RETURN $inner$COMMIT; BEGIN; 서울$inner$;
END;
$fn$;
'''
    source = '/* 앞 */ BEGIN;\n' + body + '\nCOMMIT; -- 뒤'
    result = atomic_sql(source, 'test.sql')
    assert body in result
    assert '/* 앞 */' in result and '-- 뒤' in result
    assert len(source) == len(result)
    assert source.count('\n') == result.count('\n')


@pytest.mark.parametrize('source', [
    'BEGIN; SELECT 1; COMMIT; SELECT 2;',
    'BEGIN; SELECT 1; ROLLBACK;',
    'BEGIN READ ONLY; SELECT 1; COMMIT;',
    'BEGIN; SELECT 1; COMMIT AND CHAIN;',
    'SAVEPOINT x; SELECT 1; RELEASE x;',
    'COMMIT;',
    'BEGIN; SELECT 1;',
    "PREPARE TRANSACTION 'x';",
    "BEGIN; SELECT 1; COMMIT; BEGIN; SELECT 2; COMMIT;",
    "SET TRANSACTION READ ONLY;",
    "SET SESSION CHARACTERISTICS AS TRANSACTION ISOLATION LEVEL SERIALIZABLE;",
    "SET transaction_read_only = on;",
])
def test_rejects_transaction_controls_that_change_atomic_contract(source):
    with pytest.raises(ValueError):
        atomic_sql(source, 'bad.sql')


@pytest.mark.parametrize('source', [
    'SELECT 1;', '-- BEGIN;\nSELECT $$COMMIT;$$;',
    'CREATE FUNCTION x() RETURNS int LANGUAGE SQL BEGIN ATOMIC SELECT 1; END;',
])
def test_unwrapped_sql_is_identical(source):
    assert atomic_sql(source, 'plain.sql') == source


def test_start_transaction_end_aliases_are_supported():
    assert 'SELECT 1' in atomic_sql('START TRANSACTION; SELECT 1; END;', 'aliases.sql')
