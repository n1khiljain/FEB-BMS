"""Fault behaviour: every reason, debounce, latching, reset, and invariants."""

import unittest

from bms.state_machine import BmsStateMachine
from bms.states import ALL_STATES, FaultReason, State
from tests.helpers import (TICK_MS, go_to_charging, go_to_drive, go_to_idle,
                           make_readings, run_for)

ALL_OPEN = {"air_neg": False, "precharge": False, "air_pos": False}


class FaultCase(unittest.TestCase):
    def setUp(self):
        self.m = BmsStateMachine()
        self.th = self.m.th

    def hold(self, duration_ms, start_ms=0, **overrides):
        """Feed one bad snapshot for a while. Returns the end time."""
        return run_for(self.m, make_readings(**overrides),
                       start_ms, duration_ms, tick_ms=50)


class TestEachReason(FaultCase):
    def test_cell_overvoltage(self):
        t = go_to_drive(self.m)
        self.hold(self.th.voltage_fault_ms, t,
                  cell_voltages=[3.7, 3.7, 4.25, 3.7],
                  ts_activate_requested=True, ts_voltage=14.8)
        self.assertEqual(self.m.fault.reason, FaultReason.CELL_OVERVOLTAGE)
        self.assertEqual(self.m.fault.cell_index, 2)
        self.assertEqual(self.m.fault.value, 4.25)

    def test_cell_undervoltage(self):
        t = go_to_drive(self.m)
        self.hold(self.th.voltage_fault_ms, t,
                  cell_voltages=[3.7, 2.40, 3.7, 3.7],
                  ts_activate_requested=True, ts_voltage=14.8)
        self.assertEqual(self.m.fault.reason, FaultReason.CELL_UNDERVOLTAGE)
        self.assertEqual(self.m.fault.cell_index, 1)
        self.assertEqual(self.m.fault.value, 2.40)

    def test_cell_overtemp(self):
        t = go_to_drive(self.m)
        self.hold(self.th.temp_fault_ms, t, cell_temps=[25.0, 61.0],
                  ts_activate_requested=True, ts_voltage=14.8)
        self.assertEqual(self.m.fault.reason, FaultReason.CELL_OVERTEMP)
        self.assertEqual(self.m.fault.cell_index, 1)
        self.assertEqual(self.m.fault.value, 61.0)

    def test_cell_undertemp(self):
        t = go_to_drive(self.m)
        self.hold(self.th.temp_fault_ms, t, cell_temps=[-25.0, 25.0],
                  ts_activate_requested=True, ts_voltage=14.8)
        self.assertEqual(self.m.fault.reason, FaultReason.CELL_UNDERTEMP)
        self.assertEqual(self.m.fault.cell_index, 0)

    def test_overcurrent_discharge(self):
        t = go_to_drive(self.m)
        self.hold(self.th.current_fault_ms, t, pack_current=75.0,
                  ts_activate_requested=True, ts_voltage=14.8)
        self.assertEqual(self.m.fault.reason,
                         FaultReason.OVERCURRENT_DISCHARGE)
        self.assertIsNone(self.m.fault.cell_index)
        self.assertEqual(self.m.fault.value, 75.0)

    def test_overcurrent_charge_from_regen(self):
        # Heavy regen braking pushes current back into the pack while driving.
        t = go_to_drive(self.m)
        self.hold(self.th.current_fault_ms, t, pack_current=-40.0,
                  ts_activate_requested=True, ts_voltage=14.8)
        self.assertEqual(self.m.fault.reason, FaultReason.OVERCURRENT_CHARGE)
        self.assertEqual(self.m.fault.value, -40.0)

    def test_sensor_missing(self):
        self.hold(self.th.sensor_fault_ms, 0, cell_temps=[25.0, None])
        self.assertEqual(self.m.fault.reason, FaultReason.SENSOR_MISSING)
        self.assertEqual(self.m.fault.cell_index, 1)

    def test_sensor_missing_on_an_empty_list(self):
        self.hold(self.th.sensor_fault_ms, 0, cell_voltages=[])
        self.assertEqual(self.m.fault.reason, FaultReason.SENSOR_MISSING)
        self.assertIsNone(self.m.fault.cell_index)

    def test_sensor_implausible_not_overtemp(self):
        # 200 C is not a hot cell, it is a broken sensor.
        self.hold(self.th.sensor_fault_ms, 0, cell_temps=[25.0, 200.0])
        self.assertEqual(self.m.fault.reason, FaultReason.SENSOR_IMPLAUSIBLE)
        self.assertEqual(self.m.fault.cell_index, 1)
        self.assertEqual(self.m.fault.value, 200.0)

    def test_sensor_stale(self):
        # The snapshot never updates while the clock keeps moving.
        old = make_readings(t=0)
        for now in range(0, 1000, 100):
            self.m.step(old, now)
        self.assertEqual(self.m.fault.reason, FaultReason.SENSOR_STALE)

    def test_precharge_timeout(self):
        t = go_to_idle(self.m)
        self.m.step(make_readings(t=t, ts_activate_requested=True), t)
        self.assertEqual(self.m.state, State.PRECHARGE)
        stuck = make_readings(ts_activate_requested=True,
                              accumulator_voltage=100.0, ts_voltage=10.0)
        run_for(self.m, stuck, t + TICK_MS, self.th.precharge_timeout_ms)
        self.assertEqual(self.m.fault.reason, FaultReason.PRECHARGE_TIMEOUT)
        self.assertAlmostEqual(self.m.fault.value, 0.1)

    def test_discharge_timeout(self):
        t = go_to_drive(self.m)
        self.m.step(make_readings(t=t, ts_voltage=300.0), t)
        self.assertEqual(self.m.state, State.DISCHARGE)
        stuck = make_readings(ts_voltage=300.0)
        run_for(self.m, stuck, t + TICK_MS, self.th.discharge_timeout_ms)
        self.assertEqual(self.m.fault.reason, FaultReason.DISCHARGE_TIMEOUT)
        self.assertEqual(self.m.fault.value, 300.0)


