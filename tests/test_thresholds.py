"""Thresholds validation: every rejection rule, plus the defaults staying legal."""

import unittest

from bms.thresholds import DEFAULT_THRESHOLDS, Thresholds


class TestThresholdsValidation(unittest.TestCase):
    def assert_rejects(self, **overrides):
        with self.assertRaises(ValueError):
            Thresholds(**overrides)

    def test_defaults_are_valid(self):
        Thresholds()

    def test_default_precharge_meets_rule_minimum(self):

        self.assertGreaterEqual(DEFAULT_THRESHOLDS.precharge_target_ratio, 0.90)

    def test_charge_stop_above_cell_v_max_rejected(self):
        self.assert_rejects(charge_stop_v=4.25)

    def test_charge_stop_below_cell_v_min_rejected(self):
        self.assert_rejects(charge_stop_v=2.0)

    def test_lost_decimal_point_rejected(self):

        self.assert_rejects(cell_v_max=42)

    def test_inverted_cell_voltage_limits_rejected(self):
        self.assert_rejects(cell_v_min=4.2, cell_v_max=2.5)

    def test_inverted_charge_window_rejected(self):
        self.assert_rejects(temp_min_charge=50, temp_max_charge=0)

    def test_inverted_discharge_window_rejected(self):
        self.assert_rejects(temp_min_discharge=70, temp_max_discharge=60)

    def test_equal_charge_window_rejected(self):

        self.assert_rejects(temp_min_charge=45, temp_max_charge=45)

    def test_valid_voltage_range_inside_operating_range_rejected(self):
        self.assert_rejects(cell_v_valid_min=3.0)
        self.assert_rejects(cell_v_valid_max=4.0)

    def test_valid_voltage_range_equal_to_operating_limit_rejected(self):
        self.assert_rejects(cell_v_valid_min=2.50)
        self.assert_rejects(cell_v_valid_max=4.20)

    def test_valid_temp_range_inside_operating_range_rejected(self):
        self.assert_rejects(temp_valid_min=0)
        self.assert_rejects(temp_valid_max=50)

    def test_precharge_ratio_above_one_rejected(self):

        self.assert_rejects(precharge_target_ratio=1.2)

    def test_precharge_ratio_of_zero_rejected(self):
        self.assert_rejects(precharge_target_ratio=0)

    def test_precharge_ratio_of_exactly_one_accepted(self):
        Thresholds(precharge_target_ratio=1.0)

    def test_negative_duration_rejected(self):

        t = Thresholds()
        t.precharge_timeout_ms = -1
        with self.assertRaises(ValueError):
            t.validate()


if __name__ == "__main__":
    unittest.main()
