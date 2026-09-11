"""One test per arrow in the state diagram, walked through real steps."""

import unittest

from bms.state_machine import BmsStateMachine
from bms.states import State
from tests.helpers import (TICK_MS, go_to_charging, go_to_drive, go_to_idle,
                           make_readings)


class TransitionCase(unittest.TestCase):
    def setUp(self):
        self.m = BmsStateMachine()
        self.th = self.m.th
        self.t = 0

    def feed(self, **overrides):
        """One step at the next tick. Returns the resulting state."""
        state = self.m.step(make_readings(t=self.t, **overrides), self.t)
        self.t += TICK_MS
        return state


class TestFromInit(TransitionCase):
    def test_healthy_goes_to_idle(self):
        self.assertEqual(self.feed(), State.IDLE)

    def test_live_ts_keeps_it_in_init(self):
        self.assertEqual(self.feed(ts_voltage=60.0), State.INIT)

    def test_leaves_init_once_the_ts_is_safe(self):
        self.assertEqual(self.feed(ts_voltage=60.0), State.INIT)
        self.assertEqual(self.feed(ts_voltage=59.0), State.IDLE)


class TestFromIdle(TransitionCase):
    def setUp(self):
        super().setUp()
        self.t = go_to_idle(self.m)

    def test_button_press_starts_precharge(self):
        self.assertEqual(self.feed(ts_activate_requested=True),
                         State.PRECHARGE)

    def test_open_shutdown_circuit_blocks_it(self):
        self.assertEqual(
            self.feed(ts_activate_requested=True,
                      shutdown_circuit_closed=False), State.IDLE)

    def test_button_already_held_on_entry_does_not_count(self):
        # Rising edge: the machine must see it low before it sees it high.
        m = BmsStateMachine()
        m.step(make_readings(t=0, ts_activate_requested=True), 0)
        self.assertEqual(m.state, State.IDLE)
        self.assertEqual(
            m.step(make_readings(t=100, ts_activate_requested=True), 100),
            State.IDLE)

    def test_cold_pack_may_drive_but_not_charge(self):
        cold = [-5.0, 25.0]
        m = BmsStateMachine()
        t = go_to_idle(m)
        m.step(make_readings(t=t, cell_temps=cold, charger_connected=True,
                             ts_activate_requested=True), t)
        self.assertEqual(m.state, State.IDLE)

        m2 = BmsStateMachine()
        t = go_to_idle(m2)
        m2.step(make_readings(t=t, cell_temps=cold,
                              ts_activate_requested=True), t)
        self.assertEqual(m2.state, State.PRECHARGE)


class TestFromPrecharge(TransitionCase):
    def setUp(self):
        super().setUp()
        self.t = go_to_idle(self.m)
        self.feed(ts_activate_requested=True)
        self.assertEqual(self.m.state, State.PRECHARGE)

    def test_reaching_the_target_goes_to_drive(self):
        self.assertEqual(
            self.feed(ts_activate_requested=True, accumulator_voltage=100.0,
                      ts_voltage=90.0), State.DRIVE)

    def test_just_under_the_target_keeps_precharging(self):
        self.assertEqual(
            self.feed(ts_activate_requested=True, accumulator_voltage=100.0,
                      ts_voltage=89.0), State.PRECHARGE)

    def test_charger_connected_goes_to_charging(self):
        self.assertEqual(
            self.feed(ts_activate_requested=True, charger_connected=True,
                      accumulator_voltage=100.0, ts_voltage=90.0),
            State.CHARGING)

    def test_releasing_the_button_aborts(self):
        self.assertEqual(
            self.feed(ts_activate_requested=False, accumulator_voltage=100.0,
                      ts_voltage=50.0), State.DISCHARGE)

    def test_open_shutdown_circuit_aborts(self):
        self.assertEqual(
            self.feed(ts_activate_requested=True,
                      shutdown_circuit_closed=False,
                      accumulator_voltage=100.0, ts_voltage=50.0),
            State.DISCHARGE)


