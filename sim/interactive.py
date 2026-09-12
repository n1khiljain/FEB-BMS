"""Drive the BMS by hand. Run with python -m sim.interactive."""

import math

from bms.readings import Readings
from bms.state_machine import BmsStateMachine
from bms.states import State

TICK_MS = 100
MODULES = 80
CELL_V = 3.70
PACK_V = MODULES * CELL_V
RC_PRECHARGE = 0.66
RC_BLEED = 0.50

HELP = """
  enter  advance one tick        5      advance five ticks
  t      toggle TS button        c      toggle charger
  s      toggle shutdown loop    r      press fault reset
  h / k  heat / cool module 34   v / b  raise / lower cell 7
  i / j  more / less current     x      unplug a sensor
  n      restore healthy pack    ?      this help
  q      quit
"""


class Bus:
    def __init__(self):
        self.voltage = 0.0
        self.started_ms = None
        self.start_voltage = 0.0

    def update(self, state, now_ms):
        if state == State.PRECHARGE:
            if self.started_ms is None:
                self.started_ms = now_ms
            elapsed = (now_ms - self.started_ms) / 1000.0
            self.voltage = PACK_V * (1 - math.exp(-elapsed / RC_PRECHARGE))
        elif state == State.DRIVE or state == State.CHARGING:
            self.voltage = PACK_V
            self.started_ms = None
        elif state in (State.DISCHARGE, State.FAULT):
            if self.started_ms is None:
                self.started_ms = now_ms
                self.start_voltage = self.voltage
            elapsed = (now_ms - self.started_ms) / 1000.0
            self.voltage = self.start_voltage * math.exp(-elapsed / RC_BLEED)
        else:
            self.voltage = 0.0
            self.started_ms = None


class Panel:
    def __init__(self):
        self.ts_button = False
        self.charger = False
        self.shutdown_closed = True
        self.reset_pulse = False
        self.current = 0.0
        self.temps = [25.0] * MODULES
        self.voltages = [CELL_V] * MODULES

    def readings(self, bus, now_ms):
        r = Readings(
            timestamp_ms=now_ms,
            cell_voltages=list(self.voltages),
            cell_temps=list(self.temps),
            pack_current=self.current,
            accumulator_voltage=PACK_V,
            ts_voltage=bus.voltage,
            ts_activate_requested=self.ts_button,
            shutdown_circuit_closed=self.shutdown_closed,
            charger_connected=self.charger,
            fault_reset_pressed=self.reset_pulse,
        )
        self.reset_pulse = False
        return r

    def apply(self, key):
        if key == "t":
            self.ts_button = not self.ts_button
        elif key == "c":
            self.charger = not self.charger
        elif key == "s":
            self.shutdown_closed = not self.shutdown_closed
        elif key == "r":
            self.reset_pulse = True
        elif key == "h":
            self.temps[34] += 5.0
        elif key == "k":
            self.temps[34] -= 5.0
        elif key == "v":
            self.voltages[7] += 0.05
        elif key == "b":
            self.voltages[7] -= 0.05
        elif key == "i":
            self.current += 10.0
        elif key == "j":
            self.current -= 10.0
        elif key == "x":
            self.temps[12] = None
        elif key == "n":
            self.__init__()
        else:
            return False
        return True


def status(bms, r, now_ms):
    relays = bms.relay_outputs()
    closed = ",".join(name for name, on in relays.items() if on) or "all open"
    t_hi, t_i = r.max_cell_temp()
    v_hi, v_i = r.max_cell_voltage()
    fault = f"  {bms.fault}" if bms.fault else ""
    return (f"{now_ms:>7} ms  {bms.state:<10} bus {r.ts_voltage:6.1f} V  "
            f"{r.pack_current:6.1f} A  hot {t_hi}C@{t_i}  "
            f"top {v_hi}V@{v_i}  [{closed}]{fault}")


def main():
    bms = BmsStateMachine()
    bus = Bus()
    panel = Panel()
    now_ms = 0

    print("BMS interactive sim. Press ? for the key list, q to quit.")

    while True:
        bus.update(bms.state, now_ms)
        r = panel.readings(bus, now_ms)
        bms.step(r, now_ms)
        print(status(bms, r, now_ms))

        try:
            key = input(
                f"[ts={'on' if panel.ts_button else 'off'} "
                f"chg={'on' if panel.charger else 'off'} "
                f"sdc={'closed' if panel.shutdown_closed else 'open'}] > "
            ).strip().lower()
        except EOFError:
            break

        if key == "q":
            break
        if key == "?":
            print(HELP)
            continue
        if key.isdigit():
            for _ in range(int(key) - 1):
                now_ms += TICK_MS
                bus.update(bms.state, now_ms)
                bms.step(panel.readings(bus, now_ms), now_ms)
            now_ms += TICK_MS
            continue
        if key and not panel.apply(key):
            print(f"unknown key {key!r}, press ? for help")
            continue
        now_ms += TICK_MS

    print("\nTransitions")
    for time_ms, from_state, to_state, note in bms.history:
        print(f"{time_ms:>7} ms  {from_state:<10} -> {to_state:<10} {note}")


if __name__ == "__main__":
    main()
