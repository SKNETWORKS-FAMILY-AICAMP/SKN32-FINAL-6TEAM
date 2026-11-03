# Disk duplicate cleanup handoff 2026-10-30

- Completed one scoped inventory and full SHA grouping; deleted 244/244 = 100% inactive copied GHelper fixtures, 32,975,703,428 B.
- Verified 24/24 keeper SHA groups and 244/244 deleted paths; 300/300 other hashed files remain.
- C free after deletion: 214,609,543,168 B; latest recorded: 214,632,628,224 B, 53.66% of 400GB; remaining 185,367,371,776 B.
- Preserved original baselines, published builds, unique evidence, all worktree/NPU files and all profile configuration. No jobs stopped, copies/clones created, commits or pushes.
- Ten equal worktree SWC files remain without proven inactive ownership. NPU duplicate probe graph remains protected evidence; NPU PID39260 exited during this session, which does not imply retirement permission.
- [Detailed report](../records/reports/2026-10-30_disk-duplicate-cleanup.md) and exact deletion/keeper/remaining manifests in `wiki/records/evidence/2026-10-30_disk-duplicates/`.
- Do not rerun deletion scripts; results are append-only execution evidence and candidate paths are already absent.

## Continuation 2026-10-30T00:38:56.928960+09:00

- Additional deletion: 0 files / 0 B. New profile DLL duplicate includes an active runtime (11 process references); retained both. Worktree/NPU recheck: 12/12 = 100% SHA matches; retained for unresolved retirement/dependencies. Four fixtures remain younger than six hours.
- C: free 214,621,405,184/400,000,000,000 B = 53.66%; remaining 185,378,594,816 B.
- [Continuation report](../records/reports/2026-10-30_disk-duplicate-cleanup-continuation.md). Exact empty deletion manifest, observed files, errors, hashes, handle/owner evidence, guard inventory and artifact sizes are in the continuation evidence directory. No tasks stopped or profile settings altered.

## Round 5 2026-10-30T21:13+09:00

- Deleted 138/138 = 100% regenerable NPU ONNX intermediates whose DLA is built ok (`engines/h1-eps3` 73, `engines/h16-here` 65): 15,638,812,560 B; measured +15,637,020,672 B. All DLA/logs/meta/weights/probes kept; NPU owner notified in `_coord/NOTICE-disk-cleanup-20261030-round5.md`.
- C: free 226,920,222,720/400,000,000,000 B = 56.73%; remaining 173,079,777,280 B. Not reachable with currently approved categories.
- Next needs user decisions: final_workspace scratch 83.97GB (per-target approval under AGENTS.md; list in `final-scratch-candidates.json`), Flash-Next model set 98.74GB, hiberfil 13.10GB (admin), WSL vhdx compaction (admin, NPU idle), NPU later-projection 23.91GB/F16 8.67GB (owner), default-profile scratch 44.95GB (other profile).
- [Round 5 report](../records/reports/2026-10-30_c-drive-400gb-cleanup-round5.md); evidence `wiki/records/evidence/2026-10-30_disk-round5/`. Do not rerun the delete step; paths are already absent.
