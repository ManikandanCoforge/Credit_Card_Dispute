"""Retry budget and circuit breaker for one tool dependency.

Expected waits for three attempts are about 1 second, then about 2
seconds, and no wait after the attempt that stops the call. The breaker
opens after three callers in a row use that whole budget.
"""

import threading

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
    breaker = CircuitBreaker(clock=lambda: 0)

    def fail():
        calls["n"] += 1
        raise TransientFailure("upstream timeout")

    with pytest.raises(AttemptsExhausted) as raised:
        call_with_backoff(fail, breaker, sleep=slept.append, jitter=lambda: 0.25)

    assert calls["n"] == 3
    assert raised.value.attempts == 3
    assert slept == [1.25, 2.25]
    assert raised.value.__cause__ is not None
    assert breaker.state == "closed"
    assert breaker.failure_count == 1


def test_three_exhausted_cases_in_a_row_open_the_breaker():
    breaker = CircuitBreaker(clock=lambda: 0)
    for _ in range(2):
        with pytest.raises(AttemptsExhausted):
            call_with_backoff(_timeout, breaker, sleep=lambda _seconds: None, jitter=lambda: 0)
        assert breaker.state == "closed"
    with pytest.raises(AttemptsExhausted):
        call_with_backoff(_timeout, breaker, sleep=lambda _seconds: None, jitter=lambda: 0)
    assert breaker.state == "open"
    assert breaker.failure_count == 3
    with pytest.raises(CircuitOpen):
        call_with_backoff(lambda: "next", breaker, sleep=lambda _seconds: None)


def test_one_exhausted_case_does_not_block_the_next_case():
    breaker = CircuitBreaker(clock=lambda: 0)
    calls = {"n": 0}

    def fail():
        calls["n"] += 1
        raise TransientFailure("upstream timeout")

    with pytest.raises(AttemptsExhausted):
        call_with_backoff(fail, breaker, sleep=lambda _seconds: None, jitter=lambda: 0)

    assert calls["n"] == 3
    assert breaker.state == "closed"
    assert call_with_backoff(lambda: "recovered", breaker, sleep=lambda _seconds: None) == "recovered"
    assert breaker.failure_count == 0


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
    assert calls["n"] == 4
    assert breaker.state == "closed"


def test_a_failed_probe_opens_the_breaker_again():
    now = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=60, clock=lambda: now["t"])

    with pytest.raises(AttemptsExhausted):
        call_with_backoff(_timeout, breaker, sleep=lambda _seconds: None, jitter=lambda: 0)

    now["t"] = 60.1
    with pytest.raises(TransientFailure):
        breaker.call(_timeout)

    now["t"] = 120.1
    with pytest.raises(CircuitOpen):
        breaker.call(lambda: "too soon")

    now["t"] = 120.2
    assert breaker.call(lambda: "recovered") == "recovered"


def test_a_failed_probe_stops_the_rest_of_the_attempts():
    now = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=60, clock=lambda: now["t"])
    calls = {"n": 0}

    with pytest.raises(AttemptsExhausted):
        call_with_backoff(_timeout, breaker, sleep=lambda _seconds: None, jitter=lambda: 0)

    def fail():
        calls["n"] += 1
        raise TransientFailure("upstream timeout")

    now["t"] = 60.1
    with pytest.raises(AttemptsExhausted) as raised:
        call_with_backoff(fail, breaker, sleep=lambda _seconds: None, jitter=lambda: 0)

    assert calls["n"] == 1
    assert raised.value.attempts == 1
    assert breaker.state == "open"
    assert breaker.opened_at == 60.1


def test_a_permanent_error_on_a_probe_reopens_the_breaker():
    now = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=60, clock=lambda: now["t"])

    with pytest.raises(AttemptsExhausted):
        call_with_backoff(_timeout, breaker, sleep=lambda _seconds: None, jitter=lambda: 0)

    assert breaker.state == "open"
    assert breaker.failure_count == 1
    assert breaker.opened_at == 0.0
    now["t"] = 60.1

    def bad_body():
        raise ValueError("permanent 4xx")

    with pytest.raises(ValueError, match="permanent 4xx"):
        breaker.call(bad_body)

    assert breaker.state == "open"
    assert breaker.opened_at == 60.1
    now["t"] = 60.2
    for _ in range(3):
        with pytest.raises(CircuitOpen):
            breaker.call(lambda: "admitted")
    assert breaker.state == "open"


def test_a_second_probe_is_refused_while_the_first_is_in_flight():
    now = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=60, clock=lambda: now["t"])
    with pytest.raises(AttemptsExhausted):
        call_with_backoff(_timeout, breaker, sleep=lambda _seconds: None, jitter=lambda: 0)
    now["t"] = 60.1
    started = threading.Event()
    release = threading.Event()
    calls = {"n": 0}
    outcome: dict[str, object] = {}

    def probe():
        calls["n"] += 1
        started.set()
        assert release.wait(2)
        return "ok"

    def first():
        outcome["result"] = breaker.call(probe)

    def second():
        try:
            breaker.call(lambda: "other")
        except CircuitOpen:
            outcome["error"] = "open"
        else:
            outcome["error"] = "admitted"

    reader = threading.Thread(target=first)
    other = threading.Thread(target=second)
    reader.start()
    assert started.wait(2)
    other.start()
    other.join(2)
    release.set()
    reader.join(2)
    assert outcome["error"] == "open"
    assert outcome["result"] == "ok"
    assert calls["n"] == 1
    assert breaker.state == "closed"


def test_an_answered_read_resets_the_run_of_exhausted_cases():
    breaker = CircuitBreaker(clock=lambda: 0)
    for _ in range(2):
        with pytest.raises(AttemptsExhausted):
            call_with_backoff(_timeout, breaker, sleep=lambda _seconds: None, jitter=lambda: 0)
    assert breaker.call(lambda: "ok") == "ok"
    assert breaker.failure_count == 0
    for _ in range(2):
        with pytest.raises(AttemptsExhausted):
            call_with_backoff(_timeout, breaker, sleep=lambda _seconds: None, jitter=lambda: 0)
    assert breaker.state == "closed"


def test_the_attempt_cap_stops_while_the_breaker_is_still_closed():
    calls = {"n": 0}
    slept = []

    def fail():
        calls["n"] += 1
        raise TransientFailure("upstream timeout")

    breaker = CircuitBreaker(failure_threshold=5, clock=lambda: 0)

    with pytest.raises(AttemptsExhausted) as raised:
        call_with_backoff(fail, breaker, max_attempts=2, sleep=slept.append, jitter=lambda: 0)

    assert calls["n"] == 2
    assert raised.value.attempts == 2
    assert slept == [1.0]
    assert breaker.state == "closed"


def test_the_wait_doubles_by_powers_of_two():
    slept = []
    breaker = CircuitBreaker(failure_threshold=9, clock=lambda: 0)

    with pytest.raises(AttemptsExhausted):
        call_with_backoff(_timeout, breaker, max_attempts=6, sleep=slept.append, jitter=lambda: 0)

    assert slept == [1, 2, 4, 8, 16]
    assert breaker.state == "closed"


def test_a_non_timeout_propagates_on_the_attempt_that_raised_it():
    calls = {"n": 0}
    breaker = CircuitBreaker()

    def fail():
        calls["n"] += 1
        raise RuntimeError("not a timeout")

    with pytest.raises(RuntimeError, match="not a timeout"):
        call_with_backoff(fail, breaker, sleep=lambda _seconds: None, jitter=lambda: 0)

    assert calls["n"] == 1
    assert breaker.state == "closed"
    assert breaker.failure_count == 0


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
