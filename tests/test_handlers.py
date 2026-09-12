"""Tests for the per-state handlers: one class per state."""

import unittest

from bms.state_machine import BmsStateMachine
from bms.states import ALL_STATES, FaultReason, State
from tests.test_raw_problems import healthy


class HandlerCase(unittest.TestCase):

    state = State.INIT

    def setUp(self):
        self.m = BmsStateMachine()
        self.th = self.m.th
        self.m.state = self.state
        self.m.state_entered_ms = 0

    def feed(self, r, now_ms=0):
        return self.m.step(r.replaced(timestamp_ms=now_ms), now_ms)


class TestDispatch(HandlerCase):
    def test_every_state_except_fault_has_a_handler(self):
        for state in ALL_STATES:
            if state == State.FAULT:
                continue
            self.assertIn(state, self.m._handlers, state)

    def test_fault_has_no_handler(self):
        self.assertNotIn(State.FAULT, self.m._handlers)


class TestInit(HandlerCase):
    state = State.INIT

    def test_healthy_and_safe_goes_idle(self):
        self.assertEqual(self.feed(healthy()), State.IDLE)

    def test_live_ts_stays_in_init(self):
        self.assertEqual(self.feed(healthy(ts_voltage=200.0)), State.INIT)

    def test_problem_stays_in_init(self):
        self.assertEqual(self.feed(healthy(pack_current=75.0)), State.INIT)


class TestIdle(HandlerCase):
    state = State.IDLE

    def press(self, **changes):
        self.feed(healthy(ts_activate_requested=False, **changes), 0)
        return self.feed(healthy(ts_activate_requested=True, **changes), 50)

    def test_press_starts_precharge(self):
        self.assertEqual(self.press(), State.PRECHARGE)

    def test_held_button_does_not_start_precharge(self):
        self.feed(healthy(ts_activate_requested=True), 0)
        self.m.state = State.IDLE
        self.assertEqual(
            self.feed(healthy(ts_activate_requested=True), 50), State.IDLE)

    def test_open_shutdown_circuit_blocks_precharge(self):
        self.assertEqual(self.press(shutdown_circuit_closed=False), State.IDLE)

    def test_charger_connected_needs_the_charge_window(self):
        cold = [-5.0, 25.0, 25.0, 25.0]
        self.assertEqual(
            self.press(charger_connected=True, cell_temps=cold), State.IDLE)

    def test_charger_connected_inside_the_window_proceeds(self):
        self.assertEqual(
            self.press(charger_connected=True), State.PRECHARGE)

    def test_cold_pack_may_still_drive(self):

        cold = [-5.0, 25.0, 25.0, 25.0]
        self.assertEqual(self.press(cell_temps=cold), State.PRECHARGE)


class TestPrecharge(HandlerCase):
    state = State.PRECHARGE

    def active(self, **changes):
        return healthy(ts_activate_requested=True, **changes)

    def test_reaching_the_target_goes_to_drive(self):
        r = self.active(accumulator_voltage=100.0, ts_voltage=90.0)
        self.assertEqual(self.feed(r), State.DRIVE)

    def test_reaching_the_target_with_a_charger_goes_to_charging(self):
        r = self.active(accumulator_voltage=100.0, ts_voltage=90.0,
                        charger_connected=True)
        self.assertEqual(self.feed(r), State.CHARGING)

    def test_still_climbing_stays_in_precharge(self):
        r = self.active(accumulator_voltage=100.0, ts_voltage=50.0)
        self.assertEqual(self.feed(r, 1000), State.PRECHARGE)

    def test_released_button_aborts(self):
        r = healthy(ts_activate_requested=False, accumulator_voltage=100.0,
                    ts_voltage=50.0)
        self.assertEqual(self.feed(r), State.DISCHARGE)

    def test_open_shutdown_circuit_aborts(self):
        r = self.active(shutdown_circuit_closed=False,
                        accumulator_voltage=100.0, ts_voltage=90.0)
        self.assertEqual(self.feed(r), State.DISCHARGE)

    def test_abort_wins_over_a_completed_precharge(self):
        r = healthy(ts_activate_requested=False, accumulator_voltage=100.0,
                    ts_voltage=95.0)
        self.assertEqual(self.feed(r), State.DISCHARGE)

    def test_timeout_faults(self):
        r = self.active(accumulator_voltage=100.0, ts_voltage=50.0)
        late = self.th.precharge_timeout_ms
        self.assertEqual(self.feed(r, late), State.FAULT)
        self.assertEqual(self.m.fault.reason, FaultReason.PRECHARGE_TIMEOUT)

    def test_timeout_records_the_ratio_reached(self):
        r = self.active(accumulator_voltage=100.0, ts_voltage=50.0)
        self.feed(r, self.th.precharge_timeout_ms)
        self.assertAlmostEqual(self.m.fault.value, 0.5)

    def test_success_on_the_last_tick_beats_the_timeout(self):
        r = self.active(accumulator_voltage=100.0, ts_voltage=90.0)
        self.assertEqual(self.feed(r, self.th.precharge_timeout_ms),
                         State.DRIVE)


