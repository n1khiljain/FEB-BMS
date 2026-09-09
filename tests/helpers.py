"""Input builders for tests: start from a healthy pack, override one thing."""

from bms.types import NUM_MODULES, TEMPS_PER_MODULE, SensorInputs

NOMINAL_CELL_V = 3.60   # datasheet Table 1, typical
NOMINAL_TEMP_C = 25.0   # datasheet ratings are given at 25 C


def make_inputs(**overrides):
    """A resting, healthy pack with everything off. Override any field."""
    base = dict(
        module_voltages=[NOMINAL_CELL_V] * NUM_MODULES,
        module_temps=[NOMINAL_TEMP_C] * (NUM_MODULES * TEMPS_PER_MODULE),
        sense_fuse_ok=[True] * NUM_MODULES,
        pack_voltage=NOMINAL_CELL_V * NUM_MODULES,
        t_ms=0,
    )
    base.update(overrides)
    return SensorInputs(**base)
