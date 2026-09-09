"""Unit tests for the BMS state machine.

unittest ships with Python, so there is no dependency to install. Run with
`make test` or `python3 -m unittest discover -s tests -t .`.
"""

import unittest

from bms.state_machine import BMS
from bms.types import BMSState, Fault
from tests.helpers import make_inputs


class TestBMS(unittest.TestCase):
    def setUp(self):
        self.bms = BMS()

    def test_starts_in_init_with_no_faults(self):
        """Proves the harness runs. Everything below is yours to write."""
        self.assertIs(self.bms.state, BMSState.INIT)
        self.assertEqual(self.bms.faults, Fault.NONE)
        self.assertIs(self.bms.step(make_inputs()), BMSState.INIT)

    # --- checklist -----------------------------------------------------
    # Transitions
    # def test_init_to_idle(self): ...
    # def test_idle_to_precharge_on_ts_master_switch(self): ...
    # def test_precharge_completes_at_90_percent(self): ...      EV.5.6.1a
    # def test_precharge_timeout_faults(self): ...
    # def test_hv_active_needs_brake_and_start_button(self): ... EV.9.6.2
    # def test_charging_entered_on_charger_connect(self): ...    EV.8.3
    #
    # Faults
    # def test_cell_over_voltage_faults(self): ...               EV.7.4.2
    # def test_cell_under_voltage_faults(self): ...              EV.7.4.2
    # def test_over_temp_faults_at_60c(self): ...                EV.7.5.2
    # def test_charging_temp_window(self): ...                   datasheet 0-45 C
    # def test_blown_sense_fuse_faults(self): ...                EV.7.3.4b
    # def test_missing_measurement_faults(self): ...             EV.7.3.4d
    # def test_over_current_debounces(self): ...
    #
    # Latching and recovery
    # def test_fault_latches_after_condition_clears(self): ...   EV.7.2.3a
    # def test_manual_reset_returns_to_idle(self): ...           EV.7.2.3b
    # def test_shutdown_circuit_opens_on_any_fault(self): ...    EV.7.3.5a


if __name__ == "__main__":
    unittest.main()
