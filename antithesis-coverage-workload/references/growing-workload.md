# Growing the Workload

## Goal

Each iteration makes **one** change, measures it (`measuring-progress.md`), and
records it in the ledger. One change at a time, so each result can be traced to
its cause.

## Choosing the change

Work down this list and take the first item that applies.

1. **Fix broken operations.** Any active operation that never appears in the
   outcome lines, or is almost never `ok` locally. Nothing else matters until
   this is fixed.

2. **Deepen an operation that's thinly covered.** Use the latest local `by-op`
   output: an operation with unreached functions in its code locations. Read
   those functions, see what input or situation reaches them, and change how
   the driver calls the operation:
   - values from the inputs table not used yet (limits, just past limits, empty)
   - optional arguments or flags the driver never sets
   - a smaller name pool (more collisions on the same data) or a larger one
     (more distinct data, bigger internal structures)
   - more or fewer calls per driver run

3. **Add a short sequence**, only if coverage shows it's needed. Some code is
   only reached when one operation follows another on the same data quickly
   (e.g. create then immediately delete), and Test Composer mixing separate
   drivers rarely lines this up. Add a new driver that does the short sequence.
   Keep the single-operation drivers too. Give the reason in the ledger, naming
   the unreached code it targets.

4. **Add the next tier or feature group**, once the current set has stopped
   producing new coverage (see "When to move to the next tier" in
   `measuring-progress.md`). The order is:
   - all of Tier 1
   - one Tier 2 **feature group** at a time
   - Tier 3 operations, one or a few at a time

   Respect `Requires`. Check **Enabled by**: if an operation needs a setting
   or flag turned on, the harness has to change first. Stop and ask the user
   (the change belongs in `antithesis-coverage-setup`, not this skill). Write
   the new drivers following `initial-workload.md`.
   **Keep all earlier drivers.** Much of the interesting behavior happens where
   new operations meet the core ones (e.g. a watch open while keys are written
   and deleted).

5. **Every 3–4 iterations**, run `antithesis-review-inputs` on the drivers and
   treat its findings as candidates for step 2.

If none of these applies (every tier is active and nothing grows), tell the user
the workload has levelled off and summarize the ledger.

## After the change

1. Measure locally (`measuring-progress.md`, section 2).
2. **Keep** the change if it reached new code, or if it fixed a broken
   operation. **Undo** it if it reached nothing new and made the drivers more
   complicated. Either way, add a ledger row. Failed attempts go under
   "Tried and didn't help".
3. Stop and report to the user: what changed, what it reached, and what you'd
   do next.

## When to run in Antithesis

Launch a run with `antithesis-launch`:

- after the baseline
- whenever local coverage has stopped growing for the current tiers, before
  deciding to add the next tier
- right after adding a tier or feature group
- whenever the user asks

Use the same run length as the previous Antithesis run, so coverage can be
compared. Rebuild the normal images first (without the coverage override).
Measure it with `measuring-progress.md`, section 3, and add a ledger row.

## What not to do

- Don't add properties or assertions, even "just to check" something. Tell the
  user instead.
- Don't make drivers clever: no state machines, no coordination between
  drivers, no retry loops. If a driver needs that to reach code, it probably
  needs a short sequence driver (step 3) or a change to `helper_common.py`.
- Don't add operations from a later tier just because they're easy. Order
  matters for knowing what each addition bought.
