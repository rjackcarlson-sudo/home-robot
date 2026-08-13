from __future__ import annotations

import pytest

from home_robot.commands import CommandError, CommandName, parse_command


def test_plain_text_dock_aliases() -> None:
    assert parse_command("dock").command is CommandName.DOCK
    assert parse_command(b"go_home").command is CommandName.DOCK
    assert parse_command(" STOP ").command is CommandName.STOP


def test_json_command() -> None:
    cmd = parse_command('{"command": "set_mode", "mode": "idle"}')
    assert cmd.command is CommandName.SET_MODE
    assert cmd.mode == "idle"
    assert cmd.display() == "set_mode:idle"


def test_json_dock() -> None:
    cmd = parse_command('{"command": "dock"}')
    assert cmd.command is CommandName.DOCK


def test_empty_payload() -> None:
    with pytest.raises(CommandError, match="Empty"):
        parse_command("  ")


def test_unknown_plain_text() -> None:
    with pytest.raises(CommandError, match="Unknown command"):
        parse_command("explode")


def test_set_mode_requires_mode() -> None:
    with pytest.raises(CommandError, match="mode"):
        parse_command('{"command": "set_mode"}')


def test_invalid_json() -> None:
    with pytest.raises(CommandError, match="Invalid JSON"):
        parse_command("{not-json")
