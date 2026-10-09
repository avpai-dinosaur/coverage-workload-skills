#!/bin/bash
# Run a command with its output going both to stdout and to /logs/<service>.log.
# Usage (as the start of a container's entrypoint): log-tee.sh <service> <command> [args...]
# stdout keeps working, so Antithesis still sees every line. The file on the
# shared sut-logs volume is what the sidecar reads.
set -euo pipefail
service="$1"; shift
mkdir -p /logs
exec > >(tee -a "/logs/${service}.log") 2>&1
exec "$@"
