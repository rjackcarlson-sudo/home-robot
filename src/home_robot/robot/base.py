"""Robot hardware abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod

from home_robot.commands import Command, CommandResult
from home_robot.models import RobotState


class RobotBackend(ABC):
    """Physical or simulated robot. The agent talks only to this interface."""

    @abstractmethod
    def get_state(self) -> RobotState:
        """Return a copy of the current state."""

    @abstractmethod
    def handle_command(self, command: Command) -> CommandResult:
        """Apply a high-level command. Must be safe to call from MQTT callbacks."""

    @abstractmethod
    def tick(self, dt: float) -> None:
        """Advance internal simulation / controllers by ``dt`` seconds."""

    def close(self) -> None:
        """Release hardware resources. Default is a no-op for simulated backends."""
        return None
