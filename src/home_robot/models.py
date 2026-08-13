"""Shared domain models for robot state and pose."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RobotMode(StrEnum):
    """High-level operating mode reported to Home Assistant."""

    IDLE = "idle"
    MOVING = "moving"
    DOCKING = "docking"
    CHARGING = "charging"
    ERROR = "error"


class Pose(BaseModel):
    """Indoor Cartesian pose in meters. Heading is degrees, 0 = +x."""

    x: float = 0.0
    y: float = 0.0
    heading_deg: float = 0.0


class RobotState(BaseModel):
    """Snapshot published on the MQTT state topic."""

    mode: RobotMode = RobotMode.IDLE
    battery_percent: float = Field(default=100.0, ge=0.0, le=100.0)
    pose: Pose = Field(default_factory=Pose)
    charging: bool = False
    last_command: str | None = None
    last_error: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_mqtt_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "battery_percent": round(self.battery_percent, 1),
            "pose": self.pose.model_dump(),
            "charging": self.charging,
            "last_command": self.last_command,
            "last_error": self.last_error,
            "updated_at": self.updated_at.isoformat(),
        }
