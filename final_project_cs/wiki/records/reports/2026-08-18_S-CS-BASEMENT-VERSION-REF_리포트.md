# S-CS-BASEMENT-VERSION-REF report

## Scope

Compared `final_project_cs/` directly with `final_project_sample/dist/basement/manifest.json`. No source files were copied or changed. The sample exporter was run with:

```text
python -m scripts.export_basement
exported 60 files to final_project_sample/dist/basement/manifest.json
```

Manifest metadata: basement `0.2.0`, source commit `92b4c438a8f3bce1a5c65a54b38285d150020225`, generated at `2026-08-18T13:12:11.546712Z`.

## Verification command and result

The direct SHA-256 comparison was run using [`basement_drift_check.py`](../manuals/basement_drift_check.py):

```text
python docs\manuals\basement_drift_check.py ..\final_project_sample\dist\basement\manifest.json .
```

| Category | Count |
|---|---:|
| Manifest files | 60 |
| Match | 32 |
| Exists but SHA-256 differs (drift) | 21 |
| Missing from CS | 7 |
| CS-only files under declared components | 1 |

## Match (32)

Every path below exists in CS and its SHA-256 equals the manifest value.

```text
app/application/__init__.py
app/application/proposal_guard.py
app/core/__init__.py
app/core/contracts.py
app/core/graph_retrieval/__init__.py
app/core/graph_retrieval/port.py
app/core/redaction.py
app/core/registry.py
app/core/remote_team/__init__.py
app/domain/__init__.py
app/domain/case.py
app/domain/events.py
app/infrastructure/__init__.py
app/infrastructure/a2a/__init__.py
app/infrastructure/a2a/http_transport.py
app/infrastructure/db/__init__.py
app/infrastructure/db/migrate.py
app/infrastructure/db/migrations/001_schema.sql
app/infrastructure/db/session.py
app/infrastructure/graphstore/__init__.py
app/infrastructure/llm/__init__.py
app/infrastructure/messaging/__init__.py
app/infrastructure/messaging/ports.py
app/infrastructure/rag/__init__.py
app/infrastructure/rag/retriever.py
app/presentation/__init__.py
app/presentation/a2a/__init__.py
app/presentation/a2a/agent_card.py
app/presentation/a2a/remote_agent.py
app/presentation/api/__init__.py
app/presentation/api/mcp.py
app/presentation/security.py
```

## Drift (21)

Each path exists, but the actual SHA-256 differs from the manifest SHA-256. No attempt was made to correct it.

