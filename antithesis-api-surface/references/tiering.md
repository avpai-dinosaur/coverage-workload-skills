# Tiering

## The tiers

| Tier | Meaning | Example (key-value store) |
|---|---|---|
| 0: Core | Smallest set that makes the system do its main job | put, get, delete, list keys |
| 1: Core variants | Richer forms of core operations; no new concept to learn | conditional put, batch write, read an older version |
| 2: Features | Adds a new concept with its own state | watch for changes, keys that expire |
| 3: Specialized | Admin, maintenance, niche, or experimental | add/remove a server, backup/restore, access control |

Tier 2 is split into **feature groups** so features can be added to the
workload one at a time. A feature group is a set of operations that only make
sense together (e.g. `lease.grant`, `lease.keepalive`, `lease.revoke`).

## How to decide

Use these signals, strongest first.

1. **Dependencies.** If an operation needs something that only another operation
   creates, it goes in the same tier or a later one. This rule is absolute; the
   checker enforces it. Record these dependencies in the **Requires** field.
2. **Docs.** In the quickstart or getting-started guide → Tier 0. Covered on
   the main API page as an option or variant of a core operation → Tier 1. Has
   its own feature page or guide → Tier 2. Only in admin or operations guides, or
   marked beta or experimental → Tier 3.
3. **Client library and CLI.** Top-level methods lean core. Methods inside a
   sub-client or namespace (`client.Maintenance`, `admin` subcommand) lean
   specialized.
4. **Needs a setting turned on.** Leans specialized.
5. **Code layout.** In its own module, package, or plugin → leans specialized.
6. **GitHub issues (optional).** A feature that comes up in a large share of
   issues is probably used more than the docs suggest. Use only as a tie-breaker.

## Questions that settle most cases

- **Tier 0 or Tier 1?** Could the system still do its main job without this
  operation? If yes, it's not Tier 0.
- **Tier 1 or Tier 2?** Does using it mean learning a new concept with its own
  state (a lease, a subscription, a transaction ID)? If yes, Tier 2.
- **Tier 2 or Tier 3?** Would a typical application developer use it, or mainly
  an operator or admin? Operator or admin → Tier 3.

## Keeping Tier 0 small

Tier 0 is the base of the whole workload, so keep it small: usually 2–6
operations. It should be enough to create data, read it back, change it, and
remove it. If Tier 0 has more than about 8 operations, look again.

## Writing the reason

Every **Tier reason** bullet names its evidence:

- Good: "First example in `docs/quickstart.md`; top-level `client.Put`."
- Good: "Own guide at `docs/features/leases.md`; needs `lease.grant` first."
- Bad: "Seems like a core operation."

When signals disagree, say which one you followed and why, set confidence to
`low`, and add an **Uncertain** bullet.
