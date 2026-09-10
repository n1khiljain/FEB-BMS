"""Thresholds the state machine judges sensor inputs against."""


class Thresholds:
    """All values are SI: volts, amps, degrees C."""

    def __init__(
        self,
        # EV 7.4.2
        cell_v_min=2.50,    
        cell_v_max=4.20,       
        charge_stop_v=4.15,      

        # EV 7.5.2
        temp_max_discharge=60,     
        temp_min_discharge=-20,
        temp_min_charge=0,      
        temp_max_charge=45,        

        # Current, from datasheet, assuming no cooling
        current_max_discharge=60,
        current_max_charge=15,

        # EV.5.6.1a and EV.5.6.2a 
        precharge_target_ratio=0.90,  # rule minimum: 0.90

        ts_safe_voltage=60, # boundary between HV and LV

        # Plausibility Range
        cell_v_valid_min=1.0,
        cell_v_valid_max=5.0,

        temp_valid_min=-40,
        temp_valid_max=120
    ):
        self.cell_v_min = cell_v_min
        self.cell_v_max = cell_v_max
        self.charge_stop_v = charge_stop_v
        self.temp_max_discharge = temp_max_discharge
        self.temp_min_discharge = temp_min_discharge
        self.temp_min_charge = temp_min_charge
        self.temp_max_charge = temp_max_charge
        self.current_max_discharge = current_max_discharge
        self.current_max_charge = current_max_charge
        self.precharge_target_ratio = precharge_target_ratio
        self.ts_safe_voltage = ts_safe_voltage
        self.cell_v_valid_min = cell_v_valid_min
        self.cell_v_valid_max = cell_v_valid_max
        self.temp_valid_min = temp_valid_min
        self.temp_valid_max = temp_valid_max

        self.validate()

    def validate(self):
        """Raise ValueError if any limit is impossible or out of order.

        Catches the typo that matters: a number entered in the wrong unit or
        with a lost decimal point, like cell_v_max=42, still compares fine
        against every reading and simply never trips.
        """
        # Cell voltage. Charging must stop below the hard limit, and the hard
        # limits must bracket it.
        if not self.cell_v_min < self.charge_stop_v < self.cell_v_max:
            raise ValueError(
                f"need cell_v_min < charge_stop_v < cell_v_max, got "
                f"{self.cell_v_min} / {self.charge_stop_v} / {self.cell_v_max}"
            )

        # Temperature windows, one per direction of current.
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

        # A plausibility range that sits inside an operating limit would flag
        # a healthy pack as an implausible sensor, so it must be strictly wider.
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

        # EV.5.6.1a sets a floor of 0.90; the tractive system cannot precharge
        # past its own voltage, so a ratio above 1 never completes.
        if not 0 < self.precharge_target_ratio <= 1:
            raise ValueError(
                f"precharge_target_ratio must be in (0, 1], got "
                f"{self.precharge_target_ratio}"
            )

        # Every duration, including any added later. Time does not run backward.
        for name, value in vars(self).items():
            if name.endswith("_ms") and value < 0:
                raise ValueError(f"{name} must be >= 0, got {value}")


DEFAULT_THRESHOLDS = Thresholds()