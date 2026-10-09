"""Shared by all drivers: name pool, value menus, outcome logging.

Fill in NAMES and the menus from the inputs table in api-surface.md.
Keep this file small and plain. Drivers import from it.
"""
from antithesis.random import random_choice

# Small shared pool, so drivers act on the same data. Changing its size changes
# how often operations collide.
NAMES = [f"k{i}" for i in range(16)]

# One menu per input that matters. Typical values, the limits from the inputs
# table, just inside and just outside them, and empty values.
VALUES = [b"", b"x", b"hello", b"v" * 1024, b"v" * (1024 * 1024 - 1), b"v" * (1024 * 1024 + 1)]


def pick_name():
    return random_choice(NAMES)


def pick_value():
    return random_choice(VALUES)


def pick_count(low=1, high=20):
    return random_choice(list(range(low, high + 1)))


def error_name(e):
    return f"error={type(e).__name__}"


def log_outcome(op_id, outcome):
    """One line per call. Used to measure which operations run, not to check them."""
    print(f"OP {op_id} {outcome}", flush=True)
