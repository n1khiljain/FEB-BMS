"""Builders for tests: one healthy snapshot, plus ways to drive the machine."""

from bms.readings import Readings
from bms.states import State

TICK_MS = 100


def make_readings(t=0, **overrides):
    """A healthy resting pack. Any keyword overrides one default."""
    fields = dict(
        timestamp_ms=t,
        cell_voltages=[3.7, 3.7, 3.7, 3.7],
        cell_temps=[25.0, 25.0],
        pack_current=0.0,
        accumulator_voltage=14.8,   # the four cells in series
        ts_voltage=0.0,
        ts_activate_requested=False,
        shutdown_circuit_closed=True,
        charger_connected=False,
        fault_reset_pressed=False,
    )
    fields.update(overrides)
    return Readings(**fields)


def run_for(machine, readings, start_ms, duration_ms, tick_ms=TICK_MS):
    """Step every tick_ms, re-stamping the readings so they never go stale.

    Returns the time of the tick after the last one run.
    """
    t = start_ms
    end = start_ms + duration_ms
    while t <= end:
        machine.step(readings.replaced(timestamp_ms=t), t)
        t += tick_ms
    return t


# The walkers below use only real transitions. Never set machine.state by
# hand in a test, or you can end up testing a situation the car cannot reach.

def go_to_idle(machine, start_ms=0):
    """INIT -> IDLE. Returns the next free time."""
    machine.step(make_readings(t=start_ms), start_ms)
    assert machine.state == State.IDLE, machine.state
    return start_ms + TICK_MS


def go_to_drive(machine, start_ms=0):
    """INIT -> IDLE -> PRECHARGE -> DRIVE. Returns the next free time."""
    t = go_to_idle(machine, start_ms)

    machine.step(make_readings(t=t, ts_activate_requested=True), t)
    assert machine.state == State.PRECHARGE, machine.state
    t += TICK_MS

    machine.step(make_readings(
        t=t, ts_activate_requested=True, ts_voltage=14.8), t)
    assert machine.state == State.DRIVE, machine.state
    return t + TICK_MS


def go_to_charging(machine, start_ms=0):
    """INIT -> IDLE -> PRECHARGE -> CHARGING. Returns the next free time."""
    t = go_to_idle(machine, start_ms)

    machine.step(make_readings(
        t=t, ts_activate_requested=True, charger_connected=True), t)
    assert machine.state == State.PRECHARGE, machine.state
    t += TICK_MS

    machine.step(make_readings(
        t=t, ts_activate_requested=True, charger_connected=True,
        ts_voltage=14.8), t)
    assert machine.state == State.CHARGING, machine.state
    return t + TICK_MS
