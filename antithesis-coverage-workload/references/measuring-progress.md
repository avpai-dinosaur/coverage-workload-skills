# Measuring Progress

## Goal

Tell whether the workload is reaching more of the system than before. There
are three signals, from cheapest to most expensive. Check them in this order.

All coverage goes through `scripts/coverage_report.py`, which converts
Antithesis and local coverage into the same snapshot format so they can be
compared. Snapshot paths are relative to the SUT repo.

## 1. Are the operations running? (outcome lines)

Every driver call logs `OP <id> <outcome>`.

- **Locally:** `antithesis/local/out/<label>/ops.txt` has counts per operation
  and outcome.
- **In Antithesis:** use `antithesis-query-logs` to count `OP <id>` lines per
  operation and outcome across all timelines.

Warning signs, to fix before looking at coverage:

- An operation that never appears: the driver isn't running, or crashes before
  its first call.
- An operation that is almost never `ok`, locally where there are no faults:
  wrong arguments, a wrong address, or a missing `Requires`. An operation that
  always fails only exercises error handling.
- In Antithesis, more errors than locally is normal (faults). Errors only in
  Antithesis but on *every* call usually means an environment difference.

## 2. Local coverage

Run the local run 2–3 times with different seeds, and merge the results, so
random variation isn't mistaken for progress.

Label snapshots by iteration number: `iter00` for the baseline, then `iter01`,
`iter02`, ... Each one is compared with the one before.

Take the coverage file name and `normalize` arguments (`--format`, `--repo`,
and `--keep-function` if any) from `coverage-setup.md`. The example below
assumes LCOV:

```bash
R=<skill-dir>/scripts/coverage_report.py
for seed in 1 2 3; do
  antithesis/local/run-local.sh iter05-s$seed $seed
  python3 $R normalize --format lcov antithesis/local/out/iter05-s$seed/coverage.lcov \
    --repo <sut-root> -o antithesis/local/out/iter05-s$seed/snapshot.json
done
python3 $R merge antithesis/local/out/iter05-s*/snapshot.json --label iter05 \
  -o antithesis/local/out/iter05.json

python3 $R diff antithesis/local/out/iter04.json antithesis/local/out/iter05.json
python3 $R by-op antithesis/local/out/iter05.json antithesis/scratchbook/api-surface.md
```

What to look at:

- **`diff`: new lines and functions** since the last iteration. This is the
  main number. Ignore overall percentage: startup code dominates it, and it
  stops moving early.
- **`diff`, the other direction:** code the previous iteration reached that
  this one doesn't. A little is noise. A lot means the change made something
  worse (e.g. a smaller pool that stopped some code path).
- **`by-op`:** for each operation, how many of its code locations were reached,
  and which were never reached. Local formats know about code that was never
  run, so this is where the **unreached functions** show up: the most direct
  hints for what to change next.

## 3. Antithesis coverage

After an Antithesis run finishes:

1. Use `antithesis-triage` to check the run was healthy: setup completed,
   drivers ran, no harness errors. Coverage from a broken run is meaningless.
2. Export and normalize its coverage:

   ```bash
   mkdir -p antithesis/local/antithesis
   snouty --json runs show <run-id> > antithesis/local/antithesis/<run-id>.json
   python3 $R normalize --format antithesis antithesis/local/antithesis/<run-id>.json \
     --repo <sut-root> --label <short-name> -o antithesis/local/antithesis/<short-name>.json
   python3 $R summary antithesis/local/antithesis/<short-name>.json
   ```

### What the Antithesis export contains

`.results.coverage` (format `full`) lists, for each source file, each function
and the **spans** in it that were reached at least once during the whole run.
Each span has an **edge count**: the number of distinct instrumented points
reached in it. This is not how many times it ran.

What this means for measuring:

- **Only reached code is listed.** It can't tell you what was never reached.
  Use local coverage (`by-op`) for that.
- **It covers the whole run, with no timing.** You can't see when coverage
  stopped growing within a run. Compare **runs with each other**, and keep run
  length the same between runs you compare.
- **It includes toolchain and dependency code**, sometimes with relative paths
  that look like SUT paths (e.g. a dependency's `src/lib.rs`). `--repo` drops
  files that aren't in the SUT repo. If dependency files share relative paths
  with SUT files, also pass `--keep-function` with a pattern for the SUT's own
  function names (for Rust, `'^<?mycrate::'`). Record the pattern in
  `coverage-setup.md`.
- **Function names differ by language.** Rust names are full paths
  (`mycrate::world::actions::charge`). Python names carry a tag
  (`parse_args (branch jump)`), which `normalize` strips. `by-op` matches the
  short function name in `api-surface.md` against these.

What to look at:

- **`summary`: total edges and lines** in SUT code. Compare with the previous
  Antithesis run of the same length.
- **`diff` against the previous Antithesis snapshot:** new functions and lines.
  This is the "newly discovered edges" signal. Where it lands shows which
  operations are still producing new behavior.
- **`diff` against the latest local snapshot**, both ways. **Compare
  functions, not lines.** Antithesis reports line *ranges*, which include blank
  lines and comments, while local coverage counts individual lines, so line
  counts aren't comparable between the two (they are fine between two
  Antithesis runs, or between two local runs).
  - reached only in Antithesis: code that faults and timing reach (recovery,
    retries, timeouts). Expected, and good.
  - reached only locally: usually an environment difference, or drivers that
    fail in Antithesis. Check outcome lines.

## When to move to the next tier

Move on when **both** are true for the current set of operations:

- the last 2–3 local iterations each added only a handful of new lines, and
- the latest Antithesis run added little over the previous one of the same length.

## Ledger

`antithesis/scratchbook/workload-ledger.md`. Add one row per iteration, and one
per Antithesis run.

```markdown
# Workload Ledger

| # | Date | Change | Active tiers / groups | Local: new lines / functions | Antithesis run | Antithesis: edges (Δ) | Notes |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-09 | Initial Tier 0 drivers | 0 | baseline: 812 / 64 | — | — | all ops mostly ok |
| 2 | 2026-10-09 | — | 0 | — | `a1b2…-62-0` (60 min) | 1,940 (baseline) | |
| 3 | 2026-10-10 | kv.put: values up to max_value_size | 0 | +37 / +4 | — | — | reached large-value path |

## Tried and didn't help

- (iteration, change, why it didn't help)
```

Keep snapshots in `antithesis/local/out/` and `antithesis/local/antithesis/`
named by iteration, so any two can be compared later.
