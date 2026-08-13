from __future__ import annotations

from pathlib import Path

import pytest

from home_robot.config import load_settings

EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "robot.example.yaml"


def test_load_example_yaml() -> None:
    settings = load_settings(EXAMPLE)
    assert settings.robot.id == "home-bot"
    assert settings.robot.backend == "simulated"
    assert settings.mqtt.port == 1883
    assert settings.mqtt.username is None
    assert settings.agent.telemetry_interval_seconds == 2.0


def test_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        load_settings(Path("/tmp/does-not-exist-home-robot.yaml"))


def test_env_overrides_mqtt_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME_ROBOT_MQTT_HOST", "haos.local")
    monkeypatch.setenv("HOME_ROBOT_MQTT_PORT", "1884")
    monkeypatch.setenv("HOME_ROBOT_ROBOT_ID", "garage-bot")
    settings = load_settings(EXAMPLE)
    assert settings.mqtt.host == "haos.local"
    assert settings.mqtt.port == 1884
    assert settings.robot.id == "garage-bot"
    assert settings.robot.name == "Home Bot"


def test_empty_username_env_clears_value(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = tmp_path / "robot.yaml"
    config.write_text(
        "mqtt:\n  username: broker-user\n  password: secret\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME_ROBOT_MQTT_USERNAME", "")
    monkeypatch.setenv("HOME_ROBOT_MQTT_PASSWORD", "")
    settings = load_settings(config)
    assert settings.mqtt.username is None
    assert settings.mqtt.password is None
