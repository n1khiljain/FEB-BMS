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