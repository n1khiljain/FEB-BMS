"""Tests for Readings: the extremes, the ratio, and the copies."""

import unittest

from bms.readings import Readings
from tests.helpers import make_readings


class TestExtremes(unittest.TestCase):
    def test_returns_value_and_index(self):
        r = make_readings(cell_voltages=[3.7, 3.9, 3.5, 3.7])
        self.assertEqual(r.max_cell_voltage(), (3.9, 1))
        self.assertEqual(r.min_cell_voltage(), (3.5, 2))

    def test_temps_too(self):
        r = make_readings(cell_temps=[25.0, 31.0, 19.0])
        self.assertEqual(r.max_cell_temp(), (31.0, 1))
        self.assertEqual(r.min_cell_temp(), (19.0, 2))

    def test_nones_are_skipped_and_indices_still_line_up(self):
        r = make_readings(cell_voltages=[None, 3.9, None, 3.5])
        self.assertEqual(r.max_cell_voltage(), (3.9, 1))
        self.assertEqual(r.min_cell_voltage(), (3.5, 3))

    def test_all_none_gives_none(self):
        r = make_readings(cell_voltages=[None, None], cell_temps=[None])
        self.assertEqual(r.max_cell_voltage(), (None, None))
        self.assertEqual(r.min_cell_voltage(), (None, None))
        self.assertEqual(r.max_cell_temp(), (None, None))
        self.assertEqual(r.min_cell_temp(), (None, None))

    def test_empty_list_gives_none(self):
        r = make_readings(cell_voltages=[])
        self.assertEqual(r.max_cell_voltage(), (None, None))

    def test_one_cell_is_both_extremes(self):
        r = make_readings(cell_voltages=[3.8])
        self.assertEqual(r.max_cell_voltage(), (3.8, 0))
        self.assertEqual(r.min_cell_voltage(), (3.8, 0))

    def test_ties_report_the_lower_index(self):
        r = make_readings(cell_voltages=[3.9, 3.9, 3.5])
        self.assertEqual(r.max_cell_voltage(), (3.9, 0))


class TestPrechargeRatio(unittest.TestCase):
    def test_normal_ratio(self):
        r = make_readings(accumulator_voltage=100.0, ts_voltage=90.0)
        self.assertAlmostEqual(r.precharge_ratio(), 0.9)

    def test_zero_accumulator_voltage_gives_zero(self):
        r = make_readings(accumulator_voltage=0.0, ts_voltage=90.0)
        self.assertEqual(r.precharge_ratio(), 0.0)

    def test_negative_accumulator_voltage_gives_zero(self):
        r = make_readings(accumulator_voltage=-10.0, ts_voltage=90.0)
        self.assertEqual(r.precharge_ratio(), 0.0)

    def test_empty_bus_gives_zero(self):
        self.assertEqual(make_readings().precharge_ratio(), 0.0)


class TestMissingSensor(unittest.TestCase):
    def test_healthy_pack_reports_nothing_missing(self):
        self.assertFalse(make_readings().missing_sensor())

    def test_a_none_is_missing(self):
        self.assertTrue(make_readings(cell_temps=[25.0, None]).missing_sensor())

    def test_an_empty_list_is_missing(self):
        self.assertTrue(make_readings(cell_voltages=[]).missing_sensor())


class TestCopies(unittest.TestCase):
    def test_editing_the_source_list_does_not_change_the_snapshot(self):
        cells = [3.7, 3.7, 3.7, 3.7]
        r = Readings(
            timestamp_ms=0, cell_voltages=cells, cell_temps=[25.0],
            pack_current=0.0, accumulator_voltage=14.8, ts_voltage=0.0,
            ts_activate_requested=False, shutdown_circuit_closed=True,
            charger_connected=False, fault_reset_pressed=False,
        )
        cells[0] = 9.9
        self.assertEqual(r.cell_voltages[0], 3.7)

    def test_replaced_returns_a_separate_snapshot(self):
        r = make_readings()
        later = r.replaced(timestamp_ms=500, pack_current=40.0)
        self.assertEqual(r.timestamp_ms, 0)
        self.assertEqual(r.pack_current, 0.0)
        self.assertEqual(later.timestamp_ms, 500)
        self.assertEqual(later.pack_current, 40.0)

    def test_replaced_copies_the_lists(self):
        r = make_readings()
        later = r.replaced(timestamp_ms=500)
        later.cell_voltages[0] = 9.9
        self.assertEqual(r.cell_voltages[0], 3.7)

    def test_replaced_rejects_an_unknown_field(self):
        with self.assertRaises(AttributeError):
            make_readings().replaced(pack_currrent=1.0)


class TestRepr(unittest.TestCase):
    def test_repr_shows_the_extremes_and_indices(self):
        text = repr(make_readings(cell_voltages=[3.7, 4.1, 3.5, 3.7]))
        self.assertIn("4.10@1", text)
        self.assertIn("3.50@2", text)

    def test_repr_survives_missing_sensors(self):
        self.assertIn("None", repr(make_readings(cell_voltages=[None, None])))


if __name__ == "__main__":
    unittest.main()
