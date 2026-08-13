from __future__ import annotations

import json

from home_robot.mqtt.discovery import discovery_messages
from home_robot.mqtt.topics import TopicMap


def test_topic_layout() -> None:
    topics = TopicMap.from_settings("home_robot", "home-bot", "homeassistant")
    assert topics.state == "home_robot/home-bot/state"
    assert topics.command == "home_robot/home-bot/command"
    assert topics.availability == "home_robot/home-bot/availability"
    assert (
        topics.discovery("button", "dock")
        == "homeassistant/button/home-bot/dock/config"
    )


def test_discovery_covers_core_entities() -> None:
    topics = TopicMap.from_settings("home_robot", "home-bot", "homeassistant")
    messages = discovery_messages(topics, "Home Bot")
    by_topic = {topic: json.loads(payload) for topic, payload in messages}

    battery = by_topic["homeassistant/sensor/home-bot/battery/config"]
    assert battery["unique_id"] == "home-bot_battery"
    assert battery["device_class"] == "battery"
    assert battery["device"]["identifiers"] == ["home-bot"]
    assert battery["device"]["name"] == "Home Bot"

    dock = by_topic["homeassistant/button/home-bot/dock/config"]
    assert json.loads(dock["payload_press"]) == {"command": "dock"}
    assert dock["command_topic"] == topics.command

    charging = by_topic["homeassistant/binary_sensor/home-bot/charging/config"]
    assert charging["payload_on"] == "ON"

    object_ids = {topic.split("/")[-2] for topic, _ in messages}
    assert object_ids == {"battery", "mode", "last_command", "charging", "stop", "dock"}
