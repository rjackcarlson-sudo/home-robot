"""Robot backend factory."""

from __future__ import annotations

from home_robot.config import Settings
from home_robot.robot.base import RobotBackend
from home_robot.robot.simulated import SimulatedRobot


def create_backend(settings: Settings) -> RobotBackend:
    if settings.robot.backend == "simulated":
        return SimulatedRobot(dock_duration_seconds=settings.agent.simulated_dock_seconds)
    raise ValueError(f"Unsupported robot backend: {settings.robot.backend}")
