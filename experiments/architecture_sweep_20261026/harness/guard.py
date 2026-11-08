"""Per-task CPU guard: ITIMER_VIRTUAL / SIGVTALRM (separate from the executor's ITIMER_REAL / SIGALRM guard). The
exception derives from BaseException so broad `except Exception` handlers inside CORA cannot swallow it. A task that
exceeds its CPU allowance is recorded as a timeout (a fixed resource rule, applied without looking at outcomes)."""
import signal
import threading
from contextlib import contextmanager


class TaskTimeout(BaseException):
    pass


@contextmanager
def cpu_limit(seconds):
    if not seconds or threading.current_thread() is not threading.main_thread():
        yield
        return

    def _raise(signum, frame):                              # noqa: ARG001
        raise TaskTimeout()
    old = signal.signal(signal.SIGVTALRM, _raise)
    signal.setitimer(signal.ITIMER_VIRTUAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_VIRTUAL, 0)
        signal.signal(signal.SIGVTALRM, old)
