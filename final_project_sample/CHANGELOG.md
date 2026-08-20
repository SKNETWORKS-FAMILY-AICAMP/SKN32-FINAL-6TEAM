# Changelog

All notable changes to the `basement` package are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/).

## [0.3.0] - 2026-08-19

### Changed

- **Breaking (import path):** the domain-free basement layer moved from the
  `app.*` top-level package to a new, independently installable package,
  `acop_basement` (`core`, `domain`, `application`, `infrastructure`,
  `presentation`, `tools`, `introspection`). This lets a consumer such as
  `final_project_cs`, which owns its own local `app.*` package for its
  domain Team modules, `pip install` basement without a top-level package
  name collision. `app.modules` (domain examples) and `app.composition`
  (the composition root) stay local to this repository as before.
- Composer's write channel (`composer_service.py`, `POST /composer/*`,
  `/auth/token`) moved out of `acop_basement` entirely into its own optional
  package, `acop_composer` — a "management build" concern, not something
  every basement consumer needs. `acop_basement.presentation.api.app
  .create_app()` now takes `composer_write_router`/`composer_auth_router`
  as optional keyword arguments instead of importing them unconditionally;
  passing nothing yields a Composer-free app (this repository's own
  `app.entrypoint:app` wires `acop_composer` in for local/reference use).
- The domain migration (`002_domain_customer_ops.sql`) moved out of the
  basement package into `config/migrations/` — a domain-free package must
  not ship domain-specific schema. `acop_basement.infrastructure.db.migrate`
  now applies core and domain migrations together, sorted by filename.
- `scripts/basement_manifest.py` and `docs/handoff/15` updated to the new
  component paths; `pyproject.toml` package discovery includes
  `acop_basement*` and `acop_composer*` alongside `app*`.

★검수 중 되돌린 시행착오 — 처음엔 Composer 세 파일을 `app/composer_staging/`
(product-local, non-package)로 옮겼는데, `program/plan/A-COP_Composer_v3_
설계_토글전용_UI이관.md`를 다시 확인한 뒤 그게 잘못된 해석이었음을 확인해
되돌렸다. 실제 구조는 `acop_basement`(항상 설치, Composer 없음)/
`acop_composer`(별도 선택 패키지, 관리용 빌드에만)/`final_project_ui`(패키지
아닌 독립 서비스)의 3분리다.

## [0.2.0] - 2026-08-18

### Added

- Composer write channel v2 with short-lived HMAC JWTs and separated
  `composer:read`, `composer:validate`, and `composer:write` scopes.
- Response Generation & Review Team (DoD-29), including deterministic review
  for prohibited terms, factual grounding, PII, and rule-based tone selection.
- Regression coverage for expired and forged Composer JWTs.

### Changed

- Billing/Subscription and Technical/Entitlement Teams were moved to
  `examples/` and removed from production routing/configuration while their
  example implementations remain available to evaluation.
- Composer audit output is injectable through application state, preventing
  test runs from writing to the repository's live audit path.

### Fixed

- A failure during the `CLASSIFIED` state transition is no longer reported as
  `classification_failed`; classifier failures and transition failures retain
  their distinct meanings.

The entries above are summarized from commits `c1b1a4a`, `17253ff`, `807bd2c`,
and `be298c7`.

## [0.1.0]

Initial `basement` version recorded in the package metadata. This section is a
historical baseline only; the repository has no earlier versioned changelog or
release tag from which to reconstruct a more detailed change list.

[0.3.0]: https://github.com/roroblack/A-COP/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/roroblack/A-COP/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/roroblack/A-COP/releases/tag/v0.1.0
