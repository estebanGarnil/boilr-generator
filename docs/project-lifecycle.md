# Generated project lifecycle

Boilr records the last successfully generated project in
`.boilr/state.json`. This baseline allows the CLI to inspect the current
filesystem, report drift, reconcile explicit moves, and safely update the
project after its manifest or selected modules change.

This document describes the lifecycle implemented by the `generate`,
`status`, `reconcile`, and `update` commands. It does not describe adoption of
arbitrary existing projects, which is not supported in state schema version 1.

## Lifecycle overview

A managed project moves through four explicit operations:

1. `boilr generate` creates the project and its initial state.
2. `boilr status` compares the stored baseline with the filesystem without
   writing anything.
3. `boilr reconcile` accepts explicitly selected resource moves into the
   baseline without moving or rewriting project files.
4. `boilr update` compares the stored, observed, and newly desired projects,
   then applies only safe transitions.

`project.yml` remains the source of user intent. The state file records the
last successful application of that intent; it does not replace the project
manifest.

## Internal state files

Boilr reserves the `.boilr` directory inside each managed output.

| Path | Purpose | Intended for Git |
| --- | --- | --- |
| `.boilr/state.json` | Last successfully committed project baseline | Yes |
| `.boilr/state.pending.json` | Marker and desired state for an interrupted transaction | No |

Internal files under `.boilr` are excluded from ordinary resource drift and
cannot be owned by project modules.

The committed state contains:

- project identity and normalized manifest fingerprint;
- resolved module versions, origins, fingerprints, and destinations;
- capability bindings between modules;
- stable resource identifiers;
- desired and materialized resource paths;
- ownership and contributor metadata;
- file size, SHA-256, mode, or symbolic-link target as applicable.

It never stores rendered file contents, module variables, binding values, or
secrets.

## Initial generation

Preview the complete generation plan:

```bash
boilr dry-run project.yml generated-project --info
```

Request its machine-readable representation:

```bash
boilr dry-run project.yml generated-project --json
```

Generate and persist the initial baseline:

```bash
boilr generate project.yml generated-project --info
```

Generation prepares the desired state before mutation. Execution then:

1. validates the captured filesystem state;
2. creates `.boilr/state.pending.json`;
3. applies the prepared filesystem operations;
4. atomically replaces `.boilr/state.json`;
5. removes the pending marker.

If execution fails after the transaction begins, the previous committed state
is preserved and the pending marker remains available for diagnosis. A later
mutating operation refuses to continue automatically while that marker exists.

## Inspecting project status

Inspect a generated project:

```bash
boilr status generated-project
```

Return the complete observation as JSON:

```bash
boilr status generated-project --json
```

`status` is strictly read-only. It does not create the output directory, write
state, accept moves, or repair resources.

Tracked resources can be classified as:

| Status | Meaning |
| --- | --- |
| `unchanged` | The observed resource matches the committed baseline |
| `modified` | File content or link metadata differs |
| `missing` | The materialized path no longer exists |
| `moved` | A previously reconciled resource exists at its accepted path |
| `move_candidate` | One unique matching untracked path may be a move |
| `ambiguous_move` | Several paths could represent the missing resource |
| `type_changed` | The observed filesystem kind differs |
| `mode_changed` | Relevant permissions differ |
| `untracked` | A filesystem entry is absent from the committed baseline |

Container directories required only to reach tracked resources are not
reported as untracked. Independent empty directories and user-created files
remain visible.

## Reconciling an explicit move

First inspect resource identifiers and move candidates:

```bash
boilr status generated-project --json
```

Preview acceptance of one move:

```bash
boilr reconcile generated-project \
  --accept-move module:django:render:settings-base=backend/config/settings/base.py \
  --dry-run \
  --json
```

Apply the accepted move:

```bash
boilr reconcile generated-project \
  --accept-move module:django:render:settings-base=backend/config/settings/base.py
```

`--accept-move` may be repeated for several resources.

Reconciliation changes only `.boilr/state.json`. It never moves, rewrites, or
deletes project files. Unknown resource identifiers, ambiguous candidates,
invalid paths, stale observations, and existing pending transactions are
rejected.

## Updating a generated project

Edit `project.yml` to describe the desired configuration, then preview the
safe update:

```bash
boilr update project.yml generated-project --dry-run --info
```

