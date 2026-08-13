"""YAML + environment configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class RobotSettings(BaseModel):
    id: str = "home-bot"
    name: str = "Home Bot"
    backend: Literal["simulated"] = "simulated"


class MqttSettings(BaseModel):
    host: str = "localhost"
    port: int = Field(default=1883, ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    discovery_prefix: str = "homeassistant"
    base_topic: str = "home_robot"
    keepalive_seconds: int = Field(default=30, ge=5, le=300)


class AgentSettings(BaseModel):
    telemetry_interval_seconds: float = Field(default=2.0, gt=0.1, le=60.0)
    simulated_dock_seconds: float = Field(default=5.0, gt=0.1, le=120.0)


class Settings(BaseModel):
    robot: RobotSettings = Field(default_factory=RobotSettings)
    mqtt: MqttSettings = Field(default_factory=MqttSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)


def load_settings(config_path: Path | None = None) -> Settings:
    """Load YAML config, then apply a small set of env overrides.

    Env vars (optional):
      HOME_ROBOT_MQTT_HOST, HOME_ROBOT_MQTT_PORT,
      HOME_ROBOT_MQTT_USERNAME, HOME_ROBOT_MQTT_PASSWORD,
      HOME_ROBOT_ROBOT_ID
    """
    data: dict = {}
    if config_path is not None:
        if not config_path.is_file():
            raise FileNotFoundError(
                f"Config file not found: {config_path}\n"
                "Copy config/robot.example.yaml to config/robot.yaml and edit it."
            )
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if loaded is None:
            data = {}
        elif isinstance(loaded, dict):
            data = loaded
        else:
            raise ValueError(f"Config file must be a YAML mapping: {config_path}")

    settings = Settings.model_validate(data)
    return _apply_env_overrides(settings)


def _apply_env_overrides(settings: Settings) -> Settings:
    mqtt_updates: dict = {}
    if host := os.getenv("HOME_ROBOT_MQTT_HOST"):
        mqtt_updates["host"] = host
    if port := os.getenv("HOME_ROBOT_MQTT_PORT"):
        mqtt_updates["port"] = int(port)
    if "HOME_ROBOT_MQTT_USERNAME" in os.environ:
        mqtt_updates["username"] = os.environ["HOME_ROBOT_MQTT_USERNAME"] or None
    if "HOME_ROBOT_MQTT_PASSWORD" in os.environ:
        mqtt_updates["password"] = os.environ["HOME_ROBOT_MQTT_PASSWORD"] or None

    robot_updates: dict = {}
    if robot_id := os.getenv("HOME_ROBOT_ROBOT_ID"):
        robot_updates["id"] = robot_id

    updates: dict = {}
    if mqtt_updates:
        updates["mqtt"] = settings.mqtt.model_copy(update=mqtt_updates)
    if robot_updates:
        updates["robot"] = settings.robot.model_copy(update=robot_updates)
    return settings.model_copy(update=updates) if updates else settings
