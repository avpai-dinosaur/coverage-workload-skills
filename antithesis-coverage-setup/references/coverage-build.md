# Coverage Build

## Goal

A local-only build of the SUT that records which code ran, so the workload can
be measured without an Antithesis run.

Antithesis runs keep using the normal instrumented build from `antithesis-setup`.
Antithesis reports its own coverage (see `antithesis-coverage-workload`,
`references/measuring-progress.md`).

## Steps

1. Add a build argument (e.g. `ARG COVERAGE=0`) to each SUT Dockerfile. When it
   is `1`, build with the coverage flags below.
2. Create `antithesis/config/docker-compose.coverage.yaml`, an override that:
   - sets `COVERAGE: "1"` as a build argument for each SUT service
   - gives each SUT service a **different image tag** (e.g. `image: myserver:coverage`).
     Otherwise the coverage build overwrites the images that `snouty validate`
     and `antithesis-launch` use.
   - mounts a `coverage` named volume at `/coverage` in each SUT service
   - points each service's coverage output at **its own folder**,
     `/coverage/<service>/`, using the variable from the table below. Every
     container's main process is PID 1, so file names based on the process ID
     would clash between services.
   - sets `ANTITHESIS_SDK_LOCAL_OUTPUT=/logs/sdk-<service>.jsonl` on every
     service that emits `setup_complete`, **and mounts `sut-logs` at `/logs` on
     it** (often the workload container, which otherwise doesn't have it).
     `run-local.sh` watches these files to know when setup is done.
3. Check that the SUT **writes coverage when stopped** (see below).
4. Fill in `extract_coverage()` in `run-local.sh` to turn the raw files into one
   coverage file.

## By language

| Language | Build | Output variable | Convert to |
|---|---|---|---|
| Go | `go build -cover -coverpkg=./...` | `GOCOVERDIR=/coverage/<service>` | `go tool covdata textfmt -i=<dirs> -o coverage.gocov` |
| Rust | `RUSTFLAGS="-C instrument-coverage"` | `LLVM_PROFILE_FILE=/coverage/<service>/%p-%m.profraw` | `llvm-profdata merge` then `llvm-cov export -format=lcov -Xdemangler=rustfilt <binary> -instr-profile=...` → `coverage.lcov` |
| C/C++ (clang) | `-fprofile-instr-generate -fcoverage-mapping` | same as Rust | same as Rust, with `-Xdemangler=c++filt` |
| Java | JaCoCo agent: `-javaagent:jacocoagent.jar=destfile=/coverage/<service>/jacoco.exec` | — | `jacococli report ... --xml coverage.xml` |
| Python | `coverage run --parallel-mode --source=<pkg>` | `COVERAGE_FILE=/coverage/<service>/.coverage` | `coverage combine` then `coverage lcov -o coverage.lcov` |
| JS/TS | `c8` or `NODE_V8_COVERAGE` | `NODE_V8_COVERAGE=/coverage/<service>` | `c8 report --reporter=lcov` → `coverage.lcov` |

Demangle function names (`-Xdemangler`). Without it, Rust and C++ names in
the LCOV file are unreadable symbols, and the per-operation report can't match
them to `api-surface.md`.

Go's coverage file has line ranges but no function names, so for Go the
per-operation report only shows lines reached in each operation's files.

Each coverage file goes with a `--format` value for `coverage_report.py normalize`:

| File | `--format` |
|---|---|
| `coverage.lcov` | `lcov` |
| `coverage.gocov` | `gocover` |
| `coverage.xml` | `jacoco` |

For Rust and C/C++, conversion needs the exact instrumented binary. Copy it out
of the image too, or run the conversion inside the coverage-built image.

If the SUT has several languages (e.g. a Rust server plus a Python supervisor),
convert each to LCOV and concatenate the files. The report script reads
concatenated LCOV.

## Writing coverage on stop

Most of these tools only write coverage when the process **exits normally**.
`run-local.sh` stops the SUT with SIGTERM and waits up to 60 seconds. Check:

1. Start the coverage build, wait a few seconds, run
   `docker compose stop <service>`.
2. Copy its folder out (`docker compose cp <service>:/coverage/<service>/. /tmp/cov`)
   and confirm it is not empty.

If it is empty:

- **The process is PID 1 and ignores SIGTERM.** PID 1 ignores signals it has no
  handler for. Add `init: true` to the service in the coverage override, so a
  small init process passes the signal on.
- **The process dies on SIGTERM without exiting normally.** This is the usual
  case for Go and Node programs with no signal handling.
  - Rust and C/C++: use LLVM's continuous mode, which writes counters as the
    program runs: add `%c` to the file pattern (`/coverage/<service>/%p-%c.profraw`).
  - Python: set `sigterm = true` under `[run]` in the coverage config.
  - Go and Node: no flag-only fix. Ask the user whether a small signal handler
    may be added behind the coverage build argument.
- **The process writes coverage, but to its working directory.** Check that the
  output variable is set on that service.

Don't trust any coverage numbers until this check passes.
