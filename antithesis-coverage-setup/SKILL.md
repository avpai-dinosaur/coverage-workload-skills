---
name: antithesis-coverage-setup
description: >
  Prepare an Antithesis harness for a coverage-driven workload: add a sidecar
  container that collects every SUT log, decide how Python drivers reach the
  system, add a coverage build for local runs, and add a local runner that
  stands in for Test Composer. Use after antithesis-setup and before
  antithesis-coverage-workload.
compatibility: Requires Docker Compose v2, Python 3, and snouty (https://github.com/antithesishq/snouty).
metadata:
  version: "draft"
---

# Antithesis Coverage Setup

## Purpose and Goal

Add what `antithesis-coverage-workload` needs on top of the base harness from
`antithesis-setup`. This skill writes no drivers and no properties.

Success means:

- Every SUT container's output reaches a `sidecar` container through a shared
  volume, and the sidecar feeds it to (for now, zero) reducer scripts
- It is written down how Python drivers reach the system, and a small
  `helper_client.py` exists for them to import
- A coverage build of the SUT can run locally and write coverage on a clean stop
- `antithesis/local/run-local.sh` does a full local run and produces a coverage
  file and a count of operation outcomes
- `snouty validate` still passes

## Prerequisites

- DO NOT PROCEED unless `antithesis/config/docker-compose.yaml` exists and
  reaches `setup_complete`. Use `antithesis-setup` first.
- DO NOT PROCEED unless `antithesis/scratchbook/api-surface.md` exists. Use
  `antithesis-api-surface` first.
- `snouty` must be installed.

## Reference Files

| Reference | When to read |
|---|---|
| `references/log-sidecar.md` | Step 1 |
| `references/driver-interface.md` | Step 2 |
| `references/coverage-build.md` | Step 3 |
| `references/local-runner.md` | Step 4 |

## Assets

| Asset | Copy to |
|---|---|
| `assets/log-tee.sh` | Into each SUT image, e.g. `/usr/local/bin/log-tee.sh` |
| `assets/sidecar/` | `antithesis/sidecar/` (plus an empty `reducers/` folder) |
| `assets/local_composer.py` | `antithesis/local/local_composer.py` |
| `assets/run-local.sh` | `antithesis/local/run-local.sh`, then fill in its settings |

## Workflow

Do the steps in order. After each one, check that the stack still starts and
reaches `setup_complete` before moving on.

1. **Log sidecar.** Read `references/log-sidecar.md`.
2. **Driver interface.** Read `references/driver-interface.md`. If the system
   has no network API or CLI, stop and ask the user (see that file).
3. **Coverage build.** Read `references/coverage-build.md`.
4. **Local runner.** Read `references/local-runner.md`.
5. **Validate.** Rebuild images and run `snouty validate antithesis/config`.
6. **Write `antithesis/scratchbook/coverage-setup.md`** (format below).

## Output

- `antithesis/config/docker-compose.yaml`: `sidecar` service, `sut-logs`
  volume, wrapped SUT entrypoints
- `antithesis/config/docker-compose.coverage.yaml`: local-only override
- `antithesis/sidecar/`: `Dockerfile`, `collector.py`, empty `reducers/`
- `antithesis/test/v1/main/helper_client.py`
- `antithesis/local/`: `local_composer.py`, `run-local.sh`
- `antithesis/scratchbook/coverage-setup.md`

### coverage-setup.md

Short and plain. Later skills read it.

- **How drivers reach the system:** network client / existing CLI / other, and
  what `helper_client.py` provides
- **Shared state:** where the state lives that drivers share (only needed if
  it isn't obvious, e.g. for libraries)
- **Logs:** which services write to `/logs`, and their file names
- **Local runs:** the command, how long one takes, and the coverage file it
  produces (`coverage.lcov`, `coverage.gocov`, or `coverage.xml`)
- **Coverage format and paths:** what to pass to `coverage_report.py normalize`
  (`--format`, `--repo`, and `--keep-function` if needed)
- **Known gaps:** anything not working yet

## General Guidance

- Don't change how the SUT behaves. Wrapping entrypoints and adding build flags
  is fine. Editing SUT source is a last resort; ask the user first.
- Keep the Antithesis build and the coverage build separate. Antithesis runs
  never use `docker-compose.coverage.yaml`.
- Don't add properties, assertions, or reducers.

## Self-Review

If your agent supports sub-agents, have a fresh agent check this list against
the output files. Otherwise check it yourself.

- Every SUT service's output goes to both stdout and `/logs/<service>.log`
- Logs reach the sidecar through a named volume, not the network, and no
  `logging:` driver was added
- The sidecar's `reducers/` folder exists and is empty
- `coverage-setup.md` says how drivers reach the system; for a system without a
  network API or CLI, the user's answer about shared state is recorded
- A local run produced a non-empty coverage file, and `coverage_report.py
  normalize` turned it into a snapshot with SUT files in it
- `snouty validate antithesis/config` passes with freshly built images
