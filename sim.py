"""Minimal driving loop: build inputs, tick the state machine, print the state."""

from bms.config import DEFAULT_THRESHOLDS
from bms.state_machine import BMS
from bms.types import NUM_MODULES, TEMPS_PER_MODULE, SensorInputs

TICK_MS = 10
TICKS = 10


def nominal_inputs(t_ms=0):
    """A healthy resting pack. Typical values from Li4P25RT datasheet Table 1."""
    return SensorInputs(
        module_voltages=[3.60] * NUM_MODULES,
        module_temps=[25.0] * (NUM_MODULES * TEMPS_PER_MODULE),
        pack_voltage=3.60 * NUM_MODULES,
        t_ms=t_ms,
    )


def main():
    bms = BMS(thresholds=DEFAULT_THRESHOLDS)
    for tick in range(TICKS):
        inputs = nominal_inputs(t_ms=tick * TICK_MS)
        # TODO(nikhil): drive the scenario here. Close the TSMS partway
        # through, ramp the bus voltage during precharge, inject an overheated
        # module, and watch the machine react.
        state = bms.step(inputs)
        print("t=%5d ms  %-10s faults=%r" % (inputs.t_ms, state, bms.faults))


if __name__ == "__main__":
    main()
