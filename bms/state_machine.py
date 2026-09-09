"""The BMS state machine.

Structure only. step() and check_faults() are yours to write; everything they
need is already on the context object.
"""

from bms.config import DEFAULT_THRESHOLDS
from bms.types import BMSState, Fault


class BMS:
    """Context carried across ticks: state, latched faults, and timers."""

    def __init__(self, thresholds=DEFAULT_THRESHOLDS):
        self.thresholds = thresholds
        self.state = BMSState.INIT
        self.faults = Fault.NONE       # latched, cleared only by manual reset
        self.debounce = {}             # Fault -> consecutive bad samples
        self.precharge_start_ms = None
        self.last_t_ms = 0

    # ------------------------------------------------------------------
    # To implement
    # ------------------------------------------------------------------
    def check_faults(self, inputs):
        """Return every fault condition present in this frame, un-latched.

        TODO(nikhil): implement. Points worth deciding before you write it:
          * Which checks apply in which state. EV.7.3.1 only requires
            monitoring when the tractive system is active or a charger is
            connected, but there is no rule against monitoring always.
          * Charge and discharge have different temperature windows, and the
            sign of pack_current tells you which one you are in.
          * A None entry in module_voltages or module_temps is a missing
            measurement (EV.7.3.4d), not a zero.
        """
        del inputs
        return Fault.NONE

    def step(self, inputs):
        """Advance one tick and return the new state.

        TODO(nikhil): implement. The shape most people land on is: sample
        faults, debounce them, latch into self.faults, then run the transition
        for the current state. Things to get right:
          * EV.7.3.5a, any latched fault opens the shutdown circuit, so FAULT
            takes priority over every other transition.
          * EV.7.2.3a, the tractive system stays disabled until a manual reset
            performed at the vehicle, so leaving FAULT is not automatic.
          * EV.5.6.2a, precharge ends on feedback from the intermediate circuit
            voltage, not on a timer. The timer is only there to catch a stuck
            contactor or a shorted bus.
          * EV.9.6.2, going Ready to Drive needs the tractive system active,
            the brake held, and a deliberate driver action, all at once.
        """
        del inputs
        return self.state

    # ------------------------------------------------------------------
    # Provided
    # ------------------------------------------------------------------
    def latch(self, faults):
        """Add faults to the latched mask. Latched faults never self-clear."""
        self.faults |= faults

    def reset(self):
        """Clear latched faults and timers. Call only on a manual reset."""
        self.faults = Fault.NONE
        self.debounce = {}
        self.precharge_start_ms = None

    @property
    def shutdown_circuit_closed(self):
        """EV.7.1.3, the BMS contact is normally open and closes when healthy."""
        return self.faults == Fault.NONE and self.state is not BMSState.FAULT

    def __str__(self):
        return "%s faults=%r" % (self.state, self.faults)
