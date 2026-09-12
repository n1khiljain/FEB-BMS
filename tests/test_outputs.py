"""Tests for the outputs: relays, the shutdown-circuit contact, and timing."""

import unittest

from bms.state_machine import BmsStateMachine
from bms.states import ALL_STATES, HV_CONNECTED_STATES, State

OPEN = {"air_neg": False, "precharge": False, "air_pos": False}


class TestRelayOutputs(unittest.TestCase):
    def setUp(self):
        self.m = BmsStateMachine()

    def relays(self, state):
        self.m.state = state
        return self.m.relay_outputs()

    def test_init_opens_everything(self):
        self.assertEqual(self.relays(State.INIT), OPEN)

    def test_idle_opens_everything(self):
        self.assertEqual(self.relays(State.IDLE), OPEN)

    def test_fault_opens_everything(self):
        self.assertEqual(self.relays(State.FAULT), OPEN)

    def test_discharge_opens_everything(self):
        self.assertEqual(self.relays(State.DISCHARGE), OPEN)

    def test_precharge_uses_the_resistor_path(self):
        self.assertEqual(self.relays(State.PRECHARGE),
                         {"air_neg": True, "precharge": True,
                          "air_pos": False})

    def test_drive_closes_both_airs(self):
        self.assertEqual(self.relays(State.DRIVE),
                         {"air_neg": True, "precharge": False,
                          "air_pos": True})

    def test_charging_closes_both_airs(self):
        self.assertEqual(self.relays(State.CHARGING),
                         {"air_neg": True, "precharge": False,
                          "air_pos": True})

    def test_precharge_relay_never_closes_with_the_positive_air(self):

        for state in ALL_STATES:
            out = self.relays(state)
            self.assertFalse(out["precharge"] and out["air_pos"], state)

    def test_positive_air_never_closes_alone(self):
        for state in ALL_STATES:
            out = self.relays(state)
            if out["air_pos"]:
                self.assertTrue(out["air_neg"], state)

    def test_hv_states_are_the_ones_that_close_a_relay(self):
        for state in ALL_STATES:
            connected = any(self.relays(state).values())
            self.assertEqual(connected, state in HV_CONNECTED_STATES, state)

    def test_every_state_reports_the_same_three_relays(self):
        for state in ALL_STATES:
            self.assertEqual(set(self.relays(state)), set(OPEN))


class TestBmsOk(unittest.TestCase):
    def setUp(self):
        self.m = BmsStateMachine()

    def test_ok_in_every_state_but_fault(self):
        for state in ALL_STATES:
            self.m.state = state
            self.assertEqual(self.m.bms_ok(), state != State.FAULT, state)


class TestTimeInState(unittest.TestCase):
    def setUp(self):
        self.m = BmsStateMachine()

    def test_counts_from_entry(self):
        self.m.state_entered_ms = 200
        self.assertEqual(self.m.time_in_state(950), 750)

    def test_zero_on_the_tick_we_entered(self):
        self.m.state_entered_ms = 400
        self.assertEqual(self.m.time_in_state(400), 0)

    def test_resets_when_the_state_changes(self):
        self.m.state_entered_ms = 0
        self.m._enter(State.IDLE, 1000, "moved")
        self.assertEqual(self.m.time_in_state(1000), 0)


class TestEnterHelpers(unittest.TestCase):

    def setUp(self):
        self.m = BmsStateMachine()
        self.m.state_entered_ms = 0

    def test_enter_records_all_three_things(self):
        self.m._enter(State.IDLE, 300, "self-check passed")
        self.assertEqual(self.m.state, State.IDLE)
        self.assertEqual(self.m.state_entered_ms, 300)
        self.assertEqual(self.m.history,
                         [(300, State.INIT, State.IDLE, "self-check passed")])

    def test_enter_fault_builds_the_record(self):
        self.m._enter_fault("CELL_OVERTEMP", 34, 61.4, 1200)
        self.assertEqual(self.m.state, State.FAULT)
        self.assertEqual(self.m.fault.reason, "CELL_OVERTEMP")
        self.assertEqual(self.m.fault.cell_index, 34)
        self.assertEqual(self.m.fault.value, 61.4)
        self.assertEqual(self.m.fault.time_ms, 1200)

    def test_enter_fault_logs_the_reason_as_the_note(self):
        self.m._enter_fault("CELL_OVERTEMP", 34, 61.4, 1200)
        self.assertEqual(self.m.history[-1],
                         (1200, State.INIT, State.FAULT, "CELL_OVERTEMP"))

    def test_enter_fault_opens_the_shutdown_contact(self):
        self.assertTrue(self.m.bms_ok())
        self.m._enter_fault("CELL_OVERTEMP", 34, 61.4, 1200)
        self.assertFalse(self.m.bms_ok())
        self.assertEqual(self.m.relay_outputs(), OPEN)


if __name__ == "__main__":
    unittest.main()
