"""One snapshot of every sensor input the state machine reads, at a single moment.
"""

import copy


class Readings:
    def __init__(
        self,
        timestamp_ms, # when it was measured
        cell_voltages, # List. One per module in series. None means the sensor didn't report.
        cell_temps, # List. One per temperature sensor (may be fewer than modules)
        pack_current, # Positive = discharging, negative = charging.
        accumulator_voltage, # Battery side of Isolation Relays
        ts_voltage, # inverter side of IR
        ts_activate_requested, # driver's TS button
        shutdown_circuit_closed, # is safety loop intact?
        charger_connected,
        fault_reset_pressed # Manual reset, from outside the car
    ):
        self.timestamp_ms = timestamp_ms
        self.cell_voltages = list(cell_voltages)
        self.cell_temps = list(cell_temps)
        self.pack_current = pack_current
        self.accumulator_voltage = accumulator_voltage
        self.ts_voltage = ts_voltage
        self.ts_activate_requested = ts_activate_requested
        self.shutdown_circuit_closed = shutdown_circuit_closed
        self.charger_connected = charger_connected
        self.fault_reset_pressed = fault_reset_pressed

    def missing_sensor(self):
        """True if any cell voltage or temp sensor failed to report."""
        if not self.cell_voltages or not self.cell_temps:
            return True
        return None in self.cell_voltages or None in self.cell_temps

    # The four extremes below return (value, index), never a bare number. The
    # index is the position in the original list, so a fault message can name
    # which module tripped. Nothing reported gives (None, None), which a caller
    # must test for before comparing; it is an absence, not a zero.
    def min_cell_voltage(self):
        return _extreme(self.cell_voltages, min)

    def max_cell_voltage(self):
        return _extreme(self.cell_voltages, max)

    def min_cell_temp(self):
        return _extreme(self.cell_temps, min)

    def max_cell_temp(self):
        return _extreme(self.cell_temps, max)

    def precharge_ratio(self):
        """ts_voltage / accumulator_voltage. Compare against precharge_target_ratio."""
        if self.accumulator_voltage <= 0:
            return 0.0
        return self.ts_voltage / self.accumulator_voltage

    def replaced(self, **changes):
        """A copy of this snapshot with some fields changed.

        Lets a test start from one healthy scan and vary a single field. The
        two lists are copied as well, so editing one snapshot's cells never
        reaches the other.
        """
        other = copy.copy(self)
        other.cell_voltages = list(self.cell_voltages)
        other.cell_temps = list(self.cell_temps)
        for name, value in changes.items():
            if not hasattr(self, name):
                raise AttributeError(f"Readings has no field {name!r}")
            setattr(other, name, value)
        return other

    def __repr__(self):
        v_lo, v_lo_i = self.min_cell_voltage()
        v_hi, v_hi_i = self.max_cell_voltage()
        t_lo, t_lo_i = self.min_cell_temp()
        t_hi, t_hi_i = self.max_cell_temp()
        return (
            f"Readings(t={self.timestamp_ms}ms, "
            f"V={_show(v_lo)}@{v_lo_i}..{_show(v_hi)}@{v_hi_i}, "
            f"T={_show(t_lo)}@{t_lo_i}..{_show(t_hi)}@{t_hi_i}, "
            f"I={self.pack_current}A, precharge={self.precharge_ratio():.2f}, "
            f"ts_req={self.ts_activate_requested}, "
            f"sdc={self.shutdown_circuit_closed}, "
            f"charger={self.charger_connected}, "
            f"reset={self.fault_reset_pressed})"
        )


def _extreme(values, pick):
    """(value, index) of the min or max, skipping Nones. (None, None) if empty."""
    reported = [(v, i) for i, v in enumerate(values) if v is not None]
    if not reported:
        return (None, None)
    # Key on the value alone, so a tie reports the first cell, not the last.
    return pick(reported, key=lambda pair: pair[0])


def _show(value):
    """Format a reading for __repr__, leaving a missing one visible as None."""
    return "None" if value is None else f"{value:.2f}"
