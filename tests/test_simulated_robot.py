from __future__ import annotations

from home_robot.commands import Command, CommandName
from home_robot.models import RobotMode
from home_robot.robot.simulated import SimulatedRobot


def test_initial_state() -> None:
    robot = SimulatedRobot(initial_battery=87.0)
    state = robot.get_state()
    assert state.mode is RobotMode.IDLE
    assert state.battery_percent == 87.0
    assert state.charging is False


def test_dock_then_charge_then_idle() -> None:
    robot = SimulatedRobot(dock_duration_seconds=2.0, initial_battery=50.0)
    result = robot.handle_command(Command(command=CommandName.DOCK))
    assert result.ok
    assert robot.get_state().mode is RobotMode.DOCKING

    robot.tick(1.0)
    assert robot.get_state().mode is RobotMode.DOCKING

    robot.tick(1.5)
    state = robot.get_state()
    assert state.mode is RobotMode.CHARGING
    assert state.charging is True

    # Charge rate is 1.5%/s from 50% → well past 100 in 40s.
    robot.tick(40.0)
    state = robot.get_state()
    assert state.battery_percent == 100.0
    assert state.mode is RobotMode.IDLE
    assert state.charging is False


def test_stop_cancels_dock() -> None:
    robot = SimulatedRobot(dock_duration_seconds=10.0)
    robot.handle_command(Command(command=CommandName.DOCK))
    robot.handle_command(Command(command=CommandName.STOP))
    assert robot.get_state().mode is RobotMode.IDLE
    assert robot.get_state().last_command == "stop"


def test_ping_does_not_change_mode() -> None:
    robot = SimulatedRobot()
    result = robot.handle_command(Command(command=CommandName.PING))
    assert result.ok
    assert result.message == "pong"
    assert robot.get_state().mode is RobotMode.IDLE


def test_set_mode_rejects_unknown() -> None:
    robot = SimulatedRobot()
    result = robot.handle_command(Command(command=CommandName.SET_MODE, mode="fly"))
    assert result.ok is False
    assert robot.get_state().last_error is not None


def test_idle_battery_drains() -> None:
    robot = SimulatedRobot(initial_battery=10.0)
    robot.tick(10.0)
    assert robot.get_state().battery_percent < 10.0
