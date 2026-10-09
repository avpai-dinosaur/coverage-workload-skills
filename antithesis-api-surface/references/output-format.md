# Output Format

The output is one markdown file: `antithesis/scratchbook/api-surface.md`.

Each operation has **free-text bullets** for things that need judgment, and
**tables** for fixed fields that later steps and the checker script rely on. See
`example-api-surface.md` for a complete example.

## File layout, in order

1. Provenance frontmatter (same as other Antithesis scratchbook files)
2. `# API Surface: {system name}`
3. `## Summary`: header table, then a sentence or two on what the system is for
4. `## Index`: one row per operation
5. `## Feature Groups`
6. `## Flagged`
7. `## Tier 0: Core`, `## Tier 1: Core variants`, `## Tier 2: Features`,
   `## Tier 3: Specialized`: one `###` section per operation under its tier

## Provenance frontmatter

```
---
sut_path: /abs/path/to/sut
commit: <full git SHA, or "uncommitted">
updated: YYYY-MM-DD
---
```

## Summary header table

| Field | Value |
|---|---|
| System | name |
| Tier 0 confirmed by user | `yes` or `no` |
| Operations | total count |

## Index table

| ID | Name | Tier | Feature group | Kind |
|---|---|---|---|---|
| `kv.put` | Put | 0 | — | data |

Must list exactly the same operations as the sections below, with the same tier,
feature group, and kind.

## Feature Groups table

| ID | Description |
|---|---|
| `watch` | Get notified when keys change |

Every Tier 2 operation belongs to one group. Tier 3 operations may use one.

## Flagged

Bullets for anything a person should look at: possible missed operations, things
left out on purpose (and why), conflicts between docs and code. Write `None.` if
empty.

## Operation section

Heading: `### \`{id}\`: {Name}`

**Bullets first** (free text):

- **What it does:** one or two sentences.
- **Tier reason:** why this tier, citing evidence (doc page, client method,
  config flag, code path).
- **Notes:** optional. Preconditions, odd behavior, how people use it.
- **Uncertain:** required when confidence is `low`. What the close call was.

**Fields table** (strict). Every row must be present, in this order. Use `—`
for "none". Lists are comma-separated, with IDs in backticks.

| Field | Value |
|---|---|
| ID | `kv.put`. Must match the heading |
| Tier | `0`, `1`, `2`, or `3` |
| Feature group | a group ID from the Feature Groups table, or `—` |
| Kind | `data` (reads or writes user data) or `admin` (manages the system itself) |
| How to call | e.g. `PUT /v1/kv/{key}`, `kv.KV/Put`, `kvctl put`, `client.Put()` |
| Requires | IDs of operations that must have run first, or `—` |
| Enabled by | setting or flag that must be on, or `—` |
| Changes state | short names for the data it changes (e.g. `keys`, `leases`), or `—` |
| Reads state | short names for the data it reads, or `—` |
| Related | IDs of other operations that touch the same data, or `—` |
| Code locations | `file:function` entries, paths relative to the SUT root |
| Confidence | `high` or `low` |

**Inputs table** (after the fields table). One row per input. Write `No inputs.`
instead of a table if there are none.

| Input | Type | Limits and notes |
|---|---|---|
| key | string | 1 byte to 1.5 KB; empty not allowed |

Put real limits and defaults in the last column (maximum sizes, allowed ranges,
config settings that change them). Later steps use them to pick interesting
values.

## State names

Use the same short name everywhere for the same piece of data (`keys`, not
`keys` in one place and `kv data` in another). Later steps use these names to
find operations that touch the same data.
