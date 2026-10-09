# Plan: coverage-driven workload skills

Two skills, run in this order after `antithesis-api-surface` and
`antithesis-setup`:

1. **`antithesis-coverage-setup`**: harness additions. A log sidecar, a way for
   drivers to reach the system, a coverage build, and a local runner.
2. **`antithesis-coverage-workload`**: writes the drivers and grows them using
   coverage.

```
antithesis-api-surface  →  antithesis-setup  →  antithesis-coverage-setup  →  antithesis-coverage-workload
  (what operations exist)    (base harness)        (sidecar, interface,          (drivers, measure, grow)
                                                    coverage build, local runner)
```

Neither skill adds properties. Properties are written later as reducer scripts
that read the system's logs in the sidecar.

---

# Skill 1: antithesis-coverage-setup

## What it does

Adds everything the coverage workload needs on top of the base harness from
`antithesis-setup`. It does not write any drivers.

## Inputs

- A working harness from `antithesis-setup`: `docker-compose.yaml`, SUT images,
  SDK installed, `setup_complete` emitted
- `antithesis/scratchbook/api-surface.md` (to know how operations are called)

## Skill layout

```
antithesis-coverage-setup/
  SKILL.md
  references/
    log-sidecar.md        shared log volume + sidecar container
    driver-interface.md   how Python drivers reach the system
    coverage-build.md     coverage build for local runs, per language
    local-runner.md       running the workload locally like Test Composer
  assets/
    sidecar/              Dockerfile + log collector
    local_composer.py     local stand-in for Test Composer
    coverage_report.py    raw coverage → per-function / per-operation report
```

## Output

- `sidecar` service and `sut-logs` volume in `docker-compose.yaml`
- `antithesis/sidecar/` with the collector and an empty `reducers/` folder
- `docker-compose.coverage.yaml` override and coverage build argument
- `antithesis/local/`: `local_composer.py`, `coverage_report.py`, and a
  `run-local.sh` that does the full local run
- `antithesis/scratchbook/coverage-setup.md`: how drivers reach the system,
  where logs go, how to run locally, anything left unresolved

## Reference: log-sidecar.md

- Add a named volume `sut-logs` mounted at `/logs` in every SUT container and in
  a new `sidecar` container.
- Wrap each SUT container's entrypoint so its output goes **both** to stdout
  (Antithesis still sees it) and to `/logs/{service}.log`, e.g.
  `exec "$@" > >(tee -a /logs/$SERVICE.log) 2>&1`.
- Use a shared volume, not the network. Antithesis injects network faults, and
  logs sent over the network would be dropped, so reducers would see gaps that
  aren't real.
- Don't use a Docker logging driver. `antithesis-setup` forbids custom
  `logging:` settings.
- The sidecar runs a small collector that follows every log file and passes each
  line, tagged with its service, to every reducer script in
  `/opt/reducers/`. **This skill leaves that folder empty.**
- The collector must survive being restarted. It should remember how far it read
  in each file, or re-read from the start.
- Check: start the stack and confirm lines from every SUT service reach the
  collector.

## Reference: driver-interface.md

Drivers are always Python. This step decides how they talk to the system and
writes a small `helper_client.py` that the drivers import.

**1. Network API (most systems).** The system has an HTTP, gRPC, or wire
protocol API (Redis, SQL, Kafka, ...). Drivers use a Python client for it: the
official one if it exists, otherwise `requests`, generated gRPC stubs, etc. No
extra code goes in front of the system.

**2. Existing CLI.** If the system ships a CLI that covers the operations and
talks to a running server, drivers can call it with `subprocess`.

**3. Library or other non-language-agnostic interface.** This is **left open
on purpose.** It varies too much between systems, and the right answer depends
on where shared state lives. One pattern to suggest:

- A small CLI built around the library, with a **REPL mode**. Each driver
  starts `sutcli --repl`, sends commands on stdin (one per operation in
  `api-surface.md`, named after the operation ID), and reads one result line
  per command.
- The open question is **shared state**. A REPL process keeps the library's
  in-memory state only for the life of that driver. Concurrent drivers only
  interact if the library keeps its state somewhere they all reach (files on a
  shared volume, a database). If it doesn't, drivers won't collide and much of
  the state space is unreachable.

For case 3 the skill must stop and ask the user how drivers should reach shared
state before building anything. Write the decision in `coverage-setup.md`.

## Reference: coverage-build.md

- Add a build argument (e.g. `COVERAGE=1`) to the SUT Dockerfiles, and a
  `docker-compose.coverage.yaml` override that turns it on and mounts a
  `coverage` volume.
- Antithesis runs use the normal instrumented build. The coverage build is
  only used locally.

