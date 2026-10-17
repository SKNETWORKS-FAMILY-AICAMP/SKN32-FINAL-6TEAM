# Develop route and lodging integration — 2026-10-17

Integrated develop 6fc4a2d5 with manager 7fe1b890. Preserved develop Dining/SNS and Activity changes, lodging/meal candidate linkage, and clearRegistrationDraft after registration. Map producer changes add route loading/retry, sizing and provider fit-padding. Breakfast keeps its business kind; selected hotel summary uses displayKind and explicitly labels lodging.

## Corrections and evidence

The atomic taxi-edit regression failed because lodging linkage unnecessarily loaded a review for unrelated edits. Load it only for edits containing a located place; the existing assertion is unchanged. Offscreen pins are selected via their visible edge chip, preserving selection/deselection assertions. Passing displayKind alone produced an empty hotel label, so pinKindLabel now explicitly handles lodging; a screen assertion verifies the result.

Backend ruff F/E9 passed with repository configuration. Required unit/architecture/contract: 7861 passed, 138 skipped, 442 deselected. Additional booking: 221 passed. Eight changed/related DB suites: 169 passed. Executed backend passes: 8251. DoD 26/26, MVP subset 18/18; this gate does not establish that every product feature is complete. Isolated DB stopped; production container IDs were unchanged during backend verification.

Final web: eslint, type generation, tsc, unit 802/802 and webpack build passed. Browser mock server shares state and requires one worker. Initial two-worker run: 150 passed, 5 skipped, 19 failed. One-worker failure-group retry: 113 passed, one offscreen-marker failure. After correcting the user action, the 25 plan-check-screen tests passed. A new lodging-summary assertion exposed the missing label; after correction final changed screen files passed 26/26, no skips/flaky results. These are separate runs, not one uninterrupted full browser pass.

mock server tests (screen reaction): final changed screen files 26/26. Other affected files were covered by the preceding runs.
Real cs project response verification: not performed for this final integration. Earlier producer operational route evidence is in [the map report](2026-10-17_intake-map-routes.md). Final hotel-label operational rollout still requires confirmation.

## Preservation and publication

Original local checkout, datasets, index and settings were not synchronized or cleaned. Verification used an isolated exported tree and synthetic DB. Tests did not replace production API, worker, DB, web or administrator containers. No private environment files are included.

The final tracked text tree is scanned for credential/infrastructure leaks; raw grep is retained privately without truncation. Both develop heads must match the tested parent before fast-forward publication. Main is excluded. GitHub checks are followed afterward. Personal account billing previously prevented jobs from starting; this is not a code-test success.

## CI follow-up

Team backend full non-live tests, Docker build and ruff passed on aac392393. Administrator CI failed because the committed standalone HTML was stale after integration. Regenerated it from the exact integrated source; two exports match. Administrator lint/type/unit 22/22/build, browser 22/22 and unconfigured-mode 1/1 passed in isolation. This follow-up changes only the generated HTML and this record; backend/customer-web code is identical to aac392393. Personal CI workflows are disabled_manually, so no new CI runs were generated; prior billing failures are not evidence for this commit.

## Subsequent operational web verification

After the isolated checks, the producer separately deployed the customer-web v3 candidate using preserved prior image/settings. Producer reports healthy startup, 30-second observation, zero restarts, four API/worker/DB/admin container IDs unchanged, no SQL. Operational candidate lint/types/unit 801/801/build passed; this differs from the integrated web unit scope 802/802. The producer verified the existing test intake: selected hotel summary displays lodging, first-day four route lines remain, map height 306px. The receiving session visually inspected the [final operational screenshot](../evidence/2026-10-17_intake-map-routes/final-v3-hotel-caption.jpg); this is producer live-screen evidence, not an independently repeated response test by the integration session.

## Route-label collision correction

Full web CI had one deterministic map-status-bar failure, repeated on the failed-shard retry and in isolation. Measured DOM bounds showed a route name overlapping an offscreen-navigation chip by about 3 pixels. Test-only zoom/pan attempts did not resolve it; final browser assertions and setup were restored unchanged. Names now try additional positions along the actual clipped route using measured pin, chip and control bounds and label size, transformed into map-local coordinates. With no clear position they remain hidden. A regression covers both an available clear section and a fully blocked route.

Final isolated checks: eslint/types/build, unit 803/803, four related browser files 37/37, no skips/flaky results. Backend and administrator GitHub checks passed on a70a2ee4; their source is unchanged. Personal CI remains manually disabled. Full new web CI follows publication.
