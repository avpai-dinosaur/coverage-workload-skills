# Log Sidecar

## Goal

Every line any SUT container prints reaches one `sidecar` container, where
reducer scripts can read it later. Properties are written as reducers, by
someone else, later. This step only builds the path the logs travel.

## Why a shared volume

- **Not the network.** Antithesis injects network faults. Logs sent over the
  network would be dropped or delayed, and reducers would see gaps that aren't
  real.
- **Not a Docker logging driver.** `antithesis-setup` forbids custom `logging:`
  settings.

## Steps

1. **Add a named volume** `sut-logs`. Mount it at `/logs` in every SUT service
   and in the new `sidecar` service.

2. **Wrap each SUT entrypoint** with `log-tee.sh`, so output goes to stdout
   (Antithesis still sees it) **and** to `/logs/<service>.log`:

   ```yaml
   server1:
     entrypoint: ["/usr/local/bin/log-tee.sh", "server1"]
     command: ["/usr/bin/server", "--config", "/etc/server.toml"]
   ```

   Setting `entrypoint:` clears the image's own command, so **always set
   `command:` explicitly**. Copy it from the image
   (`docker inspect --format '{{json .Config.Entrypoint}} {{json .Config.Cmd}}' <image>`).
   If the image already has an entrypoint, put it after the service name, so
   `log-tee.sh` runs first. Copy `log-tee.sh` into each SUT image. It needs
   `bash` and `tee`.

3. **Line buffering.** When output goes to a pipe, many programs buffer it in
   large blocks. Lines then show up late, or are lost on a crash. Set
   `PYTHONUNBUFFERED=1` for Python. For C programs that use stdio, wrap the
   command with `stdbuf -oL -eL`. Most Go, Rust, and Java loggers write
   unbuffered already.

4. **Add the sidecar service.** Copy `assets/sidecar/` to `antithesis/sidecar/`,
   and create an empty `antithesis/sidecar/reducers/` folder (add a `.gitkeep`).

   ```yaml
   sidecar:
     build: ../sidecar
     platform: linux/amd64
     volumes:
       - sut-logs:/logs
   ```

5. **Check.** Start the stack, then confirm a file exists for every SUT service
   and is growing:
   `docker compose exec sidecar sh -c 'ls -l /logs; tail -n 3 /logs/*.log'`

## How the collector works

`collector.py` follows every `*.log` file in `/logs`. It sends each complete
line, as `{"service": "...", "line": "..."}`, to every executable in
`/opt/reducers/` on stdin. It restarts reducers that exit, and saves how far
it read in each file (in `/logs/.collector-offsets.json`), so a restarted
collector carries on where it stopped. A reducer misses the lines sent while it
is restarting, and a slow reducer holds up the others. Neither matters until
reducers exist.

With no reducers, it only follows the files. That's expected.

## Things that go wrong

- **Service never writes a file.** The entrypoint override didn't apply. Check
  with `docker compose config`.
- **File exists but is empty.** Output is buffered (see step 3), or the program
  logs to a file of its own and not stdout. In that case, point the program's
  log file setting at `/logs/<service>.log`.
- **Two replicas of one service.** Each needs its own file name. Pass a distinct
  name per replica in the entrypoint.
