# Finding Operations

Code is the source of truth for which operations exist. Docs and client
libraries are checks against it.

## Where to look first

Start with the most formal definition the system has, then confirm against the
code that registers handlers.

| API style | Formal definition | Where handlers are registered |
|---|---|---|
| HTTP / REST | OpenAPI or Swagger files | Router setup (`HandleFunc`, `@app.route`, `router.get`, `@GetMapping`, etc.) |
| gRPC | `.proto` files (`service` blocks) | `Register*Server` calls |
| GraphQL | Schema files (`type Query`, `type Mutation`, `type Subscription`) | Resolver maps |
| Wire protocol (e.g. Redis, Postgres, Kafka) | Protocol spec or command table | Command dispatch table or `switch` on command name |
| CLI | Command tree definitions (cobra, clap, argparse, click) | Same |
| Library / embedded | Public exported API | Same |

Useful searches: `service `, `rpc `, `HandleFunc`, `route(`, `Register`,
`commandTable`, `AddCommand`, `@Mapping`.

## What counts as an operation

- One thing a user can ask the system to do, with its own handler. A GET and a
  PUT on the same path are two operations.
- Streaming calls (watches, subscriptions) count as one operation each.
- Variants that share a handler and differ only by a flag (e.g. `get` with
  `?consistent=true`) are **one** operation. Record the flag as an input.
  Split them only if they take clearly different code paths and the docs treat
  them as separate features.

## What to include

- The main data API
- Admin and maintenance operations offered through an API or CLI: membership
  changes, backup/restore, compaction, user and permission management, config
  changes at runtime

## What to leave out

- Lifecycle actions: shutdown, restart, crash recovery. Fault injection covers
  these.
- Internal traffic between servers (replication, gossip, heartbeats). These
  are not user-facing.
- Health checks, metrics, debug and profiling endpoints. List them in Flagged
  as left out, so nobody wonders whether they were missed.
- Deprecated operations that the current code no longer serves.

## Code locations

For each operation record the handler and the main function it calls into, as
`file:function` with paths relative to the SUT root. One to three entries is
usually right: the entry point plus where the real work happens. Later steps
use these to connect new code coverage back to operations.

## Checking against docs and client libraries

After listing from code, go through the API reference docs and the client
library's public methods. Anything there that has no match in your list goes in
Flagged. Either it was missed, or the docs or client are out of date.
