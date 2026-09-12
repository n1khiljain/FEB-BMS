class Thresholds:
    """All values are SI: volts, amps, degrees C."""

    def __init__(
        self,
        cell_v_min=2.50,
        cell_v_max=4.20,
        charge_stop_v=4.15,

        temp_max_discharge=60,
        temp_min_discharge=-20,
        temp_min_charge=0,
        temp_max_charge=45,

        derate_start_temp=55,

        current_max_discharge=60,
        current_max_charge=15,

        precharge_target_ratio=0.90,

        ts_safe_voltage=60,

        cell_v_valid_min=1.0,
        cell_v_valid_max=5.0,

        temp_valid_min=-40,
        temp_valid_max=120,

        voltage_fault_ms=100,
        temp_fault_ms=1000,
        current_fault_ms=100,
        sensor_fault_ms=200,

        stale_ms=250,

        precharge_timeout_ms=5000,
        discharge_timeout_ms=5000,
    ):
        self.cell_v_min = cell_v_min
        self.cell_v_max = cell_v_max
        self.charge_stop_v = charge_stop_v
        self.temp_max_discharge = temp_max_discharge
        self.temp_min_discharge = temp_min_discharge
        self.temp_min_charge = temp_min_charge
        self.temp_max_charge = temp_max_charge
        self.derate_start_temp = derate_start_temp
        self.current_max_discharge = current_max_discharge
        self.current_max_charge = current_max_charge
        self.precharge_target_ratio = precharge_target_ratio
        self.ts_safe_voltage = ts_safe_voltage
        self.cell_v_valid_min = cell_v_valid_min
        self.cell_v_valid_max = cell_v_valid_max
        self.temp_valid_min = temp_valid_min
        self.temp_valid_max = temp_valid_max
        self.voltage_fault_ms = voltage_fault_ms
        self.temp_fault_ms = temp_fault_ms
        self.current_fault_ms = current_fault_ms
        self.sensor_fault_ms = sensor_fault_ms
        self.stale_ms = stale_ms
        self.precharge_timeout_ms = precharge_timeout_ms
        self.discharge_timeout_ms = discharge_timeout_ms

        self.validate()

    def validate(self):

        if not self.cell_v_min < self.charge_stop_v < self.cell_v_max:
            raise ValueError(
                f"need cell_v_min < charge_stop_v < cell_v_max, got "
                f"{self.cell_v_min} / {self.charge_stop_v} / {self.cell_v_max}"
            )

        if not self.temp_min_charge < self.temp_max_charge:
            raise ValueError(
                f"need temp_min_charge < temp_max_charge, got "
                f"{self.temp_min_charge} / {self.temp_max_charge}"
            )
        if not self.temp_min_discharge < self.temp_max_discharge:
            raise ValueError(
                f"need temp_min_discharge < temp_max_discharge, got "
                f"{self.temp_min_discharge} / {self.temp_max_discharge}"
            )

        if not self.cell_v_valid_min < self.cell_v_min:
            raise ValueError(
                f"cell_v_valid_min {self.cell_v_valid_min} must be below "
                f"cell_v_min {self.cell_v_min}"
            )
        if not self.cell_v_valid_max > self.cell_v_max:
            raise ValueError(
                f"cell_v_valid_max {self.cell_v_valid_max} must be above "
                f"cell_v_max {self.cell_v_max}"
            )

        coldest = min(self.temp_min_charge, self.temp_min_discharge)
        hottest = max(self.temp_max_charge, self.temp_max_discharge)
        if not self.temp_valid_min < coldest:
            raise ValueError(
                f"temp_valid_min {self.temp_valid_min} must be below the "
                f"coldest operating limit {coldest}"
            )
        if not self.temp_valid_max > hottest:
            raise ValueError(
                f"temp_valid_max {self.temp_valid_max} must be above the "
                f"hottest operating limit {hottest}"
            )

        if not self.temp_min_discharge < self.derate_start_temp < self.temp_max_discharge:
            raise ValueError(
                f"need temp_min_discharge < derate_start_temp < "
                f"temp_max_discharge, got {self.temp_min_discharge} / "
                f"{self.derate_start_temp} / {self.temp_max_discharge}"
            )

        if not 0 < self.precharge_target_ratio <= 1:
            raise ValueError(
                f"precharge_target_ratio must be in (0, 1], got "
                f"{self.precharge_target_ratio}"
            )

        for name, value in vars(self).items():
            if name.endswith("_ms") and value < 0:
                raise ValueError(f"{name} must be >= 0, got {value}")


DEFAULT_THRESHOLDS = Thresholds()
