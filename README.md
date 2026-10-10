# JabJam

Open-source rhythm boxing with real motion tracking and auto-generated charts.

JabJam is a mobile-first rhythm boxing project inspired by fitness boxing games. The goal is to make a game that does not just ask the player to tap a screen: it should detect real punches and defensive movement, generate playable boxing charts from music, and run on commodity phones with optional low-cost wearable sensors.

## Product idea

- Phone camera tracks body movement: slip left/right, duck, stance and recovery.
- Two wrist IMU sensors track real punches with low latency.
- Music analysis builds a beat grid from an uploaded track.
- A choreography generator turns that beat grid into boxing combos.
- The game engine scores timing and movement quality.

## MVP

The first playable version targets:

- Left jab
- Right cross
- Left hook
- Right hook
- Slip left
- Slip right
- Duck
- Local music upload
- Automatic beat detection
- Easy / Normal / Hard chart generation
- PERFECT / GOOD / MISS timing judgement
- Android-first mobile web app

## Architecture

```text
                    +----------------------+
                    |     Music Track      |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Beat / onset analysis|
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Choreography Engine  |
                    +----------+-----------+
                               |
                               v
+-------------+      +----------------------+      +----------------+
| Wrist IMUs  | ---> |      Game Engine     | <--- | Camera / Pose  |
| BLE events  |      | timing + validation  |      | body events    |
+-------------+      +----------+-----------+      +----------------+
                               |
                               v
                    +----------------------+
                    |      Mobile UI       |
                    +----------------------+
```

See [docs/architecture.md](docs/architecture.md), [docs/event-model.md](docs/event-model.md) and [docs/mvp.md](docs/mvp.md).

## Initial technical direction

- Frontend: Angular, TypeScript, PWA
- Pose tracking: MediaPipe Pose Landmarker
- Wearables: BLE + 6-axis IMU, one device per wrist
- Chart analysis service: Python / FastAPI
- Beat analysis: start with a proven onset/beat library, keep the game-side chart format library-independent
- Storage: local-first for MVP

## Design principles

1. Gameplay must still work when the chart generator or sensor implementation changes.
2. Sensor integrations emit normalized events; the game engine never consumes raw hardware packets.
3. Automatic charts should feel like boxing combinations, not random notes placed on beats.
4. The first version optimizes for a playable loop, not motion-classification perfection.
5. Hardware is optional infrastructure, not a permanent dependency of the UI architecture.

## Status

🚧 Very early prototype. The repository is intentionally starting small and architecture-first.
