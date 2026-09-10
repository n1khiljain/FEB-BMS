"""One snapshot of every sensor input the state machine reads, at a single moment."""

class Readings:
    """All values are SI: volts, amps, degrees C, ms.

    pack_current sign convention:
        positive = discharging (current leaving the accumulator)
        negative = charging (current entering the accumulator)

    A None inside cell_voltages or cell_temps means that sensor did not report.
    """

    def __init__(
        self,
        timestamp_ms,
        cell_voltages, # list
        cell_temps, # list
        pack_current=0.0,

        # EV.5.6: precharge compares the voltage on each side of the AIRs
        accumulator_voltage=0.0,   # battery side
        ts_voltage=0.0,            # inverter side (tractive system)

        # Driver and car inputs
        ts_activate_requested=False,
        shutdown_circuit_closed=False,
        charger_connected=False,
        fault_reset_pressed=False,  # manual reset, from outside the car
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

    def min_cell_voltage(self):
        return min((v for v in self.cell_voltages if v is not None), default=None)

    def max_cell_voltage(self):
        return max((v for v in self.cell_voltages if v is not None), default=None)

    def min_cell_temp(self):
        return min((t for t in self.cell_temps if t is not None), default=None)

    def max_cell_temp(self):
        return max((t for t in self.cell_temps if t is not None), default=None)

    def precharge_ratio(self):
        """ts_voltage / accumulator_voltage. Compare against precharge_target_ratio."""
        if self.accumulator_voltage <= 0:
            return 0.0
        return self.ts_voltage / self.accumulator_voltage

    def __repr__(self):
        return (
            f"Readings(t={self.timestamp_ms}ms, "
            f"V=[{self.min_cell_voltage()}..{self.max_cell_voltage()}], "
            f"T=[{self.min_cell_temp()}..{self.max_cell_temp()}], "
            f"I={self.pack_current}A, precharge={self.precharge_ratio():.2f})"
        )