# Initial Workload

## Goal

A first workload that drives only the Tier 0 operations from `api-surface.md`,
using one tiny Python driver per operation. It's the base everything else is
added to. These rules apply to every driver written later too.

## No properties

The workload only **does things** to the system. It never checks whether the
system did them right.

- No SDK assertions: `Always`, `AlwaysOrUnreachable`, `Sometimes`, `Reachable`,
  `Unreachable`, and so on
- No checks on what an operation returned ("the value I read should be the one
  I wrote")
- No `eventually_`, `finally_`, or `anytime_` commands
- No `first_` command that checks state. A `first_` command is only allowed if
  the system needs one-time preparation before any operation can work (e.g.
  creating a database or a namespace)

Correctness is checked by reducer scripts that read the logs in the sidecar.
Those are written separately. Keeping the workload free of checks keeps it
simple, and means a wrong check never stops the workload from exploring.

## Layout

```
antithesis/test/v1/main/
  helper_client.py           from antithesis-coverage-setup: returns a ready client
  helper_common.py           key pool, value menus, outcome logging
  parallel_driver_kv_put.py
  parallel_driver_kv_get.py
  parallel_driver_kv_delete.py
```

- File name: `parallel_driver_` + the operation ID with `.` replaced by `_`.
- Use `serial_driver_` only for an operation that truly can't overlap with any
  other (rare). Default to `parallel_driver_`.
- Files starting with `helper_` are ignored by Test Composer.
- Every driver needs `#!/usr/bin/env python3` and execute permission.

## helper_common.py

Start from `assets/helper_common.py`. It holds what drivers share, so each
driver stays short:

- **A small shared pool of names.** Keys, IDs, names: whatever identifies data
  in this system. Every driver picks from the same pool. If each put wrote a
  fresh random key, gets and deletes would almost never touch the same data,
  and the system would mostly see unrelated requests. Start with about 10–20
  names. Changing the pool size is one of the main ways to change behavior
  later.
- **Value menus from the inputs table.** For each input in `api-surface.md`,
  build a short list of values: typical ones, the limits and defaults listed in
  "Limits and notes", values just inside and just outside those limits, and
  empty or zero values. Drivers pick from these lists. Don't use open-ended
  random ranges: they almost never hit the edges.
- **`log_outcome(op_id, outcome)`**, which prints one line per call:
  `OP kv.put ok` or `OP kv.put error=Timeout`. This is not a property. It's how
  `measuring-progress.md` tells whether each operation actually runs.

## Drivers

Start each driver from `assets/driver_template.py`. A driver:

1. gets a client from `helper_client.client()`
2. does a small random number of calls to its one operation (e.g. 1–20)
3. picks every argument from the pool and menus with `antithesis.random`
4. catches every error from the system, logs it with `log_outcome`, and carries on
5. exits 0

Notes:

- **All randomness comes from `antithesis.random`** (`random_choice`,
  `get_random`). Antithesis uses it to steer exploration. Outside Antithesis it
  falls back to normal randomness. Never use Python's `random` module.
- **Errors are expected.** Under faults, calls time out, connections drop,
  servers restart. That's the point. A driver exits non-zero only when the
  driver itself is broken (e.g. a typo), never because the system returned an
  error.
- **Keep it under 50 lines and obvious.** Someone should understand a driver
  in a few seconds. Anything clever belongs in `helper_common.py`, and even
  there, keep it small.

Example (`parallel_driver_kv_put.py`):

```python
#!/usr/bin/env python3
"""Put values from the value menu into keys from the shared pool."""
from helper_client import client
from helper_common import pick_name, pick_value, pick_count, log_outcome, error_name

c = client()
for _ in range(pick_count()):
    key, value = pick_name(), pick_value()
    try:
        c.put(key, value)
        log_outcome("kv.put", "ok")
    except Exception as e:
        log_outcome("kv.put", error_name(e))
```

## Check before measuring

1. Run a short local run: `antithesis/local/run-local.sh check 1` (lower
   `DURATION` for this one run if it's long).
2. In `antithesis/local/out/check/ops.txt`, every Tier 0 operation should appear,
   mostly with `ok`. In `workload.log`, no driver should have non-zero exits.
3. Fix any driver that never logs `ok`. Usually it's wrong arguments, a wrong
   address, or something in `Requires` that isn't being done.
4. Rebuild images and run `snouty validate antithesis/config`.

Then move on to the baseline (`measuring-progress.md`).
