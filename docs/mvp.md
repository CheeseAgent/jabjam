# MVP roadmap

## Definition of playable

A user can open JabJam on an Android phone, choose a song, stand in front of the camera, connect two wrist sensors, play a generated chart, and receive timing judgements for punches and defensive movement.

## Phase 0 — playable shell

- [ ] Angular PWA boots on desktop and Android Chrome
- [ ] audio file can be loaded locally
- [ ] deterministic playback clock
- [ ] note highway / action prompts
- [ ] handcrafted JSON chart
- [ ] keyboard simulator for all seven MVP actions
- [ ] PERFECT / GOOD / MISS judgement

**Exit criterion:** a complete song fragment can be played without any camera or hardware.

## Phase 1 — body movement

- [ ] MediaPipe pose camera pipeline
- [ ] neutral stance calibration
- [ ] slip-left detection
- [ ] slip-right detection
- [ ] duck detection
- [ ] confidence + cooldown handling

**Exit criterion:** defensive notes can be completed without touching the screen.

## Phase 2 — wrist sensors

- [ ] choose reference hardware
- [ ] BLE service and characteristics
- [ ] timestamp synchronization
- [ ] >=100 Hz IMU sampling
- [ ] left/right generic punch detection
- [ ] packet-loss diagnostics
- [ ] calibration UI

**Exit criterion:** a jab/cross rhythm can be scored using real hand movement.

## Phase 3 — punch classification

- [ ] collect labelled motion sessions
- [ ] establish heuristic baseline
- [ ] distinguish straight vs hook
- [ ] quantify confusion matrix
- [ ] decide whether TinyML is actually required

**Exit criterion:** four punch types are reliable enough for gameplay.

## Phase 4 — automatic charts

- [ ] audio analysis API
- [ ] beat grid
- [ ] onset strength
- [ ] section / energy features
- [ ] combo templates
- [ ] ergonomic constraints
- [ ] Easy / Normal / Hard density rules
- [ ] deterministic seed support

**Exit criterion:** a previously unseen song produces a playable chart without manual authoring.

## Choreography constraints

The generator must not place arbitrary actions independently.

Examples:

- alternate hands naturally where possible
- preserve recovery time after hooks and ducks
- avoid long runs on one arm
- prefer recognizable boxing phrases
- reduce effective note density at high BPM
- introduce defensive actions at phrase boundaries
- difficulty changes density before it changes movement complexity

The chart generator is a constrained choreography system, not a random beat mapper.