| Language | Coverage build | Where it writes |
|---|---|---|
| Go | `go build -cover` | `GOCOVERDIR=/coverage` |
| Rust | `-C instrument-coverage` | `LLVM_PROFILE_FILE=/coverage/%p.profraw` |
| C/C++ | clang `-fprofile-instr-generate -fcoverage-mapping` | same as Rust |
| Java | JaCoCo agent | `destfile=/coverage/jacoco.exec` |
| Python | `coverage run --parallel-mode` | `/coverage/.coverage.*` |
| JS/TS | `c8` / `NODE_V8_COVERAGE` | `/coverage/` |

Gotcha: most of these tools only write coverage when the process **exits
cleanly**. Local runs must stop the SUT with SIGTERM and wait, and the SUT has
to exit normally on SIGTERM. Check this before trusting any numbers.

## Reference: local-runner.md

Test Composer doesn't run locally, and `snouty validate` only checks that test
commands exist. `local_composer.py` fills the gap. It reads the test template
folder, runs `first_` commands once, then for a set number of minutes keeps N
randomly chosen `parallel_driver_` commands running at once (and runs
`serial_driver_` commands alone). It takes a seed so runs can be repeated.

`run-local.sh` does a full local run:
1. `docker compose -f docker-compose.yaml -f docker-compose.coverage.yaml up`
2. Wait for `setup_complete`
3. Run `local_composer.py` in the workload container for a fixed time and seed
4. Stop the SUT with SIGTERM and wait, so coverage is written
5. Run `coverage_report.py`: per-function coverage for the SUT's own code, per
   operation (using `code_locations` from `api-surface.md`), and a diff against
   the previous run

Check: with a single dummy driver, a local run produces a non-empty coverage
report.

---

# Skill 2: antithesis-coverage-workload

## What it does

Builds an Antithesis workload that explores as much of the system as possible,
starting from the core operations and growing outward. It uses code coverage,
both locally and from Antithesis, to tell whether each change helped.

The workload **does not check correctness**. It contains no properties or
assertions.

## Inputs

- `antithesis/scratchbook/api-surface.md`. The checker must pass.
- Everything from `antithesis-coverage-setup`, including
  `antithesis/scratchbook/coverage-setup.md`

## Skills it reuses

| Skill | Used for |
|---|---|
| `antithesis-api-surface` | List of operations, tiers, inputs and limits, code locations |
| `antithesis-coverage-setup` | Sidecar, driver interface, coverage build, local runner |
| `antithesis-launch` | Submitting runs |
| `antithesis-triage` | Checking a run finished cleanly |
| `antithesis-query-logs` | Counting operation outcomes across all timelines |
| `antithesis-review-inputs` | Periodic check on how well drivers use randomness |
| `antithesis-documentation` | Test Composer and SDK reference |

## Skill layout

```
antithesis-coverage-workload/
  SKILL.md
  references/
    initial-workload.md    first workload: Tier 0 only, simple drivers, no properties
    measuring-progress.md  how to tell if the workload is doing well (local + Antithesis)
    growing-workload.md    how to choose and make the next change
  assets/
    driver_template.py     starting point for a driver
```

## Workflow

Each time the skill is invoked, it does **one** of these steps, then stops and
reports back. Long sessions get worse results.

1. **Initial workload** (once). One driver per Tier 0 operation. →
   `initial-workload.md`
2. **Baseline.** Measure locally, then run in Antithesis and measure there. →
   `measuring-progress.md`
3. **Iterate** (repeat). Make one change, measure it locally, and record the
   result. Every few iterations, or when local coverage stops growing, run in
   Antithesis. → `growing-workload.md`, `measuring-progress.md`

Progress is recorded in `antithesis/scratchbook/workload-ledger.md` so any
session can pick up where the last one stopped.

## Reference: initial-workload.md

### Rules

- **No properties.** No `Always`, `Sometimes`, `Reachable`, or any other SDK
  assertion in drivers. No checks of returned values. No `eventually_` or
  `finally_` commands that check state. Drivers only **do things** to the
  system. Correctness belongs to the reducers in the sidecar.
- **Only Tier 0 operations** to start.
- **Test Composer.** Drivers are test commands under
  `antithesis/test/v1/main/`. Test Composer decides which drivers run, when,
  and how many at once. The drivers don't decide.
- **Python, under 50 lines per driver, readable by a person** at a glance.
  Shared code (client setup, key choice) goes in `helper_common.py` and
  `helper_client.py` so each driver stays short.

### Shape

- One driver per operation: `parallel_driver_kv_put.py`,
  `parallel_driver_kv_get.py`, ... Test Composer mixes them, so the mix of
  operations comes from Composer, not from code we write.
- Use `serial_driver_` only for operations that really can't overlap with
  others. Default to `parallel_driver_`.
- Each driver run does a small random number of calls (e.g. 1–20) to its
  operation, then exits.
- **Randomness comes from the Antithesis SDK** (`antithesis.random`) so
  Antithesis can steer choices. It falls back to normal randomness locally.
- **Small shared key space.** Drivers pick keys, IDs, and names from a small
  pool shared by all drivers, so operations collide with each other. If every
  put writes a new random key, get and delete almost never touch the same
  data.
