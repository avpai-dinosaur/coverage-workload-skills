#!/usr/bin/env python3
"""Follow every log file in the logs folder and feed each line to every reducer.

Each SUT container writes its output to <logs>/<service>.log on a shared volume.
This collector reads new lines from all of them and sends each one, as a JSON
object {"service": ..., "line": ...}, on stdin to every executable in the
reducers folder. Reducers are long-running programs that read stdin line by
line. If a reducer exits, it is restarted.

How far each file has been read is saved in the state file, on the logs volume,
so a restarted collector carries on where it stopped. Limits: a reducer misses
lines sent while it is restarting, and a reducer that reads slowly holds up
all the others. A file that shrinks (was truncated) is
read again from the start. A line is only passed on once it ends with a newline.
"""

import json
import os
import subprocess
import sys
import time

LOGS = os.environ.get("LOGS_DIR", "/logs")
REDUCERS = os.environ.get("REDUCERS_DIR", "/opt/reducers")
STATE = os.environ.get("STATE_FILE", "/logs/.collector-offsets.json")


def load_offsets():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_offsets(offsets):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(offsets, f)
    os.replace(tmp, STATE)


def reducer_paths():
    if not os.path.isdir(REDUCERS):
        return []
    return sorted(os.path.join(REDUCERS, n) for n in os.listdir(REDUCERS)
                  if not n.startswith(".") and os.access(os.path.join(REDUCERS, n), os.X_OK))


def main():
    offsets = load_offsets()
    procs = {}     # reducer path -> Popen
    print(f"[collector] following {LOGS}/*.log, reducers in {REDUCERS}", flush=True)

    while True:
        for path in reducer_paths():
            p = procs.get(path)
            if p is None or p.poll() is not None:
                procs[path] = subprocess.Popen([path], stdin=subprocess.PIPE, text=True, bufsize=1)

        changed = False
        for name in sorted(os.listdir(LOGS)) if os.path.isdir(LOGS) else []:
            if not name.endswith(".log"):
                continue
            path = os.path.join(LOGS, name)
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            pos = offsets.get(name, 0)
            if size < pos:
                pos = 0
            if size == pos:
                continue
            with open(path, "rb") as f:
                f.seek(pos)
                data = f.read()
            end = data.rfind(b"\n")
            if end < 0:
                continue  # no complete line yet
            # Only move past complete lines, so an unfinished line is re-read next time.
            offsets[name] = pos + end + 1
            lines = data[:end].decode("utf-8", errors="replace").split("\n")
            service = name[:-4]
            for line in lines:
                msg = json.dumps({"service": service, "line": line}) + "\n"
                for rpath, p in list(procs.items()):
                    try:
                        p.stdin.write(msg)
                    except (BrokenPipeError, OSError):
                        procs.pop(rpath, None)
            changed = True

        if changed:
            save_offsets(offsets)
        time.sleep(0.2)


if __name__ == "__main__":
    sys.exit(main())
