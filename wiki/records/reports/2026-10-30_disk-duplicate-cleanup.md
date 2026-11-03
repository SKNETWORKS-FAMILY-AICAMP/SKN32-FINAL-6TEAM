---
type: report
title: Verified inactive GHelper fixture duplicate cleanup toward 400GB free
description: Removed 244 byte-identical disposable fixture copies totaling 32975703428 bytes and preserved independent copies and evidence
status: done
domain: travel
impl_scope: Default Hermes profile scratch fixture files and audit records only
---

# Verified inactive duplicate cleanup on 2026-10-30

Continued [the resume audit](2026-10-30_disk-400gb-resume-audit.md) under the user's explicit approval to delete safe regenerable inactive duplicates. Deleted **244/244 files = 100%**, **32,975,703,428 B**, from 32 completed GHelper worker directories in the active default Hermes profile. These were copied test fixtures, not unique published builds. No directory, source, log, database, Git object, model, baseline, configuration or other profile file was deleted. No external job was stopped and no large preservation copy was created.

## Measured space

GB means 10^9 B. Concurrent work affects free space; deleted logical bytes are separate from measured volume change.

| Measurement | Local time | C free bytes |
|---|---|---:|
| Before scoped inventory | 2026-10-30T00:21:53.543989+09:00 | 181,914,189,824 |
| Immediately before deletion | 2026-10-30T00:31:12.191005+09:00 | 181,677,367,296 |
| Immediately after deletion | 2026-10-30T00:32:14.333132+09:00 | 214,609,543,168 |
| After verification and recording | 2026-10-30T00:34:55.299364+09:00 | 214,632,628,224 |

Deletion-window free-space increase: **32,932,175,872 B**. This is 43,527,556 B less than deleted logical bytes; allocation and concurrent writes can contribute, and that difference is not attributed to a particular job.

Latest target progress: **214,632,628,224/400,000,000,000 B = 53.66%**. Still required: **185,367,371,776 B**. The 400GB target remains unmet.

## Exact deletion manifest and retained copies

The complete absolute path, byte count, full-file SHA256, retained absolute path, Windows volume/file IDs, link counts, modification times and owner-completion evidence for every candidate are in [delete-manifest.json](../evidence/2026-10-30_disk-duplicates/delete-manifest.json). [delete-results.jsonl](../evidence/2026-10-30_disk-duplicates/delete-results.jsonl) records each actual deletion. No recursive deletion was used.

Paths below are relative to `C:/Users/kcxsz/AppData/Local/hermes/cache/scratch/`; only files under each worker's `fixtures/` directories were deleted, never its directory itself.

| Worker directory | Deleted files | Logical bytes |
|---|---:|---:|
| `broker-latest-safe-regress` | 9 | 1,216,344,477 |
| `fn-reset-independent-v010` | 8 | 1,081,167,784 |
| `ghelper-ui-regress` | 10 | 1,351,521,170 |
| `progress-20261025-gpu-integration` | 2 | 270,205,930 |
| `progress-20261025-overlay-verification-fix` | 7 | 945,991,091 |
| `progress-20261025-plan-selector` | 4 | 540,497,876 |
| `progress-20261025-plan-transition-fix` | 5 | 675,645,897 |
| `progress-20261025-power-feedback-fix` | 5 | 675,617,225 |
| `progress-20261025-power-integrated` | 5 | 675,641,801 |
| `progress-20261025-shared-integration` | 3 | 405,341,663 |
| `progress-20261025-telemetry-followup` | 4 | 540,477,396 |
| `progress-20261025-viewport-fix` | 6 | 810,818,494 |
| `progress-20261026-sensor-audit` | 8 | 1,081,188,264 |
| `progress-20261027-fans-ui` | 8 | 1,081,167,784 |
| `progress-20261027-overlay-thrm-isolated` | 8 | 1,081,167,784 |
| `progress-20261027-power-main-candidate` | 8 | 1,081,167,784 |
| `progress-20261027-thrm-lifecycle` | 8 | 1,081,167,784 |
| `progress-20261027-thrm-main` | 8 | 1,081,167,784 |
| `v011-fans-fn-candidate` | 9 | 1,216,344,477 |
| `v012-regression-independent` | 10 | 1,351,521,170 |
| `v012-republish-verification` | 10 | 1,351,521,170 |
| `v013-final-atomic` | 10 | 1,351,525,266 |
| `v013-sensor-isolated` | 10 | 1,351,521,170 |
| `v013-sensor-tdd` | 10 | 1,351,521,170 |
| `v014-integrated-final-independent` | 10 | 1,351,525,266 |
| `v014-integrated-review` | 10 | 1,351,529,362 |
| `v015-hidden-regression-repair` | 9 | 1,216,344,477 |
| `v015-npu-final-work` | 10 | 1,351,541,650 |
| `v015-npu-hidden-fix` | 10 | 1,351,541,650 |
| `v015-npu-job-final-regress` | 9 | 1,216,344,477 |
| `v015-npu-regress` | 10 | 1,351,537,554 |
| `v016-startup-safe-o6s65z_f` | 1 | 135,086,581 |
| Total | 244 | 32,975,703,428 |

All published `GHelper.exe` files and every unique SHA were retained. Original Downloads/verified baselines were untouched. 24 distinct SHA groups have independent retained files recorded in [keeper-verification.json](../evidence/2026-10-30_disk-duplicates/keeper-verification.json). Four otherwise duplicate recent fixtures, totaling 540,813,268 B, were held by the six-hour age rule; see [held.json](../evidence/2026-10-30_disk-duplicates/held.json).