class TestDrive(HandlerCase):
    state = State.DRIVE

    def test_driving_stays_in_drive(self):
        r = healthy(ts_activate_requested=True, ts_voltage=300.0,
                    accumulator_voltage=300.0, pack_current=40.0)
        self.assertEqual(self.feed(r), State.DRIVE)

    def test_released_button_discharges(self):
        r = healthy(ts_activate_requested=False, ts_voltage=300.0)
        self.assertEqual(self.feed(r), State.DISCHARGE)

    def test_open_shutdown_circuit_discharges(self):
        r = healthy(ts_activate_requested=True, ts_voltage=300.0,
                    shutdown_circuit_closed=False)
        self.assertEqual(self.feed(r), State.DISCHARGE)

    def test_plugging_in_a_charger_discharges(self):
        r = healthy(ts_activate_requested=True, ts_voltage=300.0,
                    charger_connected=True)
        self.assertEqual(self.feed(r), State.DISCHARGE)


class TestCharging(HandlerCase):
    state = State.CHARGING

    def charging(self, **changes):
        base = dict(ts_activate_requested=True, charger_connected=True,
                    ts_voltage=300.0, accumulator_voltage=300.0,
                    pack_current=-10.0)
        base.update(changes)
        return healthy(**base)

    def test_charging_continues(self):
        self.assertEqual(self.feed(self.charging()), State.CHARGING)

    def test_unplugging_the_charger_discharges(self):
        r = self.charging(charger_connected=False)
        self.assertEqual(self.feed(r), State.DISCHARGE)

    def test_released_button_discharges(self):
        r = self.charging(ts_activate_requested=False)
        self.assertEqual(self.feed(r), State.DISCHARGE)

    def test_open_shutdown_circuit_discharges(self):
        r = self.charging(shutdown_circuit_closed=False)
        self.assertEqual(self.feed(r), State.DISCHARGE)

    def test_full_pack_stops_charging(self):
        stop = self.th.charge_stop_v
        r = self.charging(cell_voltages=[3.9, stop, 3.9, 3.9])
        self.assertEqual(self.feed(r), State.DISCHARGE)

    def test_nearly_full_pack_keeps_charging(self):
        r = self.charging(cell_voltages=[3.9, self.th.charge_stop_v - 0.01,
                                         3.9, 3.9])
        self.assertEqual(self.feed(r), State.CHARGING)


class TestDischarge(HandlerCase):
    state = State.DISCHARGE

    def test_safe_voltage_returns_to_idle(self):
        r = healthy(ts_voltage=self.th.ts_safe_voltage - 1)
        self.assertEqual(self.feed(r), State.IDLE)

    def test_still_live_stays_in_discharge(self):
        r = healthy(ts_voltage=200.0)
        self.assertEqual(self.feed(r, 1000), State.DISCHARGE)

    def test_timeout_faults(self):
        r = healthy(ts_voltage=200.0)
        late = self.th.discharge_timeout_ms
        self.assertEqual(self.feed(r, late), State.FAULT)
        self.assertEqual(self.m.fault.reason, FaultReason.DISCHARGE_TIMEOUT)

    def test_falling_below_safe_on_the_last_tick_beats_the_timeout(self):
        r = healthy(ts_voltage=10.0)
        self.assertEqual(self.feed(r, self.th.discharge_timeout_ms), State.IDLE)

    def test_timeout_records_the_voltage(self):
        self.feed(healthy(ts_voltage=200.0), self.th.discharge_timeout_ms)
        self.assertEqual(self.m.fault.value, 200.0)


class TestFullLap(unittest.TestCase):

    def test_a_whole_activation_and_shutdown(self):
        m = BmsStateMachine()
        t = 0

        def feed(**changes):
            nonlocal t
            m.step(healthy(timestamp_ms=t, **changes), t)
            t += 50

        feed()
        feed()
        feed(ts_activate_requested=True)
        feed(ts_activate_requested=True, accumulator_voltage=300.0,
             ts_voltage=100.0)
        feed(ts_activate_requested=True, accumulator_voltage=300.0,
             ts_voltage=280.0)
        feed(ts_activate_requested=True, accumulator_voltage=300.0,
             ts_voltage=300.0, pack_current=40.0)
        feed(ts_activate_requested=False, ts_voltage=300.0)
        feed(ts_voltage=10.0)

        self.assertEqual(m.state, State.IDLE)
        self.assertIsNone(m.fault)
        visited = [to_state for _, _, to_state, _ in m.history]
        self.assertEqual(visited, [State.IDLE, State.PRECHARGE, State.DRIVE,
                                   State.DISCHARGE, State.IDLE])


if __name__ == "__main__":
    unittest.main()
