#!/bin/sh
# One command for JabJam regressions. Run inside the video-export image or
# a local Linux environment with Godot 4.6.3, Python/Pillow, FFmpeg and fonts.
set -eu
cd "$(dirname "$0")/.."
mode="${1:---quick}"
case "$mode" in
  --quick|--ci|--full) ;;
  *) echo 'Usage: sh scripts/verify_all.sh [--quick|--ci|--full]' >&2; exit 2 ;;
esac
echo "== JabJam verification: $mode =="
# The lightweight course check requires only Python stdlib.
python3 -S video/export.py courses/eight-moves.json --check

# Contract tests: beat-to-combo scheduling, course schema, arena scenes,
# avatar and bone motion, including Python/Godot cutout parity.
for test in \
  tests/test_video_pacing.py \
  tests/test_arena_scenes.py \
  tests/test_music_visuals.py \
  tests/test_coach_avatar.py \
  tests/test_cutout_rig.py
do
  echo "== $test =="
  python3 "$test"
done

# The quick mode fits the capped render container; --ci/--full also import
# the editor resources from a fresh isolated workspace.
if [ "$mode" = --quick ]; then
  sh scripts/verify.sh --runtime-only
else
  sh scripts/verify.sh
fi

if [ "$mode" = --full ]; then
  # Keep renders confined to build/: do not modify committed samples.
  out=build/verify-all
  mkdir -p "$out"
  python3 tests/render_video_job.py courses/four-punches.json "$out/four-punches.mp4" \
    --check-cues --song-title Pulse --difficulty easy --min-gap 1.4 --scene classic
  python3 tests/render_video_job.py courses/eight-moves.json "$out/eight-moves.mp4"
  python3 tests/check_eight_moves.py "$out/eight-moves.mp4"
  python3 tests/render_video_job.py courses/coach-demo.json "$out/coach-demo.mp4"
  python3 tests/check_coach_sample.py "$out/coach-demo.mp4"
fi
echo "== JabJam $mode checks passed =="
