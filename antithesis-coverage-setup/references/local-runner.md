# Local Runner

## Goal

One command that runs the workload locally against the coverage build and
produces a coverage file. This is how `antithesis-coverage-workload` measures a
change in minutes, without an Antithesis run.

## Why it's needed

Test Composer only runs inside Antithesis. `snouty validate` checks that test
commands exist and are set up correctly, but doesn't run them.
`local_composer.py` fills the gap:

- runs one `first_` command, if any
- for a set time, keeps up to N drivers running: `parallel_driver_` whenever a
  slot is free, `serial_driver_` alone, `singleton_driver_` once, `anytime_`
  now and then
- skips `eventually_` and `finally_`
- prints each command's output, then how many times each command ran and how
  many times it exited non-zero

The seed fixes which commands run and when. Values chosen inside drivers still
vary between runs, because the Antithesis SDK uses normal randomness outside
Antithesis. That's why measurements combine several runs.

There is no fault injection locally. Local coverage shows what the operations
reach on their own. Antithesis adds faults and timing on top.

## Steps

1. Copy `assets/local_composer.py` and `assets/run-local.sh` to
   `antithesis/local/`.
2. Fill in the settings block in `run-local.sh`: the compose folder, the service
   that holds the test templates, and the SUT services built with coverage.
3. Fill in `extract_coverage()` using the conversion for the SUT's language
   (`coverage-build.md`). It must leave one of `$out/coverage.lcov`,
   `$out/coverage.gocov`, or `$out/coverage.xml`.
4. Add `antithesis/local/out/` to `.gitignore`.

## Check

There are no real drivers yet. Add a temporary
`antithesis/test/v1/main/parallel_driver_smoke.py` that calls one Tier 0
operation through `helper_client` and prints `OP <id> ok`. Then:

```bash
antithesis/local/run-local.sh smoke 1
python3 <antithesis-coverage-workload>/scripts/coverage_report.py normalize \
  --format lcov antithesis/local/out/smoke/coverage.lcov --repo <sut-root> -o /tmp/smoke.json
python3 <antithesis-coverage-workload>/scripts/coverage_report.py summary /tmp/smoke.json
```

The summary should list SUT source files, and `out/smoke/ops.txt` should show
`OP <id> ok` lines. If the summary lists no files, the paths in the coverage
file don't match the repo: try `--strip-prefix` with the build path. Delete the
smoke driver afterwards.

Record in `coverage-setup.md` the exact `normalize` arguments that worked, and
how long one local run takes.
