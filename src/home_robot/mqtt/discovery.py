"""Home Assistant MQTT discovery payloads.

See https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from home_robot import __version__
from home_robot.mqtt.topics import TopicMap

ONLINE = "online"
OFFLINE = "offline"


def device_info(robot_id: str, robot_name: str) -> dict:
    return {
        "identifiers": [robot_id],
        "name": robot_name,
        "manufacturer": "home-robot",
        "model": "Custom Home Robot",
        "sw_version": __version__,
    }


def discovery_messages(topics: TopicMap, robot_name: str) -> list[tuple[str, str]]:
    """Return (topic, json_payload) pairs for MQTT discovery, retained by the agent."""
    device = device_info(topics.robot_id, robot_name)
    availability = {
        "topic": topics.availability,
        "payload_available": ONLINE,
        "payload_not_available": OFFLINE,
    }

    def entity(
        component: str,
        object_id: str,
        extra: dict,
    ) -> tuple[str, str]:
        payload = {
            "name": extra.pop("name"),
            "unique_id": f"{topics.robot_id}_{object_id}",
            "device": device,
            "availability": [availability],
            **extra,
        }
        return topics.discovery(component, object_id), json.dumps(payload)

    entities: Iterable[tuple[str, str]] = (
        entity(
            "sensor",
            "battery",
            {
                "name": "Battery",
                "state_topic": topics.state,
                "value_template": "{{ value_json.battery_percent }}",
                "unit_of_measurement": "%",
                "device_class": "battery",
                "state_class": "measurement",
            },
        ),
        entity(
            "sensor",
            "mode",
            {
                "name": "Mode",
                "state_topic": topics.state,
                "value_template": "{{ value_json.mode }}",
                "icon": "mdi:robot-vacuum",
            },
        ),
        entity(
            "sensor",
            "last_command",
            {
                "name": "Last command",
                "state_topic": topics.state,
                "value_template": "{{ value_json.last_command }}",
                "icon": "mdi:console",
            },
        ),
        entity(
            "binary_sensor",
            "charging",
            {
                "name": "Charging",
                "state_topic": topics.state,
                "value_template": "{{ 'ON' if value_json.charging else 'OFF' }}",
                "payload_on": "ON",
                "payload_off": "OFF",
                "device_class": "battery_charging",
            },
        ),
        entity(
            "button",
            "stop",
            {
                "name": "Stop",
                "command_topic": topics.command,
                "payload_press": json.dumps({"command": "stop"}),
                "icon": "mdi:stop",
            },
        ),
        entity(
            "button",
            "dock",
            {
                "name": "Dock",
                "command_topic": topics.command,
                "payload_press": json.dumps({"command": "dock"}),
                "icon": "mdi:home-import-outline",
            },
        ),
    )
    return list(entities)