class TestFromDrive(TransitionCase):
    def setUp(self):
        super().setUp()
        self.t = go_to_drive(self.m)

    def driving(self, **overrides):
        base = dict(ts_activate_requested=True, accumulator_voltage=14.8,
                    ts_voltage=14.8)
        base.update(overrides)
        return self.feed(**base)

    def test_driving_stays_in_drive(self):
        self.assertEqual(self.driving(pack_current=40.0), State.DRIVE)

    def test_releasing_the_button_discharges(self):
        self.assertEqual(self.driving(ts_activate_requested=False),
                         State.DISCHARGE)

    def test_open_shutdown_circuit_discharges(self):
        self.assertEqual(self.driving(shutdown_circuit_closed=False),
                         State.DISCHARGE)

    def test_plugging_in_the_charger_discharges(self):
        self.assertEqual(self.driving(charger_connected=True),
                         State.DISCHARGE)


class TestFromCharging(TransitionCase):
    def setUp(self):
        super().setUp()
        self.t = go_to_charging(self.m)

    def charging(self, **overrides):
        base = dict(ts_activate_requested=True, charger_connected=True,
                    accumulator_voltage=14.8, ts_voltage=14.8,
                    pack_current=-10.0)
        base.update(overrides)
        return self.feed(**base)

    def test_charging_continues(self):
        self.assertEqual(self.charging(), State.CHARGING)

    def test_full_pack_stops_and_does_not_fault(self):
        stop = self.th.charge_stop_v
        state = self.charging(cell_voltages=[3.9, stop, 3.9, 3.9])
        self.assertEqual(state, State.DISCHARGE)
        self.assertIsNone(self.m.fault)

    def test_unplugging_the_charger_discharges(self):
        self.assertEqual(self.charging(charger_connected=False),
                         State.DISCHARGE)

    def test_releasing_the_button_discharges(self):
        self.assertEqual(self.charging(ts_activate_requested=False),
                         State.DISCHARGE)


class TestFromDischarge(TransitionCase):
    def setUp(self):
        super().setUp()
        self.t = go_to_drive(self.m)
        self.feed(ts_activate_requested=False, ts_voltage=300.0)
        self.assertEqual(self.m.state, State.DISCHARGE)

    def test_safe_voltage_returns_to_idle(self):
        self.assertEqual(self.feed(ts_voltage=59.0), State.IDLE)

    def test_still_live_keeps_discharging(self):
        self.assertEqual(self.feed(ts_voltage=200.0), State.DISCHARGE)


class TestHappyPath(TransitionCase):
    def test_full_lap_and_its_history(self):
        self.assertEqual(self.feed(), State.IDLE)
        self.assertEqual(self.feed(ts_activate_requested=True),
                         State.PRECHARGE)
        self.assertEqual(
            self.feed(ts_activate_requested=True, accumulator_voltage=100.0,
                      ts_voltage=50.0), State.PRECHARGE)
        self.assertEqual(
            self.feed(ts_activate_requested=True, accumulator_voltage=100.0,
                      ts_voltage=95.0), State.DRIVE)
        self.assertEqual(
            self.feed(ts_activate_requested=True, accumulator_voltage=100.0,
                      ts_voltage=100.0, pack_current=40.0), State.DRIVE)
        self.assertEqual(self.feed(ts_voltage=100.0), State.DISCHARGE)
        self.assertEqual(self.feed(ts_voltage=10.0), State.IDLE)

        self.assertIsNone(self.m.fault)
        visited = [to_state for _, _, to_state, _ in self.m.history]
        self.assertEqual(visited, [State.IDLE, State.PRECHARGE, State.DRIVE,
                                   State.DISCHARGE, State.IDLE])
        times = [t for t, _, _, _ in self.m.history]
        self.assertEqual(times, sorted(times))


if __name__ == "__main__":
    unittest.main()
