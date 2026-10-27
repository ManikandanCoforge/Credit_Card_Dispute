"""Retry budget and circuit breaker for one tool dependency.

Expected waits for three attempts are about 0.2 seconds, then about 0.4
seconds, and no wait after the attempt that stops the call. The wait
doubles and never exceeds 2 seconds. The breaker opens after three
callers in a row use that whole budget.
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
    assert slept == pytest.approx([0.45, 0.65])
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
    assert slept == pytest.approx([0.2])
    assert breaker.state == "closed"


def test_the_wait_doubles_and_then_stops_at_two_seconds():
    slept = []
    breaker = CircuitBreaker(failure_threshold=9, clock=lambda: 0)

    with pytest.raises(AttemptsExhausted):
        call_with_backoff(_timeout, breaker, max_attempts=6, sleep=slept.append, jitter=lambda: 0)

    assert slept == pytest.approx([0.2, 0.4, 0.8, 1.6, 2.0])
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


def test_the_default_jitter_is_added_to_the_backoff(monkeypatch):
    draws = iter([0, 250])

    def randbelow(bound: int) -> int:
        assert bound == 1_000
        return next(draws)

    monkeypatch.setattr("src.resilience.secrets.randbelow", randbelow)
    slept = []

    def fail_twice():
        if len(slept) < 2:
            raise TransientFailure("upstream timeout")
        return "ready"

    assert call_with_backoff(fail_twice, CircuitBreaker(), sleep=slept.append) == "ready"
    assert slept == pytest.approx([0.2, 0.65])


def test_a_stale_success_does_not_admit_a_second_caller_during_a_probe():
    now = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=60, clock=lambda: now["t"])
    started = threading.Event()
    release = threading.Event()
    outcome: dict[str, object] = {}

    def slow_read():
        started.set()
        assert release.wait(2)
        return "stale"

    def run_slow():
        outcome["result"] = breaker.call(slow_read)

    worker = threading.Thread(target=run_slow)
    worker.start()
    assert started.wait(2)
    with pytest.raises(AttemptsExhausted):
        call_with_backoff(_timeout, breaker, sleep=lambda _seconds: None, jitter=lambda: 0)
    assert breaker.state == "open"
    assert breaker.failure_count == 1
    now["t"] = 60.1
    probe_started = threading.Event()
    probe_release = threading.Event()

    def probe():
        probe_started.set()
        assert probe_release.wait(2)
        return "probe"

    def run_probe():
        outcome["probe"] = breaker.call(probe)

    probe_thread = threading.Thread(target=run_probe)
    probe_thread.start()
    assert probe_started.wait(2)
    release.set()
    worker.join(2)
    assert not worker.is_alive()
    assert outcome["result"] == "stale"
    assert breaker.state == "half-open"
    assert breaker._probing is True
    with pytest.raises(CircuitOpen):
        breaker.call(lambda: "other")
    probe_release.set()
    probe_thread.join(2)
    assert not probe_thread.is_alive()
    assert outcome["probe"] == "probe"
    assert breaker.state == "closed"
    assert breaker.failure_count == 0


def test_an_exhausted_caller_does_not_clear_a_live_probe():
    now = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=60, clock=lambda: now["t"])
    entered = threading.Event()
    release = threading.Event()
    outcome: dict[str, object] = {}

    def slow_fail():
        entered.set()
        assert release.wait(2)
        raise TransientFailure("upstream timeout")

    def in_flight():
        try:
            call_with_backoff(
                slow_fail,
                breaker,
                max_attempts=1,
                sleep=lambda _seconds: None,
                jitter=lambda: 0,
            )
        except AttemptsExhausted:
            outcome["error"] = "exhausted"

    worker = threading.Thread(target=in_flight)
    worker.start()
    assert entered.wait(2)
    with pytest.raises(AttemptsExhausted):
        call_with_backoff(_timeout, breaker, sleep=lambda _seconds: None, jitter=lambda: 0)
    assert breaker.state == "open"
    assert breaker.opened_at == 0.0
    now["t"] = 60.1
    probe_entered = threading.Event()
    probe_release = threading.Event()

    def probe():
        probe_entered.set()
        assert probe_release.wait(2)
        return "ok"

    def run_probe():
        outcome["probe"] = breaker.call(probe)

    probe_thread = threading.Thread(target=run_probe)
    probe_thread.start()
    assert probe_entered.wait(2)
    release.set()
    worker.join(2)
    assert not worker.is_alive()
    assert outcome["error"] == "exhausted"
    assert breaker.state == "half-open"
    assert breaker._probing is True
    assert breaker.opened_at == 0.0
    with pytest.raises(CircuitOpen):
        breaker.call(lambda: "other")
    probe_release.set()
    probe_thread.join(2)
    assert not probe_thread.is_alive()
    assert outcome["probe"] == "ok"
    assert breaker.state == "closed"


@pytest.mark.parametrize("error", [KeyboardInterrupt, SystemExit])
def test_a_probe_that_raises_outside_exception_opens_the_breaker_again(error):
    now = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=60, clock=lambda: now["t"])
    with pytest.raises(AttemptsExhausted):
        call_with_backoff(_timeout, breaker, sleep=lambda _seconds: None, jitter=lambda: 0)
    now["t"] = 60.2

    def boom():
        raise error()

    with pytest.raises(error):
        breaker.call(boom)

    assert breaker.state == "open"
    assert breaker._probing is False
    assert breaker.opened_at == 60.2
    now["t"] = 120.1
    with pytest.raises(CircuitOpen):
        breaker.call(lambda: "too soon")
    now["t"] = 120.3
    assert breaker.call(lambda: "recovered") == "recovered"


def test_an_interrupt_on_a_closed_breaker_leaves_it_closed():
    breaker = CircuitBreaker()

    def interrupt():
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        breaker.call(interrupt)

    assert breaker.state == "closed"
    assert breaker.failure_count == 0
    assert breaker._probing is False


def test_budgets_below_one_attempt_are_rejected():
    with pytest.raises(ValueError, match="failure_threshold"):
        CircuitBreaker(failure_threshold=0)
    with pytest.raises(ValueError, match="reset_timeout"):
        CircuitBreaker(reset_timeout=-1)
    with pytest.raises(ValueError, match="max_attempts"):
        call_with_backoff(lambda: None, CircuitBreaker(), max_attempts=0)


def _timeout():
    raise TransientFailure("upstream timeout")
