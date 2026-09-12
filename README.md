# FEB-BMS

A Battery Management System state machine for SN5, written in Python with no
third-party libraries. It models how the accumulator moves between states based
on sensor readings and driver inputs, and how it faults when something goes
wrong.

Limits come from the Energus Li4P25RT datasheet (the 1s4p module SN4 used) and
the Formula SAE 2026 rules. Both are catalogued in `docs/SOURCES.md`, with rule
numbers next to each value.

## Running it

```
python -m sim.run_demo      # scripted session, prints a timeline
python -m sim.interactive   # drive it from the keyboard
python -m sim.server        # browser panel on http://127.0.0.1:8000
python -m unittest discover -s tests -t .
```

Nothing to install. Python 3.8 or newer.

## States

| State | What it means |
|---|---|
| `INIT` | Power on, self-check, everything open |
| `IDLE` | Healthy and waiting for the driver to activate the tractive system |
| `PRECHARGE` | Charging the inverter capacitors through the precharge resistor |
| `DRIVE` | Both AIRs closed, pack powering the car |
| `CHARGING` | Both AIRs closed, charger attached |
| `DISCHARGE` | AIRs open, bleeding the tractive system below 60 V |
| `FAULT` | Latched, shutdown circuit open, waiting for a manual reset |

`DISCHARGE` exists because rule EV.7.2.2c gives five seconds to reach low
voltage, and that is a state with its own timeout rather than an instant.

## Relay outputs

| State | AIR− | Precharge | AIR+ |
|---|---|---|---|
| `INIT`, `IDLE`, `DISCHARGE`, `FAULT` | open | open | open |
| `PRECHARGE` | closed | closed | open |
| `DRIVE`, `CHARGING` | closed | open | closed |

`bms_ok()` returns False in `FAULT`. On the real car that opens the BMS contact
in the shutdown circuit, which is how the BMS stops everything: it breaks the
loop and the AIRs spring open.

## Faults

Eleven reasons, all latched until a manual reset at the vehicle. The first five
cover what rule EV.7.3.4 requires the BMS to monitor for: voltages out of
range, a blown voltage-sense fuse, temperatures out of range, missing or
interrupted measurements, and a fault in the BMS itself.

Each fault carries the reason, the cell index, the measured value, and the time,
so a log line says which module failed and by how much.

Two things separate a real problem from noise:

- **Debounce.** A condition must hold continuously for its own hold time before
  it latches. Temperature holds a full second because cells cannot heat that
  fast; current and voltage hold 100 ms. One garbage sample changes nothing.
- **Plausibility.** A reading outside what any working sensor could produce is
  `SENSOR_IMPLAUSIBLE`, not an over-temperature. 200 °C is a broken sensor.

## How it is put together

```
bms/states.py          state and fault names, as plain strings
bms/thresholds.py      every limit and timing, validated on construction
bms/readings.py        one snapshot of the pack, plus simple accessors
bms/state_machine.py   the machine itself
sim/                   scripted demo, keyboard sim, web panel
tests/                 226 tests
```

`step(readings, now_ms)` runs one tick in a fixed order: update the rising-edge
inputs, collect raw problems, check staleness, debounce, then dispatch to a
handler for the current state. There is one handler per state, picked from a
dict, instead of a long if-else chain. Every transition goes through `_enter`,
so there is exactly one place that logs and one place to debug.

`Thresholds` validates itself, which catches the typo that matters: a limit
entered in the wrong unit or missing a decimal point still compares fine against
every reading and simply never trips.

## Testing

226 tests, all standard library `unittest`:

- one test per arrow in the state diagram, walked through real `step` calls
- one test per fault reason, checking the reason, index, and value
- debounce cases including a single noise spike and two separate stretches that
  each stay under the hold time
- a fuzz test that feeds 10,000 random snapshots with a fixed seed and asserts
  the invariants: the state is always valid, a faulted machine has every relay
  open, and the precharge relay is never closed alongside AIR+

Tests never set `machine.state` directly. They walk the machine there with real
readings, so no test can check a situation the car cannot reach.
