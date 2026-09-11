"""The BMS state machine."""

from bms.states import FaultReason, State
from bms.thresholds import DEFAULT_THRESHOLDS


class FaultRecord:
    """What tripped, where, and when."""

    def __init__(self, reason, time_ms, cell_index=None, value=None):
        self.reason = reason
        self.time_ms = time_ms
        self.cell_index = cell_index  # None if no single cell caused it
        self.value = value            # the measurement that broke the limit

    def __repr__(self):
        where = "" if self.cell_index is None else f" cell={self.cell_index}"
        what = "" if self.value is None else f" value={self.value}"
        return f"FaultRecord({self.reason}{where}{what} at t={self.time_ms}ms)"


class BmsStateMachine:
    def __init__(self, thresholds=DEFAULT_THRESHOLDS):
        self.th = thresholds
        self.state = State.INIT
        self.state_entered_ms = None  # set on the first step()
        self.fault = None
        self.history = []             # (time_ms, from_state, to_state, note)

        self._since = {}              # reason -> when the problem first appeared
        self._prev_ts_activate = False
        self._prev_reset = False

        self._handlers = {
            State.INIT: self._step_init,
            State.IDLE: self._step_idle,
            State.PRECHARGE: self._step_precharge,
            State.DRIVE: self._step_drive,
            State.CHARGING: self._step_charging,
            State.DISCHARGE: self._step_discharge,
        }

    def temp_limits(self):
        """(min, max) temperature allowed in the current state."""
        if self.state == State.CHARGING:
            return self.th.temp_min_charge, self.th.temp_max_charge
        return self.th.temp_min_discharge, self.th.temp_max_discharge

    def step(self, r, now_ms):
        """Advance the machine by one snapshot. Returns the current state."""
        if self.state_entered_ms is None:
            self.state_entered_ms = now_ms

        # Rising edges first, so an early return still updates them.
        ts_pressed = r.ts_activate_requested and not self._prev_ts_activate
        reset_pressed = r.fault_reset_pressed and not self._prev_reset
        self._prev_ts_activate = r.ts_activate_requested
        self._prev_reset = r.fault_reset_pressed

        problems = self._raw_problems(r)
        stale = self.is_stale(r, now_ms)

        if self.state == State.FAULT:
            can_clear = (
                reset_pressed
                and not problems
                and not stale
                and r.ts_voltage < self.th.ts_safe_voltage
            )
            if can_clear:
                self.fault = None
                self._since.clear()
                self._enter(State.INIT, now_ms, "fault reset")
            return self.state

        if stale:
            age = now_ms - r.timestamp_ms
            self._enter_fault(FaultReason.SENSOR_STALE, None, age, now_ms)
            return self.state

        confirmed = self._confirmed_problem(problems, now_ms)
        if confirmed:
            reason, cell_index, value = confirmed
            self._enter_fault(reason, cell_index, value, now_ms)
            return self.state

        handler = self._handlers.get(self.state)
        if handler:
            handler(r, now_ms, problems, ts_pressed)
        return self.state

    # --- one handler per state -----------------------------------------
    # Each takes (r, now_ms, problems, ts_pressed). Get-out conditions are
    # checked before go-further ones.

    def _step_init(self, r, now_ms, problems, ts_pressed):
        if not problems and r.ts_voltage < self.th.ts_safe_voltage:
            self._enter(State.IDLE, now_ms, "self-check passed")

    def _step_idle(self, r, now_ms, problems, ts_pressed):
        if problems or not ts_pressed or not r.shutdown_circuit_closed:
            return
        if r.charger_connected and not self._temps_ok_to_charge(r):
            return
        self._enter(State.PRECHARGE, now_ms, "TS activate")

    def _step_precharge(self, r, now_ms, problems, ts_pressed):
        if not r.ts_activate_requested or not r.shutdown_circuit_closed:
            self._enter(State.DISCHARGE, now_ms, "precharge aborted")
            return

        ratio = r.precharge_ratio()
        if ratio >= self.th.precharge_target_ratio:
            if r.charger_connected:
                self._enter(State.CHARGING, now_ms, "precharge complete")
            else:
                self._enter(State.DRIVE, now_ms, "precharge complete")
            return

        if self.time_in_state(now_ms) >= self.th.precharge_timeout_ms:
            self._enter_fault(
                FaultReason.PRECHARGE_TIMEOUT, None, ratio, now_ms)

    def _step_drive(self, r, now_ms, problems, ts_pressed):
        if (not r.ts_activate_requested
                or not r.shutdown_circuit_closed
                or r.charger_connected):
            self._enter(State.DISCHARGE, now_ms, "TS deactivated")

    def _step_charging(self, r, now_ms, problems, ts_pressed):
        if (not r.ts_activate_requested
                or not r.shutdown_circuit_closed
                or not r.charger_connected):
            self._enter(State.DISCHARGE, now_ms, "charging stopped")
            return

        v_hi, _ = r.max_cell_voltage()
        if v_hi is not None and v_hi >= self.th.charge_stop_v:
            self._enter(State.DISCHARGE, now_ms, "charge complete")

    def _step_discharge(self, r, now_ms, problems, ts_pressed):
        if r.ts_voltage < self.th.ts_safe_voltage:
            self._enter(State.IDLE, now_ms, "TS voltage safe")
            return

        if self.time_in_state(now_ms) >= self.th.discharge_timeout_ms:
            self._enter_fault(
                FaultReason.DISCHARGE_TIMEOUT, None, r.ts_voltage, now_ms)

    # --- outputs --------------------------------------------------------

    def relay_outputs(self):
        """Which contactors this state asks for."""
        if self.state == State.PRECHARGE:
            return {"air_neg": True, "precharge": True, "air_pos": False}
        if self.state in (State.DRIVE, State.CHARGING):
            return {"air_neg": True, "precharge": False, "air_pos": True}
        return {"air_neg": False, "precharge": False, "air_pos": False}

    def discharge_current_limit(self, r):
        """How much discharge current the pack allows right now.

        Full current up to derate_start_temp, then a straight line down to
        zero at temp_max_discharge, so power fades instead of cutting out.
        """
        full = self.th.current_max_discharge
        t_hi, _ = r.max_cell_temp()
        if t_hi is None:
            return 0.0   # no temperature reported, so allow nothing

        start = self.th.derate_start_temp
        limit = self.th.temp_max_discharge
        if t_hi <= start:
            return full
        if t_hi >= limit:
            return 0.0
        return full * (limit - t_hi) / (limit - start)

    def bms_ok(self):
        """The BMS contact in the shutdown circuit. False opens the loop."""
        return self.state != State.FAULT

    def time_in_state(self, now_ms):
        """How long we have been in this state."""
        return now_ms - self.state_entered_ms

    # --- helpers --------------------------------------------------------

    def _temps_ok_to_charge(self, r):
        """True if every reported temperature is inside the charge window."""
        t_lo, _ = r.min_cell_temp()
        t_hi, _ = r.max_cell_temp()
        if t_lo is None or t_hi is None:
            return False
        return (self.th.temp_min_charge <= t_lo
                and t_hi <= self.th.temp_max_charge)

    def _enter(self, new_state, now_ms, note=""):
        """Move to a state and record the move."""
        self.history.append((now_ms, self.state, new_state, note))
        self.state = new_state
        self.state_entered_ms = now_ms

    def _enter_fault(self, reason, cell_index, value, now_ms):
        """Latch a fault and enter FAULT."""
        self.fault = FaultRecord(reason, now_ms, cell_index, value)
        self._enter(State.FAULT, now_ms, reason)

    def is_stale(self, r, now_ms):
        """True if this snapshot is too old to trust."""
        return now_ms - r.timestamp_ms > self.th.stale_ms

    def _held(self, key, present, now_ms, hold_ms):
        """True once `present` has been continuously true for hold_ms."""
        if not present:
            self._since.pop(key, None)
            return False
        start = self._since.setdefault(key, now_ms)
        return now_ms - start >= hold_ms

    def _confirmed_problem(self, problems, now_ms):
        """The first problem that has lasted long enough, or None.

        Every debounced reason is checked, not just the ones present now.
        Checking an absent reason is what clears its timer.
        """
        present = {reason for reason, _, _ in problems}
        held = {}
        for reason, hold_ms in _hold_times(self.th).items():
            held[reason] = self._held(reason, reason in present, now_ms, hold_ms)

        for problem in problems:
            if held.get(problem[0]):
                return problem
        return None

    def _raw_problems(self, r): # r is readings instance
        """Everything wrong in this one snapshot.

        Returns a list of (reason, cell_index, value), worst data problems
        first. No timing, no memory: same snapshot in, same list out.
        """
        problems = []

        # Sensors first. Broken data makes every check below meaningless.
        problems += _missing(r.cell_voltages)
        problems += _missing(r.cell_temps)
        problems += _implausible(
            r.cell_voltages, self.th.cell_v_valid_min, self.th.cell_v_valid_max
        )
        problems += _implausible(
            r.cell_temps, self.th.temp_valid_min, self.th.temp_valid_max
        )
        if problems:
            return problems

        # Voltage.
        v_lo, v_lo_i = r.min_cell_voltage()
        v_hi, v_hi_i = r.max_cell_voltage()
        if v_lo < self.th.cell_v_min:
            problems.append((FaultReason.CELL_UNDERVOLTAGE, v_lo_i, v_lo))
        if v_hi > self.th.cell_v_max:
            problems.append((FaultReason.CELL_OVERVOLTAGE, v_hi_i, v_hi))

        # Temperature, against the limits for the state we are in.
        t_min, t_max = self.temp_limits()
        t_lo, t_lo_i = r.min_cell_temp()
        t_hi, t_hi_i = r.max_cell_temp()
        if t_lo < t_min:
            problems.append((FaultReason.CELL_UNDERTEMP, t_lo_i, t_lo))
        if t_hi > t_max:
            problems.append((FaultReason.CELL_OVERTEMP, t_hi_i, t_hi))

        # Current. Positive is discharge, negative is charge.
        if r.pack_current > self.th.current_max_discharge:
            problems.append(
                (FaultReason.OVERCURRENT_DISCHARGE, None, r.pack_current)
            )
        if r.pack_current < -self.th.current_max_charge:
            problems.append(
                (FaultReason.OVERCURRENT_CHARGE, None, r.pack_current)
            )

        return problems


