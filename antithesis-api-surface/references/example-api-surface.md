---
sut_path: /home/user/minikv
commit: 3f9c2a7e1b4d5c6a8e9f0a1b2c3d4e5f6a7b8c9d
updated: 2026-10-09
---

# API Surface: minikv

## Summary

| Field | Value |
|---|---|
| System | minikv |
| Tier 0 confirmed by user | yes |
| Operations | 6 |

minikv is a replicated key-value store. Its main job is storing and retrieving
values by key, with optional watches and expiring keys.

## Index

| ID | Name | Tier | Feature group | Kind |
|---|---|---|---|---|
| `kv.put` | Put | 0 | — | data |
| `kv.get` | Get | 0 | — | data |
| `kv.delete` | Delete | 0 | — | data |
| `kv.cas` | Compare and swap | 1 | — | data |
| `watch.create` | Watch | 2 | `watch` | data |
| `member.add` | Add member | 3 | — | admin |

## Feature Groups

| ID | Description |
|---|---|
| `watch` | Get notified when keys change |

## Flagged

- Left out: `/healthz` and `/metrics`. Health and metrics endpoints, not user operations.
- Docs mention "bulk import" (`docs/admin.md#import`) but no matching handler exists in code. The docs may be out of date.

## Tier 0: Core

### `kv.put`: Put

- **What it does:** Stores a value under a key, replacing any existing value.
- **Tier reason:** First example in `docs/quickstart.md`; top-level `client.Put`.

| Field | Value |
|---|---|
| ID | `kv.put` |
| Tier | 0 |
| Feature group | — |
| Kind | data |
| How to call | `PUT /v1/kv/{key}` |
| Requires | — |
| Enabled by | — |
| Changes state | keys |
| Reads state | — |
| Related | `kv.get`, `kv.delete`, `kv.cas` |
| Code locations | `server/kv/handler.go:PutHandler`, `server/store/store.go:Store.Put` |
| Confidence | high |

| Input | Type | Limits and notes |
|---|---|---|
| key | string | 1 byte to 1.5 KB |
| value | bytes | Up to 1 MB by default (`max_value_size`) |

### `kv.get`: Get

- **What it does:** Returns the current value for a key.
- **Tier reason:** In `docs/quickstart.md`; top-level `client.Get`.
- **Notes:** `consistent=true` routes the read through the leader.

| Field | Value |
|---|---|
| ID | `kv.get` |
| Tier | 0 |
| Feature group | — |
| Kind | data |
| How to call | `GET /v1/kv/{key}` |
| Requires | — |
| Enabled by | — |
| Changes state | — |
| Reads state | keys |
| Related | `kv.put`, `kv.delete` |
| Code locations | `server/kv/handler.go:GetHandler`, `server/store/store.go:Store.Get` |
| Confidence | high |

| Input | Type | Limits and notes |
|---|---|---|
| key | string | 1 byte to 1.5 KB |
| consistent | bool | Default false |

### `kv.delete`: Delete

- **What it does:** Removes a key. Deleting a missing key succeeds.
- **Tier reason:** In `docs/quickstart.md`; top-level `client.Delete`.

| Field | Value |
|---|---|
| ID | `kv.delete` |
| Tier | 0 |
| Feature group | — |
| Kind | data |
| How to call | `DELETE /v1/kv/{key}` |
| Requires | — |
| Enabled by | — |
| Changes state | keys |
| Reads state | — |
| Related | `kv.put`, `kv.get` |
| Code locations | `server/kv/handler.go:DeleteHandler`, `server/store/store.go:Store.Delete` |
| Confidence | high |

| Input | Type | Limits and notes |
|---|---|---|
| key | string | 1 byte to 1.5 KB |

## Tier 1: Core variants

### `kv.cas`: Compare and swap

- **What it does:** Writes a value only if the key's current version matches
  the given version.
- **Tier reason:** Documented as an option of put on `docs/api.md#put`; no new
  concept beyond versions, which get already returns.
- **Uncertain:** Could be Tier 2 if versions count as a separate concept. Kept
  at Tier 1 because every get response already includes the version.

| Field | Value |
|---|---|
| ID | `kv.cas` |
| Tier | 1 |
| Feature group | — |
| Kind | data |
| How to call | `PUT /v1/kv/{key}?if_version={n}` |
| Requires | — |
| Enabled by | — |
| Changes state | keys |
| Reads state | keys |
| Related | `kv.put`, `kv.get` |
| Code locations | `server/kv/handler.go:PutHandler`, `server/store/store.go:Store.CompareAndSwap` |
| Confidence | low |

| Input | Type | Limits and notes |
|---|---|---|
| key | string | 1 byte to 1.5 KB |
| value | bytes | Up to 1 MB by default |
| if_version | uint64 | 0 means "key must not exist" |

## Tier 2: Features

### `watch.create`: Watch

- **What it does:** Streams changes to a key or key prefix until the client
  disconnects.
- **Tier reason:** Own guide at `docs/features/watch.md`; adds subscriptions as
  a new concept.
- **Notes:** Only useful while writes are happening.

| Field | Value |
|---|---|
| ID | `watch.create` |
| Tier | 2 |
| Feature group | `watch` |
| Kind | data |
| How to call | `GET /v1/watch/{prefix}` (server-sent events) |
| Requires | `kv.put` |
| Enabled by | — |
| Changes state | watchers |
| Reads state | keys |
| Related | `kv.put`, `kv.delete` |
| Code locations | `server/watch/handler.go:WatchHandler`, `server/watch/hub.go:Hub.Subscribe` |
| Confidence | high |

| Input | Type | Limits and notes |
|---|---|---|
| prefix | string | Empty means all keys |
| start_version | uint64 | Replay from this version; must not be older than the last compaction |

## Tier 3: Specialized

### `member.add`: Add member

- **What it does:** Adds a new server to the cluster.
- **Tier reason:** Only in `docs/admin/cluster.md`; `kvctl member add`
  subcommand, with no method in the main client.

| Field | Value |
|---|---|
| ID | `member.add` |
| Tier | 3 |
| Feature group | — |
| Kind | admin |
| How to call | `kvctl member add {addr}` |
| Requires | — |
| Enabled by | — |
| Changes state | members |
| Reads state | members |
| Related | — |
| Code locations | `server/cluster/admin.go:AddMember` |
| Confidence | high |

| Input | Type | Limits and notes |
|---|---|---|
| addr | host:port | Must be reachable; max 7 members (`max_cluster_size`) |
