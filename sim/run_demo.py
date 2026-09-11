"""A realistic session, printed as it happens. Run with python -m sim.run_demo.

Power on, activate the tractive system, precharge, drive with rising current,
shrug off a noise spike, shut down, then cook a cell until the pack faults and
an operator resets it.
"""

import math

from bms.readings import Readings
from bms.state_machine import BmsStateMachine
from bms.states import State

TICK_MS = 50
MODULES = 80           # 1s4p modules in series
CELL_V = 3.70
PACK_V = MODULES * CELL_V

RC_PRECHARGE = 0.66    # 1.1 kOhm x 600 uF, in seconds
RC_BLEED = 0.50        # discharge resistor, in seconds

# Timeline, in milliseconds.
T_PRESS = 500          # driver presses the TS button
T_SPIKE = 3500         # one garbage temperature sample
T_RELEASE = 6000       # driver releases the button
T_HEAT = 9000          # a module starts overheating
T_RESET = 14000        # operator presses reset at the car
T_END = 16000


class Car:
    """Fakes the pack and the tractive system well enough to drive the BMS."""

    def __init__(self):
        self.precharge_started_ms = None
        self.discharge_started_ms = None
        self.ts_voltage = 0.0
        self.hot_cell_temp = 25.0

    def sense(self, bms, now_ms):
        """Build the snapshot the BMS would receive at this moment."""
        state = bms.state
        button = T_PRESS <= now_ms < T_RELEASE
        reset = T_RESET <= now_ms < T_RESET + TICK_MS * 2

        self._update_bus(state, now_ms)
        self._update_heat(now_ms)

        temps = [25.0] * MODULES
        temps[34] = self.hot_cell_temp
        if now_ms == T_SPIKE:
            temps[12] = 200.0   # one bad sample from a noisy sensor

        return Readings(
            timestamp_ms=now_ms,
            cell_voltages=[CELL_V] * MODULES,
            cell_temps=temps,
            pack_current=self._current(state, now_ms),
            accumulator_voltage=PACK_V,
            ts_voltage=self.ts_voltage,
            ts_activate_requested=button,
            shutdown_circuit_closed=True,
            charger_connected=False,
            fault_reset_pressed=reset,
        )

    def _update_bus(self, state, now_ms):
        """The intermediate circuit charges and bleeds through an RC curve."""
        if state == State.PRECHARGE:
            if self.precharge_started_ms is None:
                self.precharge_started_ms = now_ms
            elapsed = (now_ms - self.precharge_started_ms) / 1000.0
            self.ts_voltage = PACK_V * (1 - math.exp(-elapsed / RC_PRECHARGE))
            self.discharge_started_ms = None
        elif state == State.DRIVE:
            self.ts_voltage = PACK_V
            self.discharge_started_ms = None
        elif state in (State.DISCHARGE, State.FAULT):
            if self.discharge_started_ms is None:
                self.discharge_started_ms = now_ms
                self.start_voltage = self.ts_voltage
            elapsed = (now_ms - self.discharge_started_ms) / 1000.0
            self.ts_voltage = self.start_voltage * math.exp(-elapsed / RC_BLEED)
            self.precharge_started_ms = None
        else:
            self.ts_voltage = 0.0
            self.precharge_started_ms = None

    def _update_heat(self, now_ms):
        """Module 34 climbs after T_HEAT, then cools once it has faulted."""
        if T_HEAT <= now_ms < T_RESET - 1500:
            self.hot_cell_temp = min(65.0, 25.0 + (now_ms - T_HEAT) / 50.0)
        elif now_ms >= T_RESET - 1500:
            self.hot_cell_temp = max(25.0, self.hot_cell_temp - 1.0)

    def _current(self, state, now_ms):
        """Current ramps up while driving, and is zero everywhere else."""
        if state != State.DRIVE:
            return 0.0
        ramp = (now_ms - T_PRESS) / 1000.0
        return min(45.0, 8.0 * ramp)


def main():
    bms = BmsStateMachine()
    car = Car()

    print(f"{'time':>8}  {'state':<10} {'bus V':>7} {'amps':>6} "
          f"{'hot C':>6} {'limit A':>8}  note")
    print("-" * 62)

    previous = bms.state
    for now_ms in range(0, T_END + 1, TICK_MS):
        r = car.sense(bms, now_ms)
        state = bms.step(r, now_ms)

        note = ""
        if state != previous:
            note = f"{previous} -> {state}"
            if bms.fault and state == State.FAULT:
                note += f"  {bms.fault.reason} cell {bms.fault.cell_index}"
        elif now_ms == T_SPIKE:
            note = "noise spike on sensor 12, ignored"

        if note or now_ms % 1000 == 0:
            t_hi, _ = r.max_cell_temp()
            print(f"{now_ms:>6} ms  {state:<10} {r.ts_voltage:>7.1f} "
                  f"{r.pack_current:>6.1f} {t_hi:>6.1f} "
                  f"{bms.discharge_current_limit(r):>8.1f}  {note}")
        previous = state

    print("\nTransitions")
    print("-" * 62)
    for time_ms, from_state, to_state, note in bms.history:
        print(f"{time_ms:>6} ms  {from_state:<10} -> {to_state:<10} {note}")

    print(f"\nfinished in {bms.state}, "
          f"shutdown contact {'closed' if bms.bms_ok() else 'open'}")


if __name__ == "__main__":
    main()
