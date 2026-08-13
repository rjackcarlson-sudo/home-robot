from __future__ import annotations

import json
from pathlib import Path

from home_robot.agent import RobotAgent
from home_robot.config import load_settings
from home_robot.models import RobotMode
from home_robot.mqtt.client import ConnectHandler, MessageHandler
from home_robot.mqtt.discovery import OFFLINE, ONLINE
from home_robot.robot.simulated import SimulatedRobot

EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "robot.example.yaml"


class FakeMqtt:
    def __init__(self) -> None:
        self.published: list[dict] = []
        self.subscriptions: list[str] = []
        self.will: tuple[str, str] | None = None
        self.connected = False
        self._message_handler: MessageHandler | None = None
        self._connect_handler: ConnectHandler | None = None

    def set_will(self, topic: str, payload: str) -> None:
        self.will = (topic, payload)

    def set_message_handler(self, handler: MessageHandler) -> None:
        self._message_handler = handler

    def set_connect_handler(self, handler: ConnectHandler) -> None:
        self._connect_handler = handler

    def connect(self) -> None:
        self.connected = True
        if self._connect_handler:
            self._connect_handler()

    def wait_connected(self, timeout: float = 10.0) -> None:
        if not self.connected:
            raise TimeoutError("FakeMqtt is not connected")

    def disconnect(self) -> None:
        self.connected = False

    def publish(self, topic: str, payload: str, *, retain: bool = False, qos: int = 1) -> None:
        self.published.append(
            {"topic": topic, "payload": payload, "retain": retain, "qos": qos}
        )

    def subscribe(self, topic: str, qos: int = 1) -> None:
        self.subscriptions.append(topic)

    def inject(self, topic: str, payload: str | bytes) -> None:
        if self._message_handler is None:
            raise RuntimeError("No message handler registered")
        data = payload.encode("utf-8") if isinstance(payload, str) else payload
        self._message_handler(topic, data)

    def last_payload(self, topic: str) -> str | None:
        for item in reversed(self.published):
            if item["topic"] == topic:
                return item["payload"]
        return None

    def topics(self) -> list[str]:
        return [item["topic"] for item in self.published]

EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "robot.example.yaml"


def _started_agent() -> tuple[RobotAgent, FakeMqtt, SimulatedRobot]:
    settings = load_settings(EXAMPLE)
    mqtt = FakeMqtt()
    robot = SimulatedRobot(dock_duration_seconds=2.0, initial_battery=80.0)
    agent = RobotAgent(settings, robot, mqtt)
    agent.start()
    return agent, mqtt, robot


def test_start_publishes_discovery_and_online() -> None:
    agent, mqtt, _robot = _started_agent()
    assert mqtt.will == (agent.topics.availability, OFFLINE)
    assert agent.topics.command in mqtt.subscriptions
    assert mqtt.last_payload(agent.topics.availability) == ONLINE
    assert any("/battery/config" in topic for topic in mqtt.topics())
    state = json.loads(mqtt.last_payload(agent.topics.state) or "{}")
    assert state["mode"] == "idle"
    assert "battery_percent" in state


def test_dock_command_updates_state() -> None:
    agent, mqtt, robot = _started_agent()
    mqtt.inject(agent.topics.command, "dock")
    assert robot.get_state().mode is RobotMode.DOCKING
    state = json.loads(mqtt.last_payload(agent.topics.state) or "{}")
    assert state["mode"] == "docking"
    result = json.loads(mqtt.last_payload(agent.topics.command_result) or "{}")
    assert result["ok"] is True
    assert result["command"] == "dock"


def test_bad_command_reports_error() -> None:
    agent, mqtt, robot = _started_agent()
    mqtt.inject(agent.topics.command, "explode")
    assert robot.get_state().mode is RobotMode.IDLE
    result = json.loads(mqtt.last_payload(agent.topics.command_result) or "{}")
    assert result["ok"] is False


def test_tick_publishes_new_state() -> None:
    agent, mqtt, _robot = _started_agent()
    before = mqtt.last_payload(agent.topics.state)
    agent.tick(1.0)
    after = mqtt.last_payload(agent.topics.state)
    assert after is not None and after != before


def test_shutdown_publishes_offline() -> None:
    agent, mqtt, _robot = _started_agent()
    agent.shutdown()
    assert mqtt.last_payload(agent.topics.availability) == OFFLINE
    assert mqtt.connected is False
