# S-PIP-PACKAGE-ACOP-BASEMENT report

## Result

The reusable basement boundary is now `acop_basement/`. The product-owned
composition root remains under `app/`, and the three Composer control-plane
modules are staged under `app/composer_staging/`.

## Changes

- Moved `app/core`, `app/domain`, `app/application`, `app/infrastructure`,
  `app/presentation`, `app/tools`, and `app/introspection` to the matching
  `acop_basement/` paths.
- Moved Composer modules to `app/composer_staging/`:
  `composer_service.py`, `api_composer.py`, and `composer_auth.py`.
- Updated Python imports, runtime entry points, Docker, and launch settings to
  use `acop_basement.*`; Composer imports use `app.composer_staging.*`.
- Added `acop_basement*` to setuptools discovery and updated the explicit
  seven-component basement manifest.
- Updated the architecture boundary test and export tests for the new root.

## Verification

- `python -m pytest tests/architecture -q`: **72 passed**.
- `python -m pytest tests/unit/scripts/test_export_basement.py -q`: **2 passed**.
- `python -m compileall -q app acop_basement scripts eval examples tests`: passed.
- `python -m scripts.export_basement`: exported **61 files** from
  `acop_basement/**`.
- `python -m pip wheel . --no-deps --no-build-isolation`: passed; wheel package
  discovery includes `acop_basement` and its subpackages.
- Import smoke test from the repository: passed (`OK`).

The requested full pytest command reached approximately 20% and then exceeded
the 120-second execution limit without a failure report, consistent with an
environment-dependent integration wait. Editable installation was also blocked
by the environment's restricted access to PyPI build isolation and the user
site-packages directory; the no-isolation wheel build succeeded.
