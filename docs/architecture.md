# Architecture

## Components

### 1. Web app

Responsibilities:

- music selection and playback
- game rendering
- camera acquisition
- pose inference
- BLE sensor connection
- event synchronization
- scoring
- calibration
- settings

The web app should treat motion sources as adapters.

```ts
interface MotionSource {
  start(): Promise<void>;
  stop(): Promise<void>;
  events$: Observable<MotionEvent>;
}
```

This lets us swap a BLE wrist sensor for a phone-only detector, test fixture, smartwatch, or future controller without changing gameplay code.

### 2. Motion pipeline

Two primary sources:

#### Wrist IMU

Best suited for:

- punch onset
- left/right hand identity
- peak acceleration
- angular motion
- approximate punch power
- later: punch-type classification

#### Camera pose

Best suited for:

- slip left
- slip right
- duck
- stance center
- body recovery
- later: guard position and gross technique feedback

The game engine consumes normalized events rather than raw accelerometer or pose frames.

### 3. Chart service

The chart pipeline is deliberately split into two stages.

```text
audio
  -> analysis
  -> beat grid / energy / sections
  -> choreography
  -> JabJam chart
```

Analysis answers **when interesting musical moments happen**.

Choreography answers **what a boxer should do at those moments**.

Keeping them separate is important: we should be able to replace the beat detector without rewriting boxing logic.

### 4. Game engine

Inputs:

- JabJam chart
- playback clock
- normalized motion events

Outputs:

- judgement
- combo state
- score
- accuracy
- session statistics

The playback clock is authoritative. Sensor timestamps are normalized to that clock before judgement.

## Suggested repository shape

```text
jabjam/
  apps/
    web/                  # Angular PWA
  services/
    chart-api/            # FastAPI analysis + chart generation
  firmware/
    wrist-sensor/         # BLE IMU firmware
  packages/
    protocol/             # shared event/chart schemas
  docs/
    architecture.md
    event-model.md
    mvp.md
```

We do not need all folders on day one. They describe the intended boundaries.

## Latency budget

For a rhythm game, timestamp correctness matters more than UI frame rate.

Initial target:

- BLE sensor sampling: >= 100 Hz
- motion event generation: <= 20 ms after detected peak
- BLE delivery: preferably <= 30 ms
- pose pipeline: <= 80 ms practical target
- judgement performed against original event timestamp, not arrival time

The exact thresholds should be calibrated on real devices rather than hard-coded as assumptions.

## MVP sequencing

1. Game clock + static handcrafted chart
2. Simulated keyboard motion events
3. Pose-based slip / duck
4. BLE sensor transport
5. Punch onset detection
6. Automatic beat analysis
7. Choreography generator
8. Punch-type classification refinement

This sequence guarantees that every stage can be tested independently.
