"""CLI entry point: ``python -m home_robot``."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from pathlib import Path

from home_robot.agent import RobotAgent
from home_robot.config import load_settings
from home_robot.mqtt.client import PahoMqttClient
from home_robot.robot import create_backend

log = logging.getLogger("home_robot")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="home-robot",
        description="Local-first Home Assistant robot bridge (Milestone 1: status + commands).",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path(os.getenv("HOME_ROBOT_CONFIG", "config/robot.yaml")),
        help="Path to YAML config (default: config/robot.yaml or HOME_ROBOT_CONFIG)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        settings = load_settings(args.config)
    except FileNotFoundError as exc:
        log.error("%s", exc)
        return 2

    mqtt = PahoMqttClient(settings.mqtt, client_id=f"home-robot-{settings.robot.id}")
    robot = create_backend(settings)
    agent = RobotAgent(settings, robot, mqtt)

    def _handle_signal(_signum: int, _frame: object) -> None:
        log.info("Stop requested")
        agent.request_stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        agent.run_forever()
    except TimeoutError as exc:
        log.error("%s", exc)
        return 1
    except Exception:
        log.exception("Agent crashed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
