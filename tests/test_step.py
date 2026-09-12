"""Tests for step(): order of operations, faulting, and reset."""

import unittest

from bms.state_machine import BmsStateMachine
from bms.states import FaultReason, State
from tests.test_raw_problems import healthy


class TestStep(unittest.TestCase):
    def setUp(self):
        self.m = BmsStateMachine()
        self.th = self.m.th

    def run_for(self, r, start_ms, end_ms, every=50):
        t = start_ms
        while t <= end_ms:
            self.m.step(r.replaced(timestamp_ms=t), t)
            t += every

    def test_first_step_stamps_entry_time(self):
        self.assertIsNone(self.m.state_entered_ms)
        self.m.step(healthy(), 500)
        self.assertEqual(self.m.state_entered_ms, 500)

    def test_healthy_pack_leaves_init(self):
        self.m.step(healthy(), 0)
        self.assertEqual(self.m.state, State.IDLE)
        self.assertIsNone(self.m.fault)
        self.assertEqual(len(self.m.history), 1)

    def test_step_returns_the_state(self):
        self.assertEqual(self.m.step(healthy(), 0), self.m.state)

    def test_edges_update_even_when_step_returns_early(self):

        self.run_for(healthy(pack_current=75.0), 0, self.th.current_fault_ms)
        self.assertEqual(self.m.state, State.FAULT)

        held = healthy(fault_reset_pressed=True, timestamp_ms=1000,
                       pack_current=75.0)
        self.m.step(held, 1000)
        self.assertEqual(self.m.state, State.FAULT)
        self.assertTrue(self.m._prev_reset)

    def test_held_button_is_not_a_repeated_edge(self):
        self.run_for(healthy(pack_current=75.0), 0, self.th.current_fault_ms)
        held = healthy(fault_reset_pressed=True, pack_current=75.0)
        self.m.step(held.replaced(timestamp_ms=1000), 1000)
        self.m.step(healthy(fault_reset_pressed=True, timestamp_ms=1100), 1100)
        self.assertEqual(self.m.state, State.FAULT)

    def test_ts_button_edge_is_tracked(self):
        self.m.step(healthy(ts_activate_requested=True), 0)
        self.assertTrue(self.m._prev_ts_activate)
        self.m.step(healthy(ts_activate_requested=False), 50)
        self.assertFalse(self.m._prev_ts_activate)

    def test_stale_snapshot_faults_immediately(self):
        old = healthy(timestamp_ms=0)
        self.m.step(old, self.th.stale_ms + 1)
        self.assertEqual(self.m.state, State.FAULT)
        self.assertEqual(self.m.fault.reason, FaultReason.SENSOR_STALE)

    def test_stale_fault_records_the_age(self):
        self.m.step(healthy(timestamp_ms=0), 1000)
        self.assertEqual(self.m.fault.value, 1000)

    def test_stale_beats_a_debounced_problem(self):

        self.m.step(healthy(timestamp_ms=0, pack_current=75.0), 1000)
        self.assertEqual(self.m.fault.reason, FaultReason.SENSOR_STALE)

    def test_brief_problem_does_not_fault(self):
        self.m.step(healthy(pack_current=75.0), 0)
        self.m.step(healthy(timestamp_ms=50, pack_current=0.0), 50)
        self.assertNotEqual(self.m.state, State.FAULT)

    def test_sustained_problem_faults(self):
        self.run_for(healthy(pack_current=75.0), 0, self.th.current_fault_ms)
        self.assertEqual(self.m.state, State.FAULT)
        self.assertEqual(self.m.fault.reason,
                         FaultReason.OVERCURRENT_DISCHARGE)
        self.assertEqual(self.m.fault.value, 75.0)

    def test_fault_record_keeps_the_cell_index(self):
        bad = healthy(cell_voltages=[3.6, 3.6, 4.25, 3.6])
        self.run_for(bad, 0, self.th.voltage_fault_ms)
        self.assertEqual(self.m.fault.cell_index, 2)

    def test_entering_fault_is_recorded_in_history(self):
        self.run_for(healthy(pack_current=75.0), 0, self.th.current_fault_ms)
        time_ms, from_state, to_state, note = self.m.history[-1]
        self.assertEqual(from_state, State.INIT)
        self.assertEqual(to_state, State.FAULT)
        self.assertEqual(note, FaultReason.OVERCURRENT_DISCHARGE)

    def test_fault_persists_after_the_problem_clears(self):
        self.run_for(healthy(pack_current=75.0), 0, self.th.current_fault_ms)
        self.run_for(healthy(), 1000, 3000)
        self.assertEqual(self.m.state, State.FAULT)

    def test_reset_clears_a_healthy_pack(self):
        self.run_for(healthy(pack_current=75.0), 0, self.th.current_fault_ms)
        self.m.step(healthy(timestamp_ms=1000, fault_reset_pressed=True), 1000)
        self.assertEqual(self.m.state, State.INIT)
        self.assertIsNone(self.m.fault)
        self.assertEqual(self.m._since, {})

    def test_reset_is_ignored_while_the_problem_remains(self):
        self.run_for(healthy(pack_current=75.0), 0, self.th.current_fault_ms)
        still_bad = healthy(timestamp_ms=1000, pack_current=75.0,
                            fault_reset_pressed=True)
        self.m.step(still_bad, 1000)
        self.assertEqual(self.m.state, State.FAULT)

    def test_reset_is_ignored_while_hv_is_present(self):
        self.run_for(healthy(pack_current=75.0), 0, self.th.current_fault_ms)
        live = healthy(timestamp_ms=1000, ts_voltage=200.0,
                       fault_reset_pressed=True)
        self.m.step(live, 1000)
        self.assertEqual(self.m.state, State.FAULT)

    def test_reset_is_ignored_on_a_stale_snapshot(self):
        self.run_for(healthy(pack_current=75.0), 0, self.th.current_fault_ms)
        self.m.step(healthy(timestamp_ms=0, fault_reset_pressed=True), 5000)
        self.assertEqual(self.m.state, State.FAULT)

    def test_reset_needs_a_fresh_press(self):
        self.run_for(healthy(pack_current=75.0), 0, self.th.current_fault_ms)

        self.m.step(healthy(timestamp_ms=900, pack_current=75.0,
                            fault_reset_pressed=True), 900)
        self.m.step(healthy(timestamp_ms=1000, fault_reset_pressed=True), 1000)
        self.assertEqual(self.m.state, State.FAULT)
        self.m.step(healthy(timestamp_ms=1100, fault_reset_pressed=False), 1100)
        self.m.step(healthy(timestamp_ms=1200, fault_reset_pressed=True), 1200)
        self.assertEqual(self.m.state, State.INIT)

    def test_reset_is_recorded_in_history(self):
        self.run_for(healthy(pack_current=75.0), 0, self.th.current_fault_ms)
        self.m.step(healthy(timestamp_ms=1000, fault_reset_pressed=True), 1000)
        self.assertEqual(self.m.history[-1],
                         (1000, State.FAULT, State.INIT, "fault reset"))

    def test_handler_runs_for_a_healthy_pack(self):
        seen = []
        self.m._handlers[State.INIT] = lambda *args: seen.append(args)
        self.m.step(healthy(ts_activate_requested=True), 0)
        self.assertEqual(len(seen), 1)
        r, now_ms, problems, ts_pressed = seen[0]
        self.assertEqual(now_ms, 0)
        self.assertEqual(problems, [])
        self.assertTrue(ts_pressed)

    def test_handler_does_not_run_while_faulted(self):
        seen = []
        self.run_for(healthy(pack_current=75.0), 0, self.th.current_fault_ms)
        self.m._handlers[State.FAULT] = lambda *args: seen.append(args)
        self.m.step(healthy(timestamp_ms=1000), 1000)
        self.assertEqual(seen, [])

    def test_handler_does_not_run_on_a_confirmed_problem(self):
        seen = []
        self.m._handlers[State.INIT] = lambda *args: seen.append(args)
        self.run_for(healthy(pack_current=75.0), 0, self.th.current_fault_ms)

        self.assertEqual(self.m.state, State.FAULT)
        self.assertLess(len(seen), 3)

    def test_missing_handler_is_not_an_error(self):
        del self.m._handlers[State.INIT]
        self.m.step(healthy(), 0)
        self.assertEqual(self.m.state, State.INIT)


if __name__ == "__main__":
    unittest.main()
