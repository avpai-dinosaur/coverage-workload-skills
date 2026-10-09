#!/usr/bin/env python3
"""<One line: what this driver does, e.g. "Put values into keys from the shared pool.">"""
from helper_client import client
from helper_common import pick_name, pick_value, pick_count, log_outcome, error_name

OP = "<operation id from api-surface.md>"

c = client()
for _ in range(pick_count()):
    try:
        c.put(pick_name(), pick_value())  # <the one call this driver makes>
        log_outcome(OP, "ok")
    except Exception as e:
        log_outcome(OP, error_name(e))
