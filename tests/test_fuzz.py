"""Fuzz test: 10,000 random snapshots, checking what must always hold.

The seed is fixed, so a failure here is reproducible rather than a one-off.
"""

import random
import unittest

from bms.state_machine import BmsStateMachine
from bms.readings import Readings
from bms.states import ALL_STATES, State

SEED = 0
SNAPSHOTS = 10000
TICK_MS = 50


def random_readings(rng, t):
    """Mostly plausible data, with occasional excursions and dead sensors.

    All-wild data faults the machine on the first tick and latches there,
    which exercises nothing. Keeping most snapshots healthy lets the machine
    wander through the whole diagram.
    """
    def cell():
        if rng.random() < 0.02:
            return None
        if rng.random() < 0.05:
            return round(rng.uniform(1.5, 4.6), 2)   # out of range
        return round(rng.uniform(3.2, 4.0), 2)

    def temp():
        if rng.random() < 0.02:
            return None
        if rng.random() < 0.05:
            return round(rng.uniform(-45.0, 130.0), 1)
        return round(rng.uniform(15.0, 45.0), 1)

    def current():
        if rng.random() < 0.05:
            return rng.uniform(-200.0, 200.0)
        return rng.uniform(-10.0, 50.0)

    accumulator = rng.uniform(200.0, 300.0)
    return Readings(
        timestamp_ms=t,
        cell_voltages=[cell() for _ in range(4)],
        cell_temps=[temp() for _ in range(2)],
        pack_current=current(),
        accumulator_voltage=accumulator,
        ts_voltage=rng.choice([0.0, rng.uniform(0.0, accumulator)]),
        ts_activate_requested=rng.random() < 0.6,
        shutdown_circuit_closed=rng.random() < 0.95,
        charger_connected=rng.random() < 0.2,
        fault_reset_pressed=rng.random() < 0.3,
    )


class TestFuzz(unittest.TestCase):
    def test_invariants_hold_for_ten_thousand_snapshots(self):
        rng = random.Random(SEED)
        m = BmsStateMachine()
        seen = set()

        for i in range(SNAPSHOTS):
            t = i * TICK_MS
            r = random_readings(rng, t)
            state = m.step(r, t)
            seen.add(state)
            relays = m.relay_outputs()

            self.assertIn(state, ALL_STATES, f"snapshot {i}: {state}")
            self.assertEqual(state, m.state)

            if state == State.FAULT:
                self.assertFalse(any(relays.values()), f"snapshot {i}")
                self.assertFalse(m.bms_ok(), f"snapshot {i}")
                self.assertIsNotNone(m.fault, f"snapshot {i}")
            else:
                self.assertTrue(m.bms_ok(), f"snapshot {i}")

            self.assertFalse(relays["precharge"] and relays["air_pos"],
                             f"snapshot {i}: resistor bypassed while closed")
            if relays["air_pos"]:
                self.assertTrue(relays["air_neg"], f"snapshot {i}")

        # The run should be varied enough to be worth something.
        self.assertIn(State.FAULT, seen)
        self.assertGreaterEqual(len(seen), 3)

    def test_history_is_consistent(self):
        rng = random.Random(SEED)
        m = BmsStateMachine()
        for i in range(2000):
            m.step(random_readings(rng, i * TICK_MS), i * TICK_MS)

        times = [t for t, _, _, _ in m.history]
        self.assertEqual(times, sorted(times))

        state = State.INIT
        for _, from_state, to_state, _ in m.history:
            self.assertEqual(from_state, state)
            self.assertNotEqual(from_state, to_state)
            state = to_state
        self.assertEqual(state, m.state)

    def test_a_second_run_with_the_same_seed_matches(self):
        def run():
            rng = random.Random(SEED)
            m = BmsStateMachine()
            for i in range(1000):
                m.step(random_readings(rng, i * TICK_MS), i * TICK_MS)
            return m.state, list(m.history)

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
