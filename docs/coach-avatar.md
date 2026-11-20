# JabJam full-body coach — architecture and DSF handoff

Status: stage-1 scaffold. No commissioned character artwork or completed sprite pack yet.
The Python/Pillow vector rabbit is deliberately a **stand-in**, not the final 小奶茶 likeness.
Keep changes to the editor, rhythm logic, and final frame compositor independent.

## Data and dependency boundaries

1. Upstream course/arranger produces timestamped actions in seconds since song start.
   Existing IDs and combo metadata stay untouched.
2. video/coach_timeline.py selects CoachPose(state, action, phase) from **absolute time**.
   It has no Pillow, FFmpeg, Godot, or music analysis dependency.
3. video/coach_avatar.py receives that pose and draws a full-body avatar with one backend.
   VectorCoach is the development placeholder; SpriteCoach reads skin-specific PNG clips.
4. Arena.frame(t) draws the existing lanes first, optionally paints coach above the arena,
   and then overlays the existing footer and HUD. Export still calls Arena.frame(t).
5. The course's picture.coach field is opt-in. Courses without it render as before.
   Downstream Live2D/2D-bone export should implement the same pose-and-time contract,
   not read the music or maintain a second beat clock.

video/movements.py remains the canonical action registry. Do not duplicate a list of
punches inside the coach's public API. Timing is anchored to each note.time; when the
video frame grid misses the exact timestamp, the first frame at or after the beat shows
the strike. This ensures seeking and reproducible offline renders never drift.

## Course interface

picture.coach is optional. Allowed fields:
- enabled (bool, default false): explicit opt-in; old videos stay stable
- renderer ("vector" or "sprite", default "vector")
- skin (lowercase safe ID, default "milktea"), used only for sprite packs
- side ("left" or "right", default "right"), away from the central tracks
- scale (number 0.6–1.1, default 1.0); stage-1 target 1280x720 before output resize

Example: courses/coach-demo.json. Start with:
  python3 video/export.py courses/coach-demo.json --check
  python3 tests/test_coach_avatar.py
  python3 video/export.py courses/coach-demo.json build/coach-demo.mp4

For the new course, no Godot beat analyzer is required: notes and the synthetic fixture
are already in the repository. Production exports still need Pillow, FFmpeg and fonts.

## Animation semantics and assets

Prepare begins at most 0.30s before impact; strike starts exactly at note.time and lasts
0.10s; recovery lasts 0.30s. If cues arrive closely, the next prepare can interrupt
recovery after a 0.14s visible landing. Every state exposes phase in [0,1].
These windows are **animation staging**, not sports biomechanics or a new pacing rule.

The avatar presents mirror-follow-along instructions: the screen-left glove performs
left_* and the screen-right glove performs right_*. For the user's standing position,
avoid anatomical side conventions that would swap the movement.

For sprite mode see assets/coaches/README.md. PNG clip names are:
idle, <action>.prepare, <action>.strike, <action>.recover.
Never let an asset pack modify action IDs, BPM, hit times, or combo order.

## DSF next-work queue, in order

A. Check the branch and PR CI results first; do not merge before tests pass.
B. Run coach-demo.mp4 and compare frames immediately before/at/after each of eight cues.
C. Replace placeholder art with a coherent full-body 小奶茶 skin pack; check for clear
   glove distinction, rabbit ear/foot stability, alpha edges and scale on 16:9 mobile.
D. Add an explicit pose preview sheet and screenshot tests before changing animation
   windows; don't alter the arranger to compensate for a drawing issue.
E. Confirm manual combos and fast notes preserve punch hand, on-beat strike, cue effects.
F. Only later consider voice, expressions, bone animation, or Live2D. Keep providers
   behind CoachLayer and preserve old JSON files.
G. Profile memory/CPU in offline Docker; sprite cache is bounded and no server is needed.

Known limitations: stage 1 uses static speed windows, not motion-captured boxing.
It does not synchronize foot contact, solve occlusion in every scene or create sprite
images. The vector stand-in is intentionally simple. Production art and visual review
are required before calling it a finished boxing coach.

## Definition of done for stage 1

- Legacy courses without coach render without behavior changes
- Opt-in demo renders both track notes and a visibly moving full-body bunny
- Both hands, all three punching techniques, and left/right steps are addressable
- Song-time pose selection is deterministic under seeking and no cumulative drift
- Sprite backend validates pack paths/frames and fails when motions are missing
- Tests + this handoff let another agent continue without rewriting core video logic
