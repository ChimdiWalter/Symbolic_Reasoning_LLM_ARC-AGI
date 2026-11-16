"""Evaluation guard, resource stop and the checked call of the below-library experiment.
Author: Chimdi Walter Ndubuisi

A timeout of an evaluation guard and a memory failure are not ordinary errors (protocol section 10). Both are raised
here as subclasses of BaseException, so that no handler of ordinary errors (`except Exception`) catches them:

  GuardTimeout   the processor-time guard around one batch of evaluations ran out;
  ResourceStop   a memory failure (Python's MemoryError) inside a block, an operation handed to the enumerator, or
                 an evaluation of this experiment.

`guard(seconds)` is a context manager on the virtual interval timer (signal.ITIMER_VIRTUAL, signal SIGVTALRM): it
counts processor time of this process, never wall time. It restores the previous handler and disarms the timer on
every exit, and it refuses to nest: a nested call never starts, resets or disarms a deadline that is already
active. The frozen enumerator and the frozen generator use the same timer for their own hard stops; a guard must
therefore never be active while one of them runs (`assert_inactive` is called before every search and every call
of the generator), and a guard refuses to start while another virtual timer is armed.

`call_checked(fn, *args)` calls fn and turns a MemoryError into ResourceStop at once. A raw MemoryError is an
Exception, and an inner handler of ordinary errors could swallow it before any outer code sees it; so the
translation is made at every checked boundary, before such a handler: inside each block of C (blocks_c), in the
thin wrapper around every operation handed to the enumerator (build_bl), and, through call_checked, wherever this
experiment's own code evaluates library or candidate code or turns a value into canonical text.

One check does not depend on exceptions. The frozen enumerator's broad handler of ordinary errors also encloses a
few small allocations of its own, and the frozen generator's handlers enclose its calls of the true operation; a
MemoryError raised there would be taken for an ordinary error and no wrapper can reach it. The memory ceiling is a
limit on the address space of the process, and the kernel keeps the largest address space the process ever had
(VmPeak in /proc/self/status). A small request can fail only when the address space is already close to the
ceiling, so `address_space_peak_kb()` is read after every unit of work and `near_ceiling` decides: within the
margin of the ceiling, or unreadable, the unit is an infrastructure stop (NearCeiling), the record is written and
the process ends. A reading that cannot be made is a failed check, never an all-clear.

This module installs no ceiling on the memory of the process: the runner does (run_bl.set_memory_ceiling, at the
start of every run mode). Nothing in this experiment catches GuardTimeout, ResourceStop or NearCeiling with a
handler of ordinary errors. They are caught by name only, to record an infrastructure stop.
"""
import math
import resource
import signal


class GuardTimeout(BaseException):
    """The processor-time guard of a batch of evaluations ran out. Not an Exception on purpose."""


class ResourceStop(BaseException):
    """A memory failure inside a block, an operation or an evaluation of this experiment. Not an Exception on
    purpose."""


class NearCeiling(BaseException):
    """The largest address space of the process is within the margin of the memory ceiling (or could not be read)
    after a unit of work. The unit is an infrastructure stop and the process must end. Not an Exception on purpose."""

    def __init__(self, unit, peak_kb):
        BaseException.__init__(self, "address space near the ceiling after %s (peak %s kB)" % (unit, peak_kb))
        self.unit, self.peak_kb = unit, peak_kb


_STATE = {"active": False, "armed": False}


def address_space_peak_kb():
    """The largest address-space size this process ever had, in kB (VmPeak of /proc/self/status); None when it
    cannot be read. None is to be treated as a failed check."""
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmPeak:"):
                    return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return None


def resident_peak_kb():
    """The largest resident set size of this process so far, in kB (ru_maxrss); None when it cannot be read."""
    try:
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except (OSError, ValueError):
        return None


def near_ceiling(peak_kb, ceiling_bytes, margin_bytes):
    """True when the peak is within `margin_bytes` of the ceiling, or is unknown (None)."""
    return peak_kb is None or peak_kb * 1024 >= ceiling_bytes - margin_bytes


def active():
    """True while a guard is active in this process."""
    return _STATE["active"]


def assert_inactive(what="the frozen enumerator"):
    """Raise RuntimeError when a guard is active: `what` uses the same timer and must never run under a guard."""
    if _STATE["active"]:
        raise RuntimeError("an evaluation guard is active: %s must not run under it (they share one timer)" % what)


def call_checked(fn, *args, **kwargs):
    """fn(*args, **kwargs), with a MemoryError turned into ResourceStop before any handler of ordinary errors can
    see it. Every other exception passes unchanged."""
    try:
        return fn(*args, **kwargs)
    except MemoryError:
        raise ResourceStop("memory failure in %s" % getattr(fn, "__name__", "a call")) from None


def _on_timer(signum, frame):
    # Raises once, and only while the guard that armed the timer is still inside its batch. A signal that arrives
    # while the guard is being taken down is ignored: the batch has already ended.
    if _STATE["armed"]:
        _STATE["armed"] = False
        raise GuardTimeout()


class guard:
    """`with guard(seconds): ...` raises GuardTimeout inside the block after `seconds` of processor time.

    `seconds` must be a finite positive number (ValueError otherwise, before the timer is touched). On every exit
    (normal, an ordinary error, GuardTimeout, ResourceStop or any other BaseException) the timer is disarmed and
    the handler that was installed before is put back. A second guard inside an active one raises RuntimeError and
    leaves the first one untouched."""

    def __init__(self, seconds):
        try:
            ok = (not isinstance(seconds, bool) and isinstance(seconds, (int, float)) and math.isfinite(seconds)
                  and seconds > 0)
        except OverflowError:                                    # an integer too large to be a duration
            ok = False
        if not ok:
            raise ValueError("a guard needs a finite positive number of processor seconds")
        self.seconds = float(seconds)
        self._old = None

    def __enter__(self):
        if _STATE["active"]:
            raise RuntimeError("guards do not nest: one is already active")
        if signal.getitimer(signal.ITIMER_VIRTUAL)[0] > 0.0:
            raise RuntimeError("another virtual timer is armed: a guard never starts inside the frozen enumerator "
                               "or generator")
        _STATE["active"] = True
        started = False
        try:
            self._old = signal.signal(signal.SIGVTALRM, _on_timer)
            try:
                _STATE["armed"] = True
                signal.setitimer(signal.ITIMER_VIRTUAL, self.seconds)
                started = True
            finally:
                if not started:
                    # the block is never entered, so __exit__ will not run: take everything down here
                    _STATE["armed"] = False
                    try:
                        signal.setitimer(signal.ITIMER_VIRTUAL, 0)
                    finally:
                        signal.signal(signal.SIGVTALRM, self._old)
        finally:
            if not started:
                _STATE["active"] = False
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            _STATE["armed"] = False
            signal.setitimer(signal.ITIMER_VIRTUAL, 0)
        finally:
            try:
                signal.signal(signal.SIGVTALRM, self._old)
            finally:
                _STATE["active"] = False
        return False
