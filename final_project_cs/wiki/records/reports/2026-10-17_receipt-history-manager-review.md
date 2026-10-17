# Receipt history manager integration review — 2026-10-17

Integrated the producer's 13-file cumulative patch onto role-manager 7fe1b890. Included six required operational prerequisites: receipt sink registration, disaster provider receipt sink, simulation receipt/consented external-delivery support, notice delivery gate, customer delivery setting reader, and administrator gateway allowlist. Unrelated captured operational files were excluded. In particular, the operating copy lacks the newer notice_board function; the manager version remains intact.

The manager baseline reproduced the existing unrelated taxi-edit review-load regression. Applied the same narrow located-place guard already validated on develop, preserving the original regression assertion. No customer business classification or approval boundary was changed.

## Independent validation

Required unit/architecture/contract: 7568 passed, 138 skipped, 442 deselected. Booking: 221 passed. Seven changed/related DB suites including the new receipt-history suite: 178 passed. Executed backend passes: 7967. Ruff F/E9 and DoD 26/26 passed. Isolated DB stopped and retained; operational container IDs remained unchanged during these checks.

Administrator eslint/types/unit 22/22/build, two identical HTML exports, demo/offline browser 22/22, unconfigured mode 1/1 and live-mode build passed. New receipt-history mock browser tests: 2/2 at 1280px and 375px; no actual notification writes. Regenerated the committed standalone HTML from this exact administrator source.

SQL is parameterized and tenant-filtered in each history branch. Count and page reads use repeatable-read read-only transactions. Snapshot time prevents newer appended records shifting pages. Historical provider responses that were never recorded are not reconstructed. Upcoming real visits and out-of-window simulation targets are shown separately. No production SQL/schema operation is planned.

## Scope and rollout status

Manager publication only: team and personal role-manager. This receipt change is excluded from develop and main. Production rollout remains pending in this record. Use a narrow overlay on freshly checked current images, preserving runtime environment, mounts, database and customer web; reject a moved operational baseline. Previously preserved operational receipt and customer delivery functions must not be replaced with an older Git source tree. Final actual HTTP/UI verification and deployment evidence follow rollout.

See [contract](../../operations/receipt-history.md) and [producer report](2026-10-17_1530_receipt-history-and-targets.md).
