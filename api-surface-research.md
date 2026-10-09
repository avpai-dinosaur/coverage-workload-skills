# API Surface Research (Step 1) — Draft

## Goal

Produce a list of every operation the system offers, sorted from **core** (what
the system is fundamentally for) to **specific** (narrower use cases). The
workload is later built in that same order: core operations first, then more
specific ones added one layer at a time.

This step does not try to guess where bugs are. It only describes what the
system can do and how central each operation is.

## Inputs

- The system's source code (required)
- Its documentation (required)
- Client libraries and CLI, if any
- GitHub issues (optional; only used to show how people actually use the system)

## How it runs

The main agent runs four phases in order. Phase 2 can use helper agents in
parallel. If helper agents aren't available, everything runs in one agent.

1. **List the operations.** Read the code and any formal API definitions
   (OpenAPI, protobuf, GraphQL, CLI command list) to list every user-facing operation the
   system offers. Code is the source of truth for what exists. Each operation
   gets a short stable ID that all later phases use, plus the location of the
   code that handles it. This includes admin and maintenance operations, not
   just the main data API.

2. **Describe each operation.** Read the docs (and optionally issues) and add
   detail to each operation from phase 1: what it does, what inputs it takes,
   what must already exist for it to work, and what settings turn it on. Anything
   found in the docs that doesn't match a phase 1 operation is flagged, since it
   may be a missed operation.

3. **Sort into tiers.** Work out which operations depend on which, then assign
   each to a tier (see below). The user confirms which operations are in Tier 0
   before moving on.

4. **Check the result.** A fresh agent checks that:
   - every operation registered in the code appears in the list
   - no operation is in an earlier tier than something it depends on
   - every tier choice has a reason that points to evidence

## Tiers

| Tier | Meaning | Example (key-value store) |
|---|---|---|
| 0 — Core | Smallest set that makes the system do its main job | put, get, delete, list keys |
| 1 — Core variants | Richer forms of core operations, nothing new to learn | conditional put, batch write, read an older version |
| 2 — Features | Adds a new concept with its own state | watch for changes, keys that expire |
| 3 — Specialized | Admin, maintenance, niche, or experimental | add/remove a server, backup/restore, access control |

Tier 2 is split into **feature groups** (e.g. "watch", "expiry") so features can
be added to the workload one at a time.

**How tiers are decided**, strongest signal first:

1. **Dependencies.** If an operation needs something only another operation
   creates, it goes in the same tier or a later one. This sets the order.
2. **Docs.** Shown in the quickstart → core. Has its own feature page →
   Tier 2. Only in admin/ops guides, or marked beta/experimental → Tier 3.
3. **Client library / CLI.** Top-level methods lean core; methods tucked into a
   sub-section (e.g. `client.admin`) lean specific.
4. **Needs a setting turned on** → leans specific.
5. **Code layout.** Lives in its own module or plugin → leans specific.

## Output

One file: `antithesis/scratchbook/api-surface.md`. Each operation gets free-text
bullets (what it does, why it's in its tier, notes, anything uncertain), then a
table of fixed fields (ID, tier, feature group, kind, how to call, requires,
enabled by, state it changes and reads, related operations, code locations,
confidence), then a table of its inputs and their limits.

The full format is in `antithesis-api-surface/references/output-format.md`, with
a complete example in `antithesis-api-surface/references/example-api-surface.md`.

## Open questions

- Keep GitHub issues as an optional signal, or drop them? They should be an optional signal.
- Should graceful lifecycle actions (clean shutdown, rolling restart) be listed
  as Tier 3 operations, or left to Antithesis fault injection? Leave them to fault injection for now.
- How detailed do `code_locations` need to be? This depends on what the
  Antithesis edge export reports (file and line, or function names). Make it function name + file for now.
