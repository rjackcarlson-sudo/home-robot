"""Thin MQTT client wrapper so the agent does not depend on paho directly."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Protocol

from paho.mqtt.client import CallbackAPIVersion, Client, DisconnectFlags, MQTTMessage
from paho.mqtt.enums import MQTTErrorCode
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

from home_robot.config import MqttSettings

log = logging.getLogger("home_robot.mqtt")

MessageHandler = Callable[[str, bytes], None]
ConnectHandler = Callable[[], None]


class MqttClient(Protocol):
    """Protocol implemented by PahoMqttClient and test doubles."""

    def set_will(self, topic: str, payload: str) -> None: ...

    def set_message_handler(self, handler: MessageHandler) -> None: ...

    def set_connect_handler(self, handler: ConnectHandler) -> None: ...

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def publish(self, topic: str, payload: str, *, retain: bool = False, qos: int = 1) -> None: ...

    def subscribe(self, topic: str, qos: int = 1) -> None: ...

    def wait_connected(self, timeout: float = 10.0) -> None: ...


class PahoMqttClient:
    def __init__(self, settings: MqttSettings, client_id: str) -> None:
        self._settings = settings
        self._client_id = client_id
        self._on_message: MessageHandler | None = None
        self._on_connect: ConnectHandler | None = None
        self._connected = threading.Event()
        self._subscriptions: list[tuple[str, int]] = []

        self._client = Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=client_id,
            clean_session=True,
        )
        if settings.username:
            self._client.username_pw_set(settings.username, settings.password or "")
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.on_connect = self._handle_connect
        self._client.on_disconnect = self._handle_disconnect
        self._client.on_message = self._handle_message

    def set_will(self, topic: str, payload: str) -> None:
        self._client.will_set(topic, payload=payload, qos=1, retain=True)

    def set_message_handler(self, handler: MessageHandler) -> None:
        self._on_message = handler

    def set_connect_handler(self, handler: ConnectHandler) -> None:
        self._on_connect = handler

    def connect(self) -> None:
        log.info(
            "Connecting to MQTT %s:%s as %s",
            self._settings.host,
            self._settings.port,
            self._client_id,
        )
        error = self._client.connect(
            self._settings.host,
            self._settings.port,
            keepalive=self._settings.keepalive_seconds,
        )
        if error != MQTTErrorCode.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT connect failed: {error}")
        self._client.loop_start()

    def wait_connected(self, timeout: float = 10.0) -> None:
        if not self._connected.wait(timeout):
            raise TimeoutError(
                f"Timed out waiting for MQTT broker at "
                f"{self._settings.host}:{self._settings.port}"
            )

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
        self._connected.clear()

    def publish(self, topic: str, payload: str, *, retain: bool = False, qos: int = 1) -> None:
        info = self._client.publish(topic, payload=payload, qos=qos, retain=retain)
        if info.rc != MQTTErrorCode.MQTT_ERR_SUCCESS:
            log.warning("Publish to %s failed: %s", topic, info.rc)

    def subscribe(self, topic: str, qos: int = 1) -> None:
        pair = (topic, qos)
        if pair not in self._subscriptions:
            self._subscriptions.append(pair)
        self._client.subscribe(topic, qos=qos)

    def _handle_connect(
        self,
        _client: Client,
        _userdata: object,
        _flags: object,
        reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        if reason_code.is_failure:
            log.error("MQTT connection refused: %s", reason_code)
            return
        log.info("MQTT connected (%s)", reason_code)
        self._connected.set()
        for topic, qos in self._subscriptions:
            self._client.subscribe(topic, qos=qos)
        if self._on_connect:
            self._on_connect()

    def _handle_disconnect(
        self,
        _client: Client,
        _userdata: object,
        _flags: DisconnectFlags,
        reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        self._connected.clear()
        if reason_code.is_failure:
            log.warning("MQTT disconnected: %s", reason_code)
        else:
            log.info("MQTT disconnected")

    def _handle_message(self, _client: Client, _userdata: object, message: MQTTMessage) -> None:
        if not self._on_message:
            return
        try:
            self._on_message(message.topic, message.payload)
        except Exception:
            log.exception("Error handling MQTT message on %s", message.topic)
