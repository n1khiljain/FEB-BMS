"""The states the BMS can be in, and the reasons it can fault.

Both groups are plain strings. A string prints as itself, so a trace line or a
failed assertion reads "PRECHARGE" instead of "<State.PRECHARGE: 3>", and
comparison is still a cheap identity check on interned literals.
"""


class State:
    """One member per box in the state diagram."""

    INIT = "INIT"            # self-check, contactors open
    IDLE = "IDLE"            # contactors open, waiting for TS activate
    PRECHARGE = "PRECHARGE"  # charging inverter caps through the precharge resistor
    DRIVE = "DRIVE"          # AIRs closed, powering the car
    CHARGING = "CHARGING"    # AIRs closed, charger connected
    DISCHARGE = "DISCHARGE"  # AIRs open, bleeding TS voltage below 60 V
    FAULT = "FAULT"          # latched until manual reset from outside the car


# Every state, in diagram order. Useful for iterating in tests.
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
    """Why the machine entered FAULT. Tests check this, not just the state."""

    # EV.7.4.2
    CELL_UNDERVOLTAGE = "CELL_UNDERVOLTAGE"
    CELL_OVERVOLTAGE = "CELL_OVERVOLTAGE"

    # EV.7.5.2 (limit depends on state: charge vs discharge)
    CELL_OVERTEMP = "CELL_OVERTEMP"
    CELL_UNDERTEMP_CHARGE = "CELL_UNDERTEMP_CHARGE"

    # Datasheet limits
    OVERCURRENT_DISCHARGE = "OVERCURRENT_DISCHARGE"
    OVERCURRENT_CHARGE = "OVERCURRENT_CHARGE"

    # Sensor loss
    SENSOR_MISSING = "SENSOR_MISSING"  # a reading came back as None
    SENSOR_STALE = "SENSOR_STALE"      # readings stopped updating

    # EV.5.6
    PRECHARGE_TIMEOUT = "PRECHARGE_TIMEOUT"


# Every fault reason. Iterate this instead of hand-listing them in tests.
ALL_FAULT_REASONS = (
    FaultReason.CELL_UNDERVOLTAGE,
    FaultReason.CELL_OVERVOLTAGE,
    FaultReason.CELL_OVERTEMP,
    FaultReason.CELL_UNDERTEMP_CHARGE,
    FaultReason.OVERCURRENT_DISCHARGE,
    FaultReason.OVERCURRENT_CHARGE,
    FaultReason.SENSOR_MISSING,
    FaultReason.SENSOR_STALE,
    FaultReason.PRECHARGE_TIMEOUT,
)