| Path | Manifest SHA-256 | CS SHA-256 |
|---|---|---|
| `app/application/case_service.py` | `dc3e43ae224683162d7cf8175ba17202bfb89a8cf8eeae392cb37b9936e67649` | `f94b353ad26efe5cb1ca0606b477105993820a2361962dfa9973def8b35a7fcb` |
| `app/application/controller.py` | `677e69595c47687fb0aeb32167877dabb02d3fe799d90c66d60be434fcb6dd16` | `d2597679409530983d0b8288a0e76a528b1e24f459edc64efb6580f86c9f0baa` |
| `app/application/feedback_job.py` | `b5eb56e63e6937b84869da82eb779aaec50adb76251555af1af7bdeb280003af` | `990847e773f49dbff2139c1eb92da1d994cfea3a40d16b5ee3f8f3182e778eb5` |
| `app/core/context.py` | `59c8af4e4d8f7c78c78365505640c07a49205b6eeaa14cc67660af8d24f3a1aa` | `debc7b98018decd6d19c996e23ff039dffef050fad027a89a0a07926fca65dd7` |
| `app/core/idempotency.py` | `12a1942b42df58a9bc287af050bca5f673533887d027cc5e8873de72d92cd88d` | `ef90c3e7c545809a1eea0e1028b69d4952b987bc1ccd2d5ecba4f5d7bde770af` |
| `app/core/project_config.py` | `f15706bd61457557b7ff0e824f6db6daa807cb9aa3d5d3c994304ddee7794af5` | `af2edfb29a0db35bc06e31edbad518f31e024c051995a2ed430446f63b7a8e37` |
| `app/core/remote_team/a2a_executor.py` | `bfc3fa4a6b55ae6eb0d615f3a63ddade9f7dc9b560ad16de3d7faabdbe6cbd43` | `dcd1fbae70c1c9eb0bfb61f530ffe865e8bee552aa808963e947f79b83b6e26f` |
| `app/core/remote_team/executor.py` | `ce204ea9c06219ab84effd154a2bacf204d01585fee9aa74635464fd7b3b7eff` | `9966ff827821150fc8ec4f1a6cc4ae94422ddfb759aa9b114ac8322d12864e58` |
| `app/core/settings.py` | `36bc43e9df45bad6828d281a18ff9a3418379589e5afede318a3e6884199173c` | `c17efd8030866f89f35cdec42885613362ecd6e4a0176601a66509a9af105015` |
| `app/core/transition.py` | `d1d716524da0b30d0ac7a544534a1219b5957869600850fb8d6df69b053ba6af` | `0b840482a0284eff64c1e24c74de4ec48e26b12c00601c98bfd47cac1994fdb2` |
| `app/core/verification.py` | `a6b8836ff5c727eb38084d7eff0aa5e4b1018e04f05f08b80774bbcdd4b68f78` | `fcd9f7587750c07e5dc4bf62333a1765c5b002b9c4abd136a19e53c3d96b12a8` |
| `app/infrastructure/db/repository.py` | `9195514170dd7863763a519860f9a477d134b4f9699f5d5952082fe99e6b309d` | `e155a112748dc48645f7477a05434cd4ef19148a0bfc834c304763f44d658f0a` |
| `app/infrastructure/graphstore/sql_adapter.py` | `f23aed8a7fdbca4c5a7f3874d8147d889a0812200af7638e2751372561673e6b` | `4af873aef9b7c3a810501e1a2e93fbf5ec62f0e02da6b80910fa4a313835fbc2` |
| `app/infrastructure/llm/openai.py` | `1f4f91cf12b2b8b2e647ef4b9b77ac0a523a8be0866ff4fa433ea2248a44a400` | `c76f69ac1c731ba0500ece141b8e53f3e3885604ff0b8e8307597b3f548d413e` |
| `app/infrastructure/messaging/outbox.py` | `5d66031fea5755e17701118c8cdf79223ed8a3913a3e103e3881cbbff07097f2` | `b10b55b0fdfbe26dbeea67e4cdbae9a3f925e2c58a4b955e63b67e322a2ef8f6` |
| `app/infrastructure/messaging/worker.py` | `44eb04762c44e3442f31c27f5f459c68105d039d4dd322f1f6718dac6f3a2293` | `7e55ff985971336f648548e8116b4c4fae0a4df64256ccaf257179468a6bda7a` |
| `app/presentation/api/app.py` | `4acc1c5145dafc9d908274357a6ed2018c3b0f2fa09272f5acb3df8091b842d6` | `0347272cb12d1ca216f548b6f8990a5e246d1cecdf5ab705524a96c01a08d526` |
| `app/presentation/api/cases.py` | `91bcdcaed11ec8f3dd795161d8266c2cd9a6aecabca813778d5f23de3f8037e9` | `586f645d0369cfa84907586f2c16d879171a7fb7745a8dc09e3c8e144ec75f08` |
| `app/presentation/ui/__init__.py` | `660a18c36c909faabf1ce92d917d59ade37aff7d5dbfe2324de1a99dccfb9dee` | `df4fbb0149c59cfdd79e4441baa95cfff7b4b621d01bee45eb2697cc6f85e26e` |
| `app/presentation/ui/routes.py` | `6d57690962d21880a3fd4a1ec5163a15444154c13e1a5f4e18b3d2acd7cce67b` | `2e03b34b14c94bae0fd861f8d44db656ee18bcdefa8d91380747bfad98bfbade` |
| `app/presentation/ui/theme.py` | `12dddfe93d7b0a05f1ebe16c335f72d56d4858683ef327088b32415fd0a432b5` | `c1d6c333b13b5e72298bbc0cc6d7bac764e3bc49763759e9dfa80683c0775aab` |

## Missing from CS (7)

```text
app/application/composer_service.py
app/infrastructure/db/migrations/003_outbox_resolution.sql
app/infrastructure/db/migrations/004_agent_runs_active_uniqueness.sql
app/infrastructure/db/migrations/005_outbox_dedupe_key_tenant_scoped.sql
app/presentation/api/composer.py
app/presentation/api/outbox.py
app/presentation/composer_auth.py
```

## CS-only files (1)

```text
app/infrastructure/db/migrations/002_domain_commerce.sql
```

This is recorded as local drift only. No automatic correction was performed in `final_project_cs/`, and no Git operation was run.
