# Event model

JabJam keeps raw sensor frames separate from gameplay events.

## Motion event

```ts
type MotionEventType =
  | 'jab_left'
  | 'cross_right'
  | 'hook_left'
  | 'hook_right'
  | 'slip_left'
  | 'slip_right'
  | 'duck';

interface MotionEvent {
  type: MotionEventType;
  timestampMs: number;
  confidence: number; // 0..1
  source: 'imu-left' | 'imu-right' | 'camera' | 'simulator';
  metrics?: {
    power?: number;
    peakAcceleration?: number;
    peakAngularVelocity?: number;
  };
}
```

The first IMU implementation may initially emit generic left/right punches before reliable classification exists. The protocol should allow this without changing the transport layer.

## Chart event

```ts
interface ChartEvent {
  id: string;
  timeMs: number;
  action: MotionEventType;
  lane?: 'left' | 'right' | 'center';
  intensity?: number; // 0..1
}
```

## Chart

```ts
interface JabJamChart {
  version: 1;
  title: string;
  durationMs: number;
  bpm?: number;
  difficulty: 'easy' | 'normal' | 'hard';
  events: ChartEvent[];
}
```

## Judgement

Initial windows:

```text
PERFECT: |delta| <= 80 ms
GOOD:    |delta| <= 160 ms
MISS:    unmatched after 250 ms
```

These are starting values only. Real playtesting should decide final windows.

## Why normalized events?

The game engine should not care whether a punch came from:

- an nRF52840 wrist sensor
- a smartwatch
- camera-only inference
- keyboard simulation
- recorded test data

That separation gives us deterministic gameplay tests and lets hardware evolve independently.