class TestDebounce(FaultCase):
    def test_short_problem_does_not_fault(self):
        t = go_to_drive(self.m)
        self.hold(self.th.voltage_fault_ms - 50, t,
                  cell_voltages=[3.7, 4.25, 3.7, 3.7],
                  ts_activate_requested=True, ts_voltage=14.8)
        self.assertNotEqual(self.m.state, State.FAULT)

    def test_one_noise_spike_mid_drive_is_ignored(self):
        t = go_to_drive(self.m)
        driving = dict(ts_activate_requested=True, ts_voltage=14.8,
                       accumulator_voltage=14.8)
        self.m.step(make_readings(t=t, cell_temps=[25.0, 200.0], **driving), t)
        t += TICK_MS
        run_for(self.m, make_readings(**driving), t, 2000)
        self.assertEqual(self.m.state, State.DRIVE)
        self.assertIsNone(self.m.fault)

    def test_timer_restarts_after_the_problem_clears(self):
        # Two 400 ms stretches of over temperature, with good data between.
        t = go_to_drive(self.m)
        driving = dict(ts_activate_requested=True, ts_voltage=14.8,
                       accumulator_voltage=14.8)
        hot = make_readings(cell_temps=[25.0, 61.0], **driving)
        good = make_readings(**driving)

        t = run_for(self.m, hot, t, 400, tick_ms=100)
        t = run_for(self.m, good, t, 200, tick_ms=100)
        t = run_for(self.m, hot, t, 400, tick_ms=100)
        self.assertEqual(self.m.state, State.DRIVE)
        self.assertIsNone(self.m.fault)

    def test_fifty_degrees_is_fine_driving_but_faults_while_charging(self):
        warm = [25.0, 50.0]
        driving = BmsStateMachine()
        t = go_to_drive(driving)
        run_for(driving, make_readings(cell_temps=warm,
                                       ts_activate_requested=True,
                                       ts_voltage=14.8),
                t, driving.th.temp_fault_ms * 2)
        self.assertEqual(driving.state, State.DRIVE)

        charging = BmsStateMachine()
        t = go_to_charging(charging)
        run_for(charging, make_readings(cell_temps=warm,
                                        ts_activate_requested=True,
                                        charger_connected=True,
                                        ts_voltage=14.8, pack_current=-10.0),
                t, charging.th.temp_fault_ms * 2)
        self.assertEqual(charging.state, State.FAULT)
        self.assertEqual(charging.fault.reason, FaultReason.CELL_OVERTEMP)


