"""Main agent loop: telemetry out, commands in, HA discovery."""

from __future__ import annotations

import json
import logging
import threading
import time

from home_robot.commands import CommandError, CommandResult, parse_command
from home_robot.config import Settings
from home_robot.mqtt.client import MqttClient
from home_robot.mqtt.discovery import OFFLINE, ONLINE, discovery_messages
from home_robot.mqtt.topics import TopicMap
from home_robot.robot.base import RobotBackend

log = logging.getLogger("home_robot.agent")


class RobotAgent:
    """Glue between a RobotBackend and MQTT / Home Assistant."""

    def __init__(self, settings: Settings, robot: RobotBackend, mqtt: MqttClient) -> None:
        self._settings = settings
        self._robot = robot
        self._mqtt = mqtt
        self._topics = TopicMap.from_settings(
            settings.mqtt.base_topic,
            settings.robot.id,
            settings.mqtt.discovery_prefix,
        )
        self._stop = threading.Event()
        self._last_tick = time.monotonic()
        self._started = False

    @property
    def topics(self) -> TopicMap:
        return self._topics

    def start(self) -> None:
        """Connect to MQTT. Does not block; call ``run_forever`` for the loop."""
        if self._started:
            return
        self._mqtt.set_will(self._topics.availability, OFFLINE)
        self._mqtt.set_message_handler(self._on_message)
        self._mqtt.set_connect_handler(self._on_connected)
        self._mqtt.connect()
        self._started = True
        self._last_tick = time.monotonic()

    def run_forever(self) -> None:
        self.start()
        self._mqtt.wait_connected()
        interval = self._settings.agent.telemetry_interval_seconds
        log.info(
            "Agent running for %s; telemetry every %.1fs. Ctrl+C to stop.",
            self._settings.robot.id,
            interval,
        )
        try:
            while not self._stop.wait(interval):
                self.tick()
        finally:
            self.shutdown()

    def request_stop(self) -> None:
        self._stop.set()

    def tick(self, dt: float | None = None) -> None:
        now = time.monotonic()
        if dt is None:
            dt = now - self._last_tick
        self._last_tick = now
        self._robot.tick(dt)
        self.publish_state()

    def publish_state(self) -> None:
        payload = json.dumps(self._robot.get_state().to_mqtt_dict())
        self._mqtt.publish(self._topics.state, payload, retain=True)

    def shutdown(self) -> None:
        log.info("Shutting down agent")
        try:
            self._mqtt.publish(self._topics.availability, OFFLINE, retain=True)
        except Exception:
            log.exception("Failed to publish offline availability")
        try:
            self._mqtt.disconnect()
        except Exception:
            log.exception("MQTT disconnect failed")
        self._robot.close()
        self._started = False

    def _on_connected(self) -> None:
        log.info("Publishing Home Assistant MQTT discovery")
        for topic, payload in discovery_messages(self._topics, self._settings.robot.name):
            self._mqtt.publish(topic, payload, retain=True)
        self._mqtt.subscribe(self._topics.command)
        self._mqtt.publish(self._topics.availability, ONLINE, retain=True)
        self.publish_state()

    def _on_message(self, topic: str, payload: bytes) -> None:
        if topic != self._topics.command:
            return
        try:
            command = parse_command(payload)
        except CommandError as exc:
            log.warning("Bad command: %s", exc)
            self._publish_result(
                CommandResult(ok=False, command="invalid", message=str(exc), mode=None)
            )
            return

        log.info("Command received: %s", command.display())
        result = self._robot.handle_command(command)
        self._publish_result(result)
        self.publish_state()

    def _publish_result(self, result: CommandResult) -> None:
        self._mqtt.publish(
            self._topics.command_result,
            result.model_dump_json(),
            retain=False,
        )
