"""Core data types: states, fault flags, and the sensor input frame.

Types only. No decision logic lives here.
"""

from enum import Enum, IntFlag, auto

# Pack topology. SN4 used the Energus Li4P25RT, a 1s4p module, so one voltage
# measurement per module satisfies EV.7.4.1 ("when single Cells are directly
# connected in parallel, only one voltage measurement is needed").
# TODO(nikhil): set to the real SN5 segment/module count.
NUM_MODULES = 80

# The Li4P25RT has a built-in 2-point temperature sensor. EV.7.5.5a only
# requires 20% of cells monitored; monitoring every module is stricter.
TEMPS_PER_MODULE = 2


class BMSState(Enum):
    """States of the accumulator management system."""

    INIT = auto()
    IDLE = auto()
    PRECHARGE = auto()
    HV_ACTIVE = auto()
    CHARGING = auto()
    FAULT = auto()

    def __str__(self):
        return self.name


class Fault(IntFlag):
    """Fault conditions, as bit flags so several can latch at once.

    The first five mirror EV.7.3.4, the list of conditions the BMS is required
    to monitor for. The rest are implementation concerns.
    """

    NONE = 0
    CELL_OV = auto()            # EV.7.3.4a / EV.7.4.2, above datasheet max
    CELL_UV = auto()            # EV.7.3.4a / EV.7.4.2, below datasheet min
    SENSE_FUSE = auto()         # EV.7.3.4b, voltage sense OCP blown or tripped
    OVER_TEMP = auto()          # EV.7.3.4c / EV.7.5.2
    UNDER_TEMP = auto()         # EV.7.3.4c, charging below the datasheet min
    MISSING_MEAS = auto()       # EV.7.3.4d, missing or interrupted measurement
    INTERNAL = auto()           # EV.7.3.4e, a fault in the BMS itself
    OVER_CURRENT = auto()       # not an EV.7.3.4 item; protects the cells
    PRECHARGE_TIMEOUT = auto()  # intermediate circuit never reached target
    IMD = auto()                # EV.7.6.5, reported by the IMD, not the BMS


class SensorInputs:
    """One frame of sampled inputs: sensors, driver controls, and the clock.

    A measurement that did not arrive is None rather than a stale number, so
    the missing-measurement check of EV.7.3.4d has something to detect.
    """

    def __init__(
        self,
        module_voltages=None,   # volts, one per module, None if not received
        module_temps=None,      # degrees C, TEMPS_PER_MODULE per module
        sense_fuse_ok=None,     # bool, one per module
        pack_current=0.0,       # amps, positive = discharge
        pack_voltage=0.0,       # volts, accumulator side of the IRs
        bus_voltage=0.0,        # volts, intermediate circuit (EV.5.6.2a)
        ts_master_switch=False,  # TSMS
        start_button=False,     # EV.9.6.2, manual action to go Ready to Drive
        brake_pressed=False,    # EV.9.6.2, brake held during activation
        manual_reset=False,     # EV.7.2.3b, physical reset at the vehicle
        charger_connected=False,  # EV.8.3
        imd_ok=True,            # other shutdown-circuit participant, for logging
        t_ms=0,                 # monotonic tick, milliseconds
    ):
        if module_voltages is None:
            module_voltages = [None] * NUM_MODULES
        if module_temps is None:
            module_temps = [None] * (NUM_MODULES * TEMPS_PER_MODULE)
        if sense_fuse_ok is None:
            sense_fuse_ok = [True] * NUM_MODULES

        self.module_voltages = module_voltages
        self.module_temps = module_temps
        self.sense_fuse_ok = sense_fuse_ok
        self.pack_current = pack_current
        self.pack_voltage = pack_voltage
        self.bus_voltage = bus_voltage
        self.ts_master_switch = ts_master_switch
        self.start_button = start_button
        self.brake_pressed = brake_pressed
        self.manual_reset = manual_reset
        self.charger_connected = charger_connected
        self.imd_ok = imd_ok
        self.t_ms = t_ms