class TestLatchingAndReset(FaultCase):
    def fault_the_machine(self):
        t = go_to_drive(self.m)
        end = self.hold(self.th.current_fault_ms, t, pack_current=75.0,
                        ts_activate_requested=True, ts_voltage=14.8)
        self.assertEqual(self.m.state, State.FAULT)
        return end

    def test_fault_latches_after_the_pack_goes_healthy(self):
        t = self.fault_the_machine()
        run_for(self.m, make_readings(), t, 5000)
        self.assertEqual(self.m.state, State.FAULT)

    def test_reset_refused_while_the_problem_remains(self):
        t = self.fault_the_machine()
        self.m.step(make_readings(t=t, pack_current=75.0,
                                  fault_reset_pressed=True), t)
        self.assertEqual(self.m.state, State.FAULT)

    def test_reset_refused_while_the_ts_is_live(self):
        t = self.fault_the_machine()
        self.m.step(make_readings(t=t, ts_voltage=300.0,
                                  fault_reset_pressed=True), t)
        self.assertEqual(self.m.state, State.FAULT)

    def test_reset_refused_on_a_stale_snapshot(self):
        t = self.fault_the_machine()
        self.m.step(make_readings(t=0, fault_reset_pressed=True), t + 5000)
        self.assertEqual(self.m.state, State.FAULT)

    def test_reset_accepted_when_healthy_and_safe(self):
        t = self.fault_the_machine()
        self.m.step(make_readings(t=t, fault_reset_pressed=True), t)
        self.assertEqual(self.m.state, State.INIT)
        self.assertIsNone(self.m.fault)
        self.assertEqual(self.m._since, {})

    def test_the_car_can_be_driven_again_after_a_reset(self):
        t = self.fault_the_machine()
        self.m.step(make_readings(t=t, fault_reset_pressed=True), t)
        t += TICK_MS
        self.m.step(make_readings(t=t), t)
        self.assertEqual(self.m.state, State.IDLE)


class TestFaultInvariants(FaultCase):
    def test_fault_opens_every_relay_and_the_contact(self):
        t = go_to_drive(self.m)
        self.assertTrue(self.m.bms_ok())
        self.hold(self.th.current_fault_ms, t, pack_current=75.0,
                  ts_activate_requested=True, ts_voltage=14.8)
        self.assertEqual(self.m.state, State.FAULT)
        self.assertFalse(self.m.bms_ok())
        self.assertEqual(self.m.relay_outputs(), ALL_OPEN)

    def test_relay_table_holds_for_every_state(self):
        expected = {
            State.INIT: ALL_OPEN,
            State.IDLE: ALL_OPEN,
            State.DISCHARGE: ALL_OPEN,
            State.FAULT: ALL_OPEN,
            State.PRECHARGE: {"air_neg": True, "precharge": True,
                              "air_pos": False},
            State.DRIVE: {"air_neg": True, "precharge": False,
                          "air_pos": True},
            State.CHARGING: {"air_neg": True, "precharge": False,
                             "air_pos": True},
        }
        for state in ALL_STATES:
            self.m.state = state
            self.assertEqual(self.m.relay_outputs(), expected[state], state)

    def test_a_fault_is_always_logged_with_its_reason(self):
        t = go_to_drive(self.m)
        self.hold(self.th.current_fault_ms, t, pack_current=75.0,
                  ts_activate_requested=True, ts_voltage=14.8)
        time_ms, _, to_state, note = self.m.history[-1]
        self.assertEqual(to_state, State.FAULT)
        self.assertEqual(note, self.m.fault.reason)
        self.assertEqual(time_ms, self.m.fault.time_ms)


if __name__ == "__main__":
    unittest.main()
