"""The fixed list of state names and fault reasons."""

class State:
    INIT = "INIT"            # self-check, contactors open
    IDLE = "IDLE"            # contactors open, waiting for TS activate
    PRECHARGE = "PRECHARGE"  # charging inverter caps through the precharge resistor
    DRIVE = "DRIVE"          # AIRs closed, powering the car
    CHARGING = "CHARGING"    # AIRs closed, charger connected
    DISCHARGE = "DISCHARGE"  # AIRs open, bleeding TS voltage below 60 V
    FAULT = "FAULT"          # latched until manual reset from outside the car

ALL_STATES = (
    State.INIT,
    State.IDLE,
    State.PRECHARGE,
    State.DRIVE,
    State.CHARGING,
    State.DISCHARGE,
    State.FAULT,
)

# States where the accumulator is connected to the tractive system
HV_CONNECTED_STATES = frozenset({State.PRECHARGE, State.DRIVE, State.CHARGING})

class FaultReason:
    """Why the machine entered FAULT."""

    # EV.7.4.2
    CELL_UNDERVOLTAGE = "CELL_UNDERVOLTAGE"
    CELL_OVERVOLTAGE = "CELL_OVERVOLTAGE"

    # EV.7.5.2 (limit depends on state: charge vs discharge)
    CELL_OVERTEMP = "CELL_OVERTEMP"
    CELL_UNDERTEMP = "CELL_UNDERTEMP"

    # Datasheet limits
    OVERCURRENT_DISCHARGE = "OVERCURRENT_DISCHARGE"
    OVERCURRENT_CHARGE = "OVERCURRENT_CHARGE"

    # Sensor loss. EV.7.3.4d covers missing or interrupted measurements.
    SENSOR_MISSING = "SENSOR_MISSING"            # a None, or an empty list
    SENSOR_IMPLAUSIBLE = "SENSOR_IMPLAUSIBLE"    # reported, but outside the valid range
    SENSOR_STALE = "SENSOR_STALE"                # snapshot older than stale_ms

    # EV.5.6
    PRECHARGE_TIMEOUT = "PRECHARGE_TIMEOUT"      # ratio not reached in time
    DISCHARGE_TIMEOUT = "DISCHARGE_TIMEOUT"      # TS did not fall below 60 V in time

###############################

ALL_FAULT_REASONS = (
    FaultReason.CELL_OVERVOLTAGE,
    FaultReason.CELL_UNDERVOLTAGE,
    FaultReason.CELL_OVERTEMP,
    FaultReason.CELL_UNDERTEMP,
    FaultReason.OVERCURRENT_DISCHARGE,
    FaultReason.OVERCURRENT_CHARGE,
    FaultReason.SENSOR_MISSING,
    FaultReason.SENSOR_IMPLAUSIBLE,
    FaultReason.SENSOR_STALE,
    FaultReason.PRECHARGE_TIMEOUT,
    FaultReason.DISCHARGE_TIMEOUT,
)