- **Input values come from the inputs table** in `api-surface.md`: the limits
  and defaults listed there, values just above and below them, empty values,
  and typical values.
- **Errors are expected.** Under faults, calls time out and fail. Catch them,
  log them, and keep going. A driver exits non-zero only when it has a bug of
  its own.
- **Every call logs one outcome line** in a fixed format, e.g.
  `OP kv.put ok` / `OP kv.put error=timeout`. This is not a property. It's how
  we measure whether each operation actually runs (see
  `measuring-progress.md`).

### Example driver

```python
#!/usr/bin/env python3
"""Put random values into keys from the shared pool."""
from antithesis.random import random_choice
from helper_client import client
from helper_common import pick_key, pick_value, log_outcome

c = client()
for _ in range(random_choice(range(1, 21))):
    key, value = pick_key(), pick_value()
    try:
        c.put(key, value)
        log_outcome("kv.put", "ok")
    except Exception as e:
        log_outcome("kv.put", f"error={type(e).__name__}")
```

## Reference: measuring-progress.md

Three signals, from cheapest to most expensive.

### 1. Are the operations running? (outcome lines)

- Count `OP` lines per operation and per outcome.
- Locally: grep the logs. In Antithesis: use `antithesis-query-logs` across
  all timelines.
- Warning signs: an operation that is never called, or that always fails with
  the same error (wrong arguments, missing setup, wrong address). Fix these
  before looking at coverage. An operation that always errors only covers
  error-handling code.

### 2. Local coverage

Run `antithesis/local/run-local.sh` (from `antithesis-coverage-setup`). There
are no faults locally.

What to look at:
- **New code reached since the last iteration** (functions and lines), not
  overall percentage. Overall percentage is dominated by startup code and stops
  moving early.
- **Coverage per operation**: coverage inside each operation's
  `code_locations` from `api-surface.md`. This shows which operations are
  thinly exercised.
- **Only count the SUT's own code.** Leave out vendored libraries, generated
  code, and tests.
- **Run 2–3 seeds and combine them**, so random variation isn't mistaken for
  progress.

### 3. Antithesis coverage (new edges)

- After each Antithesis run, export the list of newly discovered edges:
  `snouty --json runs show <run-id> | jq '.results.coverage'`
- **Map each edge to its file and function**, then to an operation through the
  `code_locations` in `api-surface.md`.
- What to look at:
  - **The rate of new edges over the run.** If new edges stop appearing early
    in the run, the workload has run out of new places to reach.
  - **Where new edges land:** which operations and areas are still producing
    new behavior.
  - **Compare with local coverage.** Code reached only in Antithesis comes from
    faults and timing. Code reached only locally usually means a difference
    between the local and Antithesis environments.
- Before reading coverage, use `antithesis-triage` to check that the run was
  healthy (setup completed, drivers ran).

### When to move to the next tier

Move on when **both** are true for the current set of operations:
- the last 2–3 local iterations added almost no new code, and
- the most recent Antithesis run showed new edges levelling off.

### Ledger

`antithesis/scratchbook/workload-ledger.md`, one row per iteration:

| # | Date | Change | Tiers/groups active | Local new functions / lines | Antithesis run | New edges | Notes |
|---|---|---|---|---|---|---|---|

Also include a short list of things tried that didn't help, so they aren't
tried again.

## Reference: growing-workload.md

Each iteration makes **one** change, chosen in this order:

1. **Fix broken operations.** Any operation that's never called or always
   fails.
2. **Deepen current operations.** If an operation's code is thinly covered,
   change how it's called: input values from the inputs table, a smaller or
   larger key pool, optional arguments it hasn't used yet.
3. **Add the next tier or feature group.** Tier 1 next, then one Tier 2 feature
   group at a time, then Tier 3. Respect `Requires`. Keep the earlier drivers:
   much of the interesting behavior happens where new operations meet the core
   ones.
4. **Every few iterations**, run `antithesis-review-inputs` on the drivers.

After each change: measure locally (`measuring-progress.md`), add a ledger row,
and stop. Keep a change that reached new code; undo or rethink one that didn't.

---

## Status

Both skills are drafted in `antithesis-coverage-setup/` and
`antithesis-coverage-workload/`. Answers to the earlier open questions:

- **Edge export:** `snouty --json runs show <run-id> | jq .results.coverage`.
  Format `full`: for each file, each function's reached spans with a count of
  distinct edges. It covers the whole run, lists only reached code, and has no
  timing, so runs are compared with each other (same length), and local
  coverage is used to find unreached code. It includes toolchain and
  dependency code, which `coverage_report.py normalize --repo` filters out.
- **Reducers:** a separate skill or the user. The sidecar ships with an empty
  reducer folder.
- **Drivers:** one per operation to start; short sequences only when coverage
  shows they're needed.
- **Naming:** `antithesis-api-surface`.
