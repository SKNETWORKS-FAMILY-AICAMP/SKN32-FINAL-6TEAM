# Disk duplicate cleanup continuation — 2026-10-30

No additional files qualified for deletion in this continuation. Exact deletion manifest is empty: **0 files, 0 B**. The earlier 244-file deletion remains unchanged. This audit completed; the 400GB goal remains unmet.

| Measurement | Local timestamp | Real C: free bytes |
|---|---|---:|
| Before | 2026-10-30T00:36:48.780436+09:00 | 214,625,857,536 |
| After audit | 2026-10-30T00:38:56.928960+09:00 | 214,621,405,184 |

Real free change: **-4,452,352 B** with no cleanup deletion; concurrent writes and audit metadata affect space. Goal: **214,621,405,184/400,000,000,000 B = 53.66%**. Remaining: **185,378,594,816 B** (GB = 10^9 B).

Evidence directory: [continuation manifests](../evidence/2026-10-30_disk-duplicates-continuation/). All scripts are audit-only and perform no deletion, configuration change or task termination.

- Additional guguroute profile scratch metadata: 745,598 observed files, 70,781,409,031 logical bytes; 113 files at least 20MB. 3,139 path enumeration errors are preserved verbatim, and reparse points were not traversed. This is an incomplete bounded inventory, not proof of exhaustive coverage. Existing protected archives, Git packs/bundles, models, source, configurations and evidence were excluded from disposal consideration.
- Full SHA256 and exclusive Windows handle checks on four same-size generated/dependency binaries found one equal group: two `pymupdf/mupdfcpp64.dll` files, 26,288,640 B each, SHA256 `6d26bbdcbbb2489fd1343a7f317aecd5614243b98d6db5c3776db170a6edfea7`. Exact paths, independent Windows IDs and link counts are in `duplicate-groups.json`. Both retained. `api-runtime-20261025-014236` has **11 live process command references**, including Python; the other environment is not proven retired. A successful exclusive DLL open does not prove its surrounding environment is inactive.
- Existing project worktree binaries and the NPU ONNX pair: **12/12 = 100%** full SHA matches and successful exclusive opens at recheck. All retained. Ownership retirement and absence of linked dependencies remain unproven; file age or current handle availability alone does not establish disposal safety. Exact files, retained SHA and handle metadata are in `previous-candidate-recheck.json`.
- NPU source dependency evidence confirms `stream16/run_stream.py` still consumes `h1-eps3`, and `argen3/run_ab3.py` names `h16-here`, `review-silufix64`, and `h1-eps3`. Owner notice preserves probe graphs as evidence, weights and references as required inputs. Source hashes and line references are in `npu-dependency-evidence.json`. No NPU output, reference, logits or model was removed; distinct representations were not treated as equal copies.
- Four previously held GHelper fixture copies remain younger than the existing six-hour threshold (approximately 4.11–5.79 hours at recheck). Their exact paths and measured ages are in `age-held-recheck.json`. No age threshold was relaxed to claim additional capacity.
- Ownership was queried read-only from the guguroute state DB, with bounded excerpts retained in `profile-owner-evidence.json`. Only matching process IDs/names were persisted for runtime checks, not full process arguments. This is scoped evidence, not a whole-drive absence-of-dependencies claim.

No deletion was attempted, so there is no deletion-time dependency or handle guarantee to claim. Settings, skills, plugins, cron, memory, active work, original data and existing audit evidence were untouched. No clone, preservation copy, commit, push, service stop or Git mutation occurred. `disk_guard.py inventory` reports entries=[], unregistered_dirs=[]. Only small audit artifacts were created; exact artifact sizes and SHA256 are in `artifacts.json`.

Next handoff: keep the 400GB goal open. Do not count the observed logical totals as recoverable capacity. Further deletion requires positive retirement and dependency evidence for concrete files; the current newly identified duplicate includes an active runtime. Recheck recent fixtures only after their age condition is met and repeat ownership/runtime/link/SHA checks before any deletion. Original [244-file cleanup report](2026-10-30_disk-duplicate-cleanup.md) remains the record of actual deletions.
