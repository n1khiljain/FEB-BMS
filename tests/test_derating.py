"""Current derating: full power, then a straight line to zero."""

import unittest

from bms.state_machine import BmsStateMachine
from bms.thresholds import Thresholds
from tests.helpers import make_readings


class TestDischargeCurrentLimit(unittest.TestCase):
    def setUp(self):
        self.m = BmsStateMachine()
        self.th = self.m.th
        self.full = self.th.current_max_discharge

    def limit_at(self, temp, other=20.0):
        return self.m.discharge_current_limit(
            make_readings(cell_temps=[other, temp]))

    def test_cold_pack_gets_full_current(self):
        self.assertEqual(self.limit_at(25.0), self.full)

    def test_exactly_at_the_start_temperature_is_still_full(self):
        self.assertEqual(self.limit_at(self.th.derate_start_temp), self.full)

    def test_just_above_the_start_temperature_derates_a_little(self):
        limit = self.limit_at(self.th.derate_start_temp + 0.1)
        self.assertLess(limit, self.full)
        self.assertGreater(limit, self.full * 0.95)

    def test_halfway_gives_half_current(self):
        start = self.th.derate_start_temp
        halfway = (start + self.th.temp_max_discharge) / 2
        self.assertAlmostEqual(self.limit_at(halfway), self.full / 2)

    def test_at_the_fault_temperature_gives_zero(self):
        self.assertEqual(self.limit_at(self.th.temp_max_discharge), 0.0)

    def test_above_the_fault_temperature_gives_zero(self):
        self.assertEqual(self.limit_at(self.th.temp_max_discharge + 10), 0.0)

    def test_the_hottest_cell_sets_the_limit(self):
        start = self.th.derate_start_temp
        halfway = (start + self.th.temp_max_discharge) / 2
        self.assertAlmostEqual(self.limit_at(halfway, other=25.0),
                               self.limit_at(halfway, other=halfway))

    def test_the_curve_never_rises_as_the_pack_heats(self):
        limits = [self.limit_at(t) for t in range(20, 70)]
        self.assertEqual(limits, sorted(limits, reverse=True))

    def test_no_temperature_reported_allows_nothing(self):
        self.assertEqual(
            self.m.discharge_current_limit(
                make_readings(cell_temps=[None, None])), 0.0)
        self.assertEqual(
            self.m.discharge_current_limit(make_readings(cell_temps=[])), 0.0)

    def test_the_limit_never_exceeds_the_configured_maximum(self):
        for t in range(-40, 120):
            self.assertLessEqual(self.limit_at(t), self.full)
            self.assertGreaterEqual(self.limit_at(t), 0.0)

    def test_a_different_start_temperature_moves_the_curve(self):
        m = BmsStateMachine(Thresholds(derate_start_temp=30))
        r = make_readings(cell_temps=[20.0, 45.0])
        self.assertAlmostEqual(m.discharge_current_limit(r),
                               m.th.current_max_discharge / 2)


class TestDerateThresholdValidation(unittest.TestCase):
    def test_start_above_the_fault_temperature_is_rejected(self):
        with self.assertRaises(ValueError):
            Thresholds(derate_start_temp=65)

    def test_start_below_the_cold_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            Thresholds(derate_start_temp=-30)

    def test_default_start_is_inside_the_discharge_window(self):
        th = Thresholds()
        self.assertLess(th.temp_min_discharge, th.derate_start_temp)
        self.assertLess(th.derate_start_temp, th.temp_max_discharge)


if __name__ == "__main__":
    unittest.main()
