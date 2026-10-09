# Driver Interface

## Goal

Drivers are always short Python scripts. This step decides how they talk to
the system, and writes `antithesis/test/v1/main/helper_client.py` so each
driver can start with `c = client()`.

Use the **How to call** column in `api-surface.md` to see what kind of interface
the system has.

## Case 1: Network API (most systems)

The system has an HTTP, gRPC, or other network protocol (Redis, SQL, Kafka,
...).

- Use the official Python client if one exists. Otherwise use `requests`,
  generated gRPC stubs, or a small protocol library.
- `helper_client.py` holds connection details (service names, ports) and
  returns a ready client. It also sets **short timeouts** (a few seconds), so
  drivers don't hang during network faults.
- If there are several servers, let `client()` pick one at random with
  `antithesis.random.random_choice`, so traffic spreads across them.
- Install the client library and the `antithesis` Python package in the image
  that holds the test templates.

## Case 2: Existing CLI

The system ships a CLI that covers the operations and talks to a running server.

- `helper_client.py` wraps `subprocess.run([...], timeout=...)` and returns
  stdout, or raises on a non-zero exit.
- Install the CLI in the image that holds the test templates.

In every case, the image that holds the test templates also needs the
`antithesis` Python package. `helper_common.py` uses its `random` module.

## Case 3: Library, or anything else

The system is a library, or has no interface that Python can call from
another process. **There is no default for this case.** It varies too much
between systems, and the right answer depends on where shared state lives.

**Stop and ask the user** before building anything. Explain:

- Drivers are separate processes, started and stopped by Test Composer, often
  several at once.
- For drivers to collide with each other (which is how most state gets
  explored), they must all reach the same state.
- Where does this system keep its state? Files on disk (which could go on a
  shared volume), an external database, or only in memory?

One pattern to offer, when it fits:

- A small CLI built around the library, with a **REPL mode**. A driver starts
  `sutcli --repl`, writes one command per line on stdin (one command per
  operation in `api-surface.md`, named after the operation ID), and reads one
  result line per command.
- This only gives drivers shared state if the library keeps its state somewhere
  outside the process, such as files on a shared volume. If state lives only in
  memory, each driver gets its own private copy, and drivers never collide.

Record the user's decision under **Shared state** in `coverage-setup.md`.

## Check

From inside the container that holds the test templates, run a one-line Python
call for one Tier 0 operation using `helper_client.client()`, and confirm it
succeeds.
