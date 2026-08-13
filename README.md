"""home-robot — local-first custom robot + Home Assistant (HAOS) bridge

A Python agent that sits on (or next to) a custom home robot and talks to
Home Assistant over MQTT. Core control stays on your LAN: no cloud account
is required for status reporting or commands.

This repository currently implements **Milestone 1**: a simulated robot that
publishes live status and accepts a few high-level commands, with Home
Assistant MQTT Discovery so entities appear automatically.

---

## Architecture

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                         Home LAN (no cloud required)                     │
│                                                                          │
│   ┌─────────────────────┐         MQTT          ┌─────────────────────┐  │
│   │  Robot computer     │  status / commands    │  MQTT broker        │  │
│   │  (Pi / NUC / laptop)│◄─────────────────────►│  Mosquitto          │  │
│   │                     │                       │  (HAOS add-on or    │  │
│   │  ┌───────────────┐  │                       │   docker-compose)   │  │
│   │  │ Robot Agent   │  │                       └──────────┬──────────┘  │
│   │  │ (this repo)   │  │                                  │ MQTT        │
│   │  └───────┬───────┘  │                                  ▼             │
│   │          │          │                       ┌─────────────────────┐  │
│   │  ┌───────▼───────┐  │                       │  Home Assistant     │  │
│   │  │ Robot backend │  │                       │  MQTT Discovery     │  │
│   │  │ simulated M1  │  │                       │  dashboard / autom. │  │
│   │  │ hardware later│  │                       └─────────────────────┘  │
│   │  └───────────────┘  │                                                │
│   └─────────────────────┘                                                │
└──────────────────────────────────────────────────────────────────────────┘
```

### Components

| Piece | Role |
| --- | --- |
| **Robot Agent** | Python process. Publishes telemetry, receives commands, announces itself to HA via MQTT Discovery. |
| **Robot backend** | Hardware abstraction (`RobotBackend`). Milestone 1 ships `SimulatedRobot` only. |
| **MQTT broker** | Local Mosquitto. On HAOS use the official Mosquitto add-on; for bring-up use `docker compose up mosquitto`. |
| **Home Assistant** | Creates sensors/buttons from discovery messages. Dashboards and automations stay in HA. |

### Why MQTT (not REST) for the core path

Home Assistant already has a first-class MQTT integration and MQTT Discovery.
Pub/sub matches "robot reports state continuously, HA occasionally sends a
command." REST/webhooks can be added later for one-shot tools; they are not
needed for Milestone 1.

### MQTT topic layout

For robot id `home-bot`:

| Topic | Direction | Payload |
| --- | --- | --- |
| `home_robot/home-bot/availability` | robot → HA | `online` / `offline` (retained; LWT = `offline`) |
| `home_robot/home-bot/state` | robot → HA | JSON state (retained) |
| `home_robot/home-bot/command` | HA → robot | JSON `{"command": "dock"}` or plain `dock` |
| `home_robot/home-bot/command/result` | robot → HA | JSON `{ok, command, message, mode}` |
| `homeassistant/.../config` | robot → HA | MQTT Discovery (retained) |

State JSON:

```json
{
  "mode": "idle",
  "battery_percent": 87.0,
  "pose": { "x": 0.0, "y": 0.0, "heading_deg": 0.0 },
  "charging": false,
  "last_command": "dock",
  "last_error": null,
  "updated_at": "2026-08-13T17:00:00+00:00"
}
```

Commands: `stop`, `dock` (aliases `go_home` / `home`), `ping`,
`{"command": "set_mode", "mode": "idle"}`.

---

## Milestone 1 — status + command bridge (simulated robot)

**Goal:** something you can run this week on a laptop, with or without HAOS,
that proves the control loop.

Included now:

- Config file + a few env overrides (`HOME_ROBOT_MQTT_HOST`, …)
- Simulated robot with battery, mode, and a timed dock → charge cycle
- MQTT client with last-will, reconnect, retained discovery
- HA entities: battery, mode, last command, charging, **Stop** and **Dock** buttons
- `python -m home_robot` entry point
- Unit tests that do not need a broker or Home Assistant

**Success criteria**

1. `pytest` passes.
2. Agent connects to Mosquitto and publishes `availability=online` plus a state JSON.
3. `mosquitto_pub -m dock` (or the HA Dock button) moves mode to `docking`, then `charging`.
4. With HA MQTT Discovery enabled, a "Home Bot" device appears with sensors and buttons.

**Out of scope for M1:** real motors, cameras, mapping, room navigation, voice,
LLM task planning, multi-robot, TLS.

### Later milestones (not built yet)

- **M2** — hardware backend (serial / USB / vendor SDK) behind the same `RobotBackend` interface
- **M3** — `go_to` / rooms using HA areas or a simple waypoint list
- **M4** — richer sensors (bump, cliff, dock detect) and error reporting
- **M5** — optional camera / person-present hooks into HA

---

## Assumptions

- One robot for now; `robot.id` is the MQTT namespace.
- Robot computer and HAOS are on the same LAN.
- MQTT is the control plane; HA remains the UI / automation engine.
- Milestone 1 uses anonymous MQTT on a local broker. HAOS can add a username
  via `mqtt.username` / `mqtt.password` (or `HOME_ROBOT_MQTT_USERNAME`).
- No MQTT TLS yet (fine on a trusted LAN; add later if the broker is exposed).
- Indoor pose is Cartesian meters, not GPS. HA `device_tracker` is deferred.
- The simulated backend is the default until a real base exists.

---

## Quick start

Python 3.11+ (3.12 recommended).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config/robot.example.yaml config/robot.yaml
```

### 1. Run a local broker (no HAOS required)

```bash
docker compose up mosquitto
```

If you already have Mosquitto (including the HAOS add-on), skip compose and
set `mqtt.host` / `HOME_ROBOT_MQTT_HOST` to that machine.

### 2. Start the agent

```bash
python -m home_robot -c config/robot.yaml
```

### 3. Watch state / send a command

```bash
mosquitto_sub -h localhost -t 'home_robot/#' -v

mosquitto_pub -h localhost -t home_robot/home-bot/command -m dock
mosquitto_pub -h localhost -t home_robot/home-bot/command -m stop
```

Optional: run agent + broker together with `docker compose --profile agent up --build`.

### Home Assistant (HAOS)

1. Install the **Mosquitto broker** add-on (or point HA at your existing broker).
2. Enable the **MQTT** integration. Leave discovery prefix as `homeassistant`.
3. Point this agent at the broker (`mqtt.host` = HA hostname or add-on IP).
4. Start the agent. A device named **Home Bot** should appear under MQTT.
5. Add the battery / mode sensors and Stop / Dock buttons to a dashboard.

If entities do not appear: confirm HA MQTT discovery is on, the agent logged
`MQTT connected`, and `homeassistant/#` shows retained `.../config` messages.

---

## Configuration

See `config/robot.example.yaml`. Copy it to `config/robot.yaml` (gitignored).

Environment overrides (useful in Docker / systemd):

| Variable | Overrides |
| --- | --- |
| `HOME_ROBOT_CONFIG` | Config file path |
| `HOME_ROBOT_MQTT_HOST` | `mqtt.host` |
| `HOME_ROBOT_MQTT_PORT` | `mqtt.port` |
| `HOME_ROBOT_MQTT_USERNAME` | `mqtt.username` |
| `HOME_ROBOT_MQTT_PASSWORD` | `mqtt.password` |
| `HOME_ROBOT_ROBOT_ID` | `robot.id` |

---

## Project layout

```text
config/                 example YAML
mosquitto/config/       local test broker config
src/home_robot/
  __main__.py           CLI
  agent.py              telemetry loop + command handling
  config.py             YAML + env
  commands.py           command parser
  models.py             RobotState / pose / mode
  mqtt/                 paho wrapper, topics, HA discovery
  robot/                RobotBackend + SimulatedRobot
tests/
```

To add a real mobile base later, implement `RobotBackend` in
`src/home_robot/robot/` and extend `create_backend()`. Keep MQTT and HA
discovery unchanged.

---

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check src tests
```
