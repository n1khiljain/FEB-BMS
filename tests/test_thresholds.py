"""Thresholds validation: every rejection rule, plus the defaults staying legal.

Run from the repo root: python3 -m unittest discover -s tests -t .
"""

import unittest

from bms.thresholds import DEFAULT_THRESHOLDS, Thresholds


class TestThresholdsValidation(unittest.TestCase):
    def assert_rejects(self, **overrides):
        """Building a Thresholds with these overrides must raise ValueError."""
        with self.assertRaises(ValueError):
            Thresholds(**overrides)

    # --- the defaults must survive their own rules ---
    def test_defaults_are_valid(self):
        Thresholds()  # raises if not

    def test_default_precharge_meets_rule_minimum(self):
        # EV.5.6.1a: at least 90% of tractive system voltage.
        self.assertGreaterEqual(DEFAULT_THRESHOLDS.precharge_target_ratio, 0.90)

    # --- cell voltage ordering ---
    def test_charge_stop_above_cell_v_max_rejected(self):
        self.assert_rejects(charge_stop_v=4.25)

    def test_charge_stop_below_cell_v_min_rejected(self):
        self.assert_rejects(charge_stop_v=2.0)

    def test_lost_decimal_point_rejected(self):
        # The typo this whole method exists for: 42 instead of 4.2.
        self.assert_rejects(cell_v_max=42)

    def test_inverted_cell_voltage_limits_rejected(self):
        self.assert_rejects(cell_v_min=4.2, cell_v_max=2.5)

    # --- temperature windows ---
    def test_inverted_charge_window_rejected(self):
        self.assert_rejects(temp_min_charge=50, temp_max_charge=0)

    def test_inverted_discharge_window_rejected(self):
        self.assert_rejects(temp_min_discharge=70, temp_max_discharge=60)

    def test_equal_charge_window_rejected(self):
        # An empty window would fault a pack at exactly that temperature.
        self.assert_rejects(temp_min_charge=45, temp_max_charge=45)

    # --- plausibility ranges must be wider than the operating limits ---
    def test_valid_voltage_range_inside_operating_range_rejected(self):
        self.assert_rejects(cell_v_valid_min=3.0)
        self.assert_rejects(cell_v_valid_max=4.0)

    def test_valid_voltage_range_equal_to_operating_limit_rejected(self):
        self.assert_rejects(cell_v_valid_min=2.50)
        self.assert_rejects(cell_v_valid_max=4.20)

    def test_valid_temp_range_inside_operating_range_rejected(self):
        self.assert_rejects(temp_valid_min=0)     # discharge goes to -20
        self.assert_rejects(temp_valid_max=50)    # discharge goes to 60

    # --- precharge ratio ---
    def test_precharge_ratio_above_one_rejected(self):
        # The intermediate circuit cannot exceed the accumulator voltage.
        self.assert_rejects(precharge_target_ratio=1.2)

    def test_precharge_ratio_of_zero_rejected(self):
        self.assert_rejects(precharge_target_ratio=0)

    def test_precharge_ratio_of_exactly_one_accepted(self):
        Thresholds(precharge_target_ratio=1.0)  # allowed, just unreachable

    # --- durations ---
    def test_negative_duration_rejected(self):
        # Guards any *_ms field, including ones added later.
        t = Thresholds()
        t.precharge_timeout_ms = -1
        with self.assertRaises(ValueError):
            t.validate()


if __name__ == "__main__":
    unittest.main()
