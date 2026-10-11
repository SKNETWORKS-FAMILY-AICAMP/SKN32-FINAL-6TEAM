-- 중앙 설정 저장소 — 대상 하나당 선언 한 행.
--
-- ★왜 (program/plan/A-COP_Composer_중앙설정저장소_결정.md)
--   선언이 대상마다의 로컬 파일이면 그 파일을 고치는 코드가 대상 안에 있어야
--   한다. 고객 릴리즈에 쓰기 코드를 넣을 수 없고, 대상이 수천 개면 "관리할
--   때만 다시 넣는다" 도 성립하지 않는다. 그래서 선언을 여기 한 곳에 둔다.
--   대상은 자기 행을 **읽기만** 한다.
--
-- ★revision 은 선언 내용에서 계산한 값이다(ProjectConfig.compute_revision).
--   여기 같이 저장하는 이유는 조건부 UPDATE(CAS)에 쓰기 위해서다 — 별도의
--   진실이 아니다. 둘이 어긋나면 declaration 이 맞다.
--
-- ★재실행 안전하다.

CREATE TABLE IF NOT EXISTS project_configs (
    -- 어느 대상의 선언인가. 배포 인스턴스를 가리키는 키다(업무 개념인
    -- tenant_id 와 일부러 분리한다 — 한 테넌트가 여러 배포를 가질 수 있다).
    deployment_id   TEXT PRIMARY KEY,
    declaration     JSONB       NOT NULL,
    revision        TEXT        NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 관리 화면이 "최근 바뀐 순" 으로 대상을 훑는다.
CREATE INDEX IF NOT EXISTS project_configs_updated_at_idx
    ON project_configs (updated_at DESC);
