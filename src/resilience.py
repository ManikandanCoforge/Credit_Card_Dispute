"""Retry a transient tool timeout, then stop calling a dead dependency.

CARD-PROCEDURE-01 allows three total attempts. Between those attempts the
wait grows by powers of two, plus a fraction of a second of jitter. The
failure that reaches that cap opens the circuit breaker. A later call on the
same breaker fails immediately and leaves the tool untouched. The caller
treats that stop as unknown evidence and routes to manual review.

The case runner gives each complaint its own breaker. One case's outage does
not skip the next case's transaction read, because the mock faults each case
on its own.
"""

import secrets
import time
from collections.abc import Callable
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
    """Stop calling a dependency after it has failed its attempt budget.

    Closed is normal operation. Open rejects calls until the reset timeout
    passes. Half-open allows one probe. A probe that returns closes the
    breaker. A probe that times out opens it again.
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

    def call[T](self, func: Callable[[], T]) -> T:
        """Call func once, unless the breaker is open."""
        if self.state == "open":
            if self._clock() - self.opened_at > self.reset_timeout:
                self.state = "half-open"
            else:
                raise CircuitOpen()
        try:
            result = func()
        except TransientFailure:
            self._record_failure()
            raise
        self._record_success()
        return result

    def _record_success(self) -> None:
        self.failure_count = 0
        self.state = "closed"

    def _record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
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
    again. The waits are about 1s, then 2s, then 4s. The last attempt does
    not wait, and neither does a failure that opens the breaker. Any other
    exception propagates on the attempt that raised it.
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
                break
            wait((2**attempt) + pause())
    raise AttemptsExhausted(attempt + 1) from error


def _default_jitter() -> float:
    """A fraction of a second, so callers do not retry in step."""
    return secrets.randbelow(1_000) / 1_000
