#!/bin/bash
# One local run: start the coverage build, run the workload, stop cleanly, collect coverage.
# Usage: run-local.sh <label> [seed]
# Output: antithesis/local/out/<label>/  (workload.log, ops.txt, raw coverage)
#
# Filled in by antithesis-coverage-setup for this project. Edit the settings
# block and extract_coverage(); leave the steps alone.
set -euo pipefail

# ---- settings -------------------------------------------------------------
CONFIG_DIR="antithesis/config"           # holds docker-compose.yaml
WORKLOAD_SERVICE="workload"              # container that holds /opt/antithesis/test/v1
SUT_SERVICES="server1 server2"           # containers built with coverage
DURATION=300                             # seconds of driver activity
CONCURRENCY=4
READY_TIMEOUT=300                        # seconds to wait for setup_complete
# ---------------------------------------------------------------------------

label="${1:?usage: run-local.sh <label> [seed]}"
seed="${2:-0}"
out="antithesis/local/out/${label}"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
compose() { docker compose -f "$CONFIG_DIR/docker-compose.yaml" -f "$CONFIG_DIR/docker-compose.coverage.yaml" "$@"; }

# Convert raw coverage in $out/raw/<service>/ into one file the coverage report
# reads: $out/coverage.lcov, $out/coverage.gocov, or $out/coverage.xml (JaCoCo).
# See references/coverage-build.md for each language.
extract_coverage() {
  echo "TODO: fill in extract_coverage() for this project" >&2
  return 1
}

echo "== starting (coverage build)"
compose down -v --remove-orphans >/dev/null 2>&1 || true
compose up -d --build

echo "== waiting for setup_complete"
deadline=$((SECONDS + READY_TIMEOUT))
until compose exec -T sidecar sh -c 'cat /logs/sdk-*.jsonl 2>/dev/null | grep -q antithesis_setup'; do
  [ $SECONDS -lt $deadline ] || { echo "setup_complete never seen"; compose logs --tail 50; exit 1; }
  sleep 2
done

echo "== running workload for ${DURATION}s (seed ${seed})"
compose cp "$here/local_composer.py" "$WORKLOAD_SERVICE:/tmp/local_composer.py"
compose exec -T "$WORKLOAD_SERVICE" python3 /tmp/local_composer.py \
  --duration "$DURATION" --concurrency "$CONCURRENCY" --seed "$seed" | tee "$out/workload.log"
grep -o '^OP [^ ]* [^ ]*' "$out/workload.log" | sort | uniq -c | sort -rn > "$out/ops.txt" || true

echo "== stopping SUT with SIGTERM so coverage is written"
compose stop -t 60 $SUT_SERVICES
for svc in $SUT_SERVICES; do
  mkdir -p "$out/raw/$svc"
  compose cp "$svc:/coverage/$svc/." "$out/raw/$svc/"
done
[ -n "$(find "$out/raw" -type f)" ] || { echo "no coverage files written; see coverage-build.md (clean exit)"; exit 1; }
extract_coverage

compose down -v >/dev/null
echo "== done: $out"
