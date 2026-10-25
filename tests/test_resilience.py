"""Retry budget and circuit breaker for one tool dependency.

Expected waits are the procedure's three attempts: about one second, then
about two, and no wait after the attempt that stops the call.
"""

import pytest

from src.resilience import (
    AttemptsExhausted,
    CircuitBreaker,
    CircuitOpen,
    TransientFailure,
    call_with_backoff,
)


def test_a_closed_breaker_returns_the_tool_result():
    assert CircuitBreaker().call(lambda: "ready") == "ready"


def test_timeouts_wait_then_stop_at_three_attempts():
    calls = {"n": 0}
    slept = []

    def fail():
        calls["n"] += 1
        raise TransientFailure("upstream timeout")

    with pytest.raises(AttemptsExhausted) as raised:
        call_with_backoff(
            fail,
            CircuitBreaker(clock=lambda: 0),
            sleep=slept.append,
            jitter=lambda: 0.25,
        )

    assert calls["n"] == 3
    assert raised.value.attempts == 3
    assert slept == [1.25, 2.25]
    assert raised.value.__cause__ is not None


def test_a_later_call_on_an_open_breaker_does_not_touch_the_tool():
    now = {"t": 50.0}
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=60, clock=lambda: now["t"])
    calls = {"n": 0}

    def fail():
        calls["n"] += 1
        raise TransientFailure("upstream timeout")

    with pytest.raises(AttemptsExhausted):
        call_with_backoff(fail, breaker, max_attempts=3, sleep=lambda _seconds: None, jitter=lambda: 0)

    def probe():
        calls["n"] += 1
        return "recovered"

    now["t"] = 110.0
    with pytest.raises(CircuitOpen):
        call_with_backoff(probe, breaker, sleep=lambda _seconds: None)

    now["t"] = 110.1
    assert call_with_backoff(probe, breaker, sleep=lambda _seconds: None) == "recovered"
    assert calls["n"] == 2


def test_a_failed_probe_opens_the_breaker_again():
    now = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=60, clock=lambda: now["t"])

    def fail():
        raise TransientFailure("upstream timeout")

    with pytest.raises(TransientFailure):
        breaker.call(fail)

    now["t"] = 60.1
    with pytest.raises(TransientFailure):
        breaker.call(fail)

    now["t"] = 120.1
    with pytest.raises(CircuitOpen):
        breaker.call(lambda: "too soon")

    now["t"] = 120.2
    assert breaker.call(lambda: "recovered") == "recovered"


def test_a_success_clears_failures_that_have_not_opened_the_breaker():
    breaker = CircuitBreaker(failure_threshold=2, clock=lambda: 0)

    with pytest.raises(TransientFailure):
        breaker.call(_timeout)

    assert breaker.call(lambda: "ok") == "ok"
    assert breaker.state == "closed"
    assert breaker.failure_count == 0


def test_the_attempt_cap_stops_while_the_breaker_is_still_closed():
    calls = {"n": 0}
    slept = []

    def fail():
        calls["n"] += 1
        raise TransientFailure("upstream timeout")

    breaker = CircuitBreaker(failure_threshold=5, clock=lambda: 0)

    with pytest.raises(AttemptsExhausted) as raised:
        call_with_backoff(
            fail,
            breaker,
            max_attempts=2,
            sleep=slept.append,
            jitter=lambda: 0,
        )

    assert calls["n"] == 2
    assert raised.value.attempts == 2
    assert slept == [1.0]
    assert breaker.state == "closed"


def test_a_non_timeout_propagates_on_the_attempt_that_raised_it():
    calls = {"n": 0}

    def fail():
        calls["n"] += 1
        raise RuntimeError("not a timeout")

    with pytest.raises(RuntimeError, match="not a timeout"):
        call_with_backoff(fail, CircuitBreaker(), sleep=lambda _seconds: None, jitter=lambda: 0)

    assert calls["n"] == 1


def test_the_default_jitter_is_a_fraction_of_a_second():
    slept = []

    def fail_once():
        if not slept:
            raise TransientFailure("upstream timeout")
        return "ready"

    assert call_with_backoff(fail_once, CircuitBreaker(), sleep=slept.append) == "ready"
    assert len(slept) == 1
    assert 1 <= slept[0] < 2


def test_budgets_below_one_attempt_are_rejected():
    with pytest.raises(ValueError, match="failure_threshold"):
        CircuitBreaker(failure_threshold=0)
    with pytest.raises(ValueError, match="reset_timeout"):
        CircuitBreaker(reset_timeout=-1)
    with pytest.raises(ValueError, match="max_attempts"):
        call_with_backoff(lambda: None, CircuitBreaker(), max_attempts=0)


def _timeout():
    raise TransientFailure("upstream timeout")
