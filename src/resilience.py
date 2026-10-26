"""Retry a transient tool timeout, then stop calling a dead dependency.

CARD-PROCEDURE-01 allows three total attempts. Between those attempts the
wait is 2**attempt seconds plus a fraction of a second of jitter. With
three attempts the waits are about 1s, then about 2s.

Not wired into the case runner yet. When it is, keep one breaker per tool for
the whole run. The breaker counts complaints that used all three attempts. It
opens after three such complaints in a row, and any answered read resets that
count. After the cooldown, one probe is allowed. AttemptsExhausted and
CircuitOpen are the signals a caller uses to keep amount and currency unknown
and route to manual review, instead of treating the failure as an empty
transaction list.
"""

import secrets
import time
from collections.abc import Callable
from threading import Lock
from typing import Literal

# One try and two retries. The procedure's cap, not a tuning guess.
MAX_ATTEMPTS = 3

# One probe is allowed after this many seconds, to see if the tool recovered.
RESET_TIMEOUT = 60

State = Literal["closed", "open", "half-open"]


class TransientFailure(Exception):
    """One attempt failed in a way a later attempt may succeed.

    The tool caller raises this for a retryable upstream timeout. A body
    that arrived is a result, including a body with no transactions.
    """


class DependencyUnavailable(Exception):
    """The tool did not return. The caller uses its fallback."""


class CircuitOpen(DependencyUnavailable):
    """The breaker is open, so the tool was not called."""

    def __init__(self) -> None:
        super().__init__("Circuit open, not calling failing service")


class AttemptsExhausted(DependencyUnavailable):
    """The attempts for this call were used up on timeouts."""

    def __init__(self, attempts: int) -> None:
        self.attempts = attempts
        super().__init__(f"Failed after {attempts} attempts")


class CircuitBreaker:
    """Stop calling a dependency after complaints in a row exhaust their budget.

    Closed is normal operation. One timeout does not open the breaker: the
    retry loop owns the three attempts, and the breaker counts how many
    callers used all of them. Open rejects calls until the reset timeout
    passes. Half-open allows one probe. A probe that returns closes the
    breaker. A probe that raises anything opens it again.
    """

    def __init__(
        self,
        failure_threshold: int = MAX_ATTEMPTS,
        reset_timeout: float = RESET_TIMEOUT,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if reset_timeout < 0:
            raise ValueError("reset_timeout must be zero or greater")
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.state: State = "closed"
        self.opened_at = 0.0
        self._clock = clock
        self._probing = False
        self._lock = Lock()

    def call[T](self, func: Callable[[], T]) -> T:
        """Call func once, unless the breaker is open or a probe is in flight.

        A TransientFailure is handed back to the retry loop and does not, by
        itself, open the breaker. Any exception from the single half-open
        probe opens the breaker and starts the reset timeout over.
        """
        probing = self._admit()
        try:
            result = func()
        except Exception as error:
            self._on_error(probing, error)
            raise
        self._on_success()
        return result

    def _admit(self) -> bool:
        """Reserve the one half-open probe, or refuse the call."""
        with self._lock:
            if self.state == "open":
                if self._clock() - self.opened_at > self.reset_timeout:
                    self.state = "half-open"
                else:
                    raise CircuitOpen()
            if self.state == "half-open":
                if self._probing:
                    raise CircuitOpen()
                self._probing = True
                return True
            return False

    def _on_success(self) -> None:
        with self._lock:
            self._probing = False
            self.failure_count = 0
            self.state = "closed"

    def _on_error(self, probing: bool, error: Exception) -> None:
        with self._lock:
            if probing:
                self._open()
                return
            if isinstance(error, TransientFailure):
                return

    def _record_exhausted(self) -> None:
        """Count one caller that used its whole attempt budget."""
        with self._lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self._open()

    def _open(self) -> None:
        self._probing = False
        self.state = "open"
        self.opened_at = self._clock()


def call_with_backoff[T](
    func: Callable[[], T],
    breaker: CircuitBreaker,
    *,
    max_attempts: int = MAX_ATTEMPTS,
    sleep: Callable[[float], None] | None = None,
    jitter: Callable[[], float] | None = None,
) -> T:
    """Call func until it returns or the dependency is unavailable.

    A transient failure waits ``2**attempt`` seconds plus jitter, then tries
    again. With three attempts the waits are about 1s, then about 2s. The
    last attempt does not wait. The caller that uses the whole budget counts
    once toward opening the breaker. Any exception other than
    TransientFailure propagates on the attempt that raised it.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    wait = time.sleep if sleep is None else sleep
    pause = _default_jitter if jitter is None else jitter
    error = TransientFailure("no attempt was made")
    for attempt in range(max_attempts):
        try:
            return breaker.call(func)
        except TransientFailure as caught:
            error = caught
            if breaker.state == "open" or attempt + 1 == max_attempts:
                if breaker.state != "open":
                    breaker._record_exhausted()
                break
            wait((2**attempt) + pause())
    raise AttemptsExhausted(attempt + 1) from error


def _default_jitter() -> float:
    """A fraction of a second, so callers do not retry in step."""
    return secrets.randbelow(1_000) / 1_000