def _hold_times(th):
    """reason -> how long that problem must last before it counts."""
    return {
        FaultReason.CELL_UNDERVOLTAGE: th.voltage_fault_ms,
        FaultReason.CELL_OVERVOLTAGE: th.voltage_fault_ms,
        FaultReason.CELL_UNDERTEMP: th.temp_fault_ms,
        FaultReason.CELL_OVERTEMP: th.temp_fault_ms,
        FaultReason.OVERCURRENT_DISCHARGE: th.current_fault_ms,
        FaultReason.OVERCURRENT_CHARGE: th.current_fault_ms,
        FaultReason.SENSOR_MISSING: th.sensor_fault_ms,
        FaultReason.SENSOR_IMPLAUSIBLE: th.sensor_fault_ms,
    }


def _missing(values):
    """Empty list, or any sensor that did not report."""
    if not values:
        return [(FaultReason.SENSOR_MISSING, None, None)]
    return [
        (FaultReason.SENSOR_MISSING, i, None)
        for i, v in enumerate(values)
        if v is None
    ]


def _implausible(values, low, high):
    """Reported a number, but one no real sensor should produce."""
    return [
        (FaultReason.SENSOR_IMPLAUSIBLE, i, v)
        for i, v in enumerate(values)
        if v is not None and not low <= v <= high
    ]
