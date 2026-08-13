"""MQTT topic helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TopicMap:
    """All topics for a single robot.

    Layout:
      {base}/{robot_id}/availability
      {base}/{robot_id}/state
      {base}/{robot_id}/command
      {base}/{robot_id}/command/result
    """

    availability: str
    state: str
    command: str
    command_result: str
    discovery_prefix: str
    robot_id: str

    @classmethod
    def from_settings(cls, base_topic: str, robot_id: str, discovery_prefix: str) -> TopicMap:
        root = f"{base_topic.rstrip('/')}/{robot_id}"
        return cls(
            availability=f"{root}/availability",
            state=f"{root}/state",
            command=f"{root}/command",
            command_result=f"{root}/command/result",
            discovery_prefix=discovery_prefix.rstrip("/"),
            robot_id=robot_id,
        )

    def discovery(self, component: str, object_id: str) -> str:
        return f"{self.discovery_prefix}/{component}/{self.robot_id}/{object_id}/config"