## Safety evidence

- Owner: completed async-delegation records or completed batch notifications were found by indexed queries against the default profile's state DB, opened read-only. No incomplete delegation remained in that DB at the final predelete check. Gateway PID24424 being alive was not confused with a completed child worker being active. [owners.json](../evidence/2026-10-30_disk-duplicates/owners.json) retains specific evidence.
- Equality: SHA256 covered every byte, without newline normalization or sampling. Before deletion, both exact files were opened exclusively and rehashed through their held Windows handles. A changed ID, size, time, resolved path, hash, link count or live open caused a hold, not a forced delete.
- Independence: each deletion and keeper had distinct Windows file IDs, link count 1, equal full SHA256 and literal resolved paths; no junction or hardlink stood in for an independent retained file. All keepers remained open during candidate disposition.
- Live handles: exclusive read/delete access to each candidate and exclusive read access to its keeper succeeded. This rejects conflicting existing file opens and prevents new opens during hashing and deletion. Deletion used `SetFileInformationByHandle(FileDispositionInfo)` on that same verified handle. No process handle was closed and no shutdown/restart API was called.
- Runtime references: fresh process command lines, GHelper scheduled action, services and startup entries had no candidate owner-directory reference. The GHelper scheduled action points to `C:/Users/kcxsz/Downloads/GHelper_arm64_v0.10_temp_H7407BA.exe`, which was untouched. 47 reparse points from the scoped inventories and GHelper/runtime directories were decoded with zero errors and zero candidate aliases. Their tags were Windows junctions or WSL symlinks; [runtime-links.json](../evidence/2026-10-30_disk-duplicates/runtime-links.json) records all targets. This is scoped runtime/link evidence, not a claim that the entire drive has no textual reference.
- Final verification: **244/244 deleted paths absent = 100%**; **24/24 retained SHA groups match = 100%**. All **300/300 other hashed files = 100%** remain present with unchanged size and modification time. The latter is a metadata preservation check, not a second complete hash of all 300 files. [verification-summary.json](../evidence/2026-10-30_disk-duplicates/verification-summary.json).

## Other actual duplicates and retained evidence

All exact SHA groups and file paths are in [all-sha-duplicate-groups.json](../evidence/2026-10-30_disk-duplicates/all-sha-duplicate-groups.json); surviving groups and reasons are in [remaining-duplicate-manifest.json](../evidence/2026-10-30_disk-duplicates/remaining-duplicate-manifest.json).

| Scope | Actual equality | Decision |
|---|---|---|
| Old final_workspace worktrees | 10 `next-swc.win32-arm64-msvc.node` files, 96,976,384 B each; SHA256 `d3a3866c42d714299e4c9e450284060054ae92a8f5c93f38188f3bf664eb966c` | Preserved all. Equal bytes alone do not establish completed ownership or independent runtime use. The theoretical excess is 872,787,456 B, not approved disposable capacity. Other hashed build/cache artifacts did not yield another exact duplicate group. |
| NPU ONNX | `engines/h1-eps3/ffn0_h1.onnx` and `engines/eps3-probe/ffn0_h1.onnx`, 141,569,405 B each; SHA256 `1c6928769915579920b278f10cbf5e5ec1406ab4f234236de34e4eed126cf031` | Preserved both. PID39260 was active during assessment and had exited by the final process snapshot. The owner NOTICE explicitly retains probe graphs as failure evidence; safe retirement and runtime independence were not established. |
| NPU references and baseline engines | F16 GGUF, NumPy weights, DLA sets, references and logits | Untouched. Same shape/size or different storage formats do not establish bytewise equality. Active/baseline DLA and unique failure evidence remain protected by owner notices. |

No conclusion that a worktree is inactive was inferred merely from its age or an absent command-line substring. The kept worktree and NPU duplicate groups have independent Windows IDs recorded in their remaining manifest, but that alone does not authorize retirement.

## Bounded method and artifacts

One metadata inventory was made of each requested tree: default Hermes scratch (183,536 files; 78,466,603,417 B), final_workspace scratch (1,135,469 files; 83,973,974,007 B), and NPU experiments (10,243 files; 97,188,263,947 B). Reparse points were not traversed. The on-disk SQLite catalog contains 1,661 files of at least 20,000,000 B. It was reused for all grouping; there was no repeat blanket disk scan.

Full SHA256 was computed for **544 selected files, 63,111,017,014 B**: same-size GHelper fixture/publish candidates, same-size NPU ONNX, and 89 worktree build/cache files. Git packs, model references, baselines and firmware evidence were excluded from deletion. Equality groups were formed from SHA, never from size alone. Hashing used 1MiB streaming buffers. Windows BCrypt SHA256 was cross-checked against the initial hashlib result. A slower initial hashing pass overlapped the native continuation briefly without being killed; its already-inserted-row conflicts are logged in `hash-errors.jsonl`. All 544 selected files have stored hash rows; those insert conflicts were not missing hash results.

`disk_guard.py inventory` after cleanup returned entries=[], unregistered_dirs=[]; no checkout was created or released. [guard-inventory.json](../evidence/2026-10-30_disk-duplicates/guard-inventory.json). Only small audit scripts, SQLite metadata, manifests and this report were created; the final artifact inventory records their exact sizes. No product code, CI, deployment, commit or push was changed. Product tests were not relevant to these file deletions.
