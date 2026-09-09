"""Thresholds the state machine judges sensor inputs against."""


class Thresholds:
    """All values are SI: volts, amps, degrees C, ms."""

    def __init__(
        self,
        # EV 7.4.2
        cell_v_min=2.50,    
        cell_v_max=4.20,             

        # EV 7.5.2
        temp_max_discharge=60,     
        temp_min_charge=0,      
        temp_max_charge=45,        

        # Current, from datasheet, assuming no cooling
        current_max_discharge=60,
        current_max_charge=15,

        # EV.5.6.1a and EV.5.6.2a 
        precharge_target_ratio=0.90,  # rule minimum: 0.90
    ):
        self.cell_v_min = cell_v_min
        self.cell_v_max = cell_v_max
        self.temp_max_discharge = temp_max_discharge
        self.temp_min_charge = temp_min_charge
        self.temp_max_charge = temp_max_charge
        self.current_max_discharge = current_max_discharge
        self.current_max_charge = current_max_charge
        self.precharge_target_ratio = precharge_target_ratio


DEFAULT_THRESHOLDS = Thresholds()