Use JSON when another tool needs the complete decision contract:

```bash
boilr update project.yml generated-project --dry-run --json
```

Apply the update:

```bash
boilr update project.yml generated-project --info
```

The update planner compares three states:

1. the baseline stored in `.boilr/state.json`;
2. the currently observed filesystem;
3. the project newly desired by `project.yml` and the module registry.

Safe resource transitions include:

- creating a desired resource at an unused path;
- replacing an unchanged tracked resource;
- retaining an identical or locally modified resource when no replacement is
  required;
- relocating an unchanged tracked resource;
- removing an unchanged resource that is no longer desired;
- forgetting a resource already missing from the filesystem.

Unsafe transitions are returned as explicit conflicts. In particular, Boilr
does not silently:

- overwrite or remove a modified tracked resource;
- write over an untracked path;
- accept an unresolved or ambiguous move;
- remove a user-created descendant;
- cross the selected output boundary;
- execute a stale plan.

The JSON result contains the resource changes, conflicts, module transitions,
module lifecycle order, desired state, and exact executable generation plan.

## Module lifecycle

Module additions, updates, retention, and removals are derived from the
complete project manifest. Modules are never changed in isolation from their
capabilities, bindings, contributions, or generated resources.

The lifecycle graph includes:

- capability-provider dependencies;
- contribution relationships;
- resource ownership and contribution relationships;
- deterministic installation and removal order.

Candidate dependency cycles and unsafe removed-binding cycles block execution.
Module removals occur in reverse dependency order, while additions follow
dependency order.

When a module is removed, Boilr removes only unchanged resources recorded in
the previous state. Obsolete resource-container directories are removed from
the deepest to the shallowest only when they will be empty. No recursive
directory deletion is used. An untracked file or directory keeps every
containing directory in place.

## Dry-run parity

There are two different previews:

| Command | Previewed operation |
| --- | --- |
| `boilr dry-run ...` | Initial or clean generation |
| `boilr update ... --dry-run` | State-aware project update |

An update dry-run builds the same `ProjectUpdatePlan` and embedded
`GenerationPlan` used by execution. Directory creation, file writes,
permissions, exact removals, module transitions, and the desired final state
are all prepared before mutation.

The CLI rebuilds the plan when `boilr update` is invoked again. Its result is
identical to the earlier dry-run when `project.yml`, the module registry, the
committed state, and the filesystem have not changed. Changes between the two
commands cause replanning or stale-plan rejection rather than execution of an
outdated preview.

## Transaction and failure guarantees

Every mutating lifecycle operation validates its inputs before creating the
pending marker. Once a transaction starts:

- the previous `state.json` remains committed until the final atomic replace;
- a failed filesystem operation does not silently advance the baseline;
- a failed state commit preserves the previous final state;
- `state.pending.json` remains after an interrupted transition;
- subsequent mutation is blocked until the interruption is inspected;
- `status` remains available because it is read-only.

Dry runs and status commands never create, replace, or remove either state
file.

## User-created resources

A path absent from `.boilr/state.json` is untracked. Untracked resources:

- are reported by `status`;
- are never adopted automatically;
- are never overwritten automatically;
- are never removed by `update` or `reconcile`;
- may coexist inside directories containing generated resources;
- prevent removal of a containing directory while it remains non-empty.

Arbitrary project adoption and automatic acceptance of modified resources are
outside the version 1 lifecycle contract.

## Recommended workflow

Use this sequence for ordinary changes:

```bash
boilr status generated-project
boilr update project.yml generated-project --dry-run --info
boilr update project.yml generated-project --info
boilr status generated-project
```

When `status` reports a possible move:

```bash
boilr status generated-project --json
boilr reconcile generated-project --accept-move RESOURCE_ID=PATH --dry-run --json
boilr reconcile generated-project --accept-move RESOURCE_ID=PATH
boilr status generated-project
```

After a successful update without intentional local drift, the final status
must report every tracked resource as unchanged and no pending transaction.

## Current boundaries

State schema version 1 intentionally does not provide:

- adoption of arbitrary existing projects;
- semantic source-code merging;
- automatic acceptance of modified or moved resources;
- remote module registries or a module marketplace;
- arbitrary state-schema migrations;
- complete development and production profiles.

These constraints keep lifecycle operations deterministic, inspectable, and
safe.
