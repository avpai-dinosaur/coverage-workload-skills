---
name: antithesis-api-surface
description: >
  Map every user-facing operation a system offers and sort them from core to
  specialized, as the first step of building a coverage-driven Antithesis
  workload. Produces antithesis/scratchbook/api-surface.md. Use when starting a
  new workload, or when the system's API has changed.
metadata:
  version: "draft"
---

# Antithesis API Surface

## Purpose and Goal

List every operation the system under test offers to its users, describe each
one, and sort them into tiers from **core** (what the system is fundamentally
for) to **specialized** (narrow or admin use cases). The workload is later built
in that order: core operations first, then more specific ones added one tier or
feature at a time.

This skill does not look for bugs or define properties. It only describes what
the system can do and how central each operation is.

Success means:

- Every user-facing operation in the code appears in the output
- Each operation has a stable ID, a tier, its dependencies, and the code that
  handles it
- Every tier choice has a reason that points to evidence
- The user has confirmed which operations are Tier 0
- `scripts/check_api_surface.py` passes on the output

## Prerequisites

- The system's source code must be available. Code is the source of truth for
  which operations exist. DO NOT PROCEED without it.
- Documentation is strongly recommended. Ask the user where it lives if it is not
  in the repo.
- Python 3 for the checker script.

## Inputs

| Input | Required | Used for |
|---|---|---|
| Source code | yes | Finding operations and the code that handles them |
| Documentation | yes, if it exists | What each operation means; tier signals |
| Client libraries, CLI | if they exist | Finding operations; tier signals |
| GitHub issues | optional | How people actually use the system (tier tie-breaker only) |

Do not include lifecycle actions like shutdown, restart, or crash recovery.
Antithesis fault injection covers those.

## Reference Files

| Reference | When to read |
|---|---|
| `references/finding-operations.md` | Phase 1: where operations are defined for each kind of API |
| `references/tiering.md` | Phase 3: how to assign tiers |
| `references/output-format.md` | Before writing any output |
| `references/example-api-surface.md` | A complete example output |

## Workflow

### Phase 1 — List the operations

Read `references/finding-operations.md`.

Find every user-facing operation in the code, starting from formal API
definitions (OpenAPI, protobuf, GraphQL schema, CLI command tree) and route or
handler registrations. Include admin and maintenance operations, not just the
main data API.

Give each operation a stable ID in the form `area.verb` (e.g. `kv.put`,
`member.add`). Every later phase and later skill refers to operations by this ID,
so do not rename IDs after this phase.

Record each operation's ID, name, how to call it, and its code locations
(`file:function`). Write this list to `antithesis/scratchbook/api-surface.md`
using the format in `references/output-format.md`, with the other fields left
as `TODO`.

If the system has many operations (roughly 40 or more), show the user the list
of areas and counts before moving on, so they can spot anything missing or out
of scope.

### Phase 2 — Describe each operation

For each operation, read the docs, client library, and handler code, and fill in:
what it does, its inputs and their limits, what must exist before it can work,
what setting turns it on, and what data it reads and changes.

Anything found in the docs or client library that does not match an operation
from phase 1 goes in the **Flagged** section. It may be a missed operation.

If GitHub issues are in use, skim them for how people actually use each
operation and note anything relevant in the operation's notes. Do not record
bugs or try to predict where bugs are.

**Helper agents.** If your agent supports sub-agents and there are many
operations, split this phase by area: one helper per area (e.g. `kv.*`,
`watch.*`, `member.*`). Give each helper the IDs it owns, the path to
`references/output-format.md`, and tell it to write its sections to
`antithesis/scratchbook/api-surface-parts/{area}.md`. Helpers must not invent new
IDs; they report possible missing operations as flagged items. When all helpers
finish, combine the parts into `api-surface.md` and delete the parts directory.

### Phase 3 — Sort into tiers

Read `references/tiering.md`.

Work out which operations depend on which, then assign every operation a tier
from 0 to 3 and, for Tier 2, a feature group. Write a reason for each choice that
points to evidence (a doc page, a client method, a config flag, a code path).

Mark confidence `low` wherever the choice was a close call, and say why in the
operation's **Uncertain** bullet.

**Checkpoint:** show the user the Tier 0 list with a one-line reason for each,
plus any Tier 1 operations that were close calls. Ask them to confirm or adjust.
Record the answer in the header table (`Tier 0 confirmed by user`). If the user
is not available, record `no` and continue.

### Phase 4 — Check the result

Run the checker and fix every error it reports:

```bash
python3 <skill-dir>/scripts/check_api_surface.py antithesis/scratchbook/api-surface.md --repo <sut-root>
```

Then do the self-review below.

## Output

One file: `antithesis/scratchbook/api-surface.md`. Its format is defined in
`references/output-format.md`. In short:

- A header table with provenance and the Tier 0 confirmation
- An index table of every operation (ID, name, tier, feature group, kind)
- A feature groups table
- A flagged list
- One section per operation: free-text bullets, then a table of fixed fields,
  then an inputs table

If the file already exists, update it in place. Keep existing IDs and preserve
any notes or tier choices the user edited, unless the code shows they are now
wrong. If so, say what changed.

## Self-Review

If your agent supports sub-agents, have a fresh agent do this review. Give it
the path to this skill and the output file. Otherwise, re-read this file and
check each item yourself.

- The checker passes
- Every route, RPC, or command registered in the code is in the output, or is
  in Flagged with a reason it was left out
- No lifecycle actions (shutdown, restart, crash recovery) are listed
- Tier 0 is small: only what the system needs to do its main job
- No operation is in an earlier tier than something it requires
- Every tier reason cites specific evidence, not just "seems core"
- Close calls are marked `low` confidence with an **Uncertain** bullet
- Nothing in the output describes bugs, properties, or likely failure areas
