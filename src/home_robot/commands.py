"""Parse high-level robot commands from MQTT payloads."""

from __future__ import annotations

import json
from enum import StrEnum

from pydantic import BaseModel, ValidationError


class CommandName(StrEnum):
    STOP = "stop"
    DOCK = "dock"
    SET_MODE = "set_mode"
    PING = "ping"


class Command(BaseModel):
    command: CommandName
    mode: str | None = None

    def display(self) -> str:
        if self.command is CommandName.SET_MODE and self.mode:
            return f"set_mode:{self.mode}"
        return self.command.value


class CommandResult(BaseModel):
    ok: bool
    command: str
    message: str
    mode: str | None = None


class CommandError(ValueError):
    """Raised when a payload cannot be turned into a Command."""


_PLAIN_ALIASES = {
    "stop": CommandName.STOP,
    "dock": CommandName.DOCK,
    "go_home": CommandName.DOCK,
    "home": CommandName.DOCK,
    "ping": CommandName.PING,
}


def parse_command(payload: str | bytes) -> Command:
    """Accept JSON `{"command": "..."}` or a plain-text command name.

    Plain text is supported so `mosquitto_pub -m dock` works during bring-up.
    """
    if isinstance(payload, bytes):
        text = payload.decode("utf-8", errors="replace").strip()
    else:
        text = payload.strip()

    if not text:
        raise CommandError("Empty command payload")

    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON command: {exc}") from exc
        if not isinstance(data, dict):
            raise CommandError("JSON command must be an object")
        try:
            command = Command.model_validate(data)
        except ValidationError as exc:
            raise CommandError(_first_validation_message(exc)) from exc
        if command.command is CommandName.SET_MODE and not command.mode:
            raise CommandError("set_mode requires a 'mode' field")
        return command

    alias = _PLAIN_ALIASES.get(text.lower())
    if alias is None:
        raise CommandError(
            f"Unknown command {text!r}. "
            "Use stop, dock, ping, or JSON {\"command\": \"set_mode\", \"mode\": \"idle\"}."
        )
    return Command(command=alias)


def _first_validation_message(exc: ValidationError) -> str:
    error = exc.errors()[0]
    loc = ".".join(str(part) for part in error.get("loc", ()))
    msg = error.get("msg", "invalid")
    return f"{loc}: {msg}" if loc else msg
