---
name: antithesis-coverage-workload
description: >
  Build an Antithesis workload that explores as much of the system as possible,
  starting from its core operations and growing outward, using code coverage
  (local and from Antithesis) to tell whether each change helped. Writes simple
  Python Test Composer drivers with no properties. Use after
  antithesis-api-surface and antithesis-coverage-setup.
compatibility: Requires snouty (https://github.com/antithesishq/snouty) and Python 3.
metadata:
  version: "draft"
---

# Antithesis Coverage Workload

## Purpose and Goal

Write and grow a workload whose only job is to **drive the system into as many
different states as possible**. Start with the core (Tier 0) operations, then
add more specific operations tier by tier. Measure every change with coverage.

The workload **does not check correctness**. It has no properties and no
assertions. Properties are written separately, as reducer scripts in the log
sidecar that `antithesis-coverage-setup` built.

Success means:

- One simple driver per operation that is in scope, under `antithesis/test/v1/main/`
- Every driver runs, and its operation mostly succeeds (checked by outcome lines)
- Each change was measured, and the result recorded in the ledger
- Tiers were added only after the current ones stopped producing new coverage

## Prerequisites

- DO NOT PROCEED unless `antithesis/scratchbook/api-surface.md` exists and its
  checker passes:
  `python3 <antithesis-api-surface>/scripts/check_api_surface.py antithesis/scratchbook/api-surface.md`.
  Use `antithesis-api-surface` to create or fix it.
- DO NOT PROCEED unless `antithesis/scratchbook/coverage-setup.md` exists and a
  local run works. Use `antithesis-coverage-setup`.
- `snouty` must be installed.

## Skills Used

| Skill | Used for |
|---|---|
| `antithesis-launch` | Submitting Antithesis runs. Never run `snouty launch` directly |
| `antithesis-triage` | Checking a run was healthy before reading its coverage |
| `antithesis-query-logs` | Counting operation outcome lines across all timelines |
| `antithesis-review-inputs` | Every few iterations: how well drivers use randomness |
| `antithesis-documentation` | Test Composer and Python SDK reference |

## Reference Files

| Reference | When to read |
|---|---|
| `references/initial-workload.md` | Writing the first drivers, and any new driver |
| `references/measuring-progress.md` | Every measurement, local or Antithesis |
| `references/growing-workload.md` | Choosing the next change |

## Scripts and Assets

| File | What it is |
|---|---|
| `scripts/coverage_report.py` | Converts coverage (Antithesis or local) to one format; summary, diff, per-operation report |
| `assets/helper_common.py` | Starting point for `antithesis/test/v1/main/helper_common.py` |
| `assets/driver_template.py` | Starting point for each driver |

## Where things stand

Start every invocation by reading `antithesis/scratchbook/workload-ledger.md`
(if it exists) and listing `antithesis/test/v1/main/`. Tell the user in a
sentence or two which tiers are active, what the last change was, and what it
did to coverage. Then pick the step below.

## Workflow

Each invocation does **one** step, then stops and reports back. Long sessions
give worse results, and every change needs measuring before the next.

1. **Initial workload** (no drivers yet). Read `references/initial-workload.md`.
   Write `helper_common.py` and one driver per Tier 0 operation. Run locally
   once to check every driver runs and logs outcomes.
2. **Baseline** (drivers exist, no ledger rows). Read
   `references/measuring-progress.md`. Measure locally, then launch an
   Antithesis run and measure it. Write the first ledger rows.
3. **Iterate** (otherwise). Read `references/growing-workload.md`. Make one
   change, measure locally, add a ledger row. Launch an Antithesis run when
   `growing-workload.md` says to.

If the user asks for something specific (e.g. "add the watch feature group"),
do that as the step, but still measure it and record it.

## Rules

- **No properties.** No `Always`, `Sometimes`, `Reachable`, `Unreachable`, or
  any other assertion. No checks on returned values. No `eventually_`,
  `finally_`, or `anytime_` commands. If you notice something that looks like
  a bug, tell the user. Don't encode it in the workload.
- **Test Composer decides** which drivers run, when, and how many at once.
  Drivers don't schedule each other.
- **Python, under 50 lines per driver**, readable by a person at a glance.
- **One driver per operation** to start. A driver may run a short sequence of
  operations only when coverage shows it's needed (see `growing-workload.md`).
- **Don't change the SUT, the sidecar, or the harness.** If something there is
  in the way (including a setting an operation needs, its **Enabled by** field),
  tell the user and suggest `antithesis-coverage-setup`.
- **Build the normal images before any Antithesis run or `snouty validate`**
  (without the coverage override), so the coverage build is never what gets
  tested.

## Output

- `antithesis/test/v1/main/helper_common.py` and `parallel_driver_*.py` (or
  `serial_driver_*.py`) files
- `antithesis/scratchbook/workload-ledger.md`
- Coverage snapshots in `antithesis/local/out/` (local) and
  `antithesis/local/antithesis/` (from Antithesis runs)

## Self-Review

If your agent supports sub-agents, have a fresh agent check this list against
the drivers and the ledger. Otherwise check it yourself.

- No driver or helper contains an SDK assertion, a check on a returned value,
  or an `eventually_`/`finally_`/`anytime_` command
- Every driver is under 50 lines and does one operation (or a short sequence
  with a ledger row explaining why)
- Every driver uses `antithesis.random` for its choices, and logs one
  `OP <id> <outcome>` line per call
- Every driver catches errors from the system and keeps going
- Only operations from active tiers or feature groups have drivers, and every
  operation's `Requires` are also active
- The ledger has a row for this change, with its measured effect
- `snouty validate antithesis/config` passes with freshly built images
