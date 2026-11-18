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
    stage="$1"
    shift
    log="$test_root/output.log"
    code=0
    timeout "${GODOT_CHECK_TIMEOUT:-120}" "$@" >"$log" 2>&1 || code=$?
    cat "$log"
    if [ "$code" -ne 0 ]; then return "$code"; fi
    # Godot can return 0 after import, resource or script errors.
    errors=$(grep -E '(^|SCRIPT )ERROR:|Parse Error:|WARNING: ObjectDB instances leaked' "$log" || true)
    if [ "$stage" = import ] && [ "${ALLOW_EDITOR_SOCKET_ERRORS:-0}" = 1 ]; then
        # Explicit opt-in only for a sandbox that forbids editor debug listeners.
        errors=$(printf '%s\n' "$errors" | grep -v -F \
          -e 'ERROR: Condition "_sock == -1" is true. Returning: FAILED' \
          -e 'ERROR: Condition "err != OK" is true. Returning: ERR_CANT_CREATE' || true)
    fi
    if [ -n "$errors" ]; then return 1; fi
}
case "$#:${1:-}" in
    0:) run_check import "$GODOT_BIN" --headless --path . --editor --import --quit ;;
    1:--runtime-only) ;; # This prototype loads its scripts and fixtures directly.
    *) echo 'Usage: sh scripts/verify.sh [--runtime-only]' >&2; exit 2 ;;
esac
run_check tests "$GODOT_BIN" --headless --path . --script tests/run_tests.gd
run_check boot "$GODOT_BIN" --headless --path . --quit-after 120
