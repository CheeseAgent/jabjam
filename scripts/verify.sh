#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
GODOT_BIN="${GODOT_BIN:-godot}"
# Isolate verification from actual practice records and make it work in CI.
test_root=$(mktemp -d)
trap 'rm -rf "$test_root"' EXIT HUP INT TERM
export XDG_DATA_HOME="$test_root/data"
export XDG_CONFIG_HOME="$test_root/config"
export XDG_CACHE_HOME="$test_root/cache"
mkdir -p "$XDG_DATA_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME"
run_check() {
    log="$test_root/output.log"
    code=0
    "$@" >"$log" 2>&1 || code=$?
    cat "$log"
    if [ "$code" -ne 0 ]; then return "$code"; fi
    # Godot may return 0 even when a script fails to load.
    if grep -Eq 'SCRIPT ERROR:|Parse Error:|Failed to load script|WARNING: ObjectDB instances leaked' "$log"; then return 1; fi
}
run_check "$GODOT_BIN" --headless --path . --editor --import --quit
run_check "$GODOT_BIN" --headless --path . --script tests/run_tests.gd
run_check "$GODOT_BIN" --headless --path . --quit-after 120
