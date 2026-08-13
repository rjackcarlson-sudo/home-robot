"""In-memory robot used for Milestone 1 (no hardware required)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime

from home_robot.commands import Command, CommandName, CommandResult
from home_robot.models import Pose, RobotMode, RobotState
from home_robot.robot.base import RobotBackend

# Percent per second. Tuned so a 2s telemetry interval shows visible change.
_IDLE_DRAIN_PER_SEC = 0.02
_ACTIVE_DRAIN_PER_SEC = 0.15
_CHARGE_PER_SEC = 1.5


class SimulatedRobot(RobotBackend):
    """Simple state machine: idle ↔ docking → charging → idle."""

    def __init__(
        self,
        *,
        dock_duration_seconds: float = 5.0,
        initial_battery: float = 87.0,
        pose: Pose | None = None,
    ) -> None:
        self._dock_duration = dock_duration_seconds
        self._lock = threading.Lock()
        self._dock_elapsed = 0.0
        self._state = RobotState(
            mode=RobotMode.IDLE,
            battery_percent=initial_battery,
            pose=pose or Pose(),
            charging=False,
        )

    def get_state(self) -> RobotState:
        with self._lock:
            return self._state.model_copy(deep=True)

    def handle_command(self, command: Command) -> CommandResult:
        with self._lock:
            if command.command is CommandName.PING:
                return self._result(True, command, "pong")

            if command.command is CommandName.STOP:
                self._enter_idle(command.display())
                return self._result(True, command, "Stopped")

            if command.command is CommandName.DOCK:
                if self._state.mode in (RobotMode.DOCKING, RobotMode.CHARGING):
                    return self._result(True, command, "Already docking or charging")
                self._state.mode = RobotMode.DOCKING
                self._state.charging = False
                self._state.last_command = command.display()
                self._state.last_error = None
                self._dock_elapsed = 0.0
                self._touch()
                return self._result(True, command, "Docking")

            if command.command is CommandName.SET_MODE:
                return self._set_mode(command)

            return self._result(False, command, f"Unhandled command {command.command.value}")

    def tick(self, dt: float) -> None:
        if dt <= 0:
            return
        with self._lock:
            mode = self._state.mode
            battery = self._state.battery_percent

            if mode is RobotMode.CHARGING:
                battery = min(100.0, battery + _CHARGE_PER_SEC * dt)
                if battery >= 100.0:
                    battery = 100.0
                    self._state.mode = RobotMode.IDLE
                    self._state.charging = False
            elif mode is RobotMode.DOCKING:
                self._dock_elapsed += dt
                battery = max(0.0, battery - _ACTIVE_DRAIN_PER_SEC * dt)
                if self._dock_elapsed >= self._dock_duration:
                    self._state.mode = RobotMode.CHARGING
                    self._state.charging = True
                    self._dock_elapsed = 0.0
            else:
                drain = _ACTIVE_DRAIN_PER_SEC if mode is RobotMode.MOVING else _IDLE_DRAIN_PER_SEC
                battery = max(0.0, battery - drain * dt)

            self._state.battery_percent = battery
            self._touch()

    def _set_mode(self, command: Command) -> CommandResult:
        requested = (command.mode or "").lower()
        try:
            mode = RobotMode(requested)
        except ValueError:
            allowed = ", ".join(m.value for m in RobotMode)
            self._state.last_error = f"Unknown mode {requested!r}"
            self._touch()
            return self._result(False, command, f"Unknown mode. Use one of: {allowed}")

        if mode is RobotMode.DOCKING:
            self._state.mode = RobotMode.DOCKING
            self._state.charging = False
            self._dock_elapsed = 0.0
        elif mode is RobotMode.CHARGING:
            self._state.mode = RobotMode.CHARGING
            self._state.charging = True
        elif mode is RobotMode.ERROR:
            self._state.mode = RobotMode.ERROR
            self._state.charging = False
            self._state.last_error = "Forced error mode"
        else:
            self._state.mode = mode
            self._state.charging = False

        self._state.last_command = command.display()
        if mode is not RobotMode.ERROR:
            self._state.last_error = None
        self._touch()
        return self._result(True, command, f"Mode set to {mode.value}")

    def _enter_idle(self, last_command: str) -> None:
        self._state.mode = RobotMode.IDLE
        self._state.charging = False
        self._state.last_command = last_command
        self._state.last_error = None
        self._dock_elapsed = 0.0
        self._touch()

    def _touch(self) -> None:
        self._state.updated_at = datetime.now(UTC)

    def _result(self, ok: bool, command: Command, message: str) -> CommandResult:
        return CommandResult(
            ok=ok,
            command=command.display(),
            message=message,
            mode=self._state.mode.value,
        )
