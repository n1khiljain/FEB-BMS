"""Tests for _raw_problems: one snapshot in, a list of problems out."""

import unittest

from bms.readings import Readings
from bms.state_machine import BmsStateMachine
from bms.states import FaultReason, State


def healthy(**changes):
    """A resting 4-cell pack with nothing wrong."""
    r = Readings(
        timestamp_ms=0,
        cell_voltages=[3.60, 3.61, 3.59, 3.60],
        cell_temps=[25.0, 25.5, 24.8, 25.1],
        pack_current=0.0,
        accumulator_voltage=14.4,
        ts_voltage=0.0,
        ts_activate_requested=False,
        shutdown_circuit_closed=True,
        charger_connected=False,
        fault_reset_pressed=False,
    )
    return r.replaced(**changes) if changes else r


class TestRawProblems(unittest.TestCase):
    def setUp(self):
        self.m = BmsStateMachine()

    def reasons(self, r):
        return [p[0] for p in self.m._raw_problems(r)]

    # --- nothing wrong ---
    def test_healthy_pack_has_no_problems(self):
        self.assertEqual(self.m._raw_problems(healthy()), [])

    def test_any_cell_count_works(self):
        self.assertEqual(self.m._raw_problems(healthy(
            cell_voltages=[3.6] * 77, cell_temps=[25.0] * 77)), [])

    def test_fewer_temps_than_cells_is_fine(self):
        self.assertEqual(self.m._raw_problems(healthy(
            cell_voltages=[3.6] * 8, cell_temps=[25.0, 25.0])), [])

    # --- sensor problems come first ---
    def test_empty_voltage_list_is_missing(self):
        self.assertEqual(self.reasons(healthy(cell_voltages=[])),
                         [FaultReason.SENSOR_MISSING])

    def test_empty_temp_list_is_missing(self):
        self.assertEqual(self.reasons(healthy(cell_temps=[])),
                         [FaultReason.SENSOR_MISSING])

    def test_none_voltage_reports_its_index(self):
        problems = self.m._raw_problems(healthy(
            cell_voltages=[3.6, None, 3.6, 3.6]))
        self.assertEqual(problems, [(FaultReason.SENSOR_MISSING, 1, None)])

    def test_none_temp_reports_its_index(self):
        problems = self.m._raw_problems(healthy(
            cell_temps=[25.0, 25.0, None, 25.0]))
        self.assertEqual(problems, [(FaultReason.SENSOR_MISSING, 2, None)])

    def test_every_missing_sensor_is_listed(self):
        problems = self.m._raw_problems(healthy(
            cell_voltages=[None, 3.6, None, 3.6]))
        self.assertEqual([p[1] for p in problems], [0, 2])

    def test_implausible_voltage(self):
        problems = self.m._raw_problems(healthy(
            cell_voltages=[3.6, 3.6, 0.2, 3.6]))
        self.assertEqual(problems, [(FaultReason.SENSOR_IMPLAUSIBLE, 2, 0.2)])

    def test_implausible_temp(self):
        problems = self.m._raw_problems(healthy(
            cell_temps=[25.0, 500.0, 25.0, 25.0]))
        self.assertEqual(problems, [(FaultReason.SENSOR_IMPLAUSIBLE, 1, 500.0)])

    def test_sensor_problem_hides_the_rest(self):
        # A pack that is also over current, but the data cannot be trusted.
        r = healthy(cell_voltages=[3.6, None, 3.6, 3.6], pack_current=500.0)
        self.assertEqual(self.reasons(r), [FaultReason.SENSOR_MISSING])

    def test_missing_is_listed_before_implausible(self):
        r = healthy(cell_voltages=[None, 3.6, 99.0, 3.6])
        self.assertEqual(self.reasons(r),
                         [FaultReason.SENSOR_MISSING,
                          FaultReason.SENSOR_IMPLAUSIBLE])

    # --- voltage ---
    def test_undervoltage(self):
        r = healthy(cell_voltages=[3.6, 2.40, 3.6, 3.6])
        self.assertEqual(self.m._raw_problems(r),
                         [(FaultReason.CELL_UNDERVOLTAGE, 1, 2.40)])

    def test_overvoltage(self):
        r = healthy(cell_voltages=[3.6, 3.6, 4.25, 3.6])
        self.assertEqual(self.m._raw_problems(r),
                         [(FaultReason.CELL_OVERVOLTAGE, 2, 4.25)])

    def test_both_ends_out_of_range(self):
        r = healthy(cell_voltages=[2.4, 3.6, 4.25, 3.6])
        self.assertEqual(self.reasons(r),
                         [FaultReason.CELL_UNDERVOLTAGE,
                          FaultReason.CELL_OVERVOLTAGE])

    def test_exactly_at_the_limit_is_allowed(self):
        r = healthy(cell_voltages=[2.50, 4.20, 3.6, 3.6])
        self.assertEqual(self.m._raw_problems(r), [])

    # --- temperature depends on the state ---
    def test_overtemp_while_driving(self):
        self.m.state = State.DRIVE
        r = healthy(cell_temps=[25.0, 61.0, 25.0, 25.0])
        self.assertEqual(self.m._raw_problems(r),
                         [(FaultReason.CELL_OVERTEMP, 1, 61.0)])

    def test_50c_is_fine_driving_but_not_charging(self):
        r = healthy(cell_temps=[25.0, 50.0, 25.0, 25.0])
        self.m.state = State.DRIVE
        self.assertEqual(self.m._raw_problems(r), [])
        self.m.state = State.CHARGING
        self.assertEqual(self.reasons(r), [FaultReason.CELL_OVERTEMP])

    def test_minus_5c_is_fine_driving_but_not_charging(self):
        r = healthy(cell_temps=[-5.0, 25.0, 25.0, 25.0])
        self.m.state = State.DRIVE
        self.assertEqual(self.m._raw_problems(r), [])
        self.m.state = State.CHARGING
        self.assertEqual(self.reasons(r), [FaultReason.CELL_UNDERTEMP])

    def test_undertemp_while_driving(self):
        self.m.state = State.DRIVE
        r = healthy(cell_temps=[25.0, 25.0, -25.0, 25.0])
        self.assertEqual(self.m._raw_problems(r),
                         [(FaultReason.CELL_UNDERTEMP, 2, -25.0)])

    # --- current ---
    def test_overcurrent_discharge(self):
        r = healthy(pack_current=75.0)
        self.assertEqual(self.m._raw_problems(r),
                         [(FaultReason.OVERCURRENT_DISCHARGE, None, 75.0)])

    def test_overcurrent_charge(self):
        r = healthy(pack_current=-20.0)
        self.assertEqual(self.m._raw_problems(r),
                         [(FaultReason.OVERCURRENT_CHARGE, None, -20.0)])

    def test_large_charge_current_is_not_a_discharge_fault(self):
        self.assertEqual(self.reasons(healthy(pack_current=-20.0)),
                         [FaultReason.OVERCURRENT_CHARGE])

    def test_current_at_the_limit_is_allowed(self):
        self.assertEqual(self.m._raw_problems(healthy(pack_current=60.0)), [])
        self.assertEqual(self.m._raw_problems(healthy(pack_current=-15.0)), [])

    # --- shape of the result ---
    def test_problems_are_three_tuples(self):
        for problem in self.m._raw_problems(healthy(pack_current=75.0)):
            self.assertEqual(len(problem), 3)

    def test_same_snapshot_gives_the_same_answer(self):
        r = healthy(cell_voltages=[3.6, 4.9, 3.6, 3.6])
        self.assertEqual(self.m._raw_problems(r), self.m._raw_problems(r))


if __name__ == "__main__":
    unittest.main()
