"""Tests for the debounce layer: _held, _confirmed_problem, and staleness."""

import unittest

from bms.state_machine import BmsStateMachine
from bms.states import FaultReason
from tests.test_raw_problems import healthy

OV = FaultReason.CELL_OVERVOLTAGE
UV = FaultReason.CELL_UNDERVOLTAGE
OC = FaultReason.OVERCURRENT_DISCHARGE


class TestHeld(unittest.TestCase):
    def setUp(self):
        self.m = BmsStateMachine()

    def test_absent_problem_is_never_held(self):
        self.assertFalse(self.m._held("k", False, 0, 100))

    def test_first_sighting_is_not_held(self):
        self.assertFalse(self.m._held("k", True, 0, 100))

    def test_held_once_the_time_has_passed(self):
        self.m._held("k", True, 0, 100)
        self.assertFalse(self.m._held("k", True, 99, 100))
        self.assertTrue(self.m._held("k", True, 100, 100))

    def test_zero_hold_is_held_immediately(self):
        self.assertTrue(self.m._held("k", True, 0, 0))

    def test_clearing_resets_the_timer(self):
        self.m._held("k", True, 0, 100)
        self.m._held("k", False, 50, 100)
        self.assertFalse(self.m._held("k", True, 120, 100))
        self.assertTrue(self.m._held("k", True, 220, 100))

    def test_timers_are_independent(self):
        self.m._held("a", True, 0, 100)
        self.m._held("b", True, 50, 100)
        self.assertTrue(self.m._held("a", True, 100, 100))
        self.assertFalse(self.m._held("b", True, 100, 100))

    def test_cleared_timer_leaves_no_state_behind(self):
        self.m._held("k", True, 0, 100)
        self.m._held("k", False, 10, 100)
        self.assertNotIn("k", self.m._since)


class TestConfirmedProblem(unittest.TestCase):
    def setUp(self):
        self.m = BmsStateMachine()
        self.hold = self.m.th.voltage_fault_ms

    def problems(self, r):
        return self.m._raw_problems(r)

    def test_nothing_wrong_confirms_nothing(self):
        self.assertIsNone(self.m._confirmed_problem([], 0))

    def test_brief_spike_is_ignored(self):
        spike = self.problems(healthy(cell_voltages=[3.6, 4.25, 3.6, 3.6]))
        self.assertIsNone(self.m._confirmed_problem(spike, 0))
        self.assertIsNone(self.m._confirmed_problem([], 50))
        self.assertIsNone(self.m._confirmed_problem(spike, self.hold + 1))

    def test_sustained_problem_confirms(self):
        bad = self.problems(healthy(cell_voltages=[3.6, 4.25, 3.6, 3.6]))
        self.assertIsNone(self.m._confirmed_problem(bad, 0))
        confirmed = self.m._confirmed_problem(bad, self.hold)
        self.assertEqual(confirmed, (OV, 1, 4.25))

    def test_timer_survives_the_problem_moving_between_cells(self):

        first = self.problems(healthy(cell_voltages=[3.6, 4.25, 3.6, 3.6]))
        second = self.problems(healthy(cell_voltages=[3.6, 3.6, 3.6, 4.30]))
        self.assertIsNone(self.m._confirmed_problem(first, 0))
        confirmed = self.m._confirmed_problem(second, self.hold)
        self.assertEqual(confirmed, (OV, 3, 4.30))

    def test_a_different_reason_does_not_inherit_the_timer(self):
        over = self.problems(healthy(cell_voltages=[3.6, 4.25, 3.6, 3.6]))
        under = self.problems(healthy(cell_voltages=[3.6, 2.40, 3.6, 3.6]))
        self.assertIsNone(self.m._confirmed_problem(over, 0))
        self.assertIsNone(self.m._confirmed_problem(under, self.hold))
        self.assertEqual(
            self.m._confirmed_problem(under, self.hold * 2)[0], UV)

    def test_absent_reasons_get_their_timers_cleared(self):
        over = self.problems(healthy(cell_voltages=[3.6, 4.25, 3.6, 3.6]))
        self.m._confirmed_problem(over, 0)
        self.assertIn(OV, self.m._since)
        self.m._confirmed_problem([], 10)
        self.assertEqual(self.m._since, {})

    def test_each_reason_uses_its_own_hold_time(self):

        th = self.m.th
        self.assertGreater(th.temp_fault_ms, th.current_fault_ms)
        hot = self.problems(healthy(cell_temps=[25.0, 61.0, 25.0, 25.0]))
        self.assertIsNone(self.m._confirmed_problem(hot, 0))
        self.assertIsNone(self.m._confirmed_problem(hot, th.current_fault_ms))
        self.assertIsNotNone(self.m._confirmed_problem(hot, th.temp_fault_ms))

    def test_returns_the_earlier_problem_when_two_are_ready(self):
        both = self.problems(
            healthy(cell_voltages=[2.40, 3.6, 4.25, 3.6]))
        self.m._confirmed_problem(both, 0)
        confirmed = self.m._confirmed_problem(both, self.hold)
        self.assertEqual(confirmed[0], both[0][0])

    def test_faster_reason_confirms_before_a_slower_one(self):
        th = self.m.th
        r = healthy(cell_temps=[25.0, 61.0, 25.0, 25.0], pack_current=75.0)
        problems = self.problems(r)
        self.m._confirmed_problem(problems, 0)
        confirmed = self.m._confirmed_problem(problems, th.current_fault_ms)
        self.assertEqual(confirmed[0], FaultReason.OVERCURRENT_DISCHARGE)


class TestStaleness(unittest.TestCase):
    def setUp(self):
        self.m = BmsStateMachine()

    def test_fresh_snapshot_is_not_stale(self):
        self.assertFalse(self.m.is_stale(healthy(timestamp_ms=0), 100))

    def test_snapshot_at_the_limit_is_not_stale(self):
        limit = self.m.th.stale_ms
        self.assertFalse(self.m.is_stale(healthy(timestamp_ms=0), limit))

    def test_old_snapshot_is_stale(self):
        limit = self.m.th.stale_ms
        self.assertTrue(self.m.is_stale(healthy(timestamp_ms=0), limit + 1))

    def test_staleness_is_not_debounced(self):

        self.m.is_stale(healthy(timestamp_ms=0), self.m.th.stale_ms + 1)
        self.assertEqual(self.m._since, {})


if __name__ == "__main__":
    unittest.main()